import hashlib
import struct
from types import SimpleNamespace

import pytest

from ie123kit.ie3.comun import presentacion_nombres as mod
from ie123kit.ie3.comun.presentacion_nombres import (
    auditar_cota,
    localizar_por_identidad,
    medir_nombre,
    recursos_nombres,
)
from ie123kit.ie3.comun.text import TextTable


def record(ident, short, *, stat=20, local=1, metadata=7):
    result = bytearray(0x68)
    result[:6] = b"Longer"
    result[0x1C:0x2C] = short.ljust(16, b"\0")
    result[0x2C:0x30] = b"same"
    result[0x4C] = metadata
    struct.pack_into("<H", result, 0x4E, ident)
    result[0x5E] = stat
    struct.pack_into("<H", result, 0x66, local)
    return bytes(result)


def test_reorders_by_identity_and_preserves_all_non_short_bytes():
    jp = record(2, b"JP2") + record(1, b"JP1")
    es = record(1, b"Bianchi", local=9) + record(2, b"Maserati", stat=80)
    out, report = localizar_por_identidad(jp, es, TextTable.identity())
    assert out[0x1C:0x2C] == b"Maserati\0".ljust(16, b"\0")
    assert out[0x68 + 0x1C:0x68 + 0x2C] == b"Bianchi\0".ljust(16, b"\0")
    assert report["estados"] == {"insertado_nuevo": 2}
    assert report["entries"][0]["official_record"] == 1
    assert report["entries"][0]["diferencia_estadistica_5e"]
    assert all(a == b for i, (a, b) in enumerate(zip(jp, out))
               if not 0x1C <= i % 0x68 < 0x2C)


def test_duplicate_and_zero_ids_are_not_last_row_wins():
    jp = record(4, b"JP") + record(0, b"unused")
    es = record(4, b"One") + record(4, b"Two") + record(0, b"unused")
    out, report = localizar_por_identidad(jp, es, TextTable.identity())
    assert out == jp
    assert report["pendientes_por_causa"] == {"identidad_ambigua": 1, "id_cero_reservado": 1}


def test_rejects_unexplained_metadata_changes():
    jp = record(1, b"JP")
    out, report = localizar_por_identidad(jp, record(1, b"ES", metadata=8), TextTable.identity())
    assert out == jp
    assert report["pendientes_por_causa"] == {"metadata_identidad_diferente": 1}


def test_new_fields_require_terminator_with_no_truncation():
    with pytest.raises(ValueError, match="NUL interno"):
        auditar_cota(record(1, b"x" * 16))
    assert auditar_cota(record(1, b"x" * 15))["max_bytes_sin_nul"] == 15
    with pytest.raises(ValueError, match="tabla plana"):
        auditar_cota(record(1, b"x") + b"\0")


def test_identity_checked_transition_from_inherited_state():
    jp, es = record(1, b"JP"), record(1, b"Bianchi")
    out, report = localizar_por_identidad(jp, es, TextTable.identity(), actual=es)
    assert out == es
    assert report["estados"] == {"heredado_oficial": 1}
    wrong = record(1, b"Wrong")
    out, report = localizar_por_identidad(jp, es, TextTable.identity(), actual=wrong)
    assert out == wrong
    assert report["pendientes_por_causa"] == {"heredado_no_corresponde": 1}
    with pytest.raises(ValueError, match="ajenos"):
        localizar_por_identidad(jp, es, TextTable.identity(), actual=record(1, b"JP", stat=22))


def test_profile_selects_ogre_source_not_spark_inside_same_archive():
    path = "inazuma3_ogre/data_iz/logic/unitbase.dat"
    profile = SimpleNamespace(nombre="ogre", recurso="inazuma3_ogre/data_iz/script")
    payload, report = recursos_nombres(
        profile, {path: record(2, b"JP")},
        {"es/" + path: record(2, b"Correct"),
         "es/inazuma3/data_iz/logic/unitbase.dat": record(2, b"Wrong")},
        TextTable.identity(),
    )
    assert payload[path][0x1C:0x2C].startswith(b"Correct\0")
    assert report["fuente_oficial"] == "es/" + path
    assert not report["presentacion_visual_corregida"]


def test_metric_model_distinguishes_override_from_cwdh():
    font = SimpleNamespace(
        cmap={ord("i"): 0, ord("W"): 1},
        data=struct.pack("<bBBbBB", -4, 2, 2, -1, 8, 8),
        b=SimpleNamespace(width=11),
        cwdh_entry_off=lambda gi: gi * 3,
        read_cell=lambda gi: [[15] * (2 if gi == 0 else 8)],
    )
    result = medir_nombre("iWi", font)
    assert result["avance"] == {"override_superior": 30, "proporcional_hipotetico": 15}
    assert result["glifos_ausentes"] == []
    assert not result["runtime_verified"]


