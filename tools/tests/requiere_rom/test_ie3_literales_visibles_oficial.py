from pathlib import Path

import pytest

from ie123kit.ie3.comun.b123 import B123Archive
from ie123kit.ie3.comun.literales_visibles import RANGOS, parchear_submenus
from ie123kit.ie3.comun.perfiles import PERFILES
from ie123kit.ie3.comun.ui_literales import codigo_desde_exefs
from ie123kit.nucleo.ejecutable.cro import Cro

pytestmark = pytest.mark.requiere_rom
CURRENT = Path("work/ie3/shared/candidatas/spark_ogre_integrada_fase4/romfs/cro/ina_main3ogre.cro")


@pytest.mark.skipif(not CURRENT.exists(), reason="requiere candidata y fuentes oficiales")
@pytest.mark.parametrize("name", ["spark", "ogre"])
def test_complete_submenus_official_sources_pointer_readback_and_compose(name):
    profile = PERFILES[name]
    root = Path(profile.oficial).parent.parent
    with B123Archive(profile.oficial) as archive:
        args = (codigo_desde_exefs((root / "exefs.bin").read_bytes()),
                (root / "romfs/cro/static.crs").read_bytes(),
                (root / "romfs/cro/ina_main3ogre.cro").read_bytes(),
                archive.read("font/CodeTable.bin"))
    original = bytearray(CURRENT.read_bytes())
    # Other agent's reserved trampoline region is composed, never used by us.
    original[0x29BF48:0x29BF50] = b"COMPOSE!"
    original = bytes(original)
    output, report = parchear_submenus(original, *args)
    assert len(output) == len(original)
    assert output[0x29BF48:0x29C000] == original[0x29BF48:0x29C000]
    assert output[0x165E80:0x165EC4] == original[0x165E80:0x165EC4]
    assert report["labels"] == 38
    assert report["official_text_readback_exact"]
    assert [r["official"] for r in report["records"] if r["kind"] == "relocation"] == [
        ("Apodo",), ("Nivel",), None, ("Nombre",), ("Habilidades",)]
    before_relocs = {r.target: r for r in Cro(original).relocations}
    after_relocs = {r.target: r for r in Cro(output).relocations}
    assert set(before_relocs) == set(after_relocs)
    moved = {0x2B2890, 0x2B2894, 0x2B27BC, 0x2B288C, 0x2B2898}
    for target, old in before_relocs.items():
        if target not in moved:
            assert after_relocs[target] == old
        else:
            assert (old.target, old.type, old.seg_index) == (
                after_relocs[target].target, after_relocs[target].type, after_relocs[target].seg_index)
    for start, _ in RANGOS:
        bad = bytearray(original)
        bad[start] ^= 1
        with pytest.raises(ValueError, match="grupo literal original"):
            parchear_submenus(bytes(bad), *args)
