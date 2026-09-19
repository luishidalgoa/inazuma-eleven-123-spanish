"""Hoja de un .arc: JP | v03 por textura (x2) y, si existe, el .arc IE1 homónimo JP | v89.
Uso: python volcar6.py <salida.png> <arc relativo a data_iz> [min_lado=9]"""
import sys

import numpy as np
from PIL import Image, ImageDraw

import base as B
C = B.C


def fila(titulo, ims, s):
    zs = [C.ampliar(i, s) for i in ims]
    w = sum(z.width + 6 for z in zs)
    lz = Image.new('RGBA', (max(w, 200), max(z.height for z in zs) + 14), (60, 0, 0, 255))
    ImageDraw.Draw(lz).text((2, 1), titulo, fill=(255, 255, 255, 255))
    x = 0
    for z in zs:
        lz.alpha_composite(z, (x, 14))
        x += z.width + 6
    return lz


def main():
    out, arc = sys.argv[1], sys.argv[2]
    ruta = 'inazuma2/data_iz/' + arc
    jr = C.U.unwrap(C.jp().get(ruta))
    vr = C.U.unwrap(B.base_arc(ruta))
    v = {n: b for n, _, _, b in C.texturas(vr)}
    ims = []
    for n, _, _, b in C.texturas(jr):
        a = C.decodificar(b)
        if max(a.size) < 9 or not (np.array(a)[..., 3] > 0).any():
            continue
        s = 2 if max(a.size) <= 256 else 1
        t = n + ('  [v03]' if v[n] != b else '')
        ims.append(fila(t, [a] + ([C.decodificar(v[n])] if v[n] != b else []), s))
    r1 = ruta.replace('inazuma2', 'inazuma1')
    if r1 in C.jp() and r1 in C.ie1tr():
        a1 = C.texturas(C.U.unwrap(C.jp().get(r1)))
        b1 = {n: x for n, _, _, x in C.texturas(C.U.unwrap(C.ie1tr().get(r1)))}
        for n, _, _, x in a1:
            if b1.get(n, x) != x:
                A = C.decodificar(x)
                s = 2 if max(A.size) <= 256 else 1
                ims.append(fila('IE1 ' + n, [A, C.decodificar(b1[n])], s))
    C.hoja(ims, ancho=2600).save(out)


if __name__ == '__main__':
    main()
