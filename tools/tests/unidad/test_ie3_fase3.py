import struct
from types import SimpleNamespace

import pytest

from ie123kit.ie3.comun.cobertura import sha
from ie123kit.ie3.comun.controles import compilar_contexto, cota_pool
from ie123kit.ie3.comun.paquetes import leer_paquete
from ie123kit.ie3.comun.referencias import leer_referencias, reconstruir_evento
from ie123kit.ie3.fase2 import compilar
from ie123kit.ie3.fase3 import emitir_perfil, fusionar_textos_ssd
from tests.unidad.test_ie3_referencias import fixture, pack


class Archive:
    def __init__(self, ssd, evet):
        h, b = pack([ssd], True)
        eh, eb = pack([evet])
        self.entries = {"script/eve.pkh": h, "script/eve.pkb": b,
                        "script/evet.pkh": eh, "script/evet.pkb": eb}

    def read(self, path):
        return self.entries[path]


def rows_for(ssd, evet):
    refs, _, records, _, _ = leer_referencias(ssd, evet)
    rows = []
    for ref in refs:
        head = records[ref.registros[0]]
        sizes = [records[i].size for i in ref.registros]
        rows.append({"event": 0, "instruction": ref.instruccion.ident, "key": str(head.offset),
                     "offset": head.offset, "head_sha256": sha(head.raw),
                     "span_sha256": sha(evet[ref.inicio:ref.inicio + ref.longitud]),
                     "source": {"test": True}, "spanish": "¡Oficial completo!",
                     **compilar(head.text, "¡Oficial completo!", sizes)})
    return rows


def test_general_emission_classifies_transition_and_preserves_secondaries():
    s, e = fixture([["初%1F", "はつ"], ["中"], ["終"]])
    refs = leer_referencias(s, e)[0]
    inherited_s, inherited_e, _ = reconstruir_evento(s, e, {refs[1].inicio: b"Wrong legacy"})
    rows = rows_for(s, e)
    rows[2]["blockers"] = ["pending"]
    payloads, report = emitir_perfil(SimpleNamespace(recurso="script"), Archive(s, e),
                                     Archive(inherited_s, inherited_e), rows, {})
    assert report["summary"]["new_official_inserted"] == 1
    assert report["summary"]["inherited_translation_corrected"] == 1
    assert report["summary"]["pending_japanese_intact"] == 1
    assert all(x["secondary_literal"] and x["bytecode_unchanged"] for x in report["events"])
    out = leer_paquete(payloads["script/evet.pkh"], payloads["script/evet.pkb"], "evet")[0][0]
    assert b"Wrong legacy" not in out


def test_original_hash_guard_not_disabled_by_legacy_translation():
    s, e = fixture([["初"]])
    rows = rows_for(s, e)
    rows[0]["head_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="hash JP"):
        emitir_perfil(SimpleNamespace(recurso="script"), Archive(s, e), Archive(s, e), rows, {})


def test_merge_refuses_different_bytecode():
    s, _e = fixture([["初"]])
    changed = bytearray(s)
    changed[40] ^= 1
    with pytest.raises(ValueError, match="bytecode"):
        fusionar_textos_ssd(s, bytes(changed), s)


def test_decimal_bound_counts_full_signed_int32_and_keeps_control():
    s, e = fixture([["%dポイント"]], [[3, 5]])
    ref, _, records, _, _ = leer_referencias(s, e)
    result = compilar_contexto("%dポイント", "Te costará %d puntos.\\n¿Te parece bien?",
                              [records[0].size], ref[0], s, records)
    assert not result["blockers"]
    assert result["control_evidence"]["max_substitution_bytes"] == 22
    assert "%d" in result["formatted"]
    assert "W" not in result["formatted"]


def test_ruby_before_substitution_cannot_drop_argument():
    s, e = fixture([["%1F漢%d", "かん"]], [[3, 3, 5]])
    ref, _, records, _, _ = leer_referencias(s, e)
    result = compilar_contexto("%1F漢%d", "%d", [r.size for r in records], ref[0], s, records)
    assert "estructura_controles_argumentos_pendiente" in result["blockers"]


def test_pending_inherited_is_not_silently_erased():
    s, e = fixture([["初"]])
    ls, le, _ = reconstruir_evento(s, e, {0: b"Inherited"})
    rows = rows_for(s, e)
    rows[0]["blockers"] = ["not_supported"]
    _, report = emitir_perfil(SimpleNamespace(recurso="script"), Archive(s, e), Archive(ls, le), rows, {})
    assert report["summary"]["pending_inherited_preserved"] == 1


def fixture_producer(opcode=0x4099):
    s, e = fixture([["%s%1F", "はつ"]], [[3, 4, 3]])
    code_end = 32 + struct.unpack_from("<I", s, 16)[0]
    expr = struct.pack("<HHHBBII", 0x9999, 16, opcode, 1, 0, 5, 1)
    data = bytearray(s[:code_end] + expr + s[code_end:])
    struct.pack_into("<I", data, 8, len(data))
    struct.pack_into("<H", data, 12, 2)
    struct.pack_into("<I", data, 16, code_end - 32 + len(expr))
    return bytes(data), e


def test_item_substitution_uses_all_pool_entries_and_preserves_argument():
    s, e = fixture_producer()
    refs, _, records, _, _ = leer_referencias(s, e)
    bound = cota_pool([{"text": "Agua mineral", "bytes": 12}, {"text": "特殊", "bytes": 4}])
    result = compilar_contexto("%s%1F", "Has obtenido: %s.", [r.size for r in records], refs[0], s, records,
                              {"item": bound})
    assert not result["blockers"]
    assert result["formatted"] == "Has obtenido: %s."
    assert result["control_evidence"]["bound"]["entries"] == 2
    assert result["control_evidence"]["max_substitution_bytes"] == 12


def test_unknown_string_producer_does_not_borrow_item_bound():
    s, e = fixture_producer(0x4002)
    refs, _, records, _, _ = leer_referencias(s, e)
    result = compilar_contexto("%s%1F", "Has obtenido: %s.", [r.size for r in records], refs[0], s, records,
                              {"item": cota_pool([{"text": "X", "bytes": 1}])})
    assert "estructura_controles_argumentos_pendiente" in result["blockers"]


def test_string_pool_rejects_overflow_not_typical_length():
    with pytest.raises(ValueError, match="32 bytes"):
        cota_pool([{"text": "X", "bytes": 1}, {"text": "X" * 32, "bytes": 32}])


def test_string_pool_bounds_encoder_expansion_not_unicode_length():
    bound = cota_pool([{"text": "…", "bytes": 3}])
    assert bound["max_chars"] == 3
    assert bound["max_ink"] >= 6
