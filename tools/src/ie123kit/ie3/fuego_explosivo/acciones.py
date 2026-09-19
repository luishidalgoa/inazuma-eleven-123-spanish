"""Identidad del objetivo IE3 Fuego Explosivo.

Sin capacidades: toda acción devuelve NOT_SUPPORTED hasta que exista la
extracción de esta versión (ver `ie123kit.ie3.comun.reglas`).
"""

from __future__ import annotations

from ie123kit.ie3.comun.reglas import JuegoIE3

__all__ = ["JuegoFuegoExplosivo"]


class JuegoFuegoExplosivo(JuegoIE3):
    """IE3 Fuego Explosivo: identidad del objetivo, sin capacidades declaradas todavía."""

    PAQUETE = "ie123kit.ie3.fuego_explosivo"
