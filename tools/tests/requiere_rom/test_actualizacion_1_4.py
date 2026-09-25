"""#87: los parches de CRO de la candidata vigente se relocalizan todos en las CRO de la actualización 1.4.

Necesita work/shared/base_3ds (CRO 1.0), la candidata probe_ie3_fuego_v16 y Roms/shared/update/romfs.
"""

import pytest

from ie123kit.nucleo.ejecutable.relocalizar import (
    literales_absolutos,
    relocalizar,
    verificar_estructura,
    verificar_relocalizacion,
)

pytestmark = pytest.mark.requiere_rom

CRO = ("ina_menu.cro", "ina_main1.cro", "ina_main2.cro", "ina_main3ogre.cro")
#: cGameTextSystem::s_pInstance en el code.bin 1.0 -> 1.4 (mapear_direccion_absoluta, 5 votos)
ABSOLUTAS = {0x2A16D8: 0x2A06A8}


@pytest.fixture
def rutas():
    from ie123kit.nucleo.config.raiz import find_root

    r = find_root()
    rutas = (r / "work/shared/base_3ds/romfs/cro", r / "work/shared/candidatas/probe_ie3_fuego_v16",
             r / "Roms/shared/update/romfs/cro")
    if not all((d / "ina_main1.cro").is_file() for d in rutas):
        pytest.skip("faltan las CRO 1.0, la candidata o la actualización 1.4")
    return rutas


@pytest.mark.parametrize("nombre", CRO)
def test_relocaliza_la_candidata_en_la_1_4(rutas, nombre):
    base, cand, dest = ((d / nombre).read_bytes() for d in rutas)
    assert set(literales_absolutos(base, cand).values()) <= set(ABSOLUTAS)
    r = relocalizar(base, cand, dest, absolutas=ABSOLUTAS)
    assert r.ok, [p.a_dict() for p in r.fallidos][:5]
    assert verificar_estructura(dest, r.datos, r.rangos) == []
    assert verificar_relocalizacion(base, cand, dest, r) == []



@pytest.mark.parametrize("nombre", ["ina_main1.cro", "ina_main2.cro", "ina_main3ogre.cro"])
def test_bufer_rubi_en_la_1_0_y_relocalizado_en_la_1_4(rutas, nombre):
    """La capa bufer_rubi se aplica a la CRO 1.0 original y se relocaliza entera en la 1.4 (#87)."""
    from ie123kit.nucleo.ejecutable.bufer_rubi import aplicar_bufer_rubi, localizar_todos

    base, _cand, dest = ((d / nombre).read_bytes() for d in rutas)
    con_rubi, informe = aplicar_bufer_rubi(base)
    esperado = {"ina_main1.cro": 13, "ina_main2.cro": 25, "ina_main3ogre.cro": 25}[nombre]  # A 13 + B 12
    assert len(informe["parches"]) == esperado
    r = relocalizar(base, con_rubi, dest)
    assert r.ok
    directo, _ = aplicar_bufer_rubi(dest)  # aplicarla directamente a la 1.4 da lo mismo
    assert r.datos == directo
    assert verificar_relocalizacion(base, con_rubi, dest, r) == []
    assert localizar_todos(dest)
