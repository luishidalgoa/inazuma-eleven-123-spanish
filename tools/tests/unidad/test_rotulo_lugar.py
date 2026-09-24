"""Rótulo de lugar ampliado (ie123kit.nucleo.ejecutable.rotulo_lugar) sobre una CRO sintética."""

from __future__ import annotations

import struct

import pytest

from ie123kit.nucleo.ejecutable import rotulo_lugar as R
from ie123kit.nucleo.errores import ValidacionError

TAM = 0x1000
DIBUJO, REGISTRO, OAM, PIEZAS = 0x400, 0x600, 0x700, 0x900


def _pon(d, a, *palabras):
    for k, w in enumerate(palabras):
        struct.pack_into("<I", d, a + 4 * k, w)


def cro(piezas=((1, 0x180, 0x1EC0), (2, 0x200, 0x1300), (8, 0x300, 0x2940)), r2_pisado=False) -> bytes:
    d = bytearray(TAM)
    struct.pack_into("<II", d, 0xC8, 0x100, 1)                 # un segmento de código que lo cubre todo
    struct.pack_into("<III", d, 0x100, 0, TAM, 0)
    for cab in (0xF8, 0x128, 0x130):
        struct.pack_into("<II", d, cab, 0x180, 0)
    getter = (0xE5901028, 0xE2840008, 0xE12FFF31)                # ldr r1,[r0,#0x28] · add r0,r4,#8 · blx r1
    _pon(d, DIBUJO - 20, *getter, 0xE3500000, 0x0A000000)         # … cmp r0,#0 · beq
    _pon(d, DIBUJO, 0xE2805C15, 0xE3A02D05,                       # add r5,r0,#0x1500 · mov r2,#0x140
         0xE3A020FF, 0xE3A02001 if r2_pisado else 0xE1A00000,    # mov r2,#0xff · (mov r2,#1 | nop)
         0xED831A00, 0xE5832000,                                  # vstr s2,[r3] · str r2,[r3]
         0xE3A02050, 0xE28D301C, 0xE3A01008,                      # mov r2,#0x50 · add r3,sp,#0x1c · mov r1,#8
         0xE3A01D05, 0xEA000000)                                  # mov r1,#0x140 · b
    _pon(d, REGISTRO - 12, *getter, 0xE2804C15)                   # add r4,r0,#0x1500
    _pon(d, REGISTRO + 0x20, 0xE2804C15)                          # otro add #0x1500 sin el getter: no cuenta
    _pon(d, OAM, 0xE2861028, 0xE2840008, 0xE3A000A8, 0xE3A01000, 0xE3A0C010, 0xE0810001, 0xE3510005)
    for k, (pid, tam, off) in enumerate(piezas):
        struct.pack_into("<4I", d, PIEZAS + 16 * k, pid, tam, off, pid)
    struct.pack_into("<4I", d, PIEZAS + 16 * len(piezas), 3, 0xC00, 0, 3)
    return bytes(d)


def test_codificar_inmediato():
    assert R.codificar_inmediato(0x1500) == 0xC15
    assert R.codificar_inmediato(0x3E00) == 0xC3E
    assert R.codificar_inmediato(0x1F0) == 0xE1F
    with pytest.raises(ValidacionError, match="inmediato_no_codificable"):
        R.codificar_inmediato(0x101)


def test_localizar_y_reparto():
    d = cro()
    p = R.localizar(d)
    assert (p.limpieza_add, p.limpieza_tam, p.ancho_hd, p.ancho_dibujo, p.vaciado_tam) == (
        DIBUJO, DIBUJO + 4, DIBUJO + 16, DIBUJO + 24, DIBUJO + 36)
    assert (p.registro_add, p.oam_comprobacion, p.oam_baldosa, p.oam_cuenta) == (REGISTRO, OAM, OAM + 8, OAM + 24)
    assert R.reparto_vram(d) == [(1, 0x1EC0, 0x180), (2, 0x1300, 0x200), (8, 0x2940, 0x300)]


def test_aplicar_16_baldosas():
    salida, inf = R.aplicar(cro())
    u = lambda a: struct.unpack_from("<I", salida, a)[0]
    assert u(DIBUJO) == 0xE2805C3E and u(REGISTRO) == 0xE2804C3E          # + 0x3e00
    assert u(DIBUJO + 4) == 0xE3A02C02 and u(DIBUJO + 36) == 0xE3A01C02    # 0x200 B
    assert u(DIBUJO + 24) == 0xE3A02080                                     # 128 px
    assert u(DIBUJO + 16) == 0xE5832000                                     # str r2,[r3]
    assert (u(OAM), u(OAM + 8), u(OAM + 24)) == (0xE2861040, 0xE3A00E1F, 0xE3510008)
    assert len(inf["parches"]) == 9 and inf["rotulo"]["baldosas"] == 16


def test_rechazos():
    with pytest.raises(ValidacionError, match="rotulo_vram_ocupada"):
        R.parches(cro(), desplazamiento=0x2A00)
    with pytest.raises(ValidacionError, match="rotulo_vram_fuera"):
        R.parches(cro(), desplazamiento=0x3F00)
    with pytest.raises(ValidacionError, match="rotulo_baldosas"):
        R.parches(cro(), baldosas=18)
    with pytest.raises(ValidacionError, match="rotulo_r2_modificado"):
        R.localizar(cro(r2_pisado=True))
