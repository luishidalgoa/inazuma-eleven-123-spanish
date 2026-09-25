"""Vía de ancho real por llamada (motor 2 IE3) y retarget de importaciones, sobre CRO sintéticas."""

from __future__ import annotations

import struct

import pytest

from ie123kit.ie3.comun import ancho_real as AR
from ie123kit.nucleo.ejecutable.cro import Cro
from ie123kit.nucleo.errores import ValidacionError


def test_rama_codifica_b_y_beq():
    assert AR.rama(0x19FF0, 0x7AC78) == 0xEA018320
    assert AR.rama(0x7AC80, 0x1A064, cond=0) >> 24 == 0x0A
    with pytest.raises(ValueError):
        AR.rama(0, 2)


def _cro_motor(tam=0x7B000) -> bytearray:
    d = bytearray(tam)
    struct.pack_into("<I", d, 0xC8, 0x7AF00)          # tabla de segmentos
    struct.pack_into("<I", d, 0xCC, 1)
    struct.pack_into("<III", d, 0x7AF00, 0, tam, 0)
    struct.pack_into("<I", d, AR.FONT8_POR_DEFECTO, AR.LDR_IP_SP60)
    return d


def test_cueva_font8_idempotente_y_saltos():
    d = _cro_motor()
    parches = AR.cueva_font8(0x7AC78)
    uno, inf = AR.aplicar_idempotente(bytes(d), parches)
    assert not inf["ya_aplicado"]
    dos, inf2 = AR.aplicar_idempotente(uno, parches)
    assert inf2["ya_aplicado"] and dos == uno
    w = [struct.unpack_from("<I", uno, 0x7AC78 + 4 * i)[0] for i in range(5)]
    assert w[0] == 0xE59DC0A4 and w[1] == 0xE37C0003 and w[3] == AR.LDR_IP_SP60
    # beq a SIN_POR_DEFECTO y b de vuelta a FONT8_SIGUE
    assert ((w[2] & 0xFFFFFF) << 2) + 0x7AC80 + 8 - (1 << 26) == AR.SIN_POR_DEFECTO
    assert ((w[4] & 0xFFFFFF) << 2) + 0x7AC88 + 8 - (1 << 26) == AR.FONT8_SIGUE


def test_cueva_exige_hueco_a_cero():
    d = _cro_motor()
    d[0x7AC78] = 1
    with pytest.raises(ValidacionError):
        AR.aplicar_idempotente(bytes(d), AR.cueva_font8(0x7AC78))


def test_llamadas_linea():
    p = AR.llamadas_linea([(0x10, 0xE3A02F6E, "mov"), (0x20, 0x1A7, "pool")])
    assert p[0].despues == AR.MVN_R2_2 and p[1].despues == 0xFFFFFFFD


def _cro_import() -> bytearray:
    d = bytearray(0x400)
    struct.pack_into("<II", d, 0xC8, 0x200, 1)
    struct.pack_into("<III", d, 0x200, 0x300, 0x100, 0)
    struct.pack_into("<II", d, 0x100, 0x260, 1)            # 1 importación con nombre
    struct.pack_into("<II", d, 0x260, 0x280, 0x2A0)          # nombre, parches
    d[0x280:0x284] = b"g_X\0"
    struct.pack_into("<IBBBBI", d, 0x2A0, (0x10 << 4), 2, 0, 0, 0, 0x32F8)
    struct.pack_into("<IBBBBI", d, 0x2AC, (0x20 << 4), 2, 1, 0, 0, 0x40)
    return d


def test_retarget_import():
    c = Cro(_cro_import())
    assert [(t, a) for t, a, _ in c.import_patches("g_X")] == [(0x310, 0x32F8), (0x320, 0x40)]
    assert c.retarget_import("g_X", 0x310, 0x3308, esperado=0x32F8) == 0x32F8
    assert c.retarget_import("g_X", 0x310, 0x3308, esperado=0x32F8) == 0x3308   # idempotente
    assert c.import_patches("g_X")[1][1] == 0x40
    with pytest.raises(ValidacionError):
        c.retarget_import("g_X", 0x320, 0x1, esperado=0x2)
    with pytest.raises(ValidacionError):
        c.retarget_import("g_X", 0x330, 0x1)
