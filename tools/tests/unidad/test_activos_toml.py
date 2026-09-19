"""activos.toml por objetivo (F1.4 #45, F2.3 #49): esquema 1, declarativo y sin ROM.

Este módulo es el validador del esquema 1 para los siete objetivos (gate 1 de F2.3):
ninguna clave fuera del vocabulario acordado y ningún dato que no sea ruta corta.
"""

import re
import tomllib
from importlib import resources

import pytest

from ie123kit.nucleo.juego import CAPACIDADES

OBJETIVOS = {
    "juego_principal": "ie123kit.juego_principal",
    "ie1": "ie123kit.ie1",
    "ie2.tormenta_de_fuego": "ie123kit.ie2.tormenta_de_fuego",
    "ie2.ventisca_eterna": "ie123kit.ie2.ventisca_eterna",
    "ie3.rayo_celeste": "ie123kit.ie3.rayo_celeste",
    "ie3.fuego_explosivo": "ie123kit.ie3.fuego_explosivo",
    "ie3.amenaza_del_ogro": "ie123kit.ie3.amenaza_del_ogro",
}
CROS_VALIDAS = {"cro/ina_menu.cro", "cro/ina_main1.cro", "cro/ina_main2.cro", "cro/ina_main3ogre.cro"}
UNIDAD = re.compile(r"^[A-Za-z]:")

#: Vocabulario pinchado del esquema 1: tabla -> claves admitidas. Ninguna otra.
VOCABULARIO: dict[str, set[str]] = {
    "objetivo": {
        "id", "nombre", "juego", "version", "comun", "perfil_texto",
        "capacidades", "pendiente_auditoria",
    },
    "romfs": {"prefijos_fa", "cros", "solo_lectura", "sueltos"},
    "exefs": {"experimental", "ficheros"},
    "textos": {"ambitos"},
    "graficos": {"contenedores"},
    "cinematicas": {"rutas"},
    "voces": {"prefijos"},
    "eventos": {"protegidos", "apertura"},
    "familias": {
        "tipo", "prefijo_romfs", "contenedores", "perfil_texto", "ambito", "contrapartida",
    },
}
#: Claves admitidas en la raíz, además de las tablas de VOCABULARIO.
RAIZ = {"esquema"}
AMBITOS_TEXTO = {"eventos", "tablas", "cro", "gamestring"}
CONTENEDORES_GRAFICOS = {"arcv", "ctpk", "qna"}


def _leer(paquete: str) -> dict:
    recurso = resources.files(paquete).joinpath("activos.toml")
    assert recurso.is_file(), f"{paquete}: falta activos.toml"
    return tomllib.loads(recurso.read_text(encoding="utf-8"))


def _cadenas(valor):
    if isinstance(valor, str):
        yield valor
    elif isinstance(valor, dict):
        for v in valor.values():
            yield from _cadenas(v)
    elif isinstance(valor, list):
        for v in valor:
            yield from _cadenas(v)


@pytest.mark.parametrize("objetivo", list(OBJETIVOS))
def test_activos_basicos(objetivo):
    datos = _leer(OBJETIVOS[objetivo])
    assert datos["esquema"] == 1
    obj = datos["objetivo"]
    assert obj["id"] == objetivo
    assert OBJETIVOS[objetivo] == "ie123kit." + obj["id"]
    assert obj["perfil_texto"] == "tipografia_v20"
    assert isinstance(obj["capacidades"], list)
    if objetivo.startswith(("ie2.", "ie3.")):
        assert obj["capacidades"] == []
    romfs = datos["romfs"]
    for prefijo in romfs["prefijos_fa"] + romfs.get("solo_lectura", []):
        assert prefijo.endswith("/") and not prefijo.startswith("/"), prefijo
    assert set(romfs["cros"]) <= CROS_VALIDAS
    for cadena in _cadenas(datos):
        assert ".." not in cadena, cadena
        assert not cadena.startswith(("/", "\\")), cadena
        assert not UNIDAD.match(cadena), cadena


