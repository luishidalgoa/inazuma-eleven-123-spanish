"""Registro de activos (F2.1, T3): escaneo perezoso, caché y cancelación.

Sin ROM: el archive.fa es SINTÉTICO y se genera aquí mismo (Norma 2). Nada se
escribe fuera de tmp_path.
"""

from __future__ import annotations

import dataclasses
import json
import struct
from pathlib import Path
from types import SimpleNamespace

import pytest

from ie123kit.nucleo import util
from ie123kit.nucleo.errores import CanceladoError
from ie123kit.nucleo.juego import CAPACIDAD_POR_TIPO, CAPACIDADES, InfoObjetivo, JuegoBase, es_editable
from ie123kit.nucleo.tipos import CancelToken
from ie123kit.servicio import registro_activos as R


def _fa_sintetico(ruta: Path, ficheros: dict[str, bytes]) -> Path:
    """Escribe un contenedor B123 mínimo que FaArchive sabe recorrer."""
    carpetas: dict[str, list[tuple[str, bytes]]] = {}
    for rel, datos in ficheros.items():
        carpeta, _, nombre = rel.rpartition("/")
        carpetas.setdefault(carpeta + "/" if carpeta else "", []).append((nombre, datos))
    nombres, datos_blob, de, fe = bytearray(), bytearray(), bytearray(), bytearray()
    primero = 0
    for carpeta, lista in carpetas.items():
        dir_name_off = len(nombres)
        nombres += carpeta.encode("ascii") + b"\0"
        name_base = len(nombres)
        for nombre, datos in lista:
            fe += struct.pack("<IIII", 0, len(nombres) - name_base, len(datos_blob), len(datos))
            nombres += nombre.encode("ascii") + b"\0"
            datos_blob += datos
        de += struct.pack("<IHHIIII", 0, len(lista), 0, name_base, primero, 0, dir_name_off)
        primero += len(lista)
    de_off = 32
    fe_off = de_off + len(de)
    name_off = fe_off + len(fe)
    data_off = name_off + len(nombres)
    cabecera = b"B123" + struct.pack("<5i", de_off, de_off, fe_off, name_off, data_off)
    cabecera += struct.pack("<HHI", len(carpetas), 0, primero)
    ruta.write_bytes(cabecera + de + fe + nombres + datos_blob)
    return ruta


FICHEROS = {
    "inazuma1/data_iz/text/uno.str": b"texto uno",
    "inazuma1/data_iz/img/hoja.arc": b"grafico" * 3,
    "inazuma1/data_iz/evt/e.eve": b"evento",
    "inazuma1/data_iz/misc/raro.xyz": b"algo",
    "menu/data/otro.str": b"fuera del prefijo",
}


class JuegoFalso(JuegoBase):
    """Juego mínimo apoyado en el activos.toml real de ie1 (prefijos_fa = inazuma1/)."""

    PAQUETE = "ie123kit.ie1"


class JuegoConCapacidades(JuegoFalso):
    """Objetivo que YA declara capacidades, como hará cada juego en F2.3."""

    CAPACIDADES_DECLARADAS = frozenset({"textos", "graficos"})

    def info(self) -> InfoObjetivo:
        return dataclasses.replace(super().info(), capacidades=self.CAPACIDADES_DECLARADAS)


@pytest.fixture
def juego():
    return JuegoFalso()


class WorkspaceFalso:
    """Doble de Workspace: solo `work`, `candidatas` y `dirs()`."""

    def __init__(self, raiz: Path):
        self.work = raiz / "work"
        self.candidatas = raiz / "candidatas"

    def dirs(self, objetivo: str):
        base = self.work / objetivo
        return SimpleNamespace(
            raiz=base,
            capas=base / "capas",
            qa=base / "qa",
            exportaciones=base / "exportaciones",
            registro=base / "registro.json",
        )


@pytest.fixture
def ws(tmp_path):
    return WorkspaceFalso(tmp_path)


@pytest.fixture
def base(tmp_path):
    return _fa_sintetico(tmp_path / "archive.fa", FICHEROS)


def _por_ruta(registro):
    return {a.ruta_romfs: a for a in registro.activos}


