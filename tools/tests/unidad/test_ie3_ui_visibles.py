import struct

import pytest

from ie123kit.ie3.comun.ui_visibles import trasplantar_atlas_por_partes
from ie123kit.nucleo.graficos import ctpk
from ie123kit.nucleo.graficos.texturas import iter_ctpk


def _texture(name, seed, fmt=4):
    raw = bytearray(256)
    raw[:4] = b"CTPK"
    struct.pack_into("<HHI", raw, 4, 1, 1, 128)
    struct.pack_into("<IIIIHH", raw, 32, 64, 128, 0, fmt, 8, 8)
    raw[64:70] = name.encode() + b".tga\0"
    raw[128:] = bytes((i + seed) % 256 for i in range(128))
    return bytes(raw)


def _qna(order=(0, 1), x_shift=0, y_shift=0):
    raw = bytearray(128 + 128 * len(order))
    raw[:8] = b" QNA 051"
    struct.pack_into("<III", raw, 8, 2, 0, len(order))
    struct.pack_into("<III", raw, 36, 64, 0, 128)
    raw[64:70], raw[96:102] = b"x.tga\0", b"y.tga\0"
    for index, texture in enumerate(order):
        pos = 128 + 128 * index
        # Deliberate native repeated UV: no geometry is created or altered.
        struct.pack_into("<4f", raw, pos, -1, 0, 12, 8)
        struct.pack_into("<f", raw, pos + 32, x_shift if texture == 0 else y_shift)
        struct.pack_into("<I", raw, pos + 88, texture)
    return bytes(raw)


def _arc(x=0, y=0, qna=None, fmt=4, opaque=b"opaque"):
    parts = [_texture("x", x, fmt), _texture("y", y), qna or _qna(), opaque]
    raw = bytearray(60)
    raw[:4] = b"ARCV"
    struct.pack_into("<I", raw, 4, len(parts))
    for i, part in enumerate(parts):
        struct.pack_into("<III", raw, 12 + 12 * i, len(raw), len(part), 10 + i)
        raw.extend(part)
    struct.pack_into("<I", raw, 8, len(raw))
    return bytes(raw)


def test_native_extended_uv_and_reordered_parts_preserved():
    jp = _arc()
    es = _arc(x=20, qna=_qna((1, 0)))
    out, report = trasplantar_atlas_por_partes(jp, es, {"x.tga"})
    assert out == _arc(x=20)
    assert report["qna_preserved"] and report["nonpixel_preserved"]
    assert report["applied"][0]["rgba_exact"]
    assert report["applied"][0]["alpha_exact"]
    assert not report["runtime_verified"]


def test_compose_keeps_previous_pixels_and_is_idempotent():
    jp, actual, es = _arc(), _arc(y=8), _arc(x=20, y=99)
    out, _ = trasplantar_atlas_por_partes(jp, es, {"x.tga"}, actual=actual)
    assert out == _arc(x=20, y=8)
    again, report = trasplantar_atlas_por_partes(jp, es, {"x.tga"}, actual=out)
    assert again == out and not report["applied"]


def test_other_texture_regional_layout_not_copied():
    out, _ = trasplantar_atlas_por_partes(
        _arc(), _arc(x=20, qna=_qna(y_shift=9)), {"x.tga"})
    assert out == _arc(x=20)


@pytest.mark.parametrize("qna", [_qna(x_shift=1), _qna((0, 0, 1)), _qna((1,))])
def test_all_selected_consumers_must_match(qna):
    with pytest.raises(ValueError, match="consumidores"):
        trasplantar_atlas_por_partes(_arc(), _arc(x=20, qna=qna), {"x.tga"})


def test_format_conversion_is_never_silent():
    with pytest.raises(ValueError, match="formato/dimensiones"):
        trasplantar_atlas_por_partes(_arc(), _arc(x=20, fmt=2), {"x.tga"})


def test_reject_nonpixel_current_and_source_changes():
    with pytest.raises(ValueError, match="actual altera"):
        trasplantar_atlas_por_partes(_arc(), _arc(x=20), {"x.tga"},
                                    actual=_arc(qna=_qna(x_shift=1)))
    with pytest.raises(ValueError, match="no-texto desconocido"):
        trasplantar_atlas_por_partes(_arc(), _arc(x=20, opaque=b"edited"), {"x.tga"})


def test_ctpk_metadata_bytes_outside_pixels_are_immutable():
    current = bytearray(_arc())
    current[60 + 28] ^= 1
    with pytest.raises(ValueError, match="fuera de píxeles"):
        trasplantar_atlas_por_partes(_arc(), _arc(x=20), {"x.tga"}, actual=bytes(current))


def test_partial_atlas_keeps_other_regions_and_alpha_exact():
    qna = bytearray(_qna())
    struct.pack_into("<4f", qna, 128, 0, 0, 4, 8)
    jp, es = _arc(qna=bytes(qna)), _arc(x=20, qna=bytes(qna))
    out, report = trasplantar_atlas_por_partes(jp, es, {"x.tga"},
                                             regiones={"x.tga": ((0, 0, 4, 8),)})
    images = [ctpk.decode(next(iter_ctpk(data)).blob) for data in (jp, es, out)]
    assert images[2].crop((0, 0, 4, 8)).tobytes() == images[1].crop((0, 0, 4, 8)).tobytes()
    assert images[2].crop((4, 0, 8, 8)).tobytes() == images[0].crop((4, 0, 8, 8)).tobytes()
    assert report["applied"][0]["rgba_scope"] == "selected_regions"


def test_partial_consumer_and_outside_region_fail_closed():
    with pytest.raises(ValueError, match="corta un consumidor"):
        trasplantar_atlas_por_partes(_arc(), _arc(x=20), {"x.tga"},
                                    regiones={"x.tga": ((0, 0, 4, 8),)})
    with pytest.raises(ValueError, match="fuera de textura"):
        trasplantar_atlas_por_partes(_arc(), _arc(x=20), {"x.tga"},
                                    regiones={"x.tga": ((0, 0, 40, 8),)})
