"""IE3 La Amenaza del Ogro; importa solo ie123kit.nucleo y ie123kit.ie3.comun."""

from ie123kit.ie3.amenaza_del_ogro.acciones import JuegoAmenazaDelOgro

__all__ = ["JUEGO", "JuegoAmenazaDelOgro"]

#: Clase del objetivo que instancia `servicio.api._cargar_juego`.
JUEGO = JuegoAmenazaDelOgro
