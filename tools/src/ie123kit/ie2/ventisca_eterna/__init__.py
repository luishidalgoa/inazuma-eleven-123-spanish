"""IE2 Ventisca Eterna; importa solo ie123kit.nucleo y ie123kit.ie2.comun."""

from ie123kit.ie2.ventisca_eterna.acciones import JuegoVentiscaEterna

__all__ = ["JUEGO", "JuegoVentiscaEterna"]

#: Clase del objetivo que instancia `servicio.api._cargar_juego`.
JUEGO = JuegoVentiscaEterna
