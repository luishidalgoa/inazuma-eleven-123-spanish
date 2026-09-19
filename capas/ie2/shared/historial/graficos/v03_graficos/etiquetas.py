"""Inspector: numera los grupos de trazo de una textura y guarda un zoom con cajas y rejilla de 16 px.

Uso: python etiquetas.py <salida_dir> <ruta_arc> <textura> [<textura> ...]
Imprime: n caja(x0,y0,x1,y1) y colores dominantes.
"""
import sys
from collections import Counter
from pathlib import Path

import numpy as np


def norm(a):
    """Copia para comparar: todo píxel con alfa 0 pasa a (0,0,0,0)."""
    b = a.copy()
    b[b[..., 3] == 0] = 0
    return b
from PIL import Image, ImageDraw
from scipy import ndimage

import comun as C


def grupos(arr, bg_modo='alfa'):
    a = arr[..., 3] > 0 if bg_modo == 'alfa' else None
    if bg_modo == 'fila':
        arr = norm(arr)
        a = np.zeros(arr.shape[:2], bool)
        for i in range(arr.shape[0]):
            c = Counter(map(tuple, arr[i])).most_common(1)[0][0]
            a[i] = np.any(arr[i] != c, -1)
    d = ndimage.binary_dilation(a, np.ones((3, 5), bool))
    lab, _ = ndimage.label(d)
    out = []
    for s in ndimage.find_objects(lab):
        out.append((s[1].start, s[0].start, s[1].stop, s[0].stop))
    return out


def main():
    salida = Path(sys.argv[1])
    ruta = sys.argv[2]
    modo = 'fila'
    raw = C.U.unwrap(C.jp().get(ruta))
    qna = C.qna_cajas(ruta)
    for nombre, off, ln, blob in C.texturas(raw):
        if nombre not in sys.argv[3:] and sys.argv[3] != '*':
            continue
        arr = np.array(C.decodificar(blob))
        s = 4 if max(arr.shape) <= 256 else 2
        im = C.ampliar(Image.fromarray(arr), s)
        d = ImageDraw.Draw(im)
        for g in range(0, arr.shape[1], 16):
            d.line([(g * s, 0), (g * s, im.height)], fill=(80, 80, 80, 255))
        for g in range(0, arr.shape[0], 16):
            d.line([(0, g * s), (im.width, g * s)], fill=(80, 80, 80, 255))
        print('==', nombre, arr.shape[1], 'x', arr.shape[0], 'fmt', C.T.metadata(blob)[3])
        for k, (x0, y0, x1, y1) in enumerate(grupos(arr, modo)):
            zona = arr[y0:y1, x0:x1].reshape(-1, 4)
            cols = Counter(map(tuple, zona)).most_common(3)
            print(k, (x0, y0, x1, y1), [(tuple(int(v) for v in c), n) for c, n in cols])
            d.rectangle((x0 * s, y0 * s, x1 * s - 1, y1 * s - 1), outline=(255, 0, 255, 255))
            d.text((x0 * s + 1, y0 * s), str(k), fill=(0, 255, 0, 255))
        for q in sorted(qna.get(nombre, ())):
            print('  qna', q)
            x0, y0, x1, y1 = q
            d.rectangle((min(x0, x1) * s, min(y0, y1) * s, max(x0, x1) * s - 1, max(y0, y1) * s - 1),
                        outline=(0, 255, 255, 255))
        salida.mkdir(parents=True, exist_ok=True)
        im.save(salida / (Path(nombre).stem + '.png'))


if __name__ == '__main__':
    main()
