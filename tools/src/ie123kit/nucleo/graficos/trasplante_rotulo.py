"""Trasplante de un rótulo oficial (tinta de un color) de una textura a otra con otro estilo.

Caso de uso: la pantalla de ajustes del IE2 (``a_menu/system_b.arc``, ``ie02_menu_system_window_b03``) trae los
títulos de sección en japonés (crema con sombra arriba a la izquierda sobre barras marrones) y la misma pantalla
del IE3 europeo los trae en español (blanco sobre verde). Se toma la tinta oficial europea tal cual (sin
repintar letras), se borra la japonesa con el color de la barra y se pega con el color y la sombra del japonés.

Funciones puras sobre imágenes RGBA de PIL; sin rutas ni E/S.
"""
from __future__ import annotations

import numpy as np
from PIL import Image

__all__ = ["borrar_tinta", "caja_tinta", "mascara_tinta", "pegar_mascara"]


def mascara_tinta(img: Image.Image, caja: tuple[int, int, int, int], color) -> np.ndarray:
    """Máscara booleana (recortada a la tinta) de los píxeles de ``color`` (RGB) dentro de ``caja``."""
    x0, y0, x1, y1 = caja
    a = np.array(img.convert("RGBA"))[y0:y1, x0:x1]
    m = np.all(a[..., :3] == tuple(color)[:3], -1) & (a[..., 3] > 0)
    if not m.any():
        raise ValueError(f"sin tinta {tuple(color)} en {caja}")
    ys, xs = np.nonzero(m)
    return m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def caja_tinta(img: Image.Image, caja, colores) -> tuple[int, int, int, int] | None:
    """Caja (x0, y0, x1, y1) que ocupan los píxeles de ``colores`` dentro de ``caja``."""
    x0, y0, x1, y1 = caja
    a = np.array(img.convert("RGBA"))[y0:y1, x0:x1]
    m = np.zeros(a.shape[:2], bool)
    for c in colores:
        m |= np.all(a[..., :3] == tuple(c)[:3], -1)
    if not m.any():
        return None
    ys, xs = np.nonzero(m)
    return x0 + xs.min(), y0 + ys.min(), x0 + xs.max() + 1, y0 + ys.max() + 1


def borrar_tinta(img: Image.Image, caja, colores, fondo) -> Image.Image:
    """Copia de ``img`` con los píxeles de ``colores`` de ``caja`` pintados con ``fondo`` (RGBA)."""
    a = np.array(img.convert("RGBA"))
    x0, y0, x1, y1 = caja
    zona = a[y0:y1, x0:x1]
    m = np.zeros(zona.shape[:2], bool)
    for c in colores:
        m |= np.all(zona[..., :3] == tuple(c)[:3], -1)
    zona[m] = tuple(fondo)
    return Image.fromarray(a, "RGBA")


def pegar_mascara(img: Image.Image, mascara: np.ndarray, centro_x: float, y: int, color, sombra=None,
                  desp_sombra=(-1, -1), limites=None) -> tuple[Image.Image, tuple[int, int, int, int]]:
    """Pega ``mascara`` centrada en ``centro_x`` con su fila superior en ``y``: primero la sombra desplazada
    ``desp_sombra`` y encima la tinta. ``limites`` (x0, y0, x1, y1): ValueError si algo se sale.
    Devuelve (imagen, caja ocupada con la sombra)."""
    a = np.array(img.convert("RGBA"))
    h, w = mascara.shape
    x = round(centro_x - w / 2)
    capas = ([(desp_sombra, sombra)] if sombra is not None else []) + [((0, 0), color)]
    xs0 = min(x + d[0] for d, _ in capas)
    ys0 = min(y + d[1] for d, _ in capas)
    xs1 = max(x + d[0] for d, _ in capas) + w
    ys1 = max(y + d[1] for d, _ in capas) + h
    lx0, ly0, lx1, ly1 = limites if limites else (0, 0, a.shape[1], a.shape[0])
    if xs0 < lx0 or ys0 < ly0 or xs1 > lx1 or ys1 > ly1:
        raise ValueError(f"el rótulo ({xs0},{ys0})-({xs1},{ys1}) se sale de {limites}")
    for (dx, dy), c in capas:
        zona = a[y + dy:y + dy + h, x + dx:x + dx + w]
        zona[mascara] = tuple(c)
    return Image.fromarray(a, "RGBA"), (xs0, ys0, xs1, ys1)
