"""IE3 · pestañas latinas de la lista «Por nombre» (Registro y Álbum) sobre la geometría japonesa.

El código (capa lista_registro_latina en ina_main3ogre.cro) mantiene las 10 pestañas japonesas de 20 px
(あかさたなはまやらわ) y les da los grupos A-C D-F G-I J-L M-O P-R S T-V W-Y Z. La textura de pestañas
(``*_menu_binder_parts_b01``, 256×64: normales en y 0-31, atenuadas en y 32-63) debe tener esas 10 casillas de
20 px: la europea (8 pestañas de 25 px) no coincide con las posiciones del código y el resalte de la pestaña
elegida cae sobre otra («G[JKL]KL»). Se parte de la japonesa, se limpia el interior de cada pestaña y se escribe
el rótulo con las letras 5×7 de la textura europea.
"""
from __future__ import annotations

import numpy as np
from PIL import Image

ROTULOS = ["A-C", "D-F", "G-I", "J-L", "M-O", "P-R", "S", "T-V", "W-Y", "Z"]
EU_PESTANAS = ["ABC", "DEF", "GHI", "JKL", "MNO", "PQRS", "TUV", "WXYZ"]   # parts_b01 europeo (Ogro), 25 px
FRANJAS = (0, 32)                  # pestañas normales y atenuadas
Y_TXT = (18, 27)                   # filas del interior que se limpian
Y_GLIFO = 20                       # fila superior de las letras europeas (5×7)
PASO_JP, PASO_EU = 20, 25


def fondo_filas(zona: np.ndarray) -> np.ndarray:
    """Fondo de cada fila = su color más claro (el interior es liso por filas y la tinta, más oscura)."""
    brillo = zona[..., :3].sum(axis=2)
    return zona[np.arange(zona.shape[0]), brillo.argmax(axis=1)][:, None, :].copy()


def glifos_eu(eu: np.ndarray, franja: int) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """Letras de las pestañas europeas (interior x 2..22 de cada pestaña de 25 px): píxeles y máscara."""
    out = {}
    for e, rotulo in enumerate(EU_PESTANAS):
        x0 = PASO_EU * e + 2
        zona = eu[franja + Y_GLIFO:franja + Y_GLIFO + 7, x0:x0 + 21]
        tinta = np.abs(zona[..., :3] - fondo_filas(zona)[..., :3]).sum(axis=2) > 60
        cols = np.nonzero(tinta.any(axis=0))[0]
        grupos, actual = [], [cols[0]]
        for c in cols[1:]:
            if c == actual[-1] + 1:
                actual.append(c)
            else:
                grupos.append(actual)
                actual = [c]
        grupos.append(actual)
        if len(grupos) != len(rotulo):
            raise ValueError(f"pestaña europea {rotulo}: {len(grupos)} glifos")
        for letra, g in zip(rotulo, grupos):
            out[letra] = zona[:, g[0]:g[-1] + 1].copy(), tinta[:, g[0]:g[-1] + 1].copy()
    return out


def pestanas(jp_img: Image.Image, eu_img: Image.Image) -> Image.Image:
    """Textura de pestañas japonesa con los rótulos latinos centrados en los 16 px interiores de cada una."""
    a = np.array(jp_img.convert("RGBA")).astype(int)
    eu = np.array(eu_img.convert("RGBA")).astype(int)
    for franja in FRANJAS:
        gl = glifos_eu(eu, franja)
        p0, m0 = gl["A"]
        tinta_color = p0[m0][0]
        for t, rotulo in enumerate(ROTULOS):
            x0 = PASO_JP * t + 2
            zona = a[franja + Y_TXT[0]:franja + Y_TXT[1] + 1, x0:x0 + 16]
            zona[:] = fondo_filas(zona)
            piezas = []
            for ch in rotulo:
                if ch == "-":
                    m = np.zeros((7, 3), bool)
                    m[3, :] = True
                    p = np.zeros((7, 3, 4), int)
                    p[m] = tinta_color
                    piezas.append((p, m))
                else:
                    piezas.append(gl[ch])
            ancho = sum(p.shape[1] for p, _ in piezas) + len(piezas) - 1
            if ancho > 16:
                raise ValueError(f"rótulo {rotulo}: {ancho} px")
            x = x0 + (16 - ancho) // 2
            for p, m in piezas:
                sub = a[franja + Y_GLIFO:franja + Y_GLIFO + 7, x:x + p.shape[1]]
                sub[m] = p[m]
                x += p.shape[1] + 1
    return Image.fromarray(a.astype(np.uint8))
