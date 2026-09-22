from pathlib import Path

import pytest

from ie123kit.ie3.comun.b123 import B123Archive
from ie123kit.ie3.comun.casos_visibles import EVENTO_INTRO, mision_intro_actual, recursos_ficha_y_titulo
from ie123kit.ie3.comun.paquetes import leer_paquete
from ie123kit.ie3.comun.perfiles import PERFILES
from ie123kit.ie3.comun.ssd import parse_ssd
from ie123kit.ie3.comun.text import TextTable, load_text_table
from ie123kit.nucleo.texto.sjis_portador import es_encode

pytestmark = pytest.mark.requiere_rom
BASE = Path("work/shared/base_3ds/romfs/archive.fa")
CURRENT = Path("work/ie3/shared/candidatas/spark_ogre_integrada_fase4/archive.fa")


@pytest.mark.skipif(not BASE.exists() or not CURRENT.exists(), reason="requiere originales/candidata")
@pytest.mark.parametrize("profile_name", ["spark", "ogre"])
def test_visible_character_title_and_mission_real_sources(profile_name):
    profile = PERFILES[profile_name]
    with B123Archive(BASE) as jp, B123Archive(profile.oficial) as es, B123Archive(CURRENT) as current:
        payloads, reports = recursos_ficha_y_titulo(profile, jp, es, current)
        prefix = profile.recurso.rsplit("/", 1)[0] + "/logic/"
        table = load_text_table(es)
        names = payloads[prefix + "unitbase.dat"]
        assert names[1855*104:1855*104+28].split(b"\0")[0] == b"Paolo Bianchi"
        original_current = current.read(prefix + "unitbase.dat")
        assert all(names[i+28:i+104] == original_current[i+28:i+104] for i in range(0, len(names), 104))
        title = payloads[prefix + "rpgtitle.STR"][0x4C0:0x4E0].split(b"\0")[0]
        assert title == (b"El Meteoro Blanco" if profile_name == "spark" else b"Indomable")
        p = profile.recurso + "/"
        blocks = []
        for archive, path in [(jp, p), (es, "es/" + p), (current, p)]:
            pack, _ = leer_paquete(archive.read(path + "eve.pkh"), archive.read(path + "eve.pkb"), "eve")
            blocks.append(pack[EVENTO_INTRO])
        result, report = mision_intro_actual(*blocks, table)
        assert report["official"] == "¡Ayuda a la chica!"
        assert report["instruction_es"] == (1869 if profile_name == "spark" else 1984)
        before_info, before_rows = parse_ssd(blocks[2], TextTable.identity())
        _, after_rows = parse_ssd(result, TextTable.identity())
        key = (1817, 3)
        assert next(r.raw for r in after_rows if r.key == key) == es_encode("¡Ayuda a la chica!", 1000)
        for a, b in zip(before_rows, after_rows, strict=True):
            if a.key != key:
                assert result[b.offset:b.offset+b.size] == blocks[2][a.offset:a.offset+a.size]
        end = 32 + before_info["code_len"]
        assert result[:end] == blocks[2][:end]
        assert reports["rpgtitle"]["conditions_unchanged"]
