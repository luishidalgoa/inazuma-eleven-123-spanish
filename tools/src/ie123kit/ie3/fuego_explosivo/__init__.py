"""IE3 Fuego Explosivo; importa solo ie123kit.nucleo y ie123kit.ie3.comun."""

from ie123kit.ie3.fuego_explosivo.acciones import JuegoFuegoExplosivo

__all__ = ["JUEGO", "JuegoFuegoExplosivo"]

#: Clase del objetivo que instancia `servicio.api._cargar_juego`.
JUEGO = JuegoFuegoExplosivo
