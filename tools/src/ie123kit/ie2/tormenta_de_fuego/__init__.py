"""IE2 Tormenta de Fuego; importa solo ie123kit.nucleo y ie123kit.ie2.comun."""

from ie123kit.ie2.tormenta_de_fuego.acciones import JuegoTormentaDeFuego

__all__ = ["JUEGO", "JuegoTormentaDeFuego"]

#: Clase del objetivo que instancia `servicio.api._cargar_juego`.
JUEGO = JuegoTormentaDeFuego
