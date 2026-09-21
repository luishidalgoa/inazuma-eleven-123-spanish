import pytest

from ie123kit.ie3.comun.items import (
    NAME_SIZE,
    RECORD_COUNT,
    RECORD_SIZE,
    construir_items,
    desofuscar_record,
    ofuscar_record,
)
from ie123kit.ie3.comun.text import TextTable


def record(name, tail=b"\0" * 16):
    return ofuscar_record(name.encode("cp932") + b"\0" * (NAME_SIZE - len(name.encode("cp932"))) + tail)


def table(first, second, tail_first=b"\x01" + b"\0" * 13 + b"\x02\0", tail_second=b"\x03" + b"\0" * 13 + b"\x04\0"):
    rows = [record(first, tail_first), record(second, tail_second)]
    rows.extend(record("") for _ in range(RECORD_COUNT - len(rows)))
    return b"".join(rows)


def test_obfuscation_roundtrip_and_only_compatible_nonempty_names_change():
    jp = table("mizu", "same")
    # Mismo icono/tipo/efecto, pero identificadores locales distintos.
    es = table("Agua", "otro", b"\x01" + b"\0" * 13 + b"\x63\0", b"x" + b"\0" * 15)
    payload, report = construir_items(jp, es, TextTable.identity())
    assert desofuscar_record(payload[:RECORD_SIZE])[:NAME_SIZE].split(b"\0", 1)[0] == b"Agua"
    assert payload[RECORD_SIZE : 2 * RECORD_SIZE] == jp[RECORD_SIZE : 2 * RECORD_SIZE]
    assert report["applied"] == [{"record": 0, "source_record": 0, "name": "Agua"}]
    assert report["skipped"]["identity"] >= 1
    assert len(report["pool"]) == RECORD_COUNT
    assert report["pool"][0]["text"] == "Agua"
    assert report["pool_max_bytes"] <= NAME_SIZE - 1
    assert len(report["pool_sha256"]) == len(report["payload_sha256"]) == 64
    assert report["proof_nontext"]["roundtrip_exact"] is True
    assert report["proof_nontext"]["jp_tail_preserved_records"] == RECORD_COUNT
    assert report["proof_nontext"]["unpatched_obfuscated_literal"] is True


def test_rejects_bad_table_or_an_unterminated_pool_name():
    with pytest.raises(ValueError, match="1024"):
        construir_items(b"", b"", TextTable.identity())
    bad = bytearray(table("uno", "dos"))
    plain = bytearray(desofuscar_record(bad[:RECORD_SIZE]))
    plain[:NAME_SIZE] = b"x" * NAME_SIZE
    bad[:RECORD_SIZE] = ofuscar_record(bytes(plain))
    with pytest.raises(ValueError, match="terminador"):
        construir_items(bytes(bad), table("uno", "dos"), TextTable.identity())
