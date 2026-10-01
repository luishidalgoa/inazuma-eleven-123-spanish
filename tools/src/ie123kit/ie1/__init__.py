"""Inazuma Eleven 1; importa solo ie123kit.nucleo."""

from ie123kit.ie1.acciones import JuegoIE1

#: Objetivo que instancia `servicio.api._cargar_juego`.
JUEGO = JuegoIE1

__all__ = ["JUEGO", "JuegoIE1"]
