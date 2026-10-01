"""`JuegoBase`: lectura de activos.toml, perfil de texto y despacho por tipo de activo."""

from __future__ import annotations

import dataclasses
from pathlib import Path

from ie123kit.ie2.comun.reglas import JuegoIE2
from ie123kit.ie3.comun.reglas import JuegoIE3
from ie123kit.nucleo.juego import CAPACIDADES, Aportacion, InfoObjetivo, JuegoBase, PerfilTexto, Regla
from ie123kit.nucleo.tipos import AssetRef, Incidencia, Resultado, componer_id

RUTA = "inazuma1/data_iz/a_title/title_t.arc"


class JuegoDePrueba(JuegoBase):
    """Objetivo mínimo sobre un paquete real ya existente."""

    PAQUETE = "ie123kit.ie1"


class JuegoSinGraficos(JuegoDePrueba):
    """Objetivo que declara capacidades, pero NO ``graficos``.

    Desde F2.3 ie1 declara las seis capacidades, así que el despacho «sin capacidad»
    hay que probarlo con un objetivo que deje fuera la que se pide (aquí, gráficos).
    """

    def info(self) -> InfoObjetivo:
        return dataclasses.replace(super().info(), capacidades=frozenset({"textos"}))


def _ref(tipo: str) -> AssetRef:
    return AssetRef(id=componer_id("ie1", tipo, RUTA), objetivo="ie1", tipo=tipo, ruta_romfs=RUTA)


def test_info_desde_activos_toml() -> None:
    info = JuegoDePrueba().info()
    assert info.id == "ie1"
    assert info.nombre == "Inazuma Eleven"
    assert info.prefijos_romfs == ("inazuma1/",)
    assert info.cros == ("cro/ina_main1.cro",)
    assert all(c in CAPACIDADES for c in info.capacidades)
    datos = info.to_json()
    assert datos["capacidades"] == sorted(datos["capacidades"])


def test_info_cacheada() -> None:
    juego = JuegoDePrueba()
    assert juego.info() is juego.info()


def test_perfil_texto_bloqueado() -> None:
    perfil = JuegoDePrueba().perfil_texto()
    assert isinstance(perfil, PerfilTexto)
    assert perfil.nombre == "tipografia_v20"
    assert perfil.bloqueado is True


def test_ie1_declara_sus_capacidades() -> None:
    """Tras F2.3 el activos.toml de ie1 declara las seis capacidades del vocabulario."""
    assert JuegoDePrueba().info().capacidades == frozenset(CAPACIDADES)


def test_sin_capacidad_devuelve_not_supported(tmp_path: Path) -> None:
    juego = JuegoSinGraficos()
    ref = _ref("grafico")
    assert "graficos" not in juego.info().capacidades

    exportado = juego.exportar(None, ref, tmp_path / "salida.png")
    importado = juego.importar(None, ref, tmp_path / "entrada.png", simular=True)
    for res in (exportado, importado):
        assert res.ok is False
        assert [i.codigo for i in res.incidencias] == ["NOT_SUPPORTED"]
        assert res.incidencias[0].activo_id == ref.id


def test_tipo_desconocido_tambien_es_not_supported(tmp_path: Path) -> None:
    res = JuegoDePrueba().exportar(None, _ref("inventado"), tmp_path / "x")
    assert not res.ok and res.incidencias[0].codigo == "NOT_SUPPORTED"


def test_defectos_vacios() -> None:
    juego = JuegoDePrueba()
    assert juego.activos(None) == []
    assert juego.reglas_validacion() == []
    aportacion = juego.aportaciones(None, [])
    assert isinstance(aportacion, Aportacion)
    assert aportacion.entradas_fa == {} and aportacion.eventos == {}
    assert aportacion.literales_cro == {} and aportacion.romfs_sueltos == {}


def test_aportaciones_no_comparten_diccionarios() -> None:
    a, b = Aportacion(), Aportacion()
    a.entradas_fa["x"] = b"1"
    assert b.entradas_fa == {}


# --------------------------------------------------------------- bases compartidas de ie2/ie3


def test_bases_compartidas_derivan_de_juego_base() -> None:
    for base in (JuegoIE2, JuegoIE3):
        assert issubclass(base, JuegoBase)


def test_base_ie2_sin_capacidades_rechaza_todo(tmp_path: Path) -> None:
    class Prueba(JuegoIE2):
        PAQUETE = "ie123kit.ie2.tormenta_de_fuego"

    juego = Prueba()
    assert juego.info().capacidades == frozenset()
    ref = _ref("texto")
    res = juego.exportar(None, ref, tmp_path / "salida")
    assert not res.ok and res.incidencias[0].codigo == "NOT_SUPPORTED"
    assert juego.info().id in res.incidencias[0].mensaje
    reglas = juego.reglas_validacion()
    assert all(isinstance(r, Regla) for r in reglas)
    assert {r.codigo for r in reglas} >= {"V20_BLOQUEADO"}


class JuegoQueCreaCapa(JuegoDePrueba):
    """Crea su carpeta de capa y luego falla o revienta, según ``modo``."""

    def __init__(self, raiz: Path, modo: str) -> None:
        super().__init__()
        self.raiz, self.modo = raiz, modo

    def _importar_graficos(self, ws, ref, origen, **kw):
        carpeta = self.raiz / "capas" / "graficos" / "gui_x"
        carpeta.mkdir(parents=True)
        (carpeta / "capa.toml").write_text("[capa]\n", encoding="utf-8")
        self._capa_creada(carpeta)
        if self.modo == "excepcion":
            raise RuntimeError("fallo a medias")
        if self.modo == "fallo":
            return Resultado.fallo([Incidencia("NOT_SUPPORTED", "error", "no cabe")])
        return Resultado.correcto()


def test_una_importacion_fallida_no_deja_la_capa_creada(tmp_path: Path) -> None:
    import pytest

    for modo in ("fallo", "excepcion"):
        juego = JuegoQueCreaCapa(tmp_path / modo, modo)
        if modo == "excepcion":
            with pytest.raises(RuntimeError):
                juego.importar(None, _ref("grafico"), tmp_path / "x.png", simular=False)
        else:
            assert not juego.importar(None, _ref("grafico"), tmp_path / "x.png", simular=False).ok
        assert not (tmp_path / modo / "capas" / "graficos" / "gui_x").exists()
    bien = JuegoQueCreaCapa(tmp_path / "ok", "ok")
    assert bien.importar(None, _ref("grafico"), tmp_path / "x.png", simular=False).ok
    assert (tmp_path / "ok" / "capas" / "graficos" / "gui_x" / "capa.toml").is_file()
