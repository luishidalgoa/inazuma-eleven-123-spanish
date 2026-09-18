"""IE2 v17 · validación de la candidata probe_ie2_v17 con el modelo ampliado (comun17).

- TODOS los registros de diálogo de IE2 (eve y mch) del archive: ninguna página > 131 B, <= 3 líneas,
  <= 37 caracteres por línea, el dibujo (0x1C0) no parte ninguna línea; registros <= 247 B.
- Registros cambiados: mismas palabras que v16 (nada acortado); fuera de la sonda, mismo tamaño y solo
  `\\n` -> `\\f`. Sonda (22500101/2): el motor a 0x1A0 no inserta saltos.
- Resto del PackNum igual a v16; CRO iguales a v16 (8+2 B de v15 sobre la base v09).
- Vídeos: los 35 moflex del archive coinciden con el sha256 de v11/subtitulos/informe.json.
Uso: python -X utf8 work/ie2/shared/capas/v17/paginas/validate.py  -> validacion.json
"""
from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import apply as A  # noqa: E402

C, M, W = A.C, A.M, A.W
CAND = W / 'shared/candidatas/probe_ie2_v17'


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    res, fallos = {}, []

    def ok(nombre, cond, detalle=None):
        res[nombre] = dict(ok=bool(cond), detalle=detalle)
        if not cond:
            fallos.append(nombre)

    v16 = M.Archivo(A.BASE)
    v17 = M.Archivo(CAND / 'archive.fa')
    cont = Counter()
    malos, cambios_raros, sonda_mal, mayores = [], [], [], []
    for pk in ('eve', 'mch'):
        ids = v16.ids(pk)
        ok(f'{pk}_mismos_ids', ids == v17.ids(pk))
        capa = {int(p.stem) for p in A.SALIDA[pk].glob('*.ssd')}
        for eid in ids:
            b = v17.evento(pk, eid)
            a = v16.evento(pk, eid)
            if eid in capa:
                if b != (A.SALIDA[pk] / f'{eid}.ssd').read_bytes():
                    cambios_raros.append((pk, eid, 'distinto de la capa'))
            elif a != b:
                cambios_raros.append((pk, eid, 'cambiado sin estar en la capa'))
            end, ins, ra, dl = M.dialogos(a)
            _, ins2, rb = M.S.parse(b)
            if ins2 != ins or len(ra) != len(rb) or b[32:end] != a[32:end]:
                cambios_raros.append((pk, eid, 'bytecode'))
                continue
            for i in dl:
                x, y = ra[i].body, rb[i].body
                cont['registros'] += 1
                cont['paginas'] += len(C.paginas(y))
                p = C.problemas(y)
                if p:
                    malos.append((pk, eid, i, p))
                if len(y) > M.MAX_BYTES:
                    mayores.append((pk, eid, i, len(y)))
                if x == y:
                    continue
                cont['cambiados'] += 1
                if A.palabras(A.espanol(x)) != A.palabras(A.espanol(y)):
                    cambios_raros.append((pk, eid, i, 'palabras'))
                if pk == 'eve' and eid in A.SONDA:
                    if C.reajusta(y):
                        sonda_mal.append((eid, i))
                else:
                    if len(x) != len(y) or x.replace(b'\\f', b'\\n') != y.replace(b'\\f', b'\\n'):
                        cambios_raros.append((pk, eid, i, 'no es solo \\n -> \\f'))
                    cont['paginas_partidas'] += y.count(b'\\f') - x.count(b'\\f')
            for j, (r1, r2) in enumerate(zip(ra, rb)):
                if j not in dl and r1.raw != r2.raw:
                    cambios_raros.append((pk, eid, j, 'registro no diálogo'))
    ok('paginas_131_y_lineas_37', not malos, malos[:20])
    ok('registros_247', not mayores, mayores[:20])
    ok('cambios_limpios', not cambios_raros, cambios_raros[:20])
    ok('sonda_sin_reajuste', not sonda_mal, sonda_mal)
    res['cuentas'] = dict(cont)

    # CRO y romfs
    for n in ('ina_main1.cro', 'ina_main2.cro'):
        ok(f'cro_{n}', (CAND / 'romfs/cro' / n).read_bytes()
           == (W / 'shared/candidatas/probe_ie2_v16/romfs/cro' / n).read_bytes())
    cro2 = (CAND / 'romfs/cro/ina_main2.cro').read_bytes()
    ok('cro_parches_v15', [cro2[a:a + 4].hex() for a in (0x66a24, 0x4cabc, 0x4d6a0)]
       == ['1a1ea0e3', '1a2ea0e3', '072da0e3'])

    # vídeos
    inf = json.loads((W / 'ie2/shared/capas/v11/subtitulos/informe.json').read_text(encoding='utf-8'))
    vid = {v['nombre']: v['sha256'] for v in inf['videos']}
    ok('videos_35', len(vid) == 35, len(vid))
    distintos = []
    for n, h in vid.items():
        d = v17.get(f'inazuma2/data_iz/movie/{n}.moflex')
        if hashlib.sha256(d).hexdigest() != h:
            distintos.append(n)
    ok('videos_sha256', not distintos, distintos)

    out = dict(ok=not fallos, fallos=fallos, comprobaciones=res)
    (HERE / 'validacion.json').write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str),
                                          encoding='utf-8')
    print('OK' if not fallos else f'FALLOS: {fallos}', json.dumps(res['cuentas']))
    return 0 if not fallos else 1


if __name__ == '__main__':
    sys.exit(main())
