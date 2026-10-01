"""Mapas del teclado de nombre (``fcode0/1/2``): 6 filas de 26 celdas de 2 B + CRLF (314 B).

Cada carácter visible ocupa dos celdas iguales (4 B). ``AAAA`` cambia de modo, ``DDDD`` borra y
las celdas con espacios ASCII están desactivadas; ``BBBB``/``CCCC`` (fila 1 y 2, columna final)
son los diacríticos japoneses y se desactivan. Modo 0 = mayúsculas, 1 = minúsculas, 2 = símbolos
(en el modo 2 las celdas ya desactivadas se respetan).

Vale para IE1 (``inazuma1/data_iz/fcodeN.txt``) e IE2 (entradas ``FCODEN.TXT`` de los paquetes
``SPF_``): la tabla japonesa es la misma. El transporte es el de ancho completo bloqueado v20.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

__all__ = ["FILAS_LATINAS", "TAMANO", "parchear_fcode"]

#: Tabla latina aprobada en juego (IE1, issue del teclado; la misma que lleva la v18 de IE2).
FILAS_LATINAS: tuple[str, ...] = ("ABCDEFGHIJ", "KLMNÑOPQRS", "TUVWXYZÁÉÍ", "ÓÚü0123456", "789.,!?():",
                                  "+/=@&;[]  ")
TAMANO = 314


def _transporte_v20(ch: str) -> bytes:
    from ie123kit.nucleo.texto.ancho_completo import encode_fullwidth

    return encode_fullwidth(ch)


def parchear_fcode(original: bytes, modo: int, filas: Sequence[str] = FILAS_LATINAS,
                   transportar: Callable[[str], bytes] | None = None) -> bytes:
    """Mapa japonés de 314 B -> mapa con ``filas`` (mismo tamaño, controles AAAA/DDDD intactos)."""
    transportar = transportar or _transporte_v20
    if len(original) != TAMANO or original[-2:] != b"\r\n":
        raise ValueError("unexpected keyboard map")
    out = bytearray(original)
    for y, fila in enumerate(filas):
        if len(fila) != 10:
            raise ValueError(f"fila {y}: {len(fila)} teclas != 10")
        for x, ch in enumerate(fila):
            col = x * 2 + (x >= 5)
            offset = y * 52 + col * 2
            if modo == 2 and original[offset:offset + 4] == b"    ":
                continue
            codificado = transportar(ch.lower() if modo == 1 else ch)
            if len(codificado) != 2:
                raise ValueError(f"{ch!r}: transporte de {len(codificado)} B")
            out[offset:offset + 4] = codificado * 2
    for y, control in ((1, b"BBBB"), (2, b"CCCC")):
        if original[y * 52 + 48:y * 52 + 52] != control:
            raise ValueError("unexpected diacritic control position")
        out[y * 52 + 48:y * 52 + 52] = b"    "
    return bytes(out)
