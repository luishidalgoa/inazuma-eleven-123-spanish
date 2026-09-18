"""IE2 v07 · media: tiras antes/después de los rótulos del dibujo (issue #74, rotulos.py).

Columnas: 3DS japonés (antes) | vídeo recodificado de v07 (después) | NDS español (referencia, instante t*nds/3ds).
Salida: tiras/rotulos_<n>.png. Uso: python -X utf8 rotulos_tiras.py [nombres...]
"""
from __future__ import annotations

import sys

import numpy as np
from PIL import Image, ImageDraw

import comun_media as C
import tiras
import videos as V

MUESTRAS = {'a2m06': [580, 600, 625, 650, 663, 668, 965, 990, 1005],
            'a2m20b': [50, 65, 80, 90, 110, 128]}


def jp(n, ks):
    t = C.Temporal()
    try:
        Y, U, W_ = V.leer_yuv(t.moflex(n + '.moflex'))
    finally:
        t.cerrar()
    return {k: V.yuv_a_rgb(Y[k:k + 1], U[k:k + 1], W_[k:k + 1])[0] for k in ks}, len(Y)


def main():
    for n in sys.argv[1:] or list(MUESTRAS):
        ks = MUESTRAS[n]
        J, total = jp(n, ks)
        ruta = C.MODS / 'sp' / f'{n}.mods'
        ruta = ruta if ruta.exists() else C.MODS / f'{n}.mods'
        N = V.nds_a_rgb(*V.leer_yuv(ruta, 256, 192))
        F = tiras.fotogramas(V.destino(n), ks)
        im = Image.new('RGB', (980, 20 + len(ks) * 244), (18, 18, 24))
        d = ImageDraw.Draw(im)
        d.text((4, 4), f'{n}: 3DS JP (antes) | v07 recodificado (despues) | NDS ES (referencia)', fill=(230, 230, 230))
        import rotulos
        desf = {k: kw['off'] for _, kw in rotulos.TRAMOS[n] for k in range(kw['k0'], kw['k1'])}
        for i, k in enumerate(ks):
            y = 20 + i * 244
            m = min(len(N) - 1, round(k * len(N) / total) + desf.get(k, 0))
            im.paste(Image.fromarray(np.ascontiguousarray(J[k])), (0, y))
            im.paste(F[k], (330, y))
            im.paste(Image.fromarray(np.ascontiguousarray(N[m])), (660, y))
            d.text((4, y + 2), f'f{k}', fill=(255, 80, 80))
        destino = C.SALIDA / 'tiras' / f'rotulos_{n}.png'
        im.save(destino, optimize=True)
        print(destino)


if __name__ == '__main__':
    main()
