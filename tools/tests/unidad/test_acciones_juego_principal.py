"""Acciones del objetivo `juego_principal` (F2.3, #49) sin ROM: archive.fa sintético."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from ie123kit.juego_principal import JUEGO
from ie123kit.juego_principal.acciones import OBJETIVO, JuegoPrincipal
from ie123kit.nucleo import util
from ie123kit.nucleo.tipos import AssetRef, Resultado, componer_id
from ie123kit.servicio import esquemas
from ie123kit.servicio.proyecto import Workspace

CONTRATO = Path(__file__).resolve().parent.parent / "contrato"
if str(CONTRATO) not in sys.path:
    sys.path.insert(0, str(CONTRATO))

from fa_sintetico import escribir_fa  # sys.path se prepara justo arriba

FICHEROS = {
    "menu/title.arc": b"ARCV-falso-title",
    "menu/common.arc": b"ARCV-falso-common",
    "font/FONT12T.bcfnt": b"CFNT-falso",
    "message/jp/GameString.str": b"hola\x00mundo\x00",
}

IE123_TOML = """\
[proyecto]
idioma = "es-ES"

[candidatas]
patron = "probe_ie1_v{n}"
"""


@pytest.fixture
def ws(tmp_path: Path) -> Workspace:
    """Proyecto sintético mínimo con el archive.fa de pruebas (ni un byte de ROM)."""
    raiz = tmp_path / "repo"
    (raiz / "tools").mkdir(parents=True)
    (raiz / "AGENTS.md").write_text("# repo sintético\n", encoding="utf-8")
    (raiz / "tools" / "pyproject.toml").write_text('[project]\nname = "ie123kit"\n', encoding="utf-8")
    (raiz / "ie123.toml").write_text(IE123_TOML, encoding="utf-8")
    escribir_fa(raiz / "work" / "shared" / "base_3ds" / "romfs" / "archive.fa", FICHEROS)
    return Workspace.abrir(raiz, entorno={})


@pytest.fixture
def juego() -> JuegoPrincipal:
    return JuegoPrincipal()


def _ref(tipo: str, ruta: str, **kw) -> AssetRef:
    return AssetRef(id=componer_id(OBJETIVO, tipo, ruta), objetivo=OBJETIVO, tipo=tipo,
                    ruta_romfs=ruta, **kw)


def test_el_paquete_declara_el_juego() -> None:
    assert JUEGO is JuegoPrincipal
    assert JuegoPrincipal.PAQUETE == "ie123kit.juego_principal"


def test_info_valida_y_declara_las_cuatro_capacidades(juego: JuegoPrincipal) -> None:
    info = juego.info()
    assert esquemas.validar(info.to_json(), "info_objetivo") == []
    assert info.id == OBJETIVO
    assert set(info.capacidades) == {"graficos", "textos", "literales_cro", "cinematicas"}


def test_perfil_texto_bloqueado(juego: JuegoPrincipal) -> None:
    perfil = juego.perfil_texto()
    assert perfil.nombre == "tipografia_v20"
    assert perfil.bloqueado is True


def test_importar_fuente_da_bloqueo_v20_sin_escribir(juego: JuegoPrincipal, ws: Workspace,
                                                     tmp_path: Path) -> None:
    entrada = tmp_path / "FONT12T.bcfnt"
    entrada.write_bytes(b"CFNT-nuevo")
    antes = util.sha256_arbol(ws.raiz)
    res = juego.importar(ws, _ref("binario", "font/FONT12T.bcfnt"), entrada, simular=False)
    assert isinstance(res, Resultado) and not res.ok
    assert [i.codigo for i in res.incidencias] == ["BLOQUEO_V20"]
    assert util.sha256_arbol(ws.raiz) == antes


def test_importar_exefs_da_not_supported(juego: JuegoPrincipal, ws: Workspace, tmp_path: Path) -> None:
    entrada = tmp_path / "banner.bnr"
    entrada.write_bytes(b"SMDH")
    res = juego.importar(ws, _ref("ejecutable", "banner.bnr"), entrada, simular=False)
    assert not res.ok
    assert [i.codigo for i in res.incidencias] == ["NOT_SUPPORTED"]


@pytest.mark.parametrize(("tipo", "ruta"), [("voz", "menu/voz.sad"), ("evento", "menu/x.eve")])
def test_capacidad_no_declarada_da_not_supported(juego: JuegoPrincipal, ws: Workspace,
                                                 tmp_path: Path, tipo: str, ruta: str) -> None:
    res = juego.exportar(ws, _ref(tipo, ruta), tmp_path / "salida")
    assert not res.ok
    assert any(i.codigo == "NOT_SUPPORTED" for i in res.incidencias)


def test_exportar_textos_escribe_tsv_con_las_columnas_exactas(juego: JuegoPrincipal, ws: Workspace,
                                                              tmp_path: Path) -> None:
    ref = _ref("texto", "message/jp/GameString.str", cadena_contenedores=("fa",))
    res = juego.exportar(ws, ref, tmp_path / "exp")
    assert res.ok, res.to_json()
    tsv = Path(res.artefactos[0])
    cabecera = tsv.read_text(encoding="utf-8").splitlines()[0].split("\t")
    assert cabecera == ["id", "jp", "es_oficial", "traduccion", "max_px", "max_bytes", "estado"]
    assert res.datos["cadenas"] == 2


def test_importar_simular_no_escribe(juego: JuegoPrincipal, ws: Workspace, tmp_path: Path) -> None:
    ref = _ref("texto", "message/jp/GameString.str", cadena_contenedores=("fa",))
    exportado = juego.exportar(ws, ref, tmp_path / "exp")
    tsv = Path(exportado.artefactos[0])
    lineas = tsv.read_text(encoding="utf-8").splitlines()
    campos = lineas[1].split("\t")
    campos[3] = "hey"
    lineas[1] = "\t".join(campos)
    tsv.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    antes = util.sha256_arbol(ws.raiz)
    res = juego.importar(ws, ref, tsv, simular=True)
    assert res.ok, res.to_json()
    assert res.datos["simulado"] is True and res.datos["cambios"]
    assert util.sha256_arbol(ws.raiz) == antes


def test_activos_sin_rom_esta_vacio(juego: JuegoPrincipal, ws: Workspace) -> None:
    assert juego.activos(ws) == []


def test_activos_lista_cro_y_exefs(juego: JuegoPrincipal, ws: Workspace) -> None:
    base = ws.work / "shared" / "base_3ds"
    cro = base / "romfs" / "cro" / "ina_menu.cro"
    cro.parent.mkdir(parents=True, exist_ok=True)
    cro.write_bytes(b"CRO0" * 4)
    for nombre in ("banner.bnr", "icon.icn"):
        fichero = base / "exefs" / nombre
        fichero.parent.mkdir(parents=True, exist_ok=True)
        fichero.write_bytes(b"SMDH" + bytes(16))
    refs = juego.activos(ws)
    ids = {r.id for r in refs}
    assert ids == {
        componer_id(OBJETIVO, "literal_cro", "cro/ina_menu.cro"),
        componer_id(OBJETIVO, "ejecutable", "banner.bnr"),
        componer_id(OBJETIVO, "ejecutable", "icon.icn"),
    }
    assert all(r.cadena_contenedores == () for r in refs)
    assert all(not r.editable for r in refs if r.tipo == "ejecutable")
    assert juego.activos(ws, tipo="ejecutable") and not juego.activos(ws, tipo="grafico")


def test_reglas_de_validacion(juego: JuegoPrincipal) -> None:
    codigos = {r.codigo for r in juego.reglas_validacion()}
    assert {"BLOQUEO_V20", "CRO_FUERA_DE_RANGO", "LAYOUT_MOFLEX"} <= codigos


def test_aportaciones_lee_las_capas(juego: JuegoPrincipal, ws: Workspace) -> None:
    capa = ws.work / OBJETIVO / "capas" / "v1" / "gui_20260101_0000"
    (capa / "extra" / "menu").mkdir(parents=True)
    (capa / "extra" / "menu" / "title.arc").write_bytes(b"ARCV-nuevo")
    (capa / "romfs" / "cro").mkdir(parents=True)
    (capa / "romfs" / "cro" / "ina_menu.cro").write_bytes(b"CRO0")
    aportacion = juego.aportaciones(ws)
    assert set(aportacion.entradas_fa) == {"menu/title.arc"}
    assert set(aportacion.romfs_sueltos) == {"cro/ina_menu.cro"}
    assert aportacion.eventos == {}


def test_capa_nueva_va_a_graficos(juego: JuegoPrincipal, ws: Workspace) -> None:
    capa = juego._nueva_capa(ws)
    assert capa.aqui.parent == ws.work / OBJETIVO / "capas" / "graficos"
    assert capa.tema == "graficos" and capa.linea.startswith("gui_")
    (capa.aqui / "extra" / "menu").mkdir(parents=True)
    (capa.aqui / "extra" / "menu" / "title.arc").write_bytes(b"ARCV")
    assert set(juego.aportaciones(ws, capas=[f"graficos/{capa.aqui.name}"]).entradas_fa) == {"menu/title.arc"}
