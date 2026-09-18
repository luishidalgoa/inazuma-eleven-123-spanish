"""Hoja de estado de un .arc: cada textura con contenido tal como quedará (plan aplicado) o la japonesa
si no se toca, marcada en rojo si no se toca. Uso: python estado.py <salida.png> <arc relativo a data_iz>..."""
import sys

import numpy as np
from PIL import Image, ImageDraw

import comun as C
import pintado_menus as PM


def main():
    salida = sys.argv[1]
    ims = []
    for arc in sys.argv[2:]:
        ruta = 'inazuma2/data_iz/' + arc
        raw = C.U.unwrap(C.jp().get(ruta))
        plan = PM.PLAN.get(ruta, {})
        for nombre, _, _, blob in C.texturas(raw):
            a = np.array(C.decodificar(blob))
            if not (a[..., 3] > 0).any() or max(a.shape[:2]) <= 8:
                continue
            tocada = nombre in plan
            if tocada:
                try:
                    a = PM.pintar(a, plan[nombre])
                    color = (0, 160, 0, 255)
                except Exception as e:  # noqa: BLE001
                    color = (255, 160, 0, 255)
                    print('fallo', nombre, e)
            else:
                color = (200, 0, 0, 255)
            s = 2 if max(a.shape[:2]) <= 256 else 1
            z = C.ampliar(Image.fromarray(a), s)
            lienzo = Image.new('RGBA', (max(z.width, 160), z.height + 14), color)
            ImageDraw.Draw(lienzo).text((2, 1), arc.split('/')[-1] + ' ' + nombre[5:-4], fill=(255, 255, 255, 255))
            lienzo.alpha_composite(z, (0, 14))
            ims.append(lienzo)
    C.hoja(ims, ancho=2400).save(salida)


if __name__ == '__main__':
    main()
