"""v06 · gráficos de IE2 (issue #73), capa sobre v03. No construye candidata ni instala.

Para cada textura del plan v06 (planes_v06.PLAN6):
  * si v03 ya la pintó con su plan: se parte del japonés y se aplican las ops de v03 + las de v06;
  * si v03 la cambió de otro modo (IE1 exacta/regiones): se parte de la imagen de v03 + ops v06;
  * si no: japonés + ops v06.
Cada textura debe quedar entera en español: las celdas QNA con trazo que no cubre ninguna op (ni se
declaran `nada`) la envían a pendientes y NO se escribe (nada de texturas mitad japonés).
Salida: extra/<ruta> (solo .arc que difieren de v03; cada uno parte del .arc de v03),
informe.json, pendientes.json, previews/x4_<grupo>_NN.png (original | nuevo ×4 + tintes).
Uso: python apply6.py [filtro_de_ruta]
"""
import json
import shutil
import sys
from collections import defaultdict

import numpy as np
from PIL import Image

import base as B
import pintado_menus as PM
import sugerir as SG
from probar import tintes
import planes_v06 as P6

C = B.C

assert C.IE1TR_FA.exists(), C.IE1TR_FA   # referencia IE1 (base.py): lista de celdas IE1 «sin texto» activa


def v03_texturas(ruta):
    f = B.V03_EXTRA / ruta
    if not f.exists():
        return {}
    jp = {n: b for n, _, _, b in C.texturas(C.U.unwrap(C.jp().get(ruta)))}
    return {n: b for n, _, _, b in C.texturas(C.U.unwrap(f.read_bytes())) if jp.get(n) != b}


def cajas_ops(ops):
    out = []
    for o in ops:
        if 'caja' in o:
            out.append(tuple(o['caja']))
        out.extend(tuple(c) for c in o.get('cubre', ()))
    return out


def procesar(ruta, plan, pend, previews, informe):
    jp_orig = C.jp().get(ruta)
    base = B.base_arc(ruta)
    raw_jp = C.U.unwrap(jp_orig)
    raw = bytearray(C.U.unwrap(base))
    v03 = v03_texturas(ruta)
    jp_tex = {n: b for n, _, _, b in C.texturas(raw_jp)}
    cambios = []
    for nombre, off, ln, blob in C.texturas(bytes(raw)):
        if nombre not in plan:
            continue
        ops6 = plan[nombre]
        jblob = jp_tex[nombre]
        antes = np.array(C.decodificar(jblob))
        if nombre in v03 and nombre in PM.PLAN.get(ruta, {}):
            ops = list(PM.PLAN[ruta][nombre]) + list(ops6)
            inicio = antes
        elif nombre in v03:
            ops = list(ops6)
            inicio = np.array(C.decodificar(v03[nombre]))
        else:
            ops = list(ops6)
            inicio = antes
        if C.T.metadata(jblob)[3] not in C.EDITABLES:
            pend.append(dict(tipo='formato_no_editable', arc=ruta, textura=nombre))
            continue
        P6.ACTUAL = (ruta, nombre)
        try:
            arr = PM.pintar(inicio, ops)
        except (ValueError, KeyError, IndexError) as e:
            pend.append(dict(tipo='pintado_fallido', arc=ruta, textura=nombre, motivo=str(e)))
            continue
        faltan = SG.cobertura(ruta, nombre, antes, cajas_ops(ops))
        if faltan and not getattr(P6, 'SIN_COBERTURA', {}).get((ruta, nombre)):
            pend.append(dict(tipo='celdas_sin_cubrir', arc=ruta, textura=nombre, cajas=faltan[:12]))
            continue
        nuevo = C.codificar(blob, Image.fromarray(arr, 'RGBA'))
        if nuevo == blob:
            continue
        raw[off:off + ln] = nuevo
        cambios.append(dict(textura=nombre, modo='pintada_v06', sobre_v03=nombre in v03))
        final = C.decodificar(nuevo)
        a = C.decodificar(jblob)
        s = 4 if max(a.size) <= 256 else 2
        g = P6.grupo(ruta)
        previews['x4_' + g].append(C.par(a, final, s=s, titulo=f'{ruta.split("/")[-1]} {nombre}'))
        if P6.con_tintes(ruta):
            previews['x4_' + g].append(C.hoja([C.ampliar(t, 2, fondo=(0, 0, 0, 0)) for t in tintes(final)],
                                              ancho=4000))
    if not cambios:
        return
    raw = bytes(raw)
    assert C.U.entries(raw) == C.U.entries(raw_jp)
    datos = C.reenvolver(jp_orig, raw)
    if datos == base:
        return
    destino = B.EXTRA / ruta
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(datos)
    informe.append(dict(ruta=ruta, clase='textura', cambios=cambios, base='v03' if (B.V03_EXTRA / ruta).exists()
                        else 'jp', sszl=jp_orig[:4] == b'SSZL', tam_original=len(jp_orig), tam_nuevo=len(datos)))


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    filtro = sys.argv[1] if len(sys.argv) > 1 else ''
    if not filtro:
        shutil.rmtree(B.EXTRA, ignore_errors=True)
        shutil.rmtree(B.PREVIEWS, ignore_errors=True)
    B.PREVIEWS.mkdir(parents=True, exist_ok=True)
    fi, fp = B.HERE / 'informe.json', B.HERE / 'pendientes.json'
    informe = json.loads(fi.read_text(encoding='utf-8')) if filtro and fi.exists() else []
    pend = json.loads(fp.read_text(encoding='utf-8')) if filtro and fp.exists() else []
    informe = [r for r in informe if filtro not in r['ruta']]
    pend = [p for p in pend if filtro not in p.get('arc', p.get('ruta', ''))]
    previews = defaultdict(list)
    for ruta in sorted(P6.PLAN6):
        if filtro in ruta:
            procesar(ruta, P6.PLAN6[ruta], pend, previews, informe)
    for g, ims in previews.items():
        for f in B.PREVIEWS.glob(f'{g}_*.png'):
            f.unlink()
        for i in range(0, len(ims), 24):
            C.hoja(ims[i:i + 24], ancho=max(1800, max(x.width for x in ims[i:i + 24]))).save(
                B.PREVIEWS / f'{g}_{i // 24:02d}.png')
    if not filtro:
        pend.extend(P6.NOTAS)
    informe.sort(key=lambda r: r['ruta'])
    fi.write_text(json.dumps(informe, ensure_ascii=False, indent=1), encoding='utf-8')
    fp.write_text(json.dumps(pend, ensure_ascii=False, indent=1), encoding='utf-8')
    print(len(informe), 'ficheros;', sum(len(r['cambios']) for r in informe), 'texturas;', len(pend), 'pendientes')
    for p in pend:
        if filtro in p.get('arc', ''):
            print(' ', p)


if __name__ == '__main__':
    main()
