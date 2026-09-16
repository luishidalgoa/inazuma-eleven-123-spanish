"""Reglas propias del paquete de escena ``mch`` de IE1 (rótulos y diálogo de partido).

``mch.pkh``/``mch.pkb`` comparten formato con ``eve`` (PackNum + SSD), pero su
contenido es el de las escenas de partido: además del diálogo (opcode ``0x301D``,
argumento 1) llevan rótulos y contadores que el motor lee como código. Aquí viven
solo las TABLAS y los PREDICADOS; la entrada/salida está en ``ie1.texto.eventos``.

Rangos protegidos: los ids de ``mch`` observados en la recopilación caen en
``94000000..94999999``. Cualquier id fuera de ese rango se considera protegido y no
se reescribe, para no tocar por descuido una entrada que el motor use como tabla.

Límite de bytes: el de un registro SSD (``nucleo.eventos.instrucciones.LIMITE_TEXTO``),
igual que en ``eve``; ``mch`` no añade ninguna holgura.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from ie123kit.nucleo.eventos.instrucciones import LIMITE_TEXTO

__all__ = [
    "ARGUMENTO_DIALOGO",
    "LIMITE_BYTES",
    "OPCODE_DIALOGO",
    "PACK",
    "RANGOS_PROTEGIDOS",
    "evento_editable",
    "limite_bytes",
    "registros_visibles",
]

PACK = "mch"
OPCODE_DIALOGO = 0x301D
ARGUMENTO_DIALOGO = 1
LIMITE_BYTES = LIMITE_TEXTO

#: Rangos de ids de evento (inclusive) que SÍ se pueden editar en ``mch``.
RANGOS_PROTEGIDOS: tuple[tuple[int, int], ...] = ((94000000, 94999999),)


def evento_editable(eid: int) -> bool:
    """``True`` si el id cae en un rango de escena conocido de ``mch``."""
    return any(inicio <= int(eid) <= fin for inicio, fin in RANGOS_PROTEGIDOS)


def limite_bytes(indice: int | None = None) -> int:
    """Presupuesto de bytes del registro ``indice`` (constante en ``mch``)."""
    del indice
    return LIMITE_BYTES


def registros_visibles(tabla: Mapping[int, tuple[int, list]], registros: Iterable) -> list[int]:
    """Índices de los registros con texto visible en pantalla.

    ``tabla`` es la de ``nucleo.eventos.instrucciones.instrucciones`` (``ident ->
    (opcode, args)``) y ``registros`` la lista de ``ssd.TextRecord`` del evento.
    """
    salida = []
    for i, registro in enumerate(registros):
        entrada = tabla.get(registro.instruction)
        opcode = entrada[0] if isinstance(entrada, tuple) else entrada
        if opcode == OPCODE_DIALOGO and registro.argument == ARGUMENTO_DIALOGO:
            salida.append(i)
    return salida
