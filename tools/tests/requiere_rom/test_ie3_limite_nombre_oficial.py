"""El hook debe aceptar exclusivamente el CRO fase3 conservado en disco."""

import hashlib
import struct

import pytest

from ie123kit.ie3.comun import limite_nombre as mod
from ie123kit.nucleo.config.raiz import find_root

pytestmark = pytest.mark.requiere_rom


def test_real_cro_has_no_incoming_references_and_all_protected_paths_unchanged():
    path = find_root() / "work/ie3/shared/candidatas/spark_ogre_integrada_fase3/romfs/cro/ina_main3ogre.cro"
    if not path.is_file():
        pytest.skip("requiere CRO fase3 local")
    original = path.read_bytes()
    assert hashlib.sha256(original).hexdigest() == mod.CRO_FASE3_SHA256
    after, report = mod.parchear_limite_nombre(original)
    assert report["relocation_targets_checked"] == 40030
    assert report["dead_code_audit"]["preexisting_direct_relocation_export_entries"] == 0
    assert report["patch_words"] == 23
    for offset, word in mod.ANCLAS.items():
        assert struct.unpack_from("<I", after, offset)[0] == word
    assert original[:0x180930] == after[:0x180930]
    assert original[0x181000:] == after[0x181000:]
    assert len(after) == len(original)
    assert mod.parchear_limite_nombre(after)[0] == after
