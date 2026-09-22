"""Anclas reales FONT8 y preservación literal del cuerpo/CRO restante."""
import hashlib

import pytest

from ie123kit.ie3.comun.presentacion_nombres import (
    CRO_V7_SHA256,
    SALTO_FONT8,
    configuracion_nombre,
    parchear_font8_ie3,
)
from ie123kit.nucleo.config.raiz import find_root

pytestmark = pytest.mark.requiere_rom


def test_real_v7_one_word_font8_no_other_consumers_or_resources_changed():
    root = find_root()
    path = root / "work/ie3/rayo_celeste/candidatas/spark_conservadora_v7_celdas_centrado/romfs/cro/ina_main3ogre.cro"
    if not path.is_file():
        pytest.skip("requiere CRO v7 local")
    before = path.read_bytes()
    assert hashlib.sha256(before).hexdigest() == CRO_V7_SHA256
    after, report = parchear_font8_ie3(before)
    assert len(after) == len(before) == 3481600
    assert [i for i, (a, b) in enumerate(zip(before, after)) if a != b] == [SALTO_FONT8]
    # La llamada de nombres y su prologue/estado inicial siguen intactos.
    assert before[0x160E88:0x16113C] == after[0x160E88:0x16113C]
    # Todo el handler 301D/cuerpo, constructor de ventana y ancho v7 son iguales.
    assert before[0x4F05C:0x4F230] == after[0x4F05C:0x4F230]
    assert before[0x18091C:0x180930] == after[0x18091C:0x180930]
    # Se mantienen los overrides locales explícitos (también los de otras UI).
    assert before[0x180970:0x1809C0] == after[0x180970:0x1809C0]
    assert report["relocation_targets_checked"] == 40030
    assert not report["runtime_verified"]


def test_real_itx_name_configuration_and_global_defaults_are_distinct():
    root = find_root() / "work/shared/fa_extract/import"
    if not (root / "sItxInazuma3ogre.itx").is_file():
        pytest.skip("requiere ITX originales locales")
    report = configuracion_nombre(
        (root / "sItxInazuma3ogre.itx").read_bytes(),
        (root / "sItxInazuma123.itx").read_bytes(),
    )
    assert report["nombre"]["cscenedirection_1728_addW"] == {"valor": 0, "offset_s32": 0x2E50}
    assert not report["cero_local_desactiva_override"]
    assert sorted(x["valor"] for x in report["defaults_compartidos"].values()) == [6, 7]
