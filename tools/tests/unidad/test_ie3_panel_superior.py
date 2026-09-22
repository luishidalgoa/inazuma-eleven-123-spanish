import struct

import pytest

from ie123kit.ie3.comun import panel_superior as mod


def synthetic(monkeypatch):
    data = bytearray(0x200000)
    data[0x80:0x84] = b"CRO0"
    for offset, word in mod.ANCLAS_TITULO.items():
        struct.pack_into("<I", data, offset, word)
    monkeypatch.setattr(mod, "direcciones_de_tablas", lambda _: set())
    return bytes(data)


def test_reserva_titulo_exactamente_una_instruccion(monkeypatch):
    before = synthetic(monkeypatch)
    after, report = mod.parchear_reserva_titulo(before)
    assert [i for i, (a, b) in enumerate(zip(before, after, strict=True)) if a != b] == [mod.TITULO]
    assert struct.unpack_from("<I", after, mod.TITULO)[0] == 0xE3A01006
    assert report["glyph_capacity_after"] == 6
    assert report["runtime_verified"] is False
    with pytest.raises(ValueError, match="ancla"):
        mod.parchear_reserva_titulo(after)


@pytest.mark.parametrize("offset", list(mod.ANCLAS_TITULO))
def test_anclas_fail_closed(monkeypatch, offset):
    data = bytearray(synthetic(monkeypatch))
    data[offset] ^= 1
    with pytest.raises(ValueError, match="ancla"):
        mod.parchear_reserva_titulo(bytes(data))


def test_relocacion_rechazada(monkeypatch):
    data = synthetic(monkeypatch)
    monkeypatch.setattr(mod, "direcciones_de_tablas", lambda _: {mod.TITULO})
    with pytest.raises(ValueError, match="relocación"):
        mod.parchear_reserva_titulo(data)


def test_limite_real_commandos_no_pixel_width():
    for tiles in (3, 6):
        end = tiles * 8 * 8 // 2
        written = []
        cursor = 0
        for _ in range(20):
            if cursor + 32 > end:
                break
            written.append((cursor, cursor + 32))
            cursor += 32
        assert len(written) == tiles
        assert max(b for _, b in written) == end
