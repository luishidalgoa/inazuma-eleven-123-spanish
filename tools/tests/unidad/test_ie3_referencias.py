"""Referencias del consumidor, no redistribución por presupuesto heredado."""

import struct

import pytest

from ie123kit.ie3.comun.paquetes import leer_paquete, reconstruir_paquete
from ie123kit.ie3.comun.referencias import leer_referencias, reconstruir_evento
from ie123kit.nucleo.compresion import lz10
from ie123kit.nucleo.texto.sjis_portador import es_encode


def record(body, owner=(0, 0), padding=0):
    if isinstance(body, str):
        body = body.encode("cp932")
    size = (len(body) + 8) & ~3
    return struct.pack("<HBB", *owner, size) + body + b"\0" + bytes([padding]) * (size - 5 - len(body))


def fixture(groups, kinds=None):
    """Placeholders deliberadamente falsos: el loader usa owner/slot físico."""
    code, table, evet = bytearray(), bytearray(), bytearray()
    for i, group in enumerate(groups):
        types = ([3] * len(group)) if kinds is None else kinds[i]
        words = (len(types) + 7) // 8
        payload = b"".join(record(t, padding=0xAA) for t in group)
        start = len(evet)
        evet.extend(payload)
        code.extend(struct.pack("<HHHBB", i, 8 + 4 * words + 4 * len(types), 0x301D, len(types), 0))
        typewords = sum(t << (4 * j) for j, t in enumerate(types))
        code.extend(typewords.to_bytes(4 * words, "little"))
        code.extend(struct.pack(f"<{len(types)}I", *([0x9999] * len(types))))
        first = True
        for j, t in enumerate(types):
            if t == 3:
                body = f"@{start},{len(payload)}" if first else "unused"
                table.extend(record(body, (i, words + j), padding=0xAB))
                first = False
    count = sum(t == 3 for ts in (kinds or [[3] * len(g) for g in groups]) for t in ts)
    header = struct.pack(
        "<4sIIHHIIII", b"SSD\0", 0x30001, 32 + len(code) + len(table), len(groups), count, len(code), len(table), 0, 0
    )
    return header + code + table, bytes(evet)


def pack(blocks, compressed=False):
    h = bytearray(48)
    h[:16] = b"PackNum 20101110"
    b = bytearray()
    for i, body in enumerate(blocks):
        data = lz10.compress(body) if compressed else body
        h.extend(struct.pack("<III", i, len(b), len(data)))
        b.extend(data)
        b.extend(bytes((-len(b)) % 16))
    h.extend(b"\xff" * 12)
    struct.pack_into("<I", h, 16, len(h))
    struct.pack_into("<HH", h, 20, 1, len(blocks))
    struct.pack_into("<I", h, 24, 16)
    return bytes(h), bytes(b)


def test_noop_is_literal_including_nonzero_padding():
    s, e = fixture([["漢%1F", "かん"], ["次\\n終"]])
    a, b, _ = reconstruir_evento(s, e, {})
    assert (a, b) == (s, e)
    for kind, blocks, compressed in (("eve", [s, s], True), ("evet", [e, e], False)):
        h, p = pack(blocks, compressed)
        assert reconstruir_paquete(h, p, kind, {0: blocks[0]})[:2] == (h, p)


