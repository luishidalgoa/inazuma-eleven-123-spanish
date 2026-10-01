"""Nombres cortos de jugador del IE3 (unitbase.dat +0x1C) dentro del límite de 6 caracteres del partido.

Con 7 caracteres o más el partido se cuelga (#87, bisección del 2026-09-26) y las placas de alineación sacan
letras fuera; las parejas de letras (bigramas) tampoco valen (docs/FURIGANA_LECCIONES.md). Por decisión del
usuario (2026-09-26) se acortan lo mínimo: las 5 primeras letras y un punto, como los oficiales europeos
(«Tomlins.», «Bluebel.»). Si el recorte deja un espacio o un punto al final, se quita antes de poner el punto.
"""
from __future__ import annotations

from collections.abc import Mapping

__all__ = ["LIMITE", "CAMPO", "TAMANO", "acortar", "caracteres", "cortos", "reescribir"]

LIMITE = 6
TAMANO = 0x68
CAMPO = 0x1C
#: el byte 15 del campo es la marca de lista_registro_latina y no se toca
UTILES = 15


def caracteres(nombre: bytes) -> list[bytes]:
    """Caracteres de `nombre`: latín de 1 byte o Shift-JIS de 2 (portadores de las letras con tilde)."""
    out, i = [], 0
    while i < len(nombre):
        n = 2 if (0x81 <= nombre[i] <= 0x9F or 0xE0 <= nombre[i] <= 0xFC) and i + 1 < len(nombre) else 1
        out.append(nombre[i:i + n])
        i += n
    return out


def acortar(nombre: bytes, limite: int = LIMITE) -> bytes:
    """Si `nombre` pasa de `limite` caracteres, sus `limite - 1` primeros y un punto."""
    cs = caracteres(nombre)
    if len(cs) <= limite:
        return nombre
    base = b"".join(cs[:limite - 1]).rstrip(b" .")
    return base + b"."


def cortos(unitbase: bytes) -> list[bytes]:
    """Nombre corto de cada registro (sin NUL ni marca)."""
    return [unitbase[i + CAMPO:i + CAMPO + UTILES].split(b"\0", 1)[0] for i in range(0, len(unitbase), TAMANO)]


def reescribir(unitbase: bytes, nuevos: Mapping[int, bytes]) -> bytes:
    """Pone el nombre corto de los registros de `nuevos`; solo cambian los 15 bytes útiles del campo."""
    out = bytearray(unitbase)
    for reg, nombre in nuevos.items():
        if len(nombre) > UTILES - 1:
            raise ValueError(f"registro {reg}: nombre de {len(nombre)} B")
        o = reg * TAMANO + CAMPO
        out[o:o + UTILES] = nombre.ljust(UTILES, b"\0")
    return bytes(out)
