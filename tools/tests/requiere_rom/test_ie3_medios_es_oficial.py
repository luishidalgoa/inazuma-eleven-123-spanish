import hashlib
from collections import Counter

import pytest

from ie123kit.ie3.comun.b123 import B123Archive
from ie123kit.ie3.comun.medios_es import comprobar_consumidores, inventariar_videos, planificar_audio
from ie123kit.nucleo.config.raiz import find_root

pytestmark = pytest.mark.requiere_rom


def test_medios_oficiales_es():
    root = find_root()
    jp = root / "work/shared/base_3ds/romfs"
    sp = root / "work/ie3/rayo_celeste/fuentes/3ds_eu/romfs"
    og = root / "work/ie3/amenaza_del_ogro/fuentes/3ds_eu/romfs"
    if not all(p.exists() for p in (jp / "archive.fa", sp / "archive_sz.fa", og / "archive_oz.fa")):
        pytest.skip("requiere las tres extracciones oficiales")
    files, report = planificar_audio(jp, sp, og)
    assert len(files) == 532
    assert Counter(row.get("category") for row in report["rows"] if row["state"] == "preparado") == {
        "voz_dialogo": 472, "audio_cinematica": 56, "cancion": 4}
    for row in report["rows"]:
        if row["state"] == "preparado":
            assert hashlib.sha256(files[row["target"]].read_bytes()).hexdigest() == row["after"]["sha256"]
            assert hashlib.sha256((jp / row["target"]).read_bytes()).hexdigest() == row["before"]["sha256"]
    with B123Archive(jp / "archive.fa") as a, B123Archive(sp / "archive_sz.fa") as b, B123Archive(og / "archive_oz.fa") as c:
        movies = inventariar_videos(a, b, c)
    assert movies["compatible"] == 65
    assert len(movies["subtitles"]) == 98
    assert len(movies["pending"]) == 8
    assert movies["selected"] == 0
    cro = (jp / "cro/ina_main3ogre.cro").read_bytes()
    contract = comprobar_consumidores(cro)
    assert contract["subtitle_ascii_discarded"] and contract["subtitle_independent"]
    broken = bytearray(cro)
    broken[0x24030] ^= 1
    with pytest.raises(ValueError, match="consumidor"):
        comprobar_consumidores(bytes(broken))
