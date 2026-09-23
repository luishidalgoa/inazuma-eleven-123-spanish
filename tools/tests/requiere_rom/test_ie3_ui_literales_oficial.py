from pathlib import Path

import pytest

from ie123kit.ie3.comun.ui_literales import (
    LITERALES,
    codigo_desde_exefs,
    extraer_fuente_programa,
    parchear_literales_ie3,
)
from ie123kit.nucleo.contenedores.fa import FaArchive

pytestmark = pytest.mark.requiere_rom
ROOT = Path("work/ie3/rayo_celeste/fuentes/3ds_eu")
JP = Path("work/shared/base_3ds/romfs/cro/ina_main3ogre.cro")


@pytest.mark.skipif(not JP.exists() or not (ROOT / "exefs.bin").exists(),
                    reason="requiere originales JP y EU locales")
def test_official_getstring_chain_and_literal_roundtrip():
    source = FaArchive(ROOT / "romfs/archive_sz.fa")
    original = JP.read_bytes()
    args = (codigo_desde_exefs((ROOT / "exefs.bin").read_bytes()),
            (ROOT / "romfs/cro/static.crs").read_bytes(),
            (ROOT / "romfs/cro/ina_main3ogre.cro").read_bytes(),
            source.read("font/CodeTable.bin"))
    output, report = parchear_literales_ie3(original, *args)
    assert report["labels"] == 12
    assert report["roundtrip_official_exact"]
    assert report["blocks"][1]["source_texts"] == [
        "Jugadores", "Inventario", "Estrategias", "Datos", "Recursos", "Guardar"]
    allowed = {i for lit in LITERALES for i in range(lit.offset, lit.offset + lit.capacidad)}
    assert all(a == b or i in allowed for i, (a, b) in enumerate(zip(original, output, strict=True)))
    assert output[0x1F9E70:0x1F9E84] == original[0x1F9E70:0x1F9E84]
    assert parchear_literales_ie3(output, *args)[0] == output
    # Geometry/name instructions elsewhere may already differ; no whole-CRO hash gate.
    modified = bytearray(original)
    modified[0x125670:0x125674] = b"TEST"
    composed, _ = parchear_literales_ie3(bytes(modified), *args)
    assert composed[0x125670:0x125674] == b"TEST"
    for index in range(4):
        corrupt = list(args)
        bad = bytearray(corrupt[index])
        bad[-1] ^= 1
        corrupt[index] = bytes(bad)
        with pytest.raises(ValueError, match="fuente oficial"):
            parchear_literales_ie3(original, *corrupt)


@pytest.mark.skipif(not (ROOT / "exefs.bin").exists(), reason="requiere fuentes locales")
def test_ogre_independent_sources_same_consumers_ids_and_common_literals():
    ogre = Path("work/ie3/amenaza_del_ogro/fuentes/3ds_eu")
    if not (ogre / "exefs.bin").exists():
        pytest.skip("falta Ogre EU")
    extracted = []
    outputs = []
    for root, archive, profile in [(ROOT, "archive_sz.fa", "spark"), (ogre, "archive_oz.fa", "ogre")]:
        fa = FaArchive(root / "romfs" / archive)
        args = (codigo_desde_exefs((root / "exefs.bin").read_bytes()),
                (root / "romfs/cro/static.crs").read_bytes(),
                (root / "romfs/cro/ina_main3ogre.cro").read_bytes(),
                fa.read("font/CodeTable.bin"))
        source, proof = extraer_fuente_programa(*args)
        assert proof["profile"] == profile + "_eu_common_ui"
        extracted.append(source)
        outputs.append(parchear_literales_ie3(JP.read_bytes(), *args)[0])
    assert extracted[0] == extracted[1]
    assert outputs[0] == outputs[1]