def _font_for_name_simulation():
    chars = "BianchiMaseratDowWlyTomkwx¿Sra.Hob?"
    cmap = {mod._codepoint_destino(ch): i for i, ch in enumerate(sorted(set(chars)))}
    space = len(cmap)
    cmap[0x3000] = space
    return SimpleNamespace(
        cmap=cmap,
        data=struct.pack("<bBB", -3, 4, 4) * space + struct.pack("<bBB", 5, 0, 5),
        b=SimpleNamespace(width=11), t={"cell_h": 1},
        cwdh_entry_off=lambda gi: gi * 3,
        read_cell=lambda gi: [[0] * 4] if gi == space else [[15] * 4],
    )


def test_name_space_uses_runtime_ideographic_slot_without_font_or_text_changes():
    font = _font_for_name_simulation()
    original = bytes(font.data)
    compact = medir_nombre("Mark", font)
    spaced = medir_nombre("Ma rk", font)
    assert spaced["avance"]["proporcional_hipotetico"] == compact["avance"]["proporcional_hipotetico"] + 6
    assert spaced["glifos_ausentes"] == []
    assert spaced["espacios_runtime"] == [{"indice": 2, "codepoint": "U+3000"}]
    assert font.data == original
    assert 32 not in font.cmap


@pytest.mark.parametrize("name", ["Bianchi", "Maserati", "Downtown", "Willy", "iiiiiiiii", "WWWWWWWWW", "Ma rk", "¿Sra. Hob.?"])
def test_name_logical_limits_seven_eight_nine_and_spaces(name):
    font = _font_for_name_simulation()
    report = medir_nombre(name, font)
    assert report["lineas_limite_logico"]["64"] == [name[i:i + 7] for i in range(0, len(name), 7)]
    assert report["lineas_limite_logico"]["134"] == [name[i:i + 15] for i in range(0, len(name), 15)]
    assert not report["glifos_ausentes"]
    assert not report["raster_fuera_glyph_width"]


def test_name_renderer_preserves_font_and_does_not_crop_or_hide_capacity():
    font = _font_for_name_simulation()
    original = bytes(font.data)
    image = mod.render_comparacion(["Bianchi", "Maserati", "Ma rk", "iiiiiiiii", "WWWWWWWWW"], font)
    assert image.width == 780 and image.height > 200
    assert font.data == original
    with pytest.raises(ValueError, match="capacidad real"):
        mod.render_comparacion(["i" * 16], font)


def test_wide_nine_character_name_is_visual_negative_despite_logical_acceptance():
    font = SimpleNamespace(cmap={ord("W"): 0}, data=struct.pack("<bBB", -1, 9, 9),
                           b=SimpleNamespace(width=11), cwdh_entry_off=lambda _: 0,
                           read_cell=lambda _: [[15] * 9])
    report = medir_nombre("WWWWWWWWW", font)
    assert report["lineas_limite_logico"]["134"] == ["WWWWWWWWW"]
    assert report["tinta_ancho"]["proporcional_hipotetico"] == 89
    assert report["tinta_supera_region64"]


def _cro_fixture(monkeypatch):
    data = bytearray(max(mod.ANCLAS_FONT8) + 8)
    data[0x80:0x84] = b"CRO0"
    for off, value in mod.ANCLAS_FONT8.items():
        data[off:off + 4] = bytes.fromhex(value)
    struct.pack_into("<I", data, mod.SALTO_FONT8, mod.ANTES_FONT8)
    monkeypatch.setattr(mod, "CRO_V7_SHA256", hashlib.sha256(data).hexdigest())
    return bytes(data)


