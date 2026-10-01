"""IE3 · interlineado del blog (pantalla inferior) sin la fila de furigana, en ina_main3ogre.cro.

Los pintores de la entrada (0x194d4c) y del comentario (0x194908) llaman a 0x17fc4c, que pasa al gestor de texto
(0x181254) un espaciado de línea = argumento [sp+0x18] + 8; el motor 2 avanza cada renglón ese espaciado más la
altura de la letra. Los 8 px son la fila de furigana, que el texto español no usa. Japonés: entrada 1 (+8 = 9),
comentario 3 (+8 = 11), título 0 (+8). Aquí el argumento pasa a −7 (espaciado 1 px) en la entrada y el comentario
y a −8 (espaciado 0) en el título (0x194b00), cuya caja de 3 baldosas (24 px) solo admite 2 renglones de 12 px sin
espaciado (petición del usuario, 2026-09-24); 0x17fc4c no se toca (la usan 53 llamadas más).

Entrada: el bloque 0x194d80-0x194dc4 se reescribe en su sitio con los mismos argumentos salvo [sp+0x18] (18
palabras; la carga de pool de r2 se desplaza y apunta al mismo literal 0x194dfc). Comentario: 0x19494c-0x194960.
Sin relocaciones en esas palabras.
"""
from __future__ import annotations

from ie123kit.nucleo.ejecutable.parches_cro import ParchePalabra

ESPACIADO = -7            # argumento [sp+0x18]: espaciado de línea = ESPACIADO + 8 px
ESPACIADO_TITULO = -8

#: (dirección, palabra japonesa, palabra nueva, instrucción nueva)
ENTRADA = [
    (0x194D80, 0xE28D5018, 0xE3A00001, "mov r0, #1"),
    (0x194D84, 0xE3A03000, 0xE58D000C, "str r0, [sp, #0xc]"),
    (0x194D88, 0xE3A00001, 0xE58D0010, "str r0, [sp, #0x10]"),
    (0x194D8C, 0xE3A0C003, 0xE58D0014, "str r0, [sp, #0x14]"),
    (0x194D90, 0xE8851009, 0xE3E00006, "mvn r0, #6"),
    (0x194D94, 0xE58D3024, 0xE3A03000, "mov r3, #0"),
    (0x194D98, 0xE1D430BA, 0xE3A0C003, "mov ip, #3"),
    (0x194D9C, 0xE58D000C, 0xE3A0E000, "mov lr, #0"),
    (0x194DA0, 0xE58D0010, 0xE28D5018, "add r5, sp, #0x18"),
    (0x194DA4, 0xE58D0014, 0xE8855009, "stm r5, {r0, r3, ip, lr}"),
    (0x194DA8, 0xE1A03183, 0xE1D430B8, "ldrh r3, [r4, #8]"),
    (0x194DAC, 0xE58D3008, 0xE1D4C0BA, "ldrh ip, [r4, #0xa]"),
    (0x194DB0, 0xE1D400B8, 0xE1A03183, "lsl r3, r3, #3"),
    (0x194DB4, 0xE282304A, 0xE1A0C18C, "lsl ip, ip, #3"),
    (0x194DB8, 0xE58D1000, 0xE88D100A, "stm sp, {r1, r3, ip}"),
    (0x194DBC, 0xE59F2038, 0xE282304A, "add r3, r2, #0x4a"),
    (0x194DC0, 0xE1A00180, 0xE59F2034, "ldr r2, [pc, #0x34]  ; mismo literal 0x194dfc"),
    (0x194DC4, 0xE58D0004, 0xE320F000, "nop"),
]
COMENTARIO = [
    (0x19494C, 0xE3A03003, 0xE3E03006, "mvn r3, #6"),
    (0x194950, 0xE3A05002, 0xE3A05002, "mov r5, #2"),
    (0x194954, 0xE88E0028, 0xE3A0C003, "mov ip, #3"),
    (0x194958, 0xE28D5020, 0xE88E1028, "stm lr, {r3, r5, ip}"),
    (0x19495C, 0xE3A0C000, 0xE3A0C000, "mov ip, #0"),
    (0x194960, 0xE8851008, 0xE58DC024, "str ip, [sp, #0x24]"),
]

TITULO = [   # 0x194b34-0x194b64: [sp+0x18] = −8; [0x14] 0, [0x1c] 0, [0x20] 1, [0x24] 1, [0xc] 3, [0x10] 3 como antes
    (0x194B34, 0xE3A01000, 0xE3E01007, "mvn r1, #7"),
    (0x194B38, 0xE28D501C, 0xE3A03000, "mov r3, #0"),
    (0x194B3C, 0xE3A03001, 0xE3A0C001, "mov ip, #1"),
    (0x194B40, 0xE58D1018, 0xE3A0E001, "mov lr, #1"),
    (0x194B44, 0xE885000A, 0xE28D5018, "add r5, sp, #0x18"),
    (0x194B48, 0xE58D3024, 0xE885500A, "stm r5, {r1, r3, ip, lr}"),
    (0x194B4C, 0xE1D4C0BA, 0xE58D3014, "str r3, [sp, #0x14]"),
    (0x194B50, 0xE3A03003, 0xE3A03003, "mov r3, #3"),
    (0x194B54, 0xE58D300C, 0xE58D300C, "str r3, [sp, #0xc]"),
    (0x194B58, 0xE58D1014, 0xE1D4C0BA, "ldrh ip, [r4, #0xa]"),
]


def parches() -> list[ParchePalabra]:
    return [ParchePalabra(a, antes, despues, texto) for a, antes, despues, texto in ENTRADA + COMENTARIO + TITULO
            if antes != despues]
