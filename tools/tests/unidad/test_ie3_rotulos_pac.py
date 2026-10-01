"""Conversión de rótulos PAC europeos a la forma japonesa y reempaquetado del índice de 16 B (datos sintéticos)."""

from __future__ import annotations

import struct

import pytest

from ie123kit.ie3.comun import rotulos_pac as RP
from ie123kit.nucleo.compresion import lz10


def pac(ancho_datos: int, ancho_decl: int, pal: list[int], pix_idx: list[int]) -> bytes:
    size = ancho_datos * 32 // 2
    pix = bytearray(size)
    for q, v in enumerate(pix_idx):
        pix[q // 2] |= v << (4 * (q % 2))
    ps = 2 * len(pal)
    pal_off = 0x20 + size
    meta = bytearray(16)
    meta[0], meta[2], meta[3] = 1, (ancho_decl // 8).bit_length() - 1, 2
    struct.pack_into("<H", meta, 12, 99)
    cab = struct.pack("<8I", 3, 0x20, size, pal_off, ps, pal_off + ps, 16, pal_off + 0x10)
    return cab + bytes(pix) + struct.pack(f"<{len(pal)}H", *pal) + bytes(meta)


def test_paleta_completa_ancho_y_util():
    w = 128
    idx = [0] * (w * 32)
    for y in range(32):
        for x in range(10, 50):
            idx[y * w + x] = 5
    eu = pac(w, 256, list(range(16)), idx)
    jp = RP.a_forma_japonesa(eu)
    c = RP.cabecera(jp)
    assert c["size"] == w * 16 and jp[c["meta"] + 2] == 4
    assert struct.unpack_from("<H", jp, c["meta"] + 12)[0] == 56      # tinta 50 + 3 -> 56
    assert RP.indices(jp) == idx


def test_paleta_corta_fondo_a_indice_0():
    w = 256
    idx = [3] * (w * 32)                   # fondo opaco = índice 3
    idx[40] = 1
    eu = pac(w, 128, [0x7FFF, 0x1234, 0x0000, 0x03E0, 0x001F, 0x7C00, 0x1111], idx)
    jp = RP.a_forma_japonesa(eu)
    c = RP.cabecera(jp)
    assert c["ps"] == 32 and jp[c["meta"] + 2] == 5
    nuevo = RP.indices(jp)
    assert nuevo[0] == 0 and nuevo[40] == 1
    assert struct.unpack_from("<H", jp, c["pal"] + 2)[0] == 0x1234


def test_ancho_invalido():
    eu = bytearray(pac(128, 128, list(range(16)), [0] * 4096))
    struct.pack_into("<I", eu, 8, 1000)
    with pytest.raises(ValueError):
        RP.a_forma_japonesa(bytes(eu))


def test_reempaquetar_16():
    a, b = b"A" * 40, lz10.compress(b"B" * 64)
    pkb = a + b
    pkh = struct.pack("<4I", 1, 0, len(a), 40) + struct.pack("<4I", 2, 40, len(b), 0x10 | (64 << 8))
    nh, nb = RP.reempaquetar_16(pkh, pkb, {1: b"C" * 100})
    ent = RP.leer_16(nh, nb)
    assert lz10.decompress(ent[0][1]) == b"C" * 100 and ent[0][2] == 0x10 | (100 << 8)
    assert ent[1][1] == b
