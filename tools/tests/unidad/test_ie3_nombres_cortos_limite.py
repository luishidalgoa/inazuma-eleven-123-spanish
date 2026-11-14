"""Nombres cortos del IE3 a 6 caracteres (datos sintéticos)."""

from ie123kit.ie3.comun.nombres_cortos_limite import TAMANO, acortar, cortos, reescribir


def test_acortar():
    assert acortar(b"Sue") == b"Sue"
    assert acortar(b"Spires") == b"Spires"
    assert acortar(b"Sparrow") == b"Sparr."
    assert acortar(b"Tomlins.") == b"Tomli."
    assert acortar(b"Don Paolo") == b"Don P."
    assert acortar(b"Abc  xyzw") == b"Abc."
    assert acortar(bytes.fromhex("42 83a0 66616c6f")) == bytes.fromhex("42 83a0 66616c6f")  # 6 caracteres, 7 B
    assert acortar(b"Coraz" + bytes.fromhex("83a2") + b"n!") == b"Coraz."
    assert all(len(acortar(n)) <= 6 for n in (b"Downtown", b"Bluebel.", b"A. Woodbridge"))


def test_reescribir_conserva_la_marca_y_el_resto():
    reg = bytearray(TAMANO)
    reg[0x1C:0x1C + 7] = b"Sparrow"
    reg[0x1C + 15] = 0x7F
    reg[0x40] = 0x55
    d = bytes(reg) * 2
    out = reescribir(d, {1: b"Sparr."})
    assert cortos(out) == [b"Sparrow", b"Sparr."]
    assert out[TAMANO + 0x1C + 15] == 0x7F and out[TAMANO + 0x40] == 0x55
    assert out[:TAMANO] == d[:TAMANO]
