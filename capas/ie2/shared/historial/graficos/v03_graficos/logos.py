"""Logotipo «INAZUMA ELEVEN 2»: logo europeo oficial de IE1 (3DS EU, ya en la candidata v89) + el «2» del
logo japonés de IE2 (segmentado por color rojo y dilatado para incluir su contorno)."""
from functools import lru_cache

import numpy as np
from scipy import ndimage

import comun as C


@lru_cache(None)
def logo_eu():
    return {n: np.array(C.decodificar(b)) for n, _, _, b in
            C.texturas(C.U.unwrap(C.ie1tr().get('inazuma1/data_iz/a_menu/binder_t.arc')))}['ie01_menu_binder_logo01.tga']


def logo2(L, dx=-24, x_min=330):
    """L: textura 512x128 con el logo japonés de IE2 en la misma posición que la de binder_t."""
    eu = logo_eu()
    if L.shape != eu.shape:
        raise ValueError('logo de otro tamaño')
    r, g, a = L[..., 0].astype(int), L[..., 1].astype(int), L[..., 3]
    rojo = (r > 150) & (g < 120) & (a > 0)
    rojo[:, :x_min] = False
    lab, n = ndimage.label(rojo)
    if not n:
        raise ValueError('no se encuentra el 2')
    tam = ndimage.sum(rojo, lab, range(1, n + 1))
    dos = ndimage.binary_fill_holes(ndimage.binary_dilation(lab == int(np.argmax(tam)) + 1, iterations=6)) & (a > 0)
    out = L.copy()
    out[:] = L[L[..., 3] == 0][0]
    e = np.roll(eu, dx, 1)
    m = e[..., 3] > 0
    out[m] = e[m]
    out[dos] = L[dos]
    return out
