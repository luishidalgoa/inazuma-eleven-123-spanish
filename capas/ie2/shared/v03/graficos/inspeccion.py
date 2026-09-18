"""Hoja de inspección por .arc: texturas sin cubrir, ampliadas con rejilla de 8 px y cajas QNA numeradas.

Uso: python inspeccion.py <dir_salida> <arc> [<arc> ...]   (arc = ruta relativa a inazuma2/data_iz/)
Imprime por textura: tamaño, formato y lista de cajas QNA (índice: caja).
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

import comun as C


def hechas():
    try:
        inf = json.loads((C.HERE / 'informe.json').read_text(encoding='utf-8'))
    except FileNotFoundError:
        return set()
    return {(r['ruta'], c['textura']) for r in inf for c in r.get('cambios', []) if c['modo'] != 'pintada'}


def main():
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    ya = hechas()
    for a in sys.argv[2:]:
        ruta = 'inazuma2/data_iz/' + a
        raw = C.U.unwrap(C.jp().get(ruta))
        qna = C.qna_cajas(ruta)
        ims = []
        print('#####', a)
        for nombre, off, ln, blob in C.texturas(raw):
            if (ruta, nombre) in ya:
                continue
            arr = np.array(C.decodificar(blob))
            if not (arr[..., 3] > 0).any():
                continue
            s = 4 if max(arr.shape[:2]) <= 128 else (2 if max(arr.shape[:2]) <= 512 else 1)
            im = C.ampliar(Image.fromarray(arr), s)
            lienzo = Image.new('RGBA', (im.width, im.height + 12), (0, 0, 0, 255))
            lienzo.alpha_composite(im, (0, 12))
            d = ImageDraw.Draw(lienzo)
            d.text((1, 0), nombre[5:-4], fill=(255, 255, 0, 255))
            cajas = sorted(qna.get(nombre, ()), key=lambda q: (q[1], q[0]))
            print('==', nombre, f'{arr.shape[1]}x{arr.shape[0]} fmt{C.T.metadata(blob)[3]}',
                  ' '.join(f'{k}:{q}' for k, q in enumerate(cajas)))
            for k, (x0, y0, x1, y1) in enumerate(cajas):
                x0, x1 = sorted((x0, x1))
                y0, y1 = sorted((y0, y1))
                if x1 <= x0 or y1 <= y0:
                    continue
                d.rectangle((x0 * s, 12 + y0 * s, x1 * s - 1, 12 + y1 * s - 1), outline=(0, 255, 255, 255))
                d.text((x0 * s + 1, 12 + y0 * s), str(k), fill=(0, 255, 0, 255))
            ims.append(lienzo)
        if ims:
            C.hoja(ims, ancho=max(1600, max(i.width for i in ims))).save(out / (a.replace('/', '__') + '.png'))


if __name__ == '__main__':
    main()
