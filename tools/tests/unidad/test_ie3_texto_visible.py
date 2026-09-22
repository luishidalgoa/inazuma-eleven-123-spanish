import struct
from types import SimpleNamespace

from ie123kit.ie3.comun.ssd import parse_ssd
from ie123kit.ie3.comun.text import TextTable
from ie123kit.ie3.comun.texto_visible import ROLES_CONFIRMADOS, _alinear_visibles_estructural, reemplazar_ssd_visible
from ie123kit.nucleo.texto.sjis_portador import es_encode


def _ssd():
    code = struct.pack("<HHHBB", 7, 12, 0x201D, 1, 0) + struct.pack("<I", 0)
    old = "目的".encode("cp932") + b"\0\xAA\xAA\xAA"
    other = b"keep\0\xBB\xCC\xDD"
    strings = struct.pack("<HBB", 7, 0, 12) + old
    strings += struct.pack("<HBB", 9, 0, 12) + other
    return b"SSD\0" + struct.pack("<I", 0x30001) + struct.pack("<I", 0x20 + len(code) + len(strings)) + struct.pack("<HHIIII", 2, 0, len(code), len(strings), 0, 0) + code + strings


def test_visible_ssd_changes_only_selected_text_and_keeps_code():
    source = _ssd()
    result, report = reemplazar_ssd_visible(source, {(7, 0): "ok"})
    before, rows_before = parse_ssd(source, TextTable.identity())
    after, rows_after = parse_ssd(result, TextTable.identity())

    assert len(report) == 1
    assert len(result) == len(source)
    assert before["code_len"] == after["code_len"]
    assert result[0x20:0x20 + before["code_len"]] == source[0x20:0x20 + before["code_len"]]
    assert rows_after[0].raw == es_encode("ok", 247)
    assert rows_after[1].raw == rows_before[1].raw


def test_visible_ssd_rejects_unknown_or_oversized_text():
    source = _ssd()
    try:
        reemplazar_ssd_visible(source, {(7, 0): "😀"})
    except ValueError:
        pass
    else:
        raise AssertionError("no debe sustituir un carácter sin codificación aprobada")

    try:
        reemplazar_ssd_visible(source, {(7, 0): "a" * 248})
    except ValueError as exc:
        assert "capacidad_consumidor" in str(exc)
    else:
        raise AssertionError("no debe truncar un registro visible")


def test_visible_ssd_keeps_an_identical_official_literal_byte_exact():
    source = _ssd()
    result, report = reemplazar_ssd_visible(source, {(7, 0): "目的"})
    assert result == source
    assert report == []


def test_visible_role_whitelist_keeps_the_confirmed_slots_closed():
    assert ROLES_CONFIRMADOS[(0x201C, 3)] == (0x201D, 3)
    assert (0x201C, 2) not in ROLES_CONFIRMADOS


def test_visible_alignment_rejects_an_evil_intercalation_even_with_same_ordinal_role():
    def ins(ident, opcode=0x7000, tipos=(1,), valores=(9,)):
        return SimpleNamespace(ident=ident, opcode=opcode, tipos=tipos, valores=valores)

    def row(ident, text):
        return SimpleNamespace(instruction=ident, argument=3, opcode=0x201D, key=(ident, 3), text=text, size=8)

    jp_code = [ins(10), ins(11), ins(12)]
    # El campo ES parece equivalente por rol/ordinal, pero se insertó entre
    # anclas con ID distinto: ya no puede copiarse.
    es_code = [ins(10), ins(99), ins(12)]
    mapping, transitions, skipped = _alinear_visibles_estructural([row(11, "JP")], [row(99, "ES")], jp_code, es_code)
    assert mapping == {}
    assert transitions == []
    assert skipped[0]["reason"] == "instruccion_o_slot_visible_no_univoco"


def test_visible_alignment_accepts_same_instruction_with_literal_bracketing_anchors():
    def ins(ident, opcode=0x7000, tipos=(1,), valores=(9,)):
        return SimpleNamespace(ident=ident, opcode=opcode, tipos=tipos, valores=valores)

    def row(ident, text):
        return SimpleNamespace(instruction=ident, argument=3, opcode=0x201D, key=(ident, 3), text=text, size=8)

    mapping, transitions, skipped = _alinear_visibles_estructural(
        [row(11, "JP")], [row(11, "ES")], [ins(10), ins(11, 0x201D, (3,), (1,)), ins(12)],
        [ins(10), ins(11, 0x201D, (3,), (99,)), ins(12)],
    )
    assert mapping == {(11, 3): "ES"}
    assert transitions[0]["anchors"] == {"before": 10, "after": 12}
    assert skipped == []
