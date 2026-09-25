"""Objetivos de IE2/IE3 (F2.3, #49): identidad completa y capacidades vacías.

Hasta que exista la extracción de cada versión, toda acción devuelve NOT_SUPPORTED;
lo que sí debe estar completo es la identidad (paquete, `JUEGO`, `info()` y perfil v20).
"""

from __future__ import annotations

from importlib import import_module
from pathlib import Path

import pytest

from ie123kit.ie2.comun.reglas import JuegoIE2
from ie123kit.ie3.comun.reglas import JuegoIE3
from ie123kit.nucleo.juego import JuegoBase, Regla
from ie123kit.nucleo.tipos import AssetRef, componer_id
from ie123kit.servicio import esquemas
from ie123kit.servicio.api import descubrir_juegos

#: objetivo -> (paquete, clase base esperada, prefijos romfs, cros)
OBJETIVOS = {
    "ie2.tormenta_de_fuego": ("ie123kit.ie2.tormenta_de_fuego", JuegoIE2, ("inazuma2/",), ("cro/ina_main2.cro",)),
    "ie2.ventisca_eterna": ("ie123kit.ie2.ventisca_eterna", JuegoIE2, ("inazuma2/",), ("cro/ina_main2.cro",)),
    "ie3.rayo_celeste": ("ie123kit.ie3.rayo_celeste", JuegoIE3, ("inazuma3/",), ("cro/ina_main3ogre.cro",)),
    "ie3.fuego_explosivo": ("ie123kit.ie3.fuego_explosivo", JuegoIE3, ("inazuma3/",), ("cro/ina_main3ogre.cro",)),
    "ie3.amenaza_del_ogro": (
        "ie123kit.ie3.amenaza_del_ogro",
        JuegoIE3,
        ("inazuma3_ogre/",),
        ("cro/ina_main3ogre.cro",),
    ),
}

TIPOS = ("grafico", "texto", "evento", "literal_cro", "cinematica", "voz")


def _ref(objetivo: str, tipo: str, ruta: str) -> AssetRef:
    return AssetRef(id=componer_id(objetivo, tipo, ruta), objetivo=objetivo, tipo=tipo, ruta_romfs=ruta)


@pytest.mark.parametrize("objetivo", list(OBJETIVOS))
def test_el_paquete_declara_JUEGO(objetivo: str) -> None:
    paquete, base, _prefijos, _cros = OBJETIVOS[objetivo]
    modulo = import_module(paquete)
    clase = modulo.JUEGO
    assert isinstance(clase, type) and issubclass(clase, base)
    assert clase.PAQUETE == paquete
    assert clase is import_module(f"{paquete}.acciones").__dict__[clase.__name__]


@pytest.mark.parametrize("objetivo", list(OBJETIVOS))
def test_descubrir_juegos_lo_instancia(objetivo: str) -> None:
    juego = descubrir_juegos()[objetivo]
    _paquete, base, _prefijos, _cros = OBJETIVOS[objetivo]
    assert isinstance(juego, base)
    assert type(juego).__name__ != "JuegoGenerico"  # ya no cae en el respaldo del servicio


@pytest.mark.parametrize("objetivo", list(OBJETIVOS))
def test_info_completa_y_valida(objetivo: str) -> None:
    _paquete, _base, prefijos, cros = OBJETIVOS[objetivo]
    info = descubrir_juegos()[objetivo].info()
    assert info.id == objetivo
    assert info.nombre
    assert info.prefijos_romfs == prefijos
    assert info.cros == cros
    assert info.capacidades == frozenset()
    assert esquemas.validar(info.to_json(), "info_objetivo") == []


@pytest.mark.parametrize("objetivo", list(OBJETIVOS))
def test_perfil_texto_v20_bloqueado(objetivo: str) -> None:
    perfil = descubrir_juegos()[objetivo].perfil_texto()
    assert perfil.nombre == "tipografia_v20"
    assert perfil.bloqueado is True


@pytest.mark.parametrize("objetivo", list(OBJETIVOS))
@pytest.mark.parametrize("tipo", TIPOS)
def test_toda_accion_es_not_supported(objetivo: str, tipo: str, tmp_path: Path) -> None:
    juego = descubrir_juegos()[objetivo]
    ref = _ref(objetivo, tipo, f"{OBJETIVOS[objetivo][2][0]}data/x.bin")
    for res in (
        juego.exportar(None, ref, tmp_path / "salida"),
        juego.importar(None, ref, tmp_path / "entrada", simular=True),
    ):
        assert res.ok is False
        assert [i.codigo for i in res.incidencias] == ["NOT_SUPPORTED"]
        assert res.incidencias[0].activo_id == ref.id
        assert objetivo in res.incidencias[0].mensaje  # el mensaje nombra el objetivo


@pytest.mark.parametrize("objetivo", list(OBJETIVOS))
def test_inventario_y_reglas(objetivo: str) -> None:
    juego = descubrir_juegos()[objetivo]
    assert isinstance(juego, JuegoBase)
    assert juego.activos(None) == []
    reglas = juego.reglas_validacion()
    assert reglas and all(isinstance(r, Regla) for r in reglas)
    assert {r.codigo for r in reglas} >= {"V20_BLOQUEADO"}


def test_las_versiones_comparten_la_base_de_su_juego() -> None:
    assert not issubclass(JuegoIE2, JuegoIE3) and not issubclass(JuegoIE3, JuegoIE2)
    for objetivo, (_paquete, base, _p, _c) in OBJETIVOS.items():
        esperada = JuegoIE2 if objetivo.startswith("ie2.") else JuegoIE3
        assert base is esperada
