"""Ampliación del búfer del pintor con furigana (ie123kit.nucleo.ejecutable.bufer_rubi) sobre una función sintética."""

from __future__ import annotations

import struct

import pytest
from capstone import CS_ARCH_ARM, CS_MODE_ARM, Cs

from ie123kit.nucleo.ejecutable.bufer_rubi import FIRMA, aplicar_bufer_rubi, localizar, parches

F = 0x1000
CUERPO = [
    0xEBFFFFFF,  # bl (copia)
    0xE58D0AC4,  # str r0, [sp, #0xac4]      (local: no se toca)
    0xE59D1B18,  # ldr r1, [sp, #0xb18]      (argumento: +0x200)
    0xED8D8A06,  # vstr s16, [sp, #0x18]     (local)
    0xE58D6000,  # str r6, [sp]
    0xE28DDEAD,  # add sp, sp, #0xad0
    0xECBD8B04,  # vpop {d8, d9}
    0xE28DD010,  # add sp, sp, #0x10
    0xE8BD9FF0,  # pop {r4-r12, pc}
]


def cro_con_pintor(extra: int | None = None) -> bytes:
    d = bytearray(0x2000)  # tablas de segmentos y de parches vacías
    d[F:F + len(FIRMA)] = FIRMA
    cuerpo = list(CUERPO)
    if extra is not None:
        cuerpo.insert(1, extra)
    for i, w in enumerate(cuerpo):
        struct.pack_into("<I", d, F + len(FIRMA) + 4 * i, w)
    return bytes(d)


def test_localiza_y_amplia():
    d = cro_con_pintor()
    assert localizar(d) == F
    salida, informe = aplicar_bufer_rubi(d)
    assert not informe["ya_aplicado"] and informe["funcion"] == hex(F)
    md = Cs(CS_ARCH_ARM, CS_MODE_ARM)
    texto = {p.direccion - F: next(md.disasm(p.despues.to_bytes(4, "little"), p.direccion)).op_str
             for p in parches(d, F)}
    assert texto == {
        0x0C: "sp, sp, #0xcd0",
        0x10: "r1, sp, #0xa00",      # base de los argumentos (vldr [r1, #0x31c...])
        0x14: "r3, sp, #0xa00",      # base de los argumentos (ldm r3 tras +0x324)
        0x30: "r6, r6, #0x2d0",      # búfer de texto -> sp+0xad0
        0x48: "r1, [sp, #0xd18]",
        0x54: "sp, sp, #0xcd0",
    }
    otra, inf2 = aplicar_bufer_rubi(salida)
    assert otra == salida and inf2["ya_aplicado"]


def test_acceso_desconocido_no_parchea():
    d = cro_con_pintor(extra=0xE08D1002)  # add r1, sp, r2: acceso a la pila por registro
    with pytest.raises(ValueError):
        parches(d, F)


def test_sin_pintor():
    with pytest.raises(ValueError):
        aplicar_bufer_rubi(bytes(0x2000))
