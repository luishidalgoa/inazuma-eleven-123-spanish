"""IE2 Fuego v16 · validación offline de probe_ie2_v16 frente a probe_ie2_v15 (runtime_verified=false).

- archive.fa: solo difieren las entradas declaradas; mismas rutas y orden.
- eve IE2: solo cambian 22010100/200/300/500; 22500101/22500102 y el resto, idénticos a v15; en los
  cambiados, mismo número de registros, misma tabla de instrucciones y bytecode; ningún registro
  cambiado pasa de 247 B.
- romfs: CRO iguales a v15 (ina_main2 = 9f8e1d7c…); 547 SAD; sound.pb/.ph/.ph_ = los de v13 voz_titulo;
  el resto del romfs de v15, byte a byte.
- Ejecuta validate.py de cada capa.
Salida: validacion.json. Código 1 si falla algo.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys

import build as B
from ie123kit.nucleo.contenedores.fa import FaArchive
from ie123kit.nucleo.eventos import ssd as S
from ie123kit.nucleo.eventos.packnum import parse_index

DECLARADAS = {'inazuma2/data_iz/a_menu/menu_slot.arc', 'inazuma2/data_iz/a_menu/name_b.arc',
              'inazuma2/data_iz/a_title/title_t.arc', 'inazuma2/data_iz/a_title/title_b.arc',
              'inazuma2/data_iz/a_title/option_b.arc', 'inazuma2/data_iz/logic/rpgtitle.STR',
              *B.PK_EVE}
VALIDADORES = [B.W / 'ie2/shared/capas/menus_cro/cro_ranura', B.W / 'ie2/shared/capas/historial/graficos/v12_graficos',
               B.W / 'ie2/shared/capas/nombres/titulos', B.W / 'ie2/shared/capas/media/voz_titulo',
               B.W / 'ie2/tormenta_de_fuego/capas/dialogo/inicio']


def h(b):
    return hashlib.sha256(b).hexdigest()


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    fallos = []
    a15, a16 = FaArchive(str(B.BASE)), FaArchive(str(B.SALIDA))
    e15 = {p: (o, s) for p, o, s in a15.entries}
    e16 = {p: (o, s) for p, o, s in a16.entries}
    if [p for p, _, _ in a15.entries] != [p for p, _, _ in a16.entries]:
        fallos.append('rutas/orden distintos')
    difieren = sorted(p for p in e15 if bytes(a15.d[slice(e15[p][0], sum(e15[p]))])
                      != bytes(a16.d[slice(e16[p][0], sum(e16[p]))]))
    if set(difieren) != DECLARADAS:
        fallos.append(dict(difieren_no_declaradas=sorted(set(difieren) ^ DECLARADAS)))
    # eventos
    g15, g16 = B.lector(a15), B.lector(a16)
    o, s = e16[B.PK_EVE[0]]
    ids16 = [e for e, _, _ in parse_index(bytes(a16.d[o:o + s]))]
    o, s = e15[B.PK_EVE[0]]
    ids15 = [e for e, _, _ in parse_index(bytes(a15.d[o:o + s]))]
    if ids15 != ids16:
        fallos.append('índice eve distinto')
    cambian, ev = [], {}
    for eid in ids16:
        x, y = g15(eid), g16(eid)
        if x == y:
            continue
        cambian.append(eid)
        hx, ox, rx = S.parse(x)
        hy, oy, ry = S.parse(y)
        if ox != oy:
            fallos.append(('tabla_instrucciones', eid))
        if len(rx) != len(ry):
            fallos.append(('num_registros', eid))
        n, mx = 0, 0
        for i, (p, q) in enumerate(zip(rx, ry)):
            if (p.instruction, p.argument) != (q.instruction, q.argument):
                fallos.append(('identidad', eid, i))
            if p.body != q.body:
                n += 1
                mx = max(mx, len(q.body))
                if len(q.body) > 247:
                    fallos.append(('excede_247', eid, i, len(q.body)))
        ev[eid] = dict(registros=len(ry), cambiados=n, max_bytes=mx, bytes_v15=len(x), bytes=len(y))
    if sorted(cambian) != sorted(B.EXENTOS):
        fallos.append(dict(eventos_cambian=cambian))
    for eid in (22500101, 22500102):
        if h(g15(eid)) != h(g16(eid)):
            fallos.append(('v15_perdido', eid))
    # romfs
    r15, r16 = B.V15 / 'romfs', B.SALIDA_DIR / 'romfs'
    f15 = {p.relative_to(r15).as_posix() for p in r15.rglob('*') if p.is_file()}
    f16 = {p.relative_to(r16).as_posix() for p in r16.rglob('*') if p.is_file()}
    voz = {p.relative_to(B.VOZ).as_posix() for p in B.VOZ.rglob('*') if p.is_file()}
    if f16 != f15 | voz or f15 & voz:
        fallos.append('ficheros romfs inesperados')
    for r in f15:
        if B.sha(r15 / r) != B.sha(r16 / r):
            fallos.append(('romfs_distinto', r))
    for r in voz:
        if B.sha(B.VOZ / r) != B.sha(r16 / r):
            fallos.append(('voz_distinta', r))
    cro2 = B.sha(r16 / 'cro/ina_main2.cro')
    if cro2 != B.CRO2_SHA:
        fallos.append('ina_main2.cro')
    if 'inazuma2/data_iz/sound/sound.pb' not in f16:
        fallos.append('falta sound.pb')
    sad = sum(1 for _ in r16.rglob('*.SAD'))
    if sad != 547:
        fallos.append(('sad', sad))
    # validadores de capa
    capas = {}
    for d in VALIDADORES:
        r = subprocess.run([sys.executable, '-X', 'utf8', 'validate.py'], cwd=d, capture_output=True,
                           text=True, encoding='utf-8', errors='replace')
        capas[str(d.relative_to(B.W))] = dict(codigo=r.returncode, cola=(r.stdout + r.stderr)[-400:])
        if r.returncode:
            fallos.append(('validate', str(d)))
    out = dict(ok=not fallos, fallos=fallos, runtime_verified=False, difieren=difieren, eventos=ev,
               sad=sad, ina_main2_sha256=cro2, sound_pb='inazuma2/data_iz/sound/sound.pb' in f16,
               archive_sha256=B.sha(B.SALIDA), capas=capas)
    (B.HERE / 'validacion.json').write_text(json.dumps(out, ensure_ascii=False, indent=2, default=str),
                                            encoding='utf-8')
    print(json.dumps(out, ensure_ascii=False, indent=1, default=str)[:5000])
    return 0 if not fallos else 1


if __name__ == '__main__':
    sys.exit(main())
