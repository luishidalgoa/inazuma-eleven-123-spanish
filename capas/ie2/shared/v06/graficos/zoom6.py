"""Recorte ampliado con rejilla (cada 4 px fina, cada 16 px marcada) de texturas JP de IE2.
Uso: python zoom6.py <salida.png> <arc rel. a data_iz> <textura> [x0 y0 x1 y1] [escala]
     varias: separar grupos con '+' : ... tex1 x0 y0 x1 y1 + tex2 ...
"""
import sys

import numpy as np
from PIL import Image, ImageDraw

import base as B
C = B.C


def recorte(arc, tex, caja=None, s=6):
    raw = C.U.unwrap(C.jp().get('inazuma2/data_iz/' + arc))
    blob = next(b for n, _, _, b in C.texturas(raw) if n == tex or n == f'ie02_{tex}.tga' or n.endswith(tex + '.tga'))
    im = C.decodificar(blob)
    x0, y0, x1, y1 = caja or (0, 0, im.width, im.height)
    z = C.ampliar(im.crop((x0, y0, x1, y1)), s, fondo=(255, 0, 255, 255))
    lz = Image.new('RGBA', (z.width + 30, z.height + 12), (0, 0, 0, 255))
    lz.paste(z, (30, 12))
    d = ImageDraw.Draw(lz)
    for x in range(x0, x1 + 1):
        if x % 4 == 0:
            X = 30 + (x - x0) * s
            d.line([(X, 12), (X, lz.height)], fill=(0, 255, 0, 255) if x % 16 == 0 else (0, 90, 0, 255))
            if x % 8 == 0:
                d.text((X + 1, 0), str(x), fill=(255, 255, 255, 255))
    for y in range(y0, y1 + 1):
        if y % 4 == 0:
            Y = 12 + (y - y0) * s
            d.line([(30, Y), (lz.width, Y)], fill=(0, 255, 0, 255) if y % 16 == 0 else (0, 90, 0, 255))
            if y % 8 == 0:
                d.text((0, Y), str(y), fill=(255, 255, 255, 255))
    return lz


def main():
    out, arc = sys.argv[1], sys.argv[2]
    grupos, g = [], []
    for a in sys.argv[3:]:
        if a == '+':
            grupos.append(g)
            g = []
        else:
            g.append(a)
    grupos.append(g)
    ims = []
    for g in grupos:
        tex = g[0]
        nums = [int(v) for v in g[1:]]
        caja = tuple(nums[:4]) if len(nums) >= 4 else None
        s = nums[4] if len(nums) >= 5 else 6
        ims.append(recorte(arc, tex, caja, s))
    C.hoja(ims, ancho=max(2000, max(i.width for i in ims))).save(out)


if __name__ == '__main__':
    main()
