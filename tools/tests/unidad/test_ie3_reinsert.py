"""Invariantes offline de la reinserción segura de diálogo IE3."""

from ie123kit.ie3.comun.reinsert import _emitir, parchear_bloque
from ie123kit.ie3.comun.ssd import group_ruby, parse_flat_text
from ie123kit.ie3.comun.text import TextTable


def _record(text, size):
    return _emitir(0, 0, text.encode("cp932"), size)


def test_reinsert_keeps_group_bytes_and_record_offsets():
    """Un diálogo con ruby puede redistribuir bytes, nunca mover el siguiente."""
    original = _record("あ%1F", 20) + _record("a", 16) + _record("次", 20)

    patched, applied, rejected = parchear_bloque(original, {"あ%1F": "Hola"})

    assert (applied, rejected) == (1, 0)
    assert len(patched) == len(original)
    before = parse_flat_text(original, TextTable.identity())
    after = parse_flat_text(patched, TextTable.identity())
    assert [record.offset for record in after] == [record.offset for record in before]
    assert len(after) == len(before)
    groups = group_ruby(after)
    assert groups[0][0].text == "Hola"
    assert after[2].text == "次"


def test_reinsert_leaves_a_too_long_dialogue_untouched():
    original = _record("あ", 12)

    patched, applied, rejected = parchear_bloque(original, {"あ": "x" * 300})

    assert patched == original
    assert (applied, rejected) == (0, 1)


def test_reinsert_accepts_e_grave_and_rejects_unknown_character_without_fallback():
    original = _record("あ", 40)

    patched, applied, rejected = parchear_bloque(original, {"あ": "È terribile"})
    assert (applied, rejected) == (1, 0)
    assert bytes.fromhex("83ae") in patched
    assert b"? terribile" not in patched

    untouched, applied, rejected = parchear_bloque(original, {"あ": "olá".replace("á", "ã")})
    assert untouched == original
    assert (applied, rejected) == (0, 1)