def test_union_de_prefijos():
    union = set()
    for paquete in OBJETIVOS.values():
        union |= set(_leer(paquete)["romfs"]["prefijos_fa"])
    esperados = {
        "inazuma1/",
        "inazuma2/",
        "inazuma3/",
        "inazuma3_ogre/",
        "menu/",
        "movie/",
        "message/",
        "patchscript/",
    }
    assert esperados <= union, esperados - union


def _ruta_relativa_posix(valor: str) -> bool:
    return (
        ".." not in valor.split("/")
        and "\\" not in valor
        and not valor.startswith("/")
        and not UNIDAD.match(valor)
    )


@pytest.mark.parametrize("objetivo", list(OBJETIVOS))
def test_solo_claves_del_vocabulario(objetivo):
    """Ninguna clave ni tabla fuera del vocabulario acordado del esquema 1."""
    datos = _leer(OBJETIVOS[objetivo])
    sobran = set(datos) - RAIZ - set(VOCABULARIO)
    assert not sobran, f"{objetivo}: tablas/claves desconocidas en la raíz: {sorted(sobran)}"
    for tabla, admitidas in VOCABULARIO.items():
        valor = datos.get(tabla)
        if valor is None:
            continue
        entradas = valor if isinstance(valor, list) else [valor]
        for entrada in entradas:
            assert isinstance(entrada, dict), f"{objetivo}: [{tabla}] debe ser tabla"
            desconocidas = set(entrada) - admitidas
            assert not desconocidas, f"{objetivo}: [{tabla}] claves desconocidas: {sorted(desconocidas)}"


@pytest.mark.parametrize("objetivo", list(OBJETIVOS))
def test_capacidades_del_vocabulario(objetivo):
    """`capacidades` es un subconjunto de nucleo.juego.CAPACIDADES."""
    capacidades = _leer(OBJETIVOS[objetivo])["objetivo"]["capacidades"]
    assert set(capacidades) <= set(CAPACIDADES), capacidades
    assert len(set(capacidades)) == len(capacidades), f"{objetivo}: capacidades repetidas"


@pytest.mark.parametrize("objetivo", list(OBJETIVOS))
def test_secciones_opcionales(objetivo):
    """Vocabularios cerrados de [textos] y [graficos], rutas relativas y tipos correctos."""
    datos = _leer(OBJETIVOS[objetivo])
    ambitos = datos.get("textos", {}).get("ambitos", [])
    assert set(ambitos) <= AMBITOS_TEXTO, ambitos
    contenedores = datos.get("graficos", {}).get("contenedores", [])
    assert set(contenedores) <= CONTENEDORES_GRAFICOS, contenedores
    rutas = [
        *datos.get("romfs", {}).get("sueltos", []),
        *datos.get("cinematicas", {}).get("rutas", []),
        *datos.get("voces", {}).get("prefijos", []),
    ]
    for ruta in rutas:
        assert isinstance(ruta, str) and ruta, ruta
        assert _ruta_relativa_posix(ruta), ruta
    exefs = datos.get("exefs")
    if exefs is not None and "experimental" in exefs:
        assert isinstance(exefs["experimental"], bool), exefs["experimental"]


@pytest.mark.parametrize("objetivo", list(OBJETIVOS))
def test_familias_coherentes(objetivo):
    """Cada [[familias]] usa vocabularios cerrados y rutas relativas."""
    for familia in _leer(OBJETIVOS[objetivo]).get("familias", []):
        if "prefijo_romfs" in familia:
            assert _ruta_relativa_posix(familia["prefijo_romfs"]), familia
        assert set(familia.get("contenedores", [])) <= CONTENEDORES_GRAFICOS, familia
        if "ambito" in familia:
            assert familia["ambito"] in AMBITOS_TEXTO, familia
        if "perfil_texto" in familia:
            assert familia["perfil_texto"] == "tipografia_v20", familia
