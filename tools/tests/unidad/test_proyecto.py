"""Tests del Workspace y del manifiesto de candidata (F2.1 T2)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ie123kit.nucleo.config.raiz import find_root
from ie123kit.nucleo.errores import ValidacionError
from ie123kit.servicio.proyecto import ManifiestoCandidata, Workspace

IE123_TOML = """
[proyecto]
idioma = "es-ES"
nombres_europeos = true

[candidatas]
patron = "probe_ie1_v{n}"
conservar = 2
golden = ["probe_ie1_v66", "probe_ie1_v67"]

[objetivos]
habilitados = ["juego_principal", "ie1"]

[fuentes]
ttf_ui = "del_proyecto.ttf"

[golden]
manifiestos = "tools/tests/compat/golden"
"""


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    (tmp_path / "AGENTS.md").write_text("", encoding="utf-8")
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "pyproject.toml").write_text("", encoding="utf-8")
    (tmp_path / "ie123.toml").write_text(IE123_TOML, encoding="utf-8")
    return tmp_path


def _ws(repo: Path, entorno: dict[str, str] | None = None) -> Workspace:
    return Workspace.abrir(repo, entorno=entorno or {})


def test_precedencia_local_sobre_proyecto(repo: Path) -> None:
    (repo / "ie123.local.toml").write_text('[fuentes]\nttf_ui = "de_local.ttf"\n', encoding="utf-8")
    assert _ws(repo).ajuste("fuentes.ttf_ui") == "de_local.ttf"
    assert _ws(repo).ajuste("proyecto.idioma") == "es-ES"
    assert _ws(repo).ajuste("no.existe", "defecto") == "defecto"


def test_precedencia_variables_por_encima_de_todo(repo: Path) -> None:
    (repo / "ie123.local.toml").write_text('[fuentes]\nttf_ui = "de_local.ttf"\n', encoding="utf-8")
    ws = _ws(repo, {"IE123_FUENTE_TTF": "del_entorno.ttf", "IE123_AZAHAR": "mods"})
    assert ws.ajuste("fuentes.ttf_ui") == "del_entorno.ttf"
    assert ws.ajuste("azahar.mods_dir") == "mods"


def test_dirs_objetivo_simple_versionado_y_comun(repo: Path) -> None:
    ws = _ws(repo)
    d = ws.dirs("ie1")
    assert d.raiz == repo / "work" / "ie1"
    assert d.capas == d.raiz / "capas"
    assert d.qa == d.raiz / "qa"
    assert d.exportaciones == d.raiz / "exportaciones"
    assert d.registro == d.raiz / "registro.json"
    assert not d.capas.exists()
    assert ws.dirs("juego_principal").raiz == repo / "work" / "juego_principal"
    assert ws.dirs("ie2.tormenta_de_fuego").raiz == repo / "work" / "ie2" / "tormenta_de_fuego"
    assert ws.dirs("ie3.rayo_celeste").raiz == repo / "work" / "ie3" / "rayo_celeste"
    assert ws.dirs("ie2.comun").raiz == repo / "work" / "ie2" / "shared"
    assert ws.dirs("ie3.comun").raiz == repo / "work" / "ie3" / "shared"


def test_objetivo_desconocido(repo: Path) -> None:
    with pytest.raises(ValidacionError) as exc:
        _ws(repo).dirs("ie4.lo_que_sea")
    assert exc.value.codigo == "OBJETIVO_DESCONOCIDO"


def test_preparar_es_idempotente(repo: Path) -> None:
    ws = _ws(repo)
    for _ in range(2):
        d = ws.preparar("ie1")
        assert d.capas.is_dir() and d.qa.is_dir() and d.exportaciones.is_dir()


def test_objetivos_habilitados(repo: Path) -> None:
    assert _ws(repo).objetivos_habilitados() == ("juego_principal", "ie1")


def test_candidatas_ordenadas_numericamente(repo: Path) -> None:
    ws = _ws(repo)
    assert ws.nombre_candidata(68) == "probe_ie1_v68"
    assert ws.candidata("probe_ie1_v68") == repo / "work" / "shared" / "candidatas" / "probe_ie1_v68"
    assert ws.listar_candidatas() == []
    for nombre in ("probe_ie1_v67", "probe_ie1_v9", "probe_ie1_v70", "ruido"):
        (ws.candidatas / nombre).mkdir(parents=True)
    assert ws.listar_candidatas() == ["probe_ie1_v9", "probe_ie1_v67", "probe_ie1_v70"]
    assert ws.golden() == ("probe_ie1_v66", "probe_ie1_v67")
    assert ws.dir_manifiestos_golden() == repo / "tools/tests/compat/golden"


def test_manifiesto_ida_y_vuelta(repo: Path) -> None:
    destino = repo / "work" / "shared" / "candidatas" / "probe_ie1_v68"
    m = ManifiestoCandidata(
        nombre="probe_ie1_v68",
        base="probe_ie1_v67",
        base_sha256="a" * 64,
        capas=({"ruta": "capas/dialogo.tsv", "sha256": "b" * 64},),
        salidas={"romfs/data.fa": "c" * 64},
        objetivos=("ie1",),
    )
    ruta = m.escribir(destino)
    assert ruta == destino / "manifest.json"
    d = json.loads(ruta.read_text(encoding="utf-8"))
    assert d["esquema"] == 1
    assert d["runtime_verified"] is False
    assert d["generado_en"]
    leido = ManifiestoCandidata.leer(destino)
    assert leido.nombre == m.nombre
    assert leido.capas == m.capas
    assert leido.salidas == m.salidas
    assert leido.objetivos == ("ie1",)
    assert ManifiestoCandidata.leer(ruta).to_json()["runtime_verified"] is False


def test_doctor_serializable(repo: Path) -> None:
    (repo / "ie123.local.toml").write_text(
        '[herramientas]\nctrtool = "ctrtool_que_no_existe_ie123"\n', encoding="utf-8"
    )
    res = _ws(repo).doctor()
    assert res.ok
    assert any(i.codigo == "HERRAMIENTA_AUSENTE" for i in res.incidencias)
    json.dumps(res.datos)


def test_ie123_toml_real_del_repo() -> None:
    raiz = find_root()
    ws = Workspace.abrir(raiz, entorno={})
    for seccion in ("proyecto", "candidatas", "objetivos", "golden"):
        assert seccion in ws.proyecto, f"falta [{seccion}] en ie123.toml"
    assert ws.dir_manifiestos_golden().is_dir()
    assert "ie1" in ws.objetivos_habilitados()


# --- F2.3: juego_principal como quinto ámbito, init y migrar-juego-principal ---


def _servicio(repo: Path):
    from ie123kit.servicio.api import ServicioToolkit

    return ServicioToolkit(_ws(repo), juegos={})


def test_dirs_trae_el_historico_y_la_carpeta_de_traduccion(repo: Path) -> None:
    ws = _ws(repo)
    assert ws.dirs("juego_principal").historico == repo / "work" / "juego_principal" / "historico.json"
    assert ws.dir_traduccion("juego_principal") == repo / "translation" / "juego_principal"
    assert ws.dir_traduccion("ie2.tormenta_de_fuego") == repo / "translation" / "ie2" / "tormenta_de_fuego"
    assert ws.dir_traduccion("ie3.comun") == repo / "translation" / "ie3" / "shared"


def test_init_crea_los_cinco_ambitos_y_es_idempotente(repo: Path) -> None:
    from ie123kit.servicio.api import OBJETIVOS

    servicio = _servicio(repo)
    res = servicio.init()
    assert res.ok, res.incidencias
    assert sorted(res.datos["objetivos"]) == sorted(OBJETIVOS)
    for objetivo in OBJETIVOS:
        d = _ws(repo).dirs(objetivo)
        assert d.capas.is_dir() and d.qa.is_dir() and d.exportaciones.is_dir()
    assert (repo / "work" / "juego_principal" / "capas").is_dir()
    assert (repo / "translation" / "juego_principal").is_dir()
    assert res.datos["creadas"]

    # Idempotente: la segunda pasada no crea nada.
    repetido = _servicio(repo).init()
    assert repetido.ok and repetido.datos["creadas"] == []


def test_init_simular_no_toca_el_disco(repo: Path) -> None:
    res = _servicio(repo).init(rom_3ds="C:/roms/ie123.3ds", simular=True)
    assert res.ok and res.datos["simulado"] is True
    assert res.datos["creadas"]
    assert not (repo / "work").exists()
    assert not (repo / "ie123.local.toml").exists()


def test_init_anota_las_rutas_de_rom_en_ie123_local_toml(repo: Path) -> None:
    (repo / "ie123.local.toml").write_text('[fuentes]\nttf_ui = "de_local.ttf"\n', encoding="utf-8")
    res = _servicio(repo).init(rom_3ds="C:/roms/ie123.3ds", roms={"nds_es_ie1": "C:/roms/ie1_es.nds"})
    assert res.ok, res.incidencias
    ws = _ws(repo)
    assert ws.ajuste("roms.3ds_jp") == "C:/roms/ie123.3ds"
    assert ws.ajuste("roms.nds_es_ie1") == "C:/roms/ie1_es.nds"
    # No se pierde lo que ya había en el fichero.
    assert ws.ajuste("fuentes.ttf_ui") == "de_local.ttf"


def _capa_falsa(repo: Path, rel: str, *, extra: dict[str, bytes] | None = None,
                ficheros: dict[str, str] | None = None) -> Path:
    capa = repo / "work" / "ie1" / "capas" / rel
    capa.mkdir(parents=True, exist_ok=True)
    for ruta, datos in (extra or {}).items():
        destino = capa / "extra" / ruta
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(datos)
    for nombre, texto in (ficheros or {}).items():
        (capa / nombre).write_text(texto, encoding="utf-8")
    return capa


def test_migrar_juego_principal_escribe_el_historico_sin_mover_nada(repo: Path) -> None:
    del_menu = _capa_falsa(repo, "v58/logos", extra={"menu/logo.ctpk": b"x"},
                           ficheros={"apply.py": "# coloca menu/logo.ctpk\n"})
    smdh = _capa_falsa(repo, "v33/smdh", extra={"exefs/icon.icn": b"y"},
                       ficheros={"report.json": '{"salidas": ["banner.bnr"]}'})
    solo_ie1 = _capa_falsa(repo, "v67/titulo_logo", extra={"inazuma1/data_iz/ui.arc": b"z"},
                           ficheros={"apply.py": "# solo ie1\n"})

    res = _servicio(repo).migrar_juego_principal(simular=True)

    assert res.ok, res.incidencias
    historico = Path(res.datos["historico"])
    assert historico == repo / "work" / "juego_principal" / "historico.json"
    documento = json.loads(historico.read_text(encoding="utf-8"))
    assert documento["movidas"] is False
    rutas = {c["ruta"] for c in documento["capas"]}
    assert "work/ie1/capas/v58/logos" in rutas
    assert "work/ie1/capas/v33/smdh" in rutas
    assert "work/ie1/capas/v67/titulo_logo" not in rutas
    assert all(c["motivos"] for c in documento["capas"])
    # NO se mueve nada: las capas siguen donde estaban, con su contenido.
    for capa in (del_menu, smdh, solo_ie1):
        assert capa.is_dir() and any(capa.rglob("*"))
    assert not (repo / "work" / "juego_principal" / "capas" / "v58").exists()


def test_migrar_de_verdad_no_esta_soportado_pero_deja_el_historico(repo: Path) -> None:
    _capa_falsa(repo, "v58/carga", extra={"menu/carga.ctpk": b"x"})

    res = _servicio(repo).migrar_juego_principal(simular=False)

    assert not res.ok
    assert [i.codigo for i in res.incidencias] == ["NOT_SUPPORTED"]
    historico = repo / "work" / "juego_principal" / "historico.json"
    assert historico.is_file()
    assert json.loads(historico.read_text(encoding="utf-8"))["capas"]
