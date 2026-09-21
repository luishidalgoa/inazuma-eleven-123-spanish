import struct

import pytest

from ie123kit.ie3.comun.ui_graficos import trasplantar_atlas
from ie123kit.nucleo.compresion.blz import decompress
from ie123kit.nucleo.compresion.sszl import unwrap
from ie123kit.nucleo.config.raiz import find_root
from ie123kit.nucleo.contenedores.fa import FaArchive
from ie123kit.nucleo.graficos.texturas import iter_ctpk

pytestmark = pytest.mark.requiere_rom


def test_official_help_preserves_arcv_and_exact_rgba():
    root = find_root()
    base = root / "work/shared/base_3ds"
    official = root / "work/ie3/rayo_celeste/fuentes/3ds_eu/romfs/archive_sz.fa"
    if not (base / "exefs.bin").exists() or not official.exists():
        pytest.skip("requiere fuentes oficiales locales")
    exe = (base / "exefs.bin").read_bytes()
    off, size = struct.unpack_from("<II", exe, 8)
    code = decompress(exe[512 + off:512 + off + size])
    jp, es = FaArchive(str(base / "romfs/archive.fa")), FaArchive(str(official))
    prefix = "inazuma3_ogre/data_iz/a_data_replace/help_b/"
    path, parts = prefix + "data/ie03o_tt40.arc", prefix + "parts.arc"
    before, source = jp.read(path), es.read("es/" + path)
    names = {t.nombre for t in iter_ctpk(before)}
    out, report = trasplantar_atlas(before, source, names, codigo_lector=code,
                                  layout_externo=(jp.read(parts), es.read("es/" + parts),
                                                  "ie03_help_bg_ghost01"))
    assert len(unwrap(out)) == len(unwrap(before))
    assert report["applied"]
    assert all(t["rgba_exact"] and t["alpha_exact"] for t in report["applied"])
    assert not report["runtime_verified"]
