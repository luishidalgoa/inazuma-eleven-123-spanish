"""Escáner estricto de literales Shift-JIS en binarios (code.bin, CRO) para elegir códigos de bigrama.

Portado de ``work/ie1/capas/fuentes/bigramas_ritmo/escaneo_literales.py`` (IE1 v89) sin cambios de
comportamiento (F2.5, #51). Un código candidato se descarta si aparece, alineado desde cualquier inicio
posible, dentro de una cadena C formada solo por ASCII imprimible (más ``\\t``/``\\n``) y dobles bytes
Shift-JIS válidos, aunque sea un kanji suelto sin kana: ese literal lo dibujaría el juego con el glifo
reasignado.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping

__all__ = ["apariciones", "en_cadena", "valido2"]


def valido2(a: int, b: int) -> bool:
    """¿(a, b) es un doble byte Shift-JIS válido?"""
    return (0x81 <= a <= 0x9F or 0xE0 <= a <= 0xFC) and (0x40 <= b <= 0xFC and b != 0x7F)


def en_cadena(buf: bytes, p: int, atras: int = 256, adelante: int = 512) -> bool:
    """¿p (inicio de un código) está en una cadena C?

    Desde el byte siguiente a un NUL (como mucho ``atras`` bytes antes) hasta el NUL siguiente (como
    mucho ``adelante`` bytes después), todo ASCII imprimible/\\t/\\n o doble byte Shift-JIS válido, y p
    alineado con esa lectura.
    """
    z = buf.rfind(b"\0", max(0, p - atras), p)
    if z < 0:
        return False
    i = z + 1
    while i < p:
        b = buf[i]
        if 0x20 <= b <= 0x7E or b in (0x0A, 0x09):
            i += 1
        elif i + 1 < len(buf) and valido2(b, buf[i + 1]):
            i += 2
        else:
            return False
    if i != p:
        return False
    j = p
    while j < len(buf) and j - p < adelante:
        b = buf[j]
        if b == 0:
            return True
        if 0x20 <= b <= 0x7E or b in (0x0A, 0x09):
            j += 1
        elif j + 1 < len(buf) and valido2(b, buf[j + 1]):
            j += 2
        else:
            return False
    return False


def apariciones(fuentes: Mapping[str, bytes], codigos: Iterable[str]) -> dict[str, dict[str, int]]:
    """``{código: {fuente: n}}`` con las apariciones de cada código (hex) dentro de cadenas C."""
    import numpy as np

    lista = list(codigos)
    cand = np.array(sorted(int(c, 16) for c in lista), dtype=np.uint16)
    res: dict[str, dict[str, int]] = {c: {} for c in lista}
    for nombre, buf in fuentes.items():
        a = np.frombuffer(buf, dtype=np.uint8).astype(np.uint16)
        w = (a[:-1] << 8) | a[1:]
        pos = np.nonzero(np.isin(w, cand))[0]
        for p in pos.tolist():
            if en_cadena(buf, p):
                c = f"{int(w[p]):04X}"
                res[c][nombre] = res[c].get(nombre, 0) + 1
    return res