def test_filtra_por_prefijo_y_deduce_tipo(ws, juego, base):
    reg = R.construir(ws, juego, base=base)
    rutas = _por_ruta(reg)
    assert "menu/data/otro.str" not in rutas
    assert set(rutas) == {r for r in FICHEROS if r.startswith("inazuma1/")}
    assert rutas["inazuma1/data_iz/text/uno.str"].tipo == "texto"
    assert rutas["inazuma1/data_iz/img/hoja.arc"].tipo == "grafico"
    assert rutas["inazuma1/data_iz/evt/e.eve"].tipo == "evento"
    assert rutas["inazuma1/data_iz/misc/raro.xyz"].tipo == "binario"


def test_campos_del_assetref(ws, juego, base):
    reg = R.construir(ws, juego, base=base)
    ref = _por_ruta(reg)["inazuma1/data_iz/text/uno.str"]
    assert ref.id == "ie1:texto:inazuma1/data_iz/text/uno.str"
    assert ref.objetivo == "ie1"
    assert ref.cadena_contenedores == ("fa",)
    assert ref.tamano == len(FICHEROS["inazuma1/data_iz/text/uno.str"])
    assert ref.sha256 == util.sha256_bytes(FICHEROS["inazuma1/data_iz/text/uno.str"])
    assert ref.estado == "original"
    assert ref.origen == "3ds_jp"
    # `editable` sigue a las capacidades que ie1 declare en su activos.toml, sean las que sean:
    # el test no se ata a la lista de hoy (en F2.3 ie1 pasa a declararlas todas).
    assert ref.editable is es_editable("texto", juego.info().capacidades)


def test_editable_sigue_las_capacidades_declaradas(ws, base):
    """`editable` traduce tipo -> capacidad; sin traducción salía siempre False (#47)."""
    rutas = _por_ruta(R.construir(ws, JuegoConCapacidades(), base=base))
    assert rutas["inazuma1/data_iz/text/uno.str"].editable is True  # texto -> textos
    assert rutas["inazuma1/data_iz/img/hoja.arc"].editable is True  # grafico -> graficos
    assert rutas["inazuma1/data_iz/evt/e.eve"].editable is False  # eventos no declarada
    assert rutas["inazuma1/data_iz/misc/raro.xyz"].editable is False  # binario: sin capacidad


def test_vocabularios_de_tipo_y_capacidad_no_se_confunden():
    """Los dos vocabularios son disjuntos: solo CAPACIDAD_POR_TIPO los une."""
    tipos = set(R.EXTENSIONES.values())
    assert not (tipos & set(CAPACIDADES))
    assert set(CAPACIDAD_POR_TIPO) == tipos
    assert set(CAPACIDAD_POR_TIPO.values()) == set(CAPACIDADES)
    assert R.TIPO_POR_DEFECTO not in CAPACIDAD_POR_TIPO


def test_to_json_forma_exacta(ws, juego, base):
    reg = R.construir(ws, juego, base=base)
    d = reg.to_json()
    assert list(d) == ["esquema", "objetivo", "base_sha256", "generado_en", "activos"]
    assert d["esquema"] == 1
    assert d["objetivo"] == "ie1"
    assert d["base_sha256"] == util.sha256_file(base)
    assert d["generado_en"].endswith("Z")
    texto = json.dumps(d, ensure_ascii=False)
    assert json.loads(texto)["activos"][0]["objetivo"] == "ie1"
    for activo in d["activos"]:
        assert None not in activo.values()


def test_ida_y_vuelta_guardar_cargar(ws, juego, base):
    reg = R.construir(ws, juego, base=base)
    destino = R.guardar(ws, reg)
    assert destino == ws.dirs("ie1").registro and destino.is_file()
    leido = R.cargar(ws, "ie1")
    assert leido is not None
    assert leido.to_json() == reg.to_json()


def test_cargar_devuelve_none_si_falta_o_es_invalido(ws):
    assert R.cargar(ws, "ie1") is None
    ruta = ws.dirs("ie1").registro
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text("{esto no es json", encoding="utf-8")
    assert R.cargar(ws, "ie1") is None


