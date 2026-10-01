"""ie123kit.ie3.comun.pestanas_latinas: rótulos en las 10 casillas de 20 px, sin tocar fuera del interior."""
import unittest

import numpy as np
from PIL import Image

from ie123kit.ie3.comun import pestanas_latinas as P


def _eu() -> Image.Image:
    """Textura europea sintética: fondo claro y cada letra como una columna oscura de 7 px (1 px de ancho)."""
    a = np.full((64, 256, 4), 230, np.uint8)
    for franja in P.FRANJAS:
        for e, rot in enumerate(P.EU_PESTANAS):
            for i, _ in enumerate(rot):
                x = P.PASO_EU * e + 4 + 3 * i
                a[franja + P.Y_GLIFO:franja + P.Y_GLIFO + 7, x] = (20, 20, 90, 255)
    return Image.fromarray(a)


class TestPestanas(unittest.TestCase):
    def test_rotulos_en_su_casilla(self):
        jp = Image.fromarray(np.full((64, 256, 4), 200, np.uint8))
        out = np.array(P.pestanas(jp, _eu())).astype(int)
        base = np.full((64, 256, 4), 200)
        cambio = np.abs(out - base).sum(axis=2) > 0
        ys, xs = np.nonzero(cambio)
        self.assertTrue(ys.min() >= P.Y_TXT[0] and ys.max() < 32 + P.Y_TXT[1] + 1)
        for t in range(10):                      # tinta en cada casilla de 20 px, dentro de su interior
            cols = xs[(xs >= 20 * t) & (xs < 20 * t + 20)]
            self.assertTrue(len(cols) > 0)
            self.assertTrue(cols.min() >= 20 * t + 2 and cols.max() < 20 * t + 18)
        self.assertFalse(cambio[:, 200:].any())


if __name__ == "__main__":
    unittest.main()
