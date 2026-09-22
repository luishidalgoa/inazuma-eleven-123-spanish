import struct

import pytest

from ie123kit.ie3.comun.ui_graficos import trasplantar_atlas
from ie123kit.ie3.comun.ui_visibles import construir_payloads_visibles
from ie123kit.nucleo.compresion.blz import decompress
from ie123kit.nucleo.compresion.sszl import unwrap
from ie123kit.nucleo.config.raiz import find_root
from ie123kit.nucleo.contenedores.fa import FaArchive
from ie123kit.nucleo.graficos.qna import qna_in_arc

pytestmark = pytest.mark.requiere_rom


def test_official_visible_families_compose_and_preserve_all_qna():
    root = find_root()
    base = root / "work/shared/base_3ds"
    paths = [base / "romfs/archive.fa",
             root / "work/ie3/rayo_celeste/fuentes/3ds_eu/romfs/archive_sz.fa",
             root / "work/ie3/amenaza_del_ogro/fuentes/3ds_eu/romfs/archive_oz.fa"]
    if not all(p.exists() for p in [*paths, base / "exefs.bin"]):
        pytest.skip("requiere fuentes oficiales JP/ES locales")
    jp, es, ogre = [FaArchive(str(p)) for p in paths]
    exe = (base / "exefs.bin").read_bytes()
    off, size = struct.unpack_from("<II", exe, 8)
    code = decompress(exe[512 + off:512 + off + size])
    status = "inazuma3_ogre/data_iz/a_menu/status_t.arc"
    previous, _ = trasplantar_atlas(jp.read(status), es.read("es/" + status),
                                   {"ie03_menu_status_mes01_t01.tga"}, codigo_lector=code)
    payloads, report = construir_payloads_visibles(jp, es, ogre, code,
                                                  actuales={status: previous})
    assert report["payload_count"] == 7
    assert report["atlas_count"] == 24
    for path, out in payloads.items():
        before = jp.read(path)
        assert len(unwrap(out)) == len(unwrap(before))
        assert [(off, q.to_bytes()) for off, q in qna_in_arc(before)] == [
            (off, q.to_bytes()) for off, q in qna_in_arc(out)]
    assert all(row["nonpixel_preserved"] for row in report["resources"])
    assert all(a["rgba_exact"] and a["alpha_exact"] for row in report["resources"]
               for a in row["applied"])
    again, second = construir_payloads_visibles(jp, es, ogre, code, actuales=payloads)
    assert again == {} and second["atlas_count"] == 0
    assert not report["runtime_verified"]
