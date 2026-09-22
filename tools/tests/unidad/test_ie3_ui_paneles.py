import hashlib
import struct

import pytest

from ie123kit.ie3.comun import ui_paneles as mod
from ie123kit.nucleo.compresion.sszl import compress, unwrap
from ie123kit.nucleo.contenedores.arcv import entries


def _ctpk(name, fmt):
    size = 65536 if fmt == 12 else 262144
    raw = bytearray(128 + size)
    raw[:4] = b"CTPK"
    struct.pack_into("<HHI", raw, 4, 1, 1, 128)
    struct.pack_into("<IIIIHH", raw, 32, 64, size, 0, fmt, 512, 256)
    encoded = (name + ".tga").encode() + b"\0"
    raw[64:64 + len(encoded)] = encoded
    raw[128:] = b"\x12\x35" * (size // 2)
    return bytes(raw)


def _arc(blobs):
    raw = bytearray(128)
    raw[:4] = b"ARCV"
    struct.pack_into("<I", raw, 4, len(blobs))
    for i, blob in enumerate(blobs):
        struct.pack_into("<III", raw, 12 + 12 * i, len(raw), len(blob), 100 + i)
        raw.extend(blob)
    struct.pack_into("<I", raw, 8, len(raw))
    return bytes(raw)


@pytest.fixture(scope="module")
def panels():
    name = mod.PANELES[0]
    alias = "ie03_help_bg_t_ghost01"
    qna = bytearray(224)
    qna[:8] = b" QNA 051"
    struct.pack_into("<III", qna, 8, 1, 0, 1)
    struct.pack_into("<III", qna, 36, 64, 0, 96)
    qna[64:64 + len(alias)] = alias.encode()
    struct.pack_into("<4f", qna, 96, 0, 0, 400, 240)
    parts = _arc([_ctpk(alias, 12), bytes(qna)])
    return (compress(_arc([_ctpk(name, 12)])), compress(_arc([_ctpk(name, 2)])), parts)


def test_full_official_ctpk_rebuilt_without_loss(panels, monkeypatch):
    monkeypatch.setattr(mod, "LECTOR_SSZL_SHA256", hashlib.sha256(b"test reader").hexdigest())
    jp, es, parts = panels
    out, report = mod.reconstruir_panel(jp, es, parts, parts, mod.PANELES[0], b"test reader")
    oj, sj, cj = entries(unwrap(jp))[0]
    oo, so, co = entries(unwrap(out))[0]
    oe, se, _ = entries(unwrap(es))[0]
    assert (oj, cj) == (oo, co) and so > sj
    assert unwrap(out)[oo:oo + so] == unwrap(es)[oe:oe + se]
    assert report["ctpk_official_exact"] and report["alpha_exact"]
    assert not report["runtime_verified"]


def test_reader_and_unknown_panel_fail_closed(panels, monkeypatch):
    jp, es, parts = panels
    with pytest.raises(ValueError, match="lector"):
        mod.reconstruir_panel(jp, es, parts, parts, mod.PANELES[0], b"wrong")
    monkeypatch.setattr(mod, "LECTOR_SSZL_SHA256", hashlib.sha256(b"test reader").hexdigest())
    with pytest.raises(ValueError, match="semántica"):
        mod.reconstruir_panel(jp, es, parts, parts, "not reviewed", b"test reader")


def test_external_consumer_changed_is_not_transplanted(panels, monkeypatch):
    monkeypatch.setattr(mod, "LECTOR_SSZL_SHA256", hashlib.sha256(b"test reader").hexdigest())
    jp, es, parts = panels
    changed = bytearray(parts)
    offset, _, _ = entries(parts)[1]
    struct.pack_into("<f", changed, offset + 96 + 32, 5)
    with pytest.raises(ValueError, match="QNA externo distinto"):
        mod.reconstruir_panel(jp, es, parts, bytes(changed), mod.PANELES[0], b"test reader")
