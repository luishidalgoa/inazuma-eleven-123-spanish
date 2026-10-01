"""Búfer del sprintf del cartel de cambio del IE3 (ie123kit.ie3.comun.cartel_cambio) sobre una función sintética."""

from __future__ import annotations

import struct

import pytest

from ie123kit.ie3.comun import cartel_cambio as m

F = 0x1000
NOP = 0xE1A00000


def cro_sintetica(extra: tuple[int, int] | None = None) -> bytes:
    d = bytearray(0x2000)  # tablas de segmentos y de parches vacías
    for i in range(0, m.LARGO, 4):
        struct.pack_into("<I", d, F + i, NOP)
    d[F:F + len(m.FIRMA)] = m.FIRMA
    for rel, antes, _despues, _t in m.PARCHES:
        struct.pack_into("<I", d, F + rel, antes)
    if extra is not None:
        struct.pack_into("<I", d, F + extra[0], extra[1])
    return bytes(d)


def test_parchea_las_seis_palabras_e_idempotente():
    d = cro_sintetica()
    assert m.localizar(d) == F
    salida, informe = m.aplicar_cartel_cambio(d)
    assert not informe["ya_aplicado"]
    assert [p["desensamblado_despues"][0] for p in informe["parches"]] == [
        "sub sp, sp, #0x1b4", "mov r2, #0x80", "add r0, sp, #0x134", "add r0, sp, #0x134",
        "add r0, sp, #0x134", "add sp, sp, #0x1b4"]
    assert m.localizar(salida) == F
    otra, inf2 = m.aplicar_cartel_cambio(salida)
    assert otra == salida and inf2["ya_aplicado"]


def test_acceso_a_la_pila_no_previsto_no_parchea():
    d = cro_sintetica(extra=(0x100, 0xE59D0120))  # ldr r0, [sp, #0x120]: dentro del búfer viejo
    with pytest.raises(ValueError):
        m.aplicar_cartel_cambio(d)


def test_palabra_inesperada_no_parchea():
    d = cro_sintetica(extra=(0x148, 0xE28D0F47))
    with pytest.raises(ValueError):
        m.aplicar_cartel_cambio(d)


def test_longitud_del_texto():
    assert m.bytes_texto(7, 7) == 43        # «　»+NUL sobre el r7 guardado (sp+0x118+40)
    assert m.bytes_texto(14, 14) == 67      # cabe en los 128 B nuevos
    assert m.bytes_texto(4, 4) <= 0x134 - 0x118 + 12  # no llega al r7 guardado
