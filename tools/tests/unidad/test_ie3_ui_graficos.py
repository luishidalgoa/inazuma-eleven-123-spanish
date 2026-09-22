import struct

import pytest

from ie123kit.ie3.comun.ui_graficos import (
    comprobar_fuentes_compartidas,
    motivo_ayuda_pendiente,
    trasplantar_atlas,
)
from ie123kit.nucleo.contenedores.arcv import entries


def _ctpk(seed=0, fmt=4):
    raw = bytearray(128 + 128)
    raw[:4] = b"CTPK"
    struct.pack_into("<HHI", raw, 4, 1, 1, 128)
    struct.pack_into("<IIIIHH", raw, 32, 64, 128, 0, fmt, 8, 8)
    raw[64:70] = b"x.tga\0"
    raw[128:] = bytes((i + seed) % 256 for i in range(128))
    return bytes(raw)


def _qna():
    raw = bytearray(224)
    raw[:8] = b" QNA 051"
    struct.pack_into("<III", raw, 8, 1, 0, 1)
    struct.pack_into("<III", raw, 36, 64, 0, 96)
    raw[64:70] = b"x.tga\0"
    struct.pack_into("<4f", raw, 96, 0, 0, 8, 8)
    struct.pack_into("<I", raw, 184, 0)
    return bytes(raw)


def _arc(tex=None, qna=None):
    parts = [tex or _ctpk(), qna or _qna(), b"opaque unchanged"]
    raw = bytearray(48)
    raw[:4] = b"ARCV"
    struct.pack_into("<I", raw, 4, 3)
    for i, p in enumerate(parts):
        struct.pack_into("<III", raw, 12 + i * 12, len(raw), len(p), i + 10)
        raw.extend(p)
    struct.pack_into("<I", raw, 8, len(raw))
    return bytes(raw)


def test_pixel_transfer_exact_and_metadata_untouched():
    jp, es = _arc(), _arc(_ctpk(12))
    out, report = trasplantar_atlas(jp, es, {"x.tga"})
    assert out == es
    assert entries(out) == entries(jp)
    assert report["applied"][0]["rgba_exact"]
    assert report["applied"][0]["alpha_exact"]
    assert report["applied"][0]["color_error_max"] == 0
    assert not report["runtime_verified"]
    again, rpt = trasplantar_atlas(out, es, {"x.tga"})
    assert again == out and not rpt["applied"]


def test_layout_different_rejected():
    qna = bytearray(_qna())
    struct.pack_into("<f", qna, 96 + 32, 1)
    with pytest.raises(ValueError, match="layout/no-texto"):
        trasplantar_atlas(_arc(), _arc(_ctpk(1), bytes(qna)), {"x.tga"})


def test_format_change_is_pending_not_lossy_recompression():
    out, report = trasplantar_atlas(_arc(), _arc(_ctpk(1, 2)), {"x.tga"})
    assert out == _arc()
    assert report["pending"][0]["reason"] == "formato_dimensiones_no_identicos"


def test_crc_identity_and_unknown_texture_fail_closed():
    es = bytearray(_arc())
    struct.pack_into("<I", es, 20, 123)
    with pytest.raises(ValueError, match="identidades CRC"):
        trasplantar_atlas(_arc(), bytes(es), {"x.tga"})
    with pytest.raises(ValueError, match="ausente"):
        trasplantar_atlas(_arc(), _arc(), {"missing"})


def test_qna_bounds_checked():
    qna = bytearray(_qna())
    struct.pack_into("<f", qna, 96 + 8, 20)
    original = _arc(qna=bytes(qna))
    out, report = trasplantar_atlas(original, _arc(_ctpk(1), bytes(qna)), {"x.tga"})
    assert out == original
    assert report["pending"][0]["reason"] == "UV_original_fuera_atlas_no_modelado"


def test_shared_conflicts_not_last_writer_wins():
    comprobar_fuentes_compartidas(b"same", b"same")
    with pytest.raises(ValueError, match="conflicto"):
        comprobar_fuentes_compartidas(b"spark", b"ogre")


def test_help_semantics_fail_closed_for_network_and_glossary():
    assert motivo_ayuda_pendiente("ie03o_tt40") is None
    assert "StreetPass" in motivo_ayuda_pendiente("ie03o_tt55")
    assert "glosario" in motivo_ayuda_pendiente("ie03o_tt36")
    assert "sin_revision" in motivo_ayuda_pendiente("ie03o_tt999")
    assert "sin_revision" in motivo_ayuda_pendiente("ie03o_syup_bg00")


def _one(tex):
    return b"ARCV" + struct.pack("<IIIII", 1, 24 + len(tex), 24, len(tex), 10) + tex


def test_dynamic_help_requires_identical_single_placeholder():
    jp, es = _one(_ctpk()), _one(_ctpk(7))
    out, report = trasplantar_atlas(jp, es, {"x.tga"},
                                  layout_externo=(_arc(), _arc(), "x"))
    assert out == es
    assert report["dynamic_alias"] == "x"
    assert report["external_layout_sha256"]
    with pytest.raises(ValueError, match="placeholder"):
        trasplantar_atlas(jp, es, {"x.tga"}, layout_externo=(_arc(), _arc(), "other"))


def test_dynamic_help_refuses_changed_layout():
    qna = bytearray(_qna())
    struct.pack_into("<f", qna, 128, 5)
    with pytest.raises(ValueError, match="QNA externo"):
        trasplantar_atlas(_one(_ctpk()), _one(_ctpk(5)), {"x.tga"},
                         layout_externo=(_arc(), _arc(qna=bytes(qna)), "x"))
