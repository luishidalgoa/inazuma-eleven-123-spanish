import struct

import pytest

from ie123kit.ie3.comun import ui_literales as ui
from ie123kit.ie3.comun.text import TextTable


@pytest.fixture
def destino():
    data = bytearray(0x200000)
    data[0x80:0x84] = b"CRO0"
    for offset, payload in ui.ANCLAS_JP.items():
        data[offset:offset + len(bytes.fromhex(payload))] = bytes.fromhex(payload)
    for lit in ui.LITERALES:
        payload = b"".join(text.encode("shift_jis") + b"\0" for text in lit.japones)
        data[lit.offset:lit.offset + lit.capacidad] = payload.ljust(lit.capacidad, b"\0")
    return bytes(data)


@pytest.fixture
def fuente():
    return {435: ("Menú",), 436: ("Jugadores", "Inventario", "Estrategias", "Datos",
                                "Recursos", "Guardar"), 93: ("Maestro",),
            94: ("Niv. equipo",), 96: ("Título",), 58: ("Pasión",),
            59: ("Amistad",), 60: ("Jugadores",)}


def test_exact_fit_idempotent_and_no_changes_outside_literals(destino, fuente):
    result, report = ui._aplicar(destino, fuente)
    changed = {i for i, (a, b) in enumerate(zip(destino, result, strict=True)) if a != b}
    allowed = {i for lit in ui.LITERALES for i in range(lit.offset, lit.offset + lit.capacidad)}
    assert changed <= allowed
    assert report["labels"] == 12
    assert report["modified_blocks"] == 7
    assert result[0x165E8C:0x165EC4].endswith(b"Guardar\0")
    assert result[0x165EC4:0x165EC8] == bytes.fromhex("ff7f0000")
    repeated, second = ui._aplicar(result, fuente)
    assert repeated == result
    assert second["modified_blocks"] == 0
    assert report["pending"][0]["source_id"] == 60
    assert result[0x1F9E70:0x1F9E84] == destino[0x1F9E70:0x1F9E84]


def test_composes_unrelated_existing_cro_change(destino, fuente):
    changed = bytearray(destino)
    changed[0x14000:0x14004] = b"NAME"
    result, _ = ui._aplicar(bytes(changed), fuente)
    assert result[0x14000:0x14004] == b"NAME"


@pytest.mark.parametrize("position", [0x165E80, 0x165EC3, 0x5EEF7])
def test_unexpected_literal_or_padding_is_rejected(destino, fuente, position):
    data = bytearray(destino)
    data[position] ^= 1
    with pytest.raises(ValueError, match="literal JP/padding"):
        ui._aplicar(bytes(data), fuente)


def test_consumer_anchor_is_mandatory(destino, fuente):
    data = bytearray(destino)
    data[0x1755E8] ^= 1
    with pytest.raises(ValueError, match="ancla"):
        ui._aplicar(bytes(data), fuente)


def test_relocation_overlap_is_rejected(destino, fuente, monkeypatch):
    monkeypatch.setattr(ui, "direcciones_de_tablas", lambda _: {0x165E80 - 1})
    with pytest.raises(ValueError, match="relocación"):
        ui._aplicar(destino, fuente)


def test_overflow_never_truncates(destino, fuente):
    fuente[436] = ("Jugadores", "Inventario", "Estrategias", "Datos", "Recursos", "Guardar!")
    with pytest.raises(ValueError, match="completo no cabe"):
        ui._aplicar(destino, fuente)


@pytest.mark.parametrize("value", [("Menú\0X",), (), ("",)])
def test_malformed_source_field(destino, fuente, value):
    fuente[435] = value
    with pytest.raises(ValueError, match="cadenas inesperado"):
        ui._aplicar(destino, fuente)


def test_wrong_official_source_fails_before_patch(destino):
    with pytest.raises(ValueError, match="fuente oficial"):
        ui.parchear_literales_ie3(destino, b"", b"", b"", b"")


def test_id_lookup_reads_pointed_nul_list():
    code = bytearray(0x80000)
    struct.pack_into("<I", code, 0x7AFE0, 0x100000 + 0x100)
    struct.pack_into("<I", code, 0x100 + 4 * 436, 0x100000 + 0x1000)
    code[0x1000:0x1008] = b"uno\0dos\0"
    assert ui._leer_id(bytes(code), TextTable.identity(), 436, 2) == ("uno", "dos")
    with pytest.raises(ValueError, match="ID fuera"):
        ui._leer_id(bytes(code), TextTable.identity(), 864)
