from pathlib import Path

import pytest

from ie123kit.ie3.comun.geometria_submenus import CAMBIOS_TITULO, parchear_titulos
from ie123kit.ie3.comun.literales_visibles import _adr_target

pytestmark = pytest.mark.requiere_rom
ORIGINAL = Path("work/shared/base_3ds/romfs/cro/ina_main3ogre.cro")


@pytest.mark.skipif(not ORIGINAL.exists(), reason="requiere CRO JP original")
def test_title_class_patch_consumers_other_bytes_unchanged():
    original = bytearray(ORIGINAL.read_bytes())
    # A title translated by a prior adapter, at its original ADR destination.
    import struct
    target = _adr_target(struct.unpack_from("<I", original, 0x165F38)[0], 0x165F38)
    original[target:target+11] = b"Inventario\0"
    # Unrelated cave may already contain the main-menu implementation.
    original[0x29BF50:0x29BF58] = b"COMPOSE!"
    original = bytes(original)
    output, report = parchear_titulos(original)
    assert len(original) == len(output)
    assert len(report["constructor_callers"]) == 9
    assert len(report["titles"]) == 8
    assert report["buffer_bytes_after"] == 512
    assert report["title_selection_uv_width"] == 128
    assert not report["runtime_verified"]
    restored = bytearray(output)
    for offset in CAMBIOS_TITULO:
        restored[offset:offset+4] = original[offset:offset+4]
    assert bytes(restored) == original
    with pytest.raises(ValueError, match="constante de título distinta"):
        parchear_titulos(output)
    bad = bytearray(original)
    bad[target:target+15] = b"A"*15
    with pytest.raises(ValueError, match="sin NUL"):
        parchear_titulos(bytes(bad))
    bad = bytearray(original)
    bad[0x269FE8] ^= 1
    with pytest.raises(ValueError, match="ancla"):
        parchear_titulos(bytes(bad))