def _audit_archive(monkeypatch, name=b"Bianchi", *, argument_type=3, terminated=True):
    font = _font_for_name_simulation()
    files = {"font/FONT8.bcfnt": bytes(font.data)}
    for prefix in ("inazuma3", "inazuma3_ogre"):
        for suffix, stride, field in (("unitbase.dat", 104, 28), ("unitbase_npc.dat", 80, 16)):
            data = bytearray(stride)
            data[field:field + 16] = name.ljust(16, b"\0")[:16]
            files[prefix + "/data_iz/logic/" + suffix] = bytes(data)
        for suffix in ("pkh", "pkb"):
            files[prefix + "/data_iz/script/eve." + suffix] = b"fixture"
    files["inazuma3_ogre/data_iz/logic/ex_binder/unitbase.dat"] = files["inazuma3/data_iz/logic/unitbase.dat"]
    body = b"xxxx" + name + (b"\0" if terminated else b"!")
    row = SimpleNamespace(key=(7, 2), offset=0, size=len(body), raw=name)
    instruction = SimpleNamespace(ident=7, opcode=0x3019, tipos=(argument_type,), slots=(2,))
    monkeypatch.setattr(mod, "leer_paquete", lambda *_: ({1: body}, {}))
    monkeypatch.setattr(mod, "parse_ssd", lambda *_: ({}, [row]))
    monkeypatch.setattr(mod, "instrucciones", lambda _: [instruction])
    return SimpleNamespace(read=files.__getitem__), font, files


def test_reusable_audit_all_sources_no_writes(monkeypatch):
    archive, font, files = _audit_archive(monkeypatch, b"Ma rk")
    original = dict(files)
    report = mod.auditar_presentacion(archive, font)
    assert report["totals"] == {"unitbase_rows": 5, "ssd3019_names": 2}
    assert all(row["spaces"] == 1 for row in report["unitbase"].values())
    assert all(row["all_ink_within64"] for row in report["ssd3019"].values())
    assert report["logical_limit"] == 134
    assert report["physical_width_unchanged"] == 64
    assert not report["native_origin_and_tab_frame_verified"]
    assert not report["runtime_verified"]
    assert files == original


@pytest.mark.parametrize("change,reason", [("font", "FONT8"), ("nul", "NUL16"),
                                          ("shape", "alineada"), ("glyph", "no modelados")])
def test_reusable_audit_rejects_wrong_font_table_and_glyph(monkeypatch, change, reason):
    archive, font, files = _audit_archive(monkeypatch)
    path = "inazuma3/data_iz/logic/unitbase.dat"
    if change == "font":
        files["font/FONT8.bcfnt"] += b"x"
    elif change == "shape":
        files[path] += b"x"
    else:
        data = bytearray(files[path])
        data[28:44] = b"i" * 16 if change == "nul" else b"!".ljust(16, b"\0")
        files[path] = bytes(data)
    with pytest.raises(ValueError, match=reason):
        mod.auditar_presentacion(archive, font)


@pytest.mark.parametrize("argument_type,terminated,reason", [(4, True, "no constante"), (3, False, "sin NUL")])
def test_reusable_audit_rejects_dynamic_or_unterminated_ssd_names(monkeypatch, argument_type, terminated, reason):
    archive, font, _ = _audit_archive(monkeypatch, argument_type=argument_type, terminated=terminated)
    with pytest.raises(ValueError, match=reason):
        mod.auditar_presentacion(archive, font)


def test_one_word_patch_idempotence_hash_and_relocation_guards(monkeypatch):
    data = _cro_fixture(monkeypatch)
    changed, report = mod.parchear_font8_ie3(data)
    assert [i for i, (a, b) in enumerate(zip(data, changed)) if a != b] == [mod.SALTO_FONT8]
    assert report["font12_body_unchanged"]
    again, report = mod.parchear_font8_ie3(changed)
    assert again == changed and report["already_applied"]
    wrong = bytearray(data)
    wrong[300] ^= 1
    with pytest.raises(ValueError, match="referencia funcional v7"):
        mod.parchear_font8_ie3(bytes(wrong))
    monkeypatch.setattr(mod, "direcciones_de_tablas", lambda _data: {mod.SALTO_FONT8})
    with pytest.raises(ValueError, match="relocación"):
        mod.parchear_font8_ie3(data)


@pytest.mark.parametrize("font_type", [0, 1, 2, 3, 4, 255])
def test_arm_branch_changes_only_font8_and_preserves_font12_path(font_type):
    # Decode actual ARM B<cond> words, after cmp r3,#1 at 180914.
    def next_pc(word):
        assert word >> 28 == 0  # EQ
        assert (word >> 24) & 15 == 0xA  # B, not BL; registers/flags untouched
        if font_type != 1:
            return mod.SALTO_FONT8 + 4
        displacement = word & 0xFFFFFF
        if displacement & 0x800000:
            displacement -= 0x1000000
        return mod.SALTO_FONT8 + 8 + displacement * 4

    before, after = next_pc(mod.ANTES_FONT8), next_pc(mod.DESPUES_FONT8)
    if font_type == 1:
        assert (before, after) == (0x180930, 0x180970)
    else:
        assert before == after == 0x18091C
