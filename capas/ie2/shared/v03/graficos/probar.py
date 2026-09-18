"""Banco de pruebas del plan de menús: pinta las texturas de un .arc y guarda zoom ×4 + tintes.

Uso: python probar.py <salida.png> <nombre_arc (sin ruta)> [textura ...]
Tintes: el juego oscurece/aclara/colorea los botones al pulsarlos; se multiplica la textura por
tres colores y se compone sobre un fondo de contraste para comprobar que no aparece ninguna caja.
"""
import sys

import numpy as np
from PIL import Image

import comun as C
import pintado_menus as PM


def tintes(im):
    a = np.array(im).astype(float)
    out = []
    for t in ((0.45, 0.45, 0.45), (1.0, 0.55, 0.2), (0.5, 0.8, 1.0)):
        b = a.copy()
        b[..., :3] *= t
        out.append(Image.fromarray(b.clip(0, 255).astype(np.uint8), 'RGBA'))
    for fondo in ((255, 0, 255, 255), (255, 255, 255, 255)):
        z = Image.new('RGBA', im.size, fondo)
        z.alpha_composite(im)
        out.append(z)
    return out


def main():
    salida, arcn = sys.argv[1], sys.argv[2]
    ruta = next(r for r in PM.PLAN if r.endswith('/' + arcn))
    raw = C.U.unwrap(C.jp().get(ruta))
    ims = []
    for nombre, off, ln, blob in C.texturas(raw):
        if nombre not in PM.PLAN[ruta] or (sys.argv[3:] and nombre not in sys.argv[3:]):
            continue
        antes = C.decodificar(blob)
        arr = PM.pintar(np.array(antes), PM.PLAN[ruta][nombre])
        final = C.cuantizar(blob, Image.fromarray(arr, 'RGBA'))
        s = 4 if max(antes.size) <= 256 else 2
        ims.append(C.par(antes, final, s=s, titulo=nombre))
        ims.append(C.hoja([C.ampliar(t, 2, fondo=(0, 0, 0, 0)) for t in tintes(final)], ancho=4000))
    C.hoja(ims, ancho=max(i.width for i in ims)).save(salida)


if __name__ == '__main__':
    main()
