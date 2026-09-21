import hashlib
import json
import struct

import pytest

from ie123kit.ie3.comun.b123 import B123Archive
from ie123kit.ie3.comun.colocacion_visible import CAMBIOS, instrucciones, parchear
from ie123kit.ie3.comun.geometria_dialogo import Medidor
from ie123kit.ie3.comun.tipografia import FuenteBCFNT
from ie123kit.nucleo.config.raiz import find_root

pytestmark = pytest.mark.requiere_rom


def test_real_patch_font_and_regressions(tmp_path):
    root = find_root() / "work/ie3/shared/candidatas"
    previous = root / "spark_ogre_integrada_fase4"
    if not previous.exists():
        pytest.skip("requiere candidata fase4")
    cro = (previous / "romfs/cro/ina_main3ogre.cro").read_bytes()
    out, report = parchear(cro)
    assert len(out) == len(cro) and not report["runtime_verified"]
    table = struct.unpack_from("<I", cro, 0xC8)[0]
    allowed = {p + n for p in set(CAMBIOS) | set(instrucciones()) | {table + 4} for n in range(4)}
    assert all(i in allowed for i, (a, b) in enumerate(zip(cro, out, strict=True)) if a != b)
    assert cro[0x29BF48:0x29BF50] == out[0x29BF48:0x29BF50] == bytes(8)
    with B123Archive(previous / "archive.fa") as archive:
        font_data = archive.read("font/FONT12.bcfnt")
    assert hashlib.sha256(font_data).hexdigest() == "7908857da6b8055c7847635c8449f1b916a00bca12997a4d2af4b67eb3be4466"
    fp = tmp_path / "FONT12.bcfnt"
    fp.write_bytes(font_data)
    f = FuenteBCFNT(fp)
    old, new = Medidor(f), Medidor(f, word_spacing=3, extra_line=1, vertical_percent=100)
    assert f.b.height + new.extra_line == 17
    assert old.glifo(" ")[0] == 7 and new.glifo(" ") == (3, ())
    for char in "Bianchi Maserati ¡¿Èáéíóúñ!":
        if char != " ":
            assert new.glifo(char) == old.glifo(char)
    rows = json.loads((root / "spark_ogre_integrada_fase3/spark/messages.json").read_text("utf-8"))
    wanted = {"spark:evet:32010100:00000000", "spark:evet:32500100:00000000",
              "spark:evet:32500100:00000104", "spark:evet:32500100:000001DC"}
    found = [r for r in rows if r["key"] in wanted]
    assert len(found) == 4
    for row in found:
        text = row["formatted"]
        result = new.maquetar(text)
        assert result is not None
        assert result.replace("\\n", " ") == text.replace("\\n", " ")
        assert all(new.exceso(line) <= 0 for line in result.split("\\n"))
        for line in text.split("\\n"):
            assert old.medir(line)["avance"] - new.medir(line)["avance"] == line.count(" ") * 4
    assert fp.read_bytes() == font_data