@pytest.mark.parametrize("index", [0, 1, 2])
def test_growth_first_middle_last_preserves_every_other_record(index):
    s, e = fixture([["初%1F", "はつ"], ["中"], ["終"]])
    refs, _, records, _, info = leer_referencias(s, e)
    at = refs[index].inicio
    body = es_encode("¡Texto completo!\\nÈ y ñ", 1000)
    a, b, trace = reconstruir_evento(s, e, {at: body})
    assert a[32 : 32 + info["code_len"]] == s[32 : 32 + info["code_len"]]
    for r, t in zip(records, trace["records"]):
        if r.offset != at:
            assert b[t["new_offset"] : t["new_offset"] + r.size] == e[r.offset : r.offset + r.size]
    new_refs = leer_referencias(a, b)[0]
    delta = len(b) - len(e)
    assert delta > 0
    for j, (old, new) in enumerate(zip(refs, new_refs)):
        assert new.inicio == old.inicio + (delta if j > index else 0)
        assert new.longitud == old.longitud + (delta if j == index else 0)
    h, p = pack([e, e, e])
    nh, np, _ = reconstruir_paquete(h, p, "evet", {1: b})
    decoded, _ = leer_paquete(nh, np, "evet")
    assert decoded == {0: e, 1: b, 2: e}
    assert nh[-12:] == h[-12:] == b"\xff" * 12
    assert struct.unpack_from("<I", nh, 28)[0] == (len(b) + 15) & ~15


def test_physical_slot_includes_multiple_type_words_and_skips_nonstrings():
    s, e = fixture([["uno", "dos", "tres"]], [[3, 4, 5, 1, 2, 6, 3, 1, 3]])
    refs, *_ = leer_referencias(s, e)
    assert len(refs[0].registros) == 3
    assert refs[0].instruccion.slots == (2, 3, 4, 5, 6, 7, 8, 9, 10)
    assert reconstruir_evento(s, e, {0: b"Texto bastante largo"})[1].endswith(record("tres", padding=0xAA))


def test_controls_and_multibyte_roundtrip_not_interpreted_by_relocator():
    s, e = fixture([["%s\\n%d\\f漢%1F", "かん"]], [[3, 5, 5, 3]])
    assert reconstruir_evento(s, e, {})[:2] == (s, e)


def test_unreferenced_records_preserved():
    s, e = fixture([["uno"]])
    orphan = record("孤立", padding=0xAC)
    _, output, _ = reconstruir_evento(s, e + orphan, {0: b"Texto mas largo"})
    assert output.endswith(orphan)


def test_u8_and_group_buffer_limits_are_not_silenced():
    s, e = fixture([["x"]])
    with pytest.raises(ValueError, match="u8"):
        reconstruir_evento(s, e, {0: b"x" * 248})
    s, e = fixture([["a"] * 5])
    # 5x200 =1000 original; grow main to252 =>1044.
    e = b"".join(record(b"a" * 195) for _ in range(5))
    from ie123kit.ie3.comun.referencias import sustituir_tabla

    s = sustituir_tabla(s, {0: b"@0,1000"})
    with pytest.raises(ValueError, match="1024"):
        reconstruir_evento(s, e, {0: b"x" * 247})


def test_invalid_target_and_missing_nul_rejected():
    s, e = fixture([["x"]])
    with pytest.raises(ValueError, match="cabeza"):
        reconstruir_evento(s, e, {1: b"bad"})
    with pytest.raises(ValueError, match="NUL"):
        leer_referencias(s, e[:4] + b"xxxx")


@pytest.mark.parametrize("tail_size", [0, 4, 8, 12])
def test_pack_tail_is_not_always_a_full_sentinel(tail_size):
    e = record("あ")
    h, b = pack([e, e])
    h = bytearray(h[:-12] + b"\xff" * tail_size)
    struct.pack_into("<I", h, 16, len(h))
    nh, nb, _ = reconstruir_paquete(bytes(h), b, "evet", {0: record("longer text")})
    assert nh[72:] == bytes(h)[72:]
    assert struct.unpack_from("<I", nh, 16)[0] == len(h)
    assert leer_paquete(nh, nb, "evet")[0][1] == e


def test_empty_evet_entry_preserved():
    h, b = pack([b"", record("あ")])
    nh, nb, _ = reconstruir_paquete(h, b, "evet", {1: record("longer text")})
    assert leer_paquete(nh, nb, "evet")[0][0] == b""


