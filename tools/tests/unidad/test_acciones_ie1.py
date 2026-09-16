"""Ganchos reales del objetivo IE1 (F2.3), sobre datos sintéticos: ni un byte de ROM (Norma 2)."""

from __future__ import annotations

import struct
from itertools import pairwise
from pathlib import Path

import pytest

from ie123kit.ie1.acciones import CABECERA_TSV, JuegoIE1
from ie123kit.nucleo import util
from ie123kit.nucleo.errores import CanceladoError
from ie123kit.nucleo.tipos import AssetRef, CancelToken, Progreso, Resultado, componer_id
from ie123kit.servicio import esquemas
from ie123kit.servicio.proyecto import Workspace

IE123_TOML = """\
[proyecto]
idioma = "es-ES"

[candidatas]
patron = "probe_ie1_v{n}"

[objetivos]
habilitados = ["ie1"]
"""

TABLA = "inazuma1/data_iz/item.dat"
FUENTE = "inazuma1/data_iz/font/FONT12.bcfnt"
VOZ = "inazuma1/data_iz/sound/voice_0001.SAD"
EVENTOS = "inazuma1/data_iz/script/eve.pkb"


def _bytes_fa(ficheros: dict[str, bytes]) -> bytes:
    """Contenedor B123 mínimo (misma construcción que tools/tests/contrato/fa_sintetico.py)."""
    carpetas: dict[str, list[tuple[str, bytes]]] = {}
    for rel, datos in ficheros.items():
        carpeta, _, nombre = rel.rpartition("/")
        carpetas.setdefault(carpeta + "/" if carpeta else "", []).append((nombre, datos))
    nombres, blob, de, fe = bytearray(), bytearray(), bytearray(), bytearray()
    primero = 0
    for carpeta, lista in carpetas.items():
        dir_name_off = len(nombres)
        nombres += carpeta.encode("ascii") + b"\0"
        name_base = len(nombres)
        for nombre, datos in lista:
            fe += struct.pack("<IIII", 0, len(nombres) - name_base, len(blob), len(datos))
            nombres += nombre.encode("ascii") + b"\0"
            blob += datos
        de += struct.pack("<IHHIIII", 0, len(lista), 0, name_base, primero, 0, dir_name_off)
        primero += len(lista)
    de_off = 32
    fe_off = de_off + len(de)
    name_off = fe_off + len(fe)
    data_off = name_off + len(nombres)
    cabecera = b"B123" + struct.pack("<5i", de_off, de_off, fe_off, name_off, data_off)
    cabecera += struct.pack("<HHI", len(carpetas), 0, primero)
    return bytes(cabecera + de + fe + nombres + blob)


def _registro(nombre: bytes) -> bytes:
    return nombre.ljust(19, b"\0") + bytes(13)


@pytest.fixture
def ws(tmp_path: Path) -> Workspace:
    """Repo sintético con base_3ds mínima: tabla de 32 B, una fuente y un SADL de mentira."""
    raiz = tmp_path / "repo"
    (raiz / "tools").mkdir(parents=True)
    (raiz / "AGENTS.md").write_text("# repo sintético\n", encoding="utf-8")
    (raiz / "tools" / "pyproject.toml").write_text('[project]\nname = "ie123kit"\n', encoding="utf-8")
    (raiz / "ie123.toml").write_text(IE123_TOML, encoding="utf-8")
    romfs = raiz / "work" / "shared" / "base_3ds" / "romfs"
    romfs.mkdir(parents=True)
    (romfs / "archive.fa").write_bytes(
        _bytes_fa({TABLA: _registro(b"aaa") + _registro(b"bbb"), FUENTE: b"FONT" * 4})
    )
    (romfs / "cro").mkdir()
    (romfs / "cro" / "ina_main1.cro").write_bytes(b"CRO0" * 8)
    sonido = romfs / "inazuma1" / "data_iz" / "sound"
    sonido.mkdir(parents=True)
    (sonido / "voice_0001.SAD").write_bytes(b"sadl" + bytes(0x60))
    return Workspace.abrir(raiz, entorno={})


