"""Transporte latino de ancho completo: re-export PEREZOSO de ``tools/dialogue_typography.py``.

``tools/dialogue_typography.py`` es un fichero bloqueado v20: nunca se copia ni se
reformatea. ``encode_fullwidth``, ``ACCENTS`` y ``TOKEN`` se sirven por atributo (son
los mismos objetos) y el módulo congelado no se carga hasta el primer acceso.

:func:`decode_fullwidth` es el inverso de ``encode_fullwidth``. Dominio donde
``decode_fullwidth(encode_fullwidth(x)) == x``: textos que no contienen ya caracteres
de ancho completo (U+3000, U+FF01..U+FF5E) ni los caracteres portadores griegos de
``ACCENTS`` (y que ``shift_jis`` pueda codificar). ``ACCENTS`` es inyectivo.
"""
from __future__ import annotations

from functools import lru_cache

__all__ = ["NOMBRES", "decode_fullwidth"]

NOMBRES = ("encode_fullwidth", "ACCENTS", "TOKEN")


@lru_cache(maxsize=1)
def _modulo():
    from ie123kit.nucleo.config.congelados import cargar
    return cargar("dialogue_typography")


def __getattr__(nombre: str):
    if nombre in NOMBRES:
        return getattr(_modulo(), nombre)
    raise AttributeError(f"module {__name__!r} has no attribute {nombre!r}")


def decode_fullwidth(datos: bytes) -> str:
    """Inverso de ``encode_fullwidth``: SJIS estricto -> texto con acentos y ASCII."""
    inverso = {portador: ch for ch, portador in _modulo().ACCENTS.items()}
    salida = []
    for ch in datos.decode("shift_jis"):
        cp = ord(ch)
        if cp == 0x3000:
            salida.append(" ")
        elif 0xFF01 <= cp <= 0xFF5E:
            salida.append(chr(cp - 0xFEE0))
        else:
            salida.append(inverso.get(ch, ch))
    return "".join(salida)
