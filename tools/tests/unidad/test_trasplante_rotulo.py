"""Trasplante de rótulos entre texturas (ie123kit.nucleo.graficos.trasplante_rotulo)."""

from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from ie123kit.nucleo.graficos import trasplante_rotulo as TR

BARRA, CREMA, SOMBRA = (156, 57, 0, 255), (255, 222, 139, 255), (123, 41, 8, 255)


def _barra():
    im = Image.new("RGBA", (40, 12), BARRA)
    a = np.array(im)
    a[0, :] = SOMBRA                     # borde de la barra con el mismo color que la sombra
    a[4:7, 10:14] = SOMBRA
    a[5:8, 11:15] = CREMA
    return Image.fromarray(a, "RGBA")


def test_mascara_y_caja():
    im = Image.new("RGBA", (10, 10), (0, 0, 0, 255))
    a = np.array(im)
    a[2:4, 3:6] = (255, 255, 255, 255)
    m = TR.mascara_tinta(Image.fromarray(a, "RGBA"), (0, 0, 10, 10), (255, 255, 255))
    assert m.shape == (2, 3) and m.all()
    assert TR.caja_tinta(_barra(), (0, 1, 40, 12), (CREMA,)) == (11, 5, 15, 8)
    with pytest.raises(ValueError):
        TR.mascara_tinta(im, (0, 0, 10, 10), (255, 255, 255))


def test_borrar_y_pegar_con_sombra():
    im = TR.borrar_tinta(_barra(), (10, 4, 15, 8), (CREMA, SOMBRA), BARRA)
    a = np.array(im)
    assert (a[0] == SOMBRA).all()                                     # el borde no se toca
    assert (a[1:] == BARRA).all()
    m = np.ones((2, 4), bool)
    im2, caja = TR.pegar_mascara(im, m, 20, 5, CREMA, SOMBRA, (-1, -1), limites=(0, 1, 40, 12))
    b = np.array(im2)
    assert caja == (17, 4, 22, 7)
    assert tuple(b[4, 17]) == SOMBRA and tuple(b[5, 18]) == CREMA and tuple(b[6, 21]) == CREMA
    with pytest.raises(ValueError):
        TR.pegar_mascara(im, m, 1, 5, CREMA, SOMBRA, limites=(0, 1, 40, 12))
