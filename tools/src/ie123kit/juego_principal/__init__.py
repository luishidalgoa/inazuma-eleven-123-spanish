"""Juego principal de la recopilación; importa solo ie123kit.nucleo."""

from ie123kit.juego_principal.acciones import JuegoPrincipal

#: Clase que `servicio.api._cargar_juego` instancia para este objetivo.
JUEGO = JuegoPrincipal

__all__ = ["JUEGO", "JuegoPrincipal"]
