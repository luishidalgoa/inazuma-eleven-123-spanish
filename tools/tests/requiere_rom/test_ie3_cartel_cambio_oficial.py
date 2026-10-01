"""Cartel de cambio del IE3: el parche se aplica sobre la ina_main3ogre.cro japonesa 1.0 local."""

import pytest

from ie123kit.ie3.comun import cartel_cambio as m
from ie123kit.nucleo.config.raiz import find_root

pytestmark = pytest.mark.requiere_rom


def test_cro_japonesa():
    path = find_root() / "work/shared/base_3ds/romfs/cro/ina_main3ogre.cro"
    if not path.is_file():
        pytest.skip("requiere la CRO japonesa local")
    original = path.read_bytes()
    assert m.localizar(original) == m.ORIGEN
    salida, informe = m.aplicar_cartel_cambio(original)
    assert informe["bytes_distintos"] == [hex(m.ORIGEN + rel + k) for rel, a, b, _ in m.PARCHES
                                          for k in range(4) if (a >> 8 * k) & 0xFF != (b >> 8 * k) & 0xFF]
    assert len(salida) == len(original)
    assert m.aplicar_cartel_cambio(salida)[0] == salida
