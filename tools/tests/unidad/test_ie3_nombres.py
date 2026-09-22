from ie123kit.ie3.comun.nombres import (
    HEADER,
    RECORD_SIZE,
    SHORT_OFFSET,
    caracteres_cortos,
    localizar_cortos,
)
from ie123kit.ie3.comun.text import TextTable


def _table(short: bytes, marker: bytes = b"same") -> bytes:
    data = bytearray(HEADER + RECORD_SIZE)
    data[HEADER:HEADER + 6] = marker[:6].ljust(6, b"\0")
    data[HEADER + 0x34:HEADER + 0x34 + len(marker)] = marker
    data[HEADER + SHORT_OFFSET:HEADER + SHORT_OFFSET + len(short)] = short
    data[HEADER + 0x56:HEADER + 0x58] = (0xC62).to_bytes(2, "little")
    return bytes(data)


def test_ie3_short_name_requires_structure_and_preserves_field_size():
    jp = _table("フィディオ".encode("cp932"))
    es = _table(b"Bianchi")
    patched, report = localizar_cortos(jp, es, TextTable.identity())

    assert report["applied"] == 1
    assert report["entries"] == [{"record": 0, "speaker_id": 0xC62, "name": "Bianchi"}]
    assert patched[HEADER + SHORT_OFFSET:HEADER + SHORT_OFFSET + 16] == b"Bianchi\0".ljust(16, b"\0")
    assert len(patched) == len(jp)


def test_ie3_short_name_rejects_unmatched_record():
    jp = _table("フィディオ".encode("cp932"))
    es = _table(b"Bianchi", marker=b"other")
    patched, report = localizar_cortos(jp, es, TextTable.identity())

    assert patched == jp
    assert report["applied"] == 0
    assert report["skipped_structure"] == 1


def test_ie3_short_name_characters_are_individual_and_same_size():
    jp = _table("フィディオ".encode("cp932"))
    es = _table(b"Bianchi")
    patched, report = localizar_cortos(jp, es, TextTable.identity())

    field = patched[HEADER + SHORT_OFFSET:HEADER + SHORT_OFFSET + 16]
    assert caracteres_cortos(jp, es, TextTable.identity()) == set("Bianchi")
    assert report["characters"] == len(set("Bianchi"))
    assert len(field) == 16
    assert field == b"Bianchi\0".ljust(16, b"\0")