def test_original_reference_without_nul_requires_a_real_decimal_terminator():
    s, e = fixture([["a"], ["b"]])
    table_start = 32 + struct.unpack_from("<I", s, 16)[0]
    s = bytearray(s)
    s[table_start + 4 : table_start + 12] = b"@00000,8"
    assert reconstruir_evento(bytes(s), e, {})[:2] == (bytes(s), e)
    grown, _, _ = reconstruir_evento(bytes(s), e, {0: b"longer message"})
    assert b"@0,20\0" in grown
    s[table_start + 12] = 0x31
    with pytest.raises(ValueError, match="terminador decimal"):
        leer_referencias(bytes(s), e)


def test_shared_references_updated_and_partial_overlap_rejected():
    from ie123kit.ie3.comun.referencias import sustituir_tabla

    s, e = fixture([["a"], ["b"]])
    s = sustituir_tabla(s, {1: b"@0,8"})
    ns, ne, _ = reconstruir_evento(s, e, {0: b"longer message"})
    refs = leer_referencias(ns, ne)[0]
    assert [(r.inicio, r.longitud) for r in refs] == [(0, 20), (0, 20)]
    s, e = fixture([["a", "b"], ["c", "d"]])
    s = sustituir_tabla(s, {2: b"@8,16"})
    with pytest.raises(ValueError, match="solapados"):
        leer_referencias(s, e)


def test_signed_counts_and_reference_boundaries():
    from ie123kit.ie3.comun.referencias import sustituir_tabla

    s, e = fixture([["a"]])
    with pytest.raises(ValueError, match="límites de registro"):
        leer_referencias(sustituir_tabla(s, {0: b"@1,7"}), e)
    bad = bytearray(s)
    struct.pack_into("<H", bad, 12, 0x8000)
    with pytest.raises(ValueError, match="signed16"):
        leer_referencias(bytes(bad), e)


def test_correspondence_conflict_resolved_only_with_matching_official_identity():
    from ie123kit.ie3.fase2 import resolver

    eligible = [{"es_final": "Uno"}, {"es_final": "Otro"}]
    aligned = [
        {
            "jp_text": "同じ",
            "es_text": "Otro",
            "event_id": "7",
            "es_offset": "0xC",
            "string_id": "m01",
            "status": "structural",
        }
    ]
    assert resolver("同じ", eligible, aligned, {(7, 12): "Otro"})[0] == "Otro"
    assert resolver("同じ", eligible, [], {(7, 12): "Otro"}) == (None, None)
    assert resolver("同じ", eligible, aligned, {(7, 12): "No coincide"}) == (None, None)


def test_content_limits_preserve_frozen_layout_and_do_not_silently_remove_controls():
    from ie123kit.ie3.fase2 import compilar

    assert not compilar("漢%1F", "È ¡sí!", [8, 8])["blockers"]
    assert "layout_paginacion" in compilar("a", "uno\\fdos", [8])["blockers"]
    assert "estructura_controles_argumentos_pendiente" in compilar("%s", "Nombre %s", [8])["blockers"]
    assert "caracter_no_soportado" in compilar("a", "ã", [8])["blockers"]


def test_legacy_real_ruby_can_move_an_internal_record_but_never_next_group():
    from ie123kit.ie3.comun.reinsert import _emitir, parchear_bloque
    from ie123kit.ie3.comun.ssd import parse_flat_text
    from ie123kit.ie3.comun.text import TextTable

    original = (
        _emitir(0, 0, "漢%1F".encode("cp932"), 16)
        + _emitir(0, 0, "かん".encode("cp932"), 24)
        + _emitir(0, 0, "次".encode("cp932"), 12)
    )
    patched, applied, rejected = parchear_bloque(original, {"漢%1F": "Texto bastante largo"})
    assert (applied, rejected) == (1, 0)
    before = parse_flat_text(original, TextTable.identity())
    after = parse_flat_text(patched, TextTable.identity())
    assert after[1].offset != before[1].offset
    assert after[2].offset == before[2].offset
    assert len(patched) == len(original)
