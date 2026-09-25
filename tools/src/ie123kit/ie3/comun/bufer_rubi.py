"""IE3 · búfer de texto del pintor con furigana (motor 1 + rubí) de ina_main3ogre.cro: 136 B -> 512 B.

El pintor 0x181370 (28 llamadas: rótulos, mensajes y pistas que pasan por el motor 1 con furigana) copia el texto
con la rutina 0x23fd0 a un búfer de su pila en ``sp+0xa38`` **sin comprobar el tamaño**. Detrás del búfer:
``[sp+0xac0]`` y ``[sp+0xac4]`` (variables que se escriben después de copiar: un texto de más de 136 B sale
corrompido), ``d8``/``d9`` en ``sp+0xad0`` y los registros guardados desde ``sp+0xae0`` (r7 en ``sp+0xafc``).
Con la copia de 1 byte (capa copia_1byte, v16) los textos en español ocupan más y uno de 198 B pisó el r7
guardado con «　» + NUL (0x00004081): el llamador acaba llamando a ``BuildTextCommand`` con ``this`` nulo
(cuelgue al terminar el primer tiempo, «Undefined Instruction» en PC 0).

Ampliación sin código nuevo (como bufer_pagina): el marco crece ``AMPLIACION`` bytes por encima de las variables
locales (``sub/add sp`` y todo acceso a ``sp+k`` con ``k >= 0xad0``, también los que usan la base ``sp+0x800``) y
el búfer pasa a esa zona nueva (``sp+0xad0``, 512 B), lejos de las variables y de los registros guardados.
Cada palabra se comprueba antes de escribirla; las direcciones son las de la 1.0 (para la 1.4 se relocaliza
con :mod:`ie123kit.nucleo.ejecutable.relocalizar`).
"""
from __future__ import annotations

from ie123kit.nucleo.ejecutable.parches_cro import ParchePalabra, aplicar

__all__ = ["AMPLIACION", "BUFER_NUEVO", "PALABRAS", "aplicar_bufer_rubi"]

AMPLIACION = 0x200
BUFER_NUEVO = 0xAD0

#: (dirección, palabra de la 1.0, palabra nueva, instrucción nueva)
PALABRAS = [
    (0x18137C, 0xE24DDEAD, 0xE24DDECD, "sub sp, sp, #0xcd0"),
    (0x181380, 0xE28D1B02, 0xE28D1C0A, "add r1, sp, #0xa00   ; vldr [r1, #0x31c/0x320/0x32c] = argumentos"),
    (0x181384, 0xE28D3B02, 0xE28D3C0A, "add r3, sp, #0xa00   ; ldm [r3+0x324] = argumentos"),
    (0x1813A0, 0xE2866F8E, 0xE2866FB4, "add r6, r6, #0x2d0   ; búfer en sp+0xad0 (512 B)"),
    (0x1813D4, 0xE59D1B18, 0xE59D1D18, "ldr r1, [sp, #0xd18]"),
    (0x1813E4, 0xE59D1B18, 0xE59D1D18, "ldr r1, [sp, #0xd18]"),
    (0x1813FC, 0xE59D1B18, 0xE59D1D18, "ldr r1, [sp, #0xd18]"),
    (0x18142C, 0xE59D1B34, 0xE59D1D34, "ldr r1, [sp, #0xd34]"),
    (0x181448, 0xE59D2B30, 0xE59D2D30, "ldr r2, [sp, #0xd30]"),
    (0x181480, 0xE59D3AE8, 0xE59D3CE8, "ldr r3, [sp, #0xce8]"),
    (0x181550, 0xE59D3AE8, 0xE59D3CE8, "ldr r3, [sp, #0xce8]"),
    (0x1815A8, 0xE59D1B18, 0xE59D1D18, "ldr r1, [sp, #0xd18]"),
    (0x1815BC, 0xE28DDEAD, 0xE28DDECD, "add sp, sp, #0xcd0"),
]


def aplicar_bufer_rubi(cro: bytes) -> tuple[bytes, dict]:
    """Aplica la ampliación (idempotente). Devuelve ``(cro, informe)``; ValidacionError si algo no cuadra."""
    pendientes = []
    for direccion, antes, despues, texto in PALABRAS:
        actual = int.from_bytes(cro[direccion:direccion + 4], "little")
        if actual == despues:
            continue
        pendientes.append(ParchePalabra(direccion, antes, despues, texto))
    if not pendientes:
        return bytes(cro), {"ya_aplicado": True, "parches": []}
    if len(pendientes) != len(PALABRAS):
        raise ValueError("ampliación a medias: el CRO tiene parte de las palabras ya cambiadas")
    salida, informe = aplicar(cro, pendientes)
    informe["ya_aplicado"] = False
    return salida, informe
