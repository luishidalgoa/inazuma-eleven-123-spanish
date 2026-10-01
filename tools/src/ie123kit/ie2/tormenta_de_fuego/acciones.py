"""Identidad del objetivo IE2 Tormenta de Fuego.

Sin capacidades: toda acción devuelve NOT_SUPPORTED hasta que exista la
extracción de esta versión (ver `ie123kit.ie2.comun.reglas`).
"""

from __future__ import annotations

from ie123kit.ie2.comun.reglas import JuegoIE2

__all__ = ["JuegoTormentaDeFuego"]


class JuegoTormentaDeFuego(JuegoIE2):
    """IE2 Tormenta de Fuego: identidad del objetivo, sin capacidades declaradas todavía."""

    PAQUETE = "ie123kit.ie2.tormenta_de_fuego"
