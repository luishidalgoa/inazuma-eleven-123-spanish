import struct

import pytest

from ie123kit.ie3.comun.tablas_ui import TECNICAS, construir_rotulos, construir_tabla_str, leer_ranura
from ie123kit.ie3.comun.text import TextTable
from ie123kit.nucleo.texto.sjis_portador import es_encode


def fixture_tables(target="Tiro de fuego", description="Lanza un balón.\nCon fuerza."):
    jp, es = bytearray(512 * 36), bytearray(512 * 36)
    jp[36] = es[36] = 1
    struct.pack_into("<HH", jp, 36 + 24, 1, 2)
    struct.pack_into("<HH", es, 36 + 24, 1, 2)
    pool_j = bytes(32) + "シュート".encode("cp932").ljust(32, b"\0") + "ボールをける。\nはやい。".encode("cp932").ljust(64, b"\0")
    # Fuente europea sintética con tabla de acento oficial.
    table = TextTable({0xFF71: ord("ó"), 0xFF72: ord("ä")})
    encoded_desc = table.encode(description)
    pool_e = bytes(32) + table.encode(target).ljust(32, b"\0") + encoded_desc.ljust((len(encoded_desc) + 32) // 32 * 32, b"\0")
    return bytes(jp), bytes(es), pool_j, pool_e, table


def test_emits_fields_keeps_table_and_offsets():
    args = fixture_tables()
    out, report = construir_tabla_str(*args, TECNICAS)
    assert out[32:64].split(b"\0")[0] == b"Tiro de fuego"
    assert out[64:].split(b"\0")[0] == es_encode("Lanza un balón.\nCon fuerza.", 1000)
    assert len(out) == len(args[2])
    assert report["by_field"] == {"nombre": 1, "descripcion": 1}
    assert report["nontext_and_references_unchanged"]


def test_metadata_change_does_not_translate():
    args = list(fixture_tables())
    es = bytearray(args[1])
    es[40] ^= 1
    args[1] = bytes(es)
    out, report = construir_tabla_str(*args, TECNICAS)
    assert out == args[2]
    assert report["pending_by_reason"] == {"identity": 2}


def test_overflow_leaves_complete_original():
    args = fixture_tables(description="A" * 70)
    out, report = construir_tabla_str(*args, TECNICAS)
    assert out[64:] == args[2][64:]
    assert report["pending_by_reason"] == {"capacity": 1}


def test_unsupported_encoding_no_question_mark():
    args = fixture_tables(target="März")
    out, report = construir_tabla_str(*args, TECNICAS)
    assert out[32:64] == args[2][32:64]
    assert report["pending_by_reason"] == {"encoding": 1}


def test_dynamic_control_not_borrowed_from_dialogue():
    args = fixture_tables(description="Da %s puntos.")
    out, report = construir_tabla_str(*args, TECNICAS)
    assert out[64:] == args[2][64:]
    assert report["pending_by_reason"] == {"control_not_audited": 1}


def test_unverified_alias_prevents_shared_write():
    args = list(fixture_tables())
    jp = bytearray(args[0])
    struct.pack_into("<H", jp, 72 + 24, 1)
    args[0] = bytes(jp)
    out, report = construir_tabla_str(*args, TECNICAS)
    assert out[32:64] == args[2][32:64]
    assert report["pending_by_reason"]["alias_conflict_or_unverified_owner"] == 1


@pytest.mark.parametrize("data,pointer", [(bytes(32), 1), (b"a" * 32, 0), (b"a\0b" + bytes(29), 0)])
def test_slot_rejects_bounds_nul_padding(data, pointer):
    with pytest.raises(ValueError):
        leer_ranura(data, pointer)


def test_european_character_reference_scale_is_256_not_japanese_32():
    data = bytes(256) + b"Descripcion correcta\0" + bytes(235)
    assert leer_ranura(data, 1, 256) == (b"Descripcion correcta", 256, 256)
    assert leer_ranura(data, 1, 32)[0] == b""


def test_wrong_table_geometry_fails():
    args = list(fixture_tables())
    args[0] = args[0][:-1]
    with pytest.raises(ValueError, match="geometría"):
        construir_tabla_str(*args, TECNICAS)


def _label(ident, text, size):
    return bytes([ident]) + text.encode("cp932").ljust(size - 1, b"\0")


def test_route_titles_align_by_id_not_offset_and_keep_sentinel():
    jp = _label(3, "日本", 33) + _label(7, "文字", 33) + bytes([255]) + bytes(32)
    es = _label(7, "Segundo", 64) + _label(3, "Primero", 64) + bytes([255]) + bytes(63)
    out, report = construir_rotulos(jp, es, TextTable.identity(), "BattleRouteTitle")
    assert out[1:33].split(b"\0")[0] == b"Primero"
    assert out[34:66].split(b"\0")[0] == b"Segundo"
    assert out[66:] == jp[66:]
    assert report["applied_fields"] == 2


def test_route_long_title_intact_no_abbreviation():
    jp = _label(3, "日本", 33) + bytes([255]) + bytes(32)
    es = _label(3, "A" * 32, 64) + bytes([255]) + bytes(63)
    out, report = construir_rotulos(jp, es, TextTable.identity(), "BattleRouteTitle")
    assert out == jp
    assert report["pending_by_reason"] == {"capacity": 1}


def test_route_duplicate_id_rejected():
    jp = _label(3, "日本", 33) * 2 + bytes([255]) + bytes(32)
    es = _label(3, "Uno", 64) + bytes([255]) + bytes(63)
    with pytest.raises(ValueError, match="duplicado"):
        construir_rotulos(jp, es, TextTable.identity(), "BattleRouteTitle")


def test_teamtitle_preserves_all_six_stat_bytes_and_rejects_change():
    jp = b"".join("日本".encode("cp932").ljust(26, b"\0") + bytes([i + 1]) + bytes(5) for i in range(20))
    es = b"".join(f"Equipo{i}".encode().ljust(26, b"\0") + bytes([i + 1]) + bytes(5) for i in range(20))
    out, report = construir_rotulos(jp, es, TextTable.identity(), "teamtitle")
    assert report["applied_fields"] == 20
    assert all(out[o+26:o+32] == jp[o+26:o+32] for o in range(0, 640, 32))
    changed_es = bytearray(es)
    changed_es[26] = 90
    out, report = construir_rotulos(jp, bytes(changed_es), TextTable.identity(), "teamtitle")
    assert out[:32] == jp[:32]
    assert report["pending_by_reason"] == {"metadata_identity": 1}


def test_conditions_missing_sentinel_rejected():
    jp = _label(3, "日本", 81)
    with pytest.raises(ValueError, match="centinela"):
        construir_rotulos(jp, _label(3, "Uno", 128), TextTable.identity(), "ClearCondition")
