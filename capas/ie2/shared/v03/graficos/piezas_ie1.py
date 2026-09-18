"""Piezas gráficas de la traducción de IE1 (v89) para reutilizar en IE2: iconos que sustituyeron a kanji."""
from functools import lru_cache

import numpy as np

import comun as C


@lru_cache(None)
def texturas(ruta):
    a = {n: np.array(C.decodificar(b)) for n, _, _, b in C.texturas(C.U.unwrap(C.jp().get(ruta)))}
    b = {n: np.array(C.decodificar(x)) for n, _, _, x in C.texturas(C.U.unwrap(C.ie1tr().get(ruta)))}
    return a, b


def celda(ruta, tex, caja, solo_cambio=False):
    """Celda traducida (RGBA) recortada a su tinta; con solo_cambio, solo los píxeles que difieren del JP."""
    a, b = texturas(ruta)
    x0, y0, x1, y1 = caja
    ja, tb = a[tex][y0:y1, x0:x1], b[tex][y0:y1, x0:x1].copy()
    if solo_cambio:
        d = np.any(ja != tb, -1)
        tb[~d] = 0
    m = tb[..., 3] > 0
    r, c = np.where(m.any(1))[0], np.where(m.any(0))[0]
    return tb[r[0]:r[-1] + 1, c[0]:c[-1] + 1]


def pegar(arr, pieza, caja, dx=0, dy=0):
    x0, y0, x1, y1 = caja
    h, w = pieza.shape[:2]
    if w > x1 - x0 or h > y1 - y0:
        raise ValueError(f'pieza {w}x{h} no cabe en {caja}')
    x = x0 + (x1 - x0 - w) // 2 + dx
    y = y0 + (y1 - y0 - h) // 2 + dy
    z = arr[y:y + h, x:x + w]
    m = pieza[..., 3] > 0
    z[m] = pieza[m]
    return arr


def rayo(ruta, tex, caja):
    """Solo los trazos blancos y rojos del icono (sin el fondo del botón)."""
    p = celda(ruta, tex, caja)
    r, g, b, a = [p[..., i].astype(int) for i in range(4)]
    blanco = (r > 190) & (g > 190) & (b > 190)
    rojo = (r > 170) & (g < 90) & (b < 90)
    gris = (abs(r - g) < 20) & (abs(g - b) < 20) & (r > 150)
    q = p.copy()
    q[~(blanco | rojo | gris)] = 0
    m = q[..., 3] > 0
    rr, cc = np.where(m.any(1))[0], np.where(m.any(0))[0]
    return q[rr[0]:rr[-1] + 1, cc[0]:cc[-1] + 1]


def borrar_kanji_boton(arr, caja, margen=7):
    """Rellena el interior del botón redondo con el color dominante de cada fila (quita el kanji)."""
    from collections import Counter
    x0, y0, x1, y1 = caja
    for y in range(y0 + margen, y1 - margen):
        fila = arr[y, x0 + margen:x1 - margen]
        c = Counter(map(tuple, fila[fila[:, 3] > 0])).most_common()
        fondo = [k for k, _ in c if not (k[0] > 170 and k[1] < 90) and not (min(k[:3]) > 190)]
        if fondo:
            m = np.array([(t[0] > 170 and t[1] < 90) or min(t[:3]) > 190 for t in map(tuple, fila)])
            fila[m & (fila[:, 3] > 0)] = fondo[0]
    return arr


def gris(f):
    def g():
        p = f().copy()
        m = p[..., 3] > 0
        lum = (p[..., :3].astype(int) @ np.array([30, 59, 11]) // 100).clip(0, 255)
        v = (lum * 0.7 + 40).clip(0, 255).astype(np.uint8)
        p[m, 0] = p[m, 1] = p[m, 2] = v[m]
        return p
    return g