@pytest.fixture
def juego() -> JuegoIE1:
    return JuegoIE1()


def _ref(tipo: str, ruta: str, tamano: int = 32) -> AssetRef:
    return AssetRef(
        id=componer_id("ie1", tipo, ruta),
        objetivo="ie1",
        tipo=tipo,
        ruta_romfs=ruta,
        cadena_contenedores=("fa",) if ruta.startswith("inazuma1/") else (),
        tamano=tamano,
        editable=True,
    )


def _escribir_tsv(ruta: Path, filas: list[list[object]]) -> Path:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    lineas = ["\t".join(CABECERA_TSV), *["\t".join(str(c) for c in fila) for fila in filas]]
    ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    return ruta


# --------------------------------------------------------------------------- identidad


def test_info_declara_las_seis_capacidades(juego: JuegoIE1) -> None:
    info = juego.info()
    assert info.id == "ie1"
    assert set(info.capacidades) == {
        "graficos", "textos", "eventos", "literales_cro", "cinematicas", "voces",
    }
    assert esquemas.validar(info.to_json(), "info_objetivo") == []


def test_perfil_texto_bloqueado(juego: JuegoIE1) -> None:
    perfil = juego.perfil_texto()
    assert perfil.nombre == "tipografia_v20"
    assert perfil.bloqueado is True


def test_reglas_de_validacion(juego: JuegoIE1) -> None:
    codigos = {r.codigo for r in juego.reglas_validacion()}
    assert {"ENTRADAS_IDENTICAS", "CRO_SOLO_LITERALES", "FUENTES_INTACTAS",
            "AUDIO_IDENTICO", "LAYOUT_MOFLEX"} <= codigos


def test_activos_fuera_del_archive(juego: JuegoIE1, ws: Workspace) -> None:
    refs = juego.activos(ws)
    rutas = {r.ruta_romfs: r for r in refs}
    assert set(rutas) == {"cro/ina_main1.cro", VOZ}
    assert rutas["cro/ina_main1.cro"].tipo == "literal_cro"
    assert rutas[VOZ].tipo == "voz"
    assert all(r.cadena_contenedores == () for r in refs)
    assert all(r.editable for r in refs)


def test_activos_sin_rom_no_lanza(juego: JuegoIE1, tmp_path: Path) -> None:
    raiz = tmp_path / "vacio"
    (raiz / "tools").mkdir(parents=True)
    (raiz / "AGENTS.md").write_text("#\n", encoding="utf-8")
    (raiz / "tools" / "pyproject.toml").write_text('[project]\n', encoding="utf-8")
    assert JuegoIE1().activos(Workspace.abrir(raiz, entorno={})) == []


# --------------------------------------------------------------------------- bloqueos


def test_importar_sobre_las_fuentes_da_bloqueo_v20(juego: JuegoIE1, ws: Workspace, tmp_path: Path) -> None:
    origen = tmp_path / "png"
    origen.mkdir()
    antes = util.sha256_arbol(ws.raiz)
    res = juego.importar(ws, _ref("grafico", FUENTE), origen, simular=False)
    assert isinstance(res, Resultado) and not res.ok
    assert [i.codigo for i in res.incidencias] == ["BLOQUEO_V20"]
    assert util.sha256_arbol(ws.raiz) == antes


def test_importar_voz_wav_no_soportado(juego: JuegoIE1, ws: Workspace, tmp_path: Path) -> None:
    wav = tmp_path / "voz.wav"
    wav.write_bytes(b"RIFF")
    res = juego.importar(ws, _ref("voz", VOZ), wav, simular=False)
    assert not res.ok
    assert [i.codigo for i in res.incidencias] == ["NOT_SUPPORTED"]


