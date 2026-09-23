import hashlib
import json

import pytest

from ie123kit.ie3.comun.b123 import B123Archive
from ie123kit.ie3.comun.geometria_dialogo import Medidor, parchear_origen
from ie123kit.ie3.comun.tipografia import FuenteBCFNT
from ie123kit.ie3.fase4 import leer_codigo
from ie123kit.nucleo.config.raiz import find_root

pytestmark = pytest.mark.requiere_rom


def test_geometry_reference_and_regression_messages(tmp_path):
    root = find_root()
    ref = root/"work/ie3/shared/candidatas/spark_ogre_integrada_fase3"
    if not (ref/"archive.fa").exists():
        pytest.skip("requiere referencia fase3")
    with B123Archive(ref/"archive.fa") as arc:
        font = arc.read("font/FONT12.bcfnt")
    fp = tmp_path/"FONT12.bcfnt"
    fp.write_bytes(font)
    m = Medidor(FuenteBCFNT(fp))
    rows = json.loads((ref/"spark/messages.json").read_text("utf-8"))
    keys = {"spark:evet:32010100:00000000", "spark:evet:32500100:00000000",
            "spark:evet:32500100:00000104", "spark:evet:32500100:000001DC"}
    found = [r for r in rows if r["key"] in keys]
    assert len(found) == 4
    for row in found:
        layout = m.maquetar(row["formatted"])
        assert layout is not None
        assert layout.replace("\\n", " ") == row["formatted"].replace("\\n", " ")
        assert len(layout.split("\\n")) <= 3
        assert all(m.exceso(line) <= 0 for line in layout.split("\\n"))
    equipos = next(r for r in found if r["event"] == 32010100)
    assert equipos["formatted"].endswith("mundiales...")
    old = m.medir(equipos["formatted"].split("\\n")[0], 12)
    assert old["derecha"] == 318
    assert all(s["avance"] == 7 for s in old["espacios"])
    assert hashlib.sha256(fp.read_bytes()).digest() == hashlib.sha256(font).digest()
    cro = (ref/"romfs/cro/ina_main3ogre.cro").read_bytes()
    new, _ = parchear_origen(cro)
    assert new[:0x3ABC8] == cro[:0x3ABC8]
    assert new[0x3ABCC:] == cro[0x3ABCC:]
    # Conversión real de espacio ASCII: cmp0x20 y rama U+3000; no parcheada.
    code = leer_codigo(root/"work/shared/base_3ds/exefs.bin")
    assert code[0xA0FDC:0xA0FE0] == bytes.fromhex("200054e3")
