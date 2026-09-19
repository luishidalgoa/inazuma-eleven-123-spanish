"""IE2 v13 · cro_ranura: validación offline (runtime_verified=false).

- extra/ contiene solo inazuma2/data_iz/a_menu/menu_slot.arc.
- Envoltura SSZL como el japonés; unwrap con la misma tabla ARCV que el japonés y que v06/v10.
- Respecto al menu_slot.arc de v06 (= probe_ie2_v10) solo cambia la entrada CTPK ie02_slot_b_font01;
  metadata CTPK idéntica y códec ida y vuelta; el QNA y el resto de texturas, byte a byte.
- Píxeles: fuera de las celdas QNA de la textura no cambia nada respecto a v10; las celdas que v03 ya
  tenía bien (Nivel equipo, Tiempo, h, m, Opciones ×2) quedan idénticas a v10; la celda 人 queda vacía;
  cada rótulo nuevo tiene tinta, cabe en su celda con 1 px de margen lateral y no pasa de la fila 14.
- Ninguna parte QNA de la ranura apunta fuera de las celdas conocidas (no se movió el atlas).
- ina_main2.cro no se toca: el literal 0x216528 de v09 es «Raimon» (8 B, como el japonés, sin NUL dentro).
Salida: validacion.json. Código 1 si falla algo.
"""
from __future__ import annotations

import json
import sys

import numpy as np

import apply as A

C = A.C


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    problemas = []
    escritos = sorted(str(p.relative_to(A.HERE / 'extra')).replace('\\', '/')
                      for p in (A.HERE / 'extra').rglob('*') if p.is_file())
    if escritos != [A.RUTA]:
        problemas.append(f'extra/ inesperado: {escritos}')
    nuevo = A.SALIDA.read_bytes()
    jp = C.jp().get(A.RUTA)
    base = A.BASE_ARC.read_bytes()
    if C.Archivo(A.CAND).get(A.RUTA) != base:
        problemas.append('la base v06 no es la instalada en probe_ie2_v10')
    if (nuevo[:4] == b'SSZL') != (jp[:4] == b'SSZL'):
        problemas.append('envoltura SSZL distinta')
    rj, rb, rn = C.U.unwrap(jp), C.U.unwrap(base), C.U.unwrap(nuevo)
    if not (C.U.entries(rj) == C.U.entries(rb) == C.U.entries(rn)) or len(rb) != len(rn):
        problemas.append('tabla ARCV distinta')
    cambiadas = []
    for off, ln, _ in C.U.entries(rb):
        x, y = rb[off:off + ln], rn[off:off + ln]
        if x == y:
            continue
        nombre = C.T.metadata(x)[0] if x[:4] == b'CTPK' else None
        cambiadas.append(nombre)
        if nombre != A.TEX:
            problemas.append(f'entrada no declarada: {nombre}')
        elif C.T.metadata(x) != C.T.metadata(y):
            problemas.append('metadata CTPK')
        elif C.T.encode(y, C.T.decode(y)) != y:
            problemas.append('códec')
    if cambiadas != [A.TEX]:
        problemas.append(f'cambian {cambiadas}')

    tn, tv, tj = A.texturas(rn), A.texturas(rb), A.texturas(rj)
    fin = np.array(C.decodificar(tn[A.TEX][2]))
    v10 = np.array(C.decodificar(tv[A.TEX][2]))
    celdas = sorted({tuple(int(v) for v in uv) for i, n, uv, wh, xy in A.qna_partes(rj) if n == A.TEX[:-4]})
    conocidas = {tuple(o['caja']) for o in A.OPS}
    if set(celdas) != conocidas:
        problemas.append(f'celdas QNA {celdas} != plan {sorted(conocidas)}')
    for i, n, uv, wh, xy in A.qna_partes(rn):
        if n == A.TEX[:-4] and tuple(int(v) for v in uv) not in conocidas:
            problemas.append(f'parte {i} fuera de las celdas')
    fuera = np.ones(fin.shape[:2], bool)
    for x0, y0, x1, y1 in conocidas:
        fuera[y0:y1, x0:x1] = False
    if not np.array_equal(fin[fuera], v10[fuera]):
        problemas.append('píxeles cambiados fuera de las celdas')
    for x0, y0, x1, y1 in A.IGUALES_V10:
        if not np.array_equal(fin[y0:y1, x0:x1], v10[y0:y1, x0:x1]):
            problemas.append(f'celda {(x0, y0, x1, y1)} distinta de v10')
    tinta = {}
    for o in A.OPS:
        x0, y0, x1, y1 = o['caja']
        t = A.caja_tinta(fin, o['caja'])
        tinta[str(o['caja'])] = t
        if not o['texto']:
            if t is not None:
                problemas.append(f'celda {o["caja"]} debería estar vacía')
            continue
        if t is None:
            problemas.append(f'celda {o["caja"]} sin tinta')
            continue
        if t[0] < 1 or t[2] > (x1 - x0) - 2 or t[3] > 14:
            problemas.append(f'celda {o["caja"]} sin margen: {t}')
    if not any(np.any(fin[y0:y1, x0:x1] != v10[y0:y1, x0:x1]) for x0, y0, x1, y1 in A.CAMBIADAS):
        problemas.append('no cambió ninguna celda del plan')

    cro9 = A.CRO_V09.read_bytes()
    lit = cro9[0x216528:0x216530]
    if lit != bytes.fromhex('82719df8828de28d') or len(A.CRO_JP.read_bytes()[0x216528:0x216530]) != 8:
        problemas.append('literal 0x216528 de v09 no es «Raimon» de v04')
    if cro9[0x216530] != 0:
        problemas.append('literal 0x216528 sin NUL')

    res = dict(archivo=A.RUTA, bytes=len(nuevo), entradas_cambiadas=cambiadas, celdas_qna=celdas, tinta=tinta,
               cro='sin cambios (v09)', problemas=problemas, resultado='PASS' if not problemas else 'FAIL',
               runtime_verified=False)
    (A.HERE / 'validacion.json').write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return 1 if problemas else 0


if __name__ == '__main__':
    sys.exit(main())
