"""Ampliación del búfer del pintor con furigana del IE3 (ie123kit.ie3.comun.bufer_rubi). CRO sintética mínima."""

from __future__ import annotations

import struct

import pytest
from capstone import CS_ARCH_ARM, CS_MODE_ARM, Cs

from ie123kit.ie3.comun.bufer_rubi import PALABRAS, aplicar_bufer_rubi


def cro_con_pintor() -> bytes:
    d = bytearray(0x182000)  # tablas de segmentos y de parches vacías (offset 0, 0 entradas)
    for direccion, antes, _despues, _t in PALABRAS:
        struct.pack_into("<I", d, direccion, antes)
    return bytes(d)


def test_amplia_marco_y_bufer():
    salida, informe = aplicar_bufer_rubi(cro_con_pintor())
    assert not informe["ya_aplicado"] and len(informe["parches"]) == len(PALABRAS)
    md = Cs(CS_ARCH_ARM, CS_MODE_ARM)
    texto = {a: next(md.disasm(salida[a:a + 4], a)) for a, *_ in PALABRAS}
    assert texto[0x18137C].op_str == "sp, sp, #0xcd0"
    assert texto[0x1815BC].op_str == "sp, sp, #0xcd0"
    assert texto[0x1813D4].op_str == "r1, [sp, #0xd18]"
    # el búfer queda en sp+0x800+0x2d0 = sp+0xad0, la zona nueva de 0x200 B
    assert (0x800 + int(struct.unpack_from("<I", salida, 0x1813A0)[0] & 0xFF) * 4) == 0xAD0
    # idempotente
    otra, inf2 = aplicar_bufer_rubi(salida)
    assert otra == salida and inf2["ya_aplicado"]


def test_estado_inesperado_falla():
    d = bytearray(cro_con_pintor())
    struct.pack_into("<I", d, PALABRAS[0][0], PALABRAS[0][2])  # solo una palabra ya cambiada
    with pytest.raises(ValueError):
        aplicar_bufer_rubi(bytes(d))
