"""IE3 Rayo Celeste; importa solo ie123kit.nucleo y ie123kit.ie3.comun."""

from ie123kit.ie3.rayo_celeste.acciones import JuegoRayoCeleste

__all__ = ["JUEGO", "JuegoRayoCeleste"]

#: Clase del objetivo que instancia `servicio.api._cargar_juego`.
JUEGO = JuegoRayoCeleste
