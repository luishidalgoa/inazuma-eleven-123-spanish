from pathlib import Path

import pytest

from ie123kit.ie3.comun.perfiles import PERFILES
from ie123kit.ie3.comun.tablas_ui import recursos_tablas_ui, verificar_consumidor, verificar_consumidor_europeo
from ie123kit.nucleo.contenedores.fa import FaArchive
from ie123kit.nucleo.texto.sjis_portador import es_encode

pytestmark = pytest.mark.requiere_rom
BASE = Path("work/shared/base_3ds/romfs")


@pytest.mark.skipif(not (BASE / "archive.fa").exists(), reason="requiere originales locales")
@pytest.mark.parametrize("profile_name", ["spark", "ogre"])
def test_pools_and_label_fields_official_roundtrip(profile_name):
    profile = PERFILES[profile_name]
    if not Path(profile.oficial).exists():
        pytest.skip("falta fuente oficial")
    proof = verificar_consumidor((BASE / "cro/ina_main3ogre.cro").read_bytes())
    assert proof["sha256"] == profile.consumer_sha256
    original = FaArchive(BASE / "archive.fa")
    payloads, reports = recursos_tablas_ui(profile, original, FaArchive(profile.oficial))
    official_cro = Path(profile.oficial).parent / "cro/ina_main3ogre.cro"
    assert verificar_consumidor_europeo(official_cro.read_bytes())["source_scales"]["unitbase"] == 256
    assert len(payloads) == 8
    assert reports["item"]["applied_fields"] == 673
    assert reports["command"]["by_field"] == {"nombre": 398, "descripcion": 382}
    assert reports["tacticscmd"]["applied_fields"] == 21
    assert reports["unitbase"]["applied_fields"] == (2336 if profile_name == "spark" else 2352)
    # Independent known character/content check: roundtrip alone failed to catch wrong EU scale.
    bianchi = next(row for row in reports["unitbase"]["applied"] if row["record"] == 1855)
    expected = "¡El delantero estrella conocido\ncomo el Meteoro Blanco Italiano!"
    assert bianchi["official"] == expected
    assert bianchi["source_offset"] == 0x73F00
    assert bianchi["source_pointer_scale"] == 256
    pool = payloads[profile.recurso.rsplit("/", 1)[0] + "/logic/unitbase.STR"]
    assert pool[0x32A40:0x32AA0].split(b"\0")[0] == es_encode(expected, 1 << 30)
    assert reports["teamtitle"]["applied_fields"] == 20
    assert reports["BattleRouteTitle"]["applied_fields"] == (7 if profile_name == "spark" else 8)
    assert reports["ClearCondition"]["applied_fields"] == 38
    assert reports["OpenCondition"]["applied_fields"] == (27 if profile_name == "spark" else 25)
    assert reports["games"]["jp_es_common_identical"]
    for path, content in payloads.items():
        assert len(content) == len(original.read(path))
    for name, report in reports.items():
        if name != "games":
            assert report["roundtrip_official_exact"]
            assert report["size_preserved"]