def test_evento_protegido_se_rechaza(juego: JuegoIE1, ws: Workspace, tmp_path: Path) -> None:
    origen = tmp_path / "eve"
    _escribir_tsv(origen / "81000040.tsv", [[1, "テスト", "", "Hola", 0, 0, "traducido"]])
    antes = util.sha256_arbol(ws.raiz)
    res = juego.importar(ws, _ref("evento", EVENTOS), origen, simular=False)
    assert not res.ok
    assert any("81000040" in i.mensaje for i in res.incidencias)
    assert util.sha256_arbol(ws.raiz) == antes


def test_simular_no_escribe_nada(juego: JuegoIE1, ws: Workspace, tmp_path: Path) -> None:
    tsv = _escribir_tsv(tmp_path / "tabla.tsv", [[0, "aaa", "", "Balon", 0, 19, "traducido"]])
    antes = util.sha256_arbol(ws.raiz)
    res = juego.importar(ws, _ref("texto", TABLA, 64), tsv, simular=True)
    assert isinstance(res, Resultado)
    assert esquemas.validar(res.to_json(), "resultado") == []
    assert util.sha256_arbol(ws.raiz) == antes


def test_cabecera_tsv_incorrecta_se_denuncia(juego: JuegoIE1, ws: Workspace, tmp_path: Path) -> None:
    tsv = tmp_path / "malo.tsv"
    tsv.write_text("id\ttexto\n0\tHola\n", encoding="utf-8")
    res = juego.importar(ws, _ref("texto", TABLA, 64), tsv, simular=True)
    assert not res.ok


# --------------------------------------------------------------------------- progreso y cancelación


def test_progreso_monotono_al_exportar_tabla(juego: JuegoIE1, ws: Workspace, tmp_path: Path) -> None:
    eventos: list[Progreso] = []
    res = juego.exportar(ws, _ref("texto", TABLA, 64), tmp_path / "tabla.tsv", progreso=eventos.append)
    assert res.ok, res.to_json()
    assert esquemas.validar(res.to_json(), "resultado") == []
    assert eventos and {e.total for e in eventos} == {2}
    for previo, siguiente in pairwise(eventos):
        assert siguiente.actual >= previo.actual
    assert (tmp_path / "tabla.tsv").read_text(encoding="utf-8").startswith("\t".join(CABECERA_TSV))


def test_cancelacion_corta_la_exportacion(juego: JuegoIE1, ws: Workspace, tmp_path: Path) -> None:
    cancel = CancelToken()
    cancel.cancelar()
    with pytest.raises(CanceladoError):
        juego.exportar(ws, _ref("texto", TABLA, 64), tmp_path / "tabla.tsv", cancel=cancel)


# --------------------------------------------------------------------------- aportaciones


def test_aportaciones_de_una_capa_sintetica(juego: JuegoIE1, ws: Workspace) -> None:
    capa = ws.work / "ie1" / "capas" / "v1" / "gui_20260101_0000"
    (capa / "extra" / "inazuma1" / "data_iz").mkdir(parents=True)
    (capa / "extra" / "inazuma1" / "data_iz" / "a_title.arc").write_bytes(b"ARC")
    (capa / "events").mkdir(parents=True)
    (capa / "events" / "90000000.ssd").write_bytes(b"SSD")
    (capa / "romfs" / "cro").mkdir(parents=True)
    (capa / "romfs" / "cro" / "ina_main1.cro").write_bytes(b"CRO0")
    (capa / "capa.toml").write_text('[capa]\nobjetivo = "ie1"\n', encoding="utf-8")

    aportacion = juego.aportaciones(ws)
    assert set(aportacion.entradas_fa) == {"inazuma1/data_iz/a_title.arc"}
    assert all(isinstance(v, Path) and v.is_file() for v in aportacion.entradas_fa.values())
    assert set(aportacion.eventos) == {"eve"}
    assert set(aportacion.romfs_sueltos) == {"cro/ina_main1.cro"}


def test_aportaciones_sin_capas(juego: JuegoIE1, ws: Workspace) -> None:
    aportacion = juego.aportaciones(ws)
    assert aportacion.entradas_fa == {} and aportacion.eventos == {} and aportacion.romfs_sueltos == {}