def test_obtener_usa_la_cache_y_la_invalida(ws, juego, base, monkeypatch):
    llamadas = {"n": 0}
    real = R.construir

    def espia(*args, **kwargs):
        llamadas["n"] += 1
        return real(*args, **kwargs)

    monkeypatch.setattr(R, "construir", espia)

    R.obtener(ws, juego, base=base)
    assert llamadas["n"] == 1
    R.obtener(ws, juego, base=base)
    assert llamadas["n"] == 1  # caché válida: no se vuelve a escanear

    _fa_sintetico(base, dict(FICHEROS, **{"inazuma1/data_iz/text/dos.str": b"nuevo"}))
    reg = R.obtener(ws, juego, base=base)
    assert llamadas["n"] == 2
    assert "inazuma1/data_iz/text/dos.str" in _por_ruta(reg)


def test_base_ausente_da_registro_vacio(ws, juego, tmp_path):
    reg = R.construir(ws, juego, base=tmp_path / "no_existe.fa")
    assert reg.objetivo == "ie1"
    assert reg.base_sha256 == ""
    assert reg.activos == ()


def test_progreso_monotono(ws, juego, base):
    vistos = []

    def cb(p):
        for nombre in ("hecho", "actual", "n", "completado", "valor"):
            if hasattr(p, nombre):
                vistos.append(getattr(p, nombre))
                return
        pytest.fail("Progreso sin contador reconocible")

    R.construir(ws, juego, base=base, progreso=cb)
    assert vistos
    assert vistos == sorted(vistos)


def test_cancelacion(ws, juego, base):
    token = CancelToken()
    token.cancelar()
    with pytest.raises(CanceladoError):
        R.construir(ws, juego, base=base, cancel=token)


def test_familias_derivadas_del_activos_toml(juego):
    fams = R.familias(juego)
    assert fams
    assert {f.prefijo_romfs for f in fams} == {"inazuma1/", "inazuma1/data_iz/font/"}
    assert all(f.perfil_texto == "tipografia_v20" for f in fams)
    assert all(f.contenedores == ("fa",) for f in fams)
    assert {f.ambito for f in fams} == {"editable", "solo_lectura"}
    assert "texto" in {f.tipo for f in fams}


def test_estado_de(ws, juego, base):
    ref = R.construir(ws, juego, base=base).activos[0]
    assert R.estado_de(ref) == "original"
    assert R.estado_de(ref, sha_candidata=ref.sha256) == "original"
    assert R.estado_de(ref, sha_candidata="0" * 64) == "construido"


class JuegoMenu(JuegoBase):
    """Objetivo del menú: su `activos.toml` declara `[romfs].solo_lectura` (fuentes v20)."""

    PAQUETE = "ie123kit.juego_principal"


class JuegoMenuConCapacidades(JuegoMenu):
    """Igual, pero declarando capacidades: el bloqueo de solo_lectura tiene que ganarles."""

    def info(self) -> InfoObjetivo:
        return dataclasses.replace(super().info(), capacidades=frozenset({"textos", "graficos"}))


def _prefijos_del_menu() -> tuple[str, str]:
    """(prefijo editable, prefijo de solo lectura) leídos del activos.toml real."""
    romfs = R._activos_toml(JuegoMenu()).get("romfs", {})
    return str(romfs["prefijos_fa"][0]), str(romfs["solo_lectura"][0])


def test_escanea_tambien_los_prefijos_de_solo_lectura(ws, tmp_path):
    """Las fuentes bloqueadas por el perfil v20 salen en el inventario, marcadas no editables.

    Antes solo se escaneaba `prefijos_fa`, así que `font/*.bcfnt` no aparecía: era
    indistinguible de «no existe» en vez de «existe y no se toca».
    """
    editable, bloqueado = _prefijos_del_menu()
    ficheros = {
        f"{editable}data/uno.str": b"texto del menu",
        f"{bloqueado}ui.bcfnt": b"fuente bloqueada v20",
        f"{bloqueado}dialogo.str": b"texto dentro de la carpeta bloqueada",
        "otro_juego/x.str": b"fuera de los dos prefijos",
    }
    base = _fa_sintetico(tmp_path / "menu.fa", ficheros)

    rutas = _por_ruta(R.construir(ws, JuegoMenuConCapacidades(), base=base))

    assert f"{bloqueado}ui.bcfnt" in rutas
    assert "otro_juego/x.str" not in rutas
    assert rutas[f"{editable}data/uno.str"].editable is True  # texto -> textos declarada
    # solo_lectura manda sobre la capacidad declarada: ni el .str de dentro es editable.
    assert rutas[f"{bloqueado}ui.bcfnt"].editable is False
    assert rutas[f"{bloqueado}dialogo.str"].editable is False
