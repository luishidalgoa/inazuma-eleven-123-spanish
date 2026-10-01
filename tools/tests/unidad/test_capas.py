"""Entorno de capa: Capa(__file__) y ejecutar(main)."""
from pathlib import Path

import pytest

from ie123kit.nucleo.construir.capas import Capa, ejecutar, listar_capas, ubicacion


def _capa_falsa(tmp_path: Path, *, con_toml: bool = True) -> Path:
    aqui = tmp_path / "work" / "ie1" / "capas" / "v70" / "pachangas"
    aqui.mkdir(parents=True)
    if con_toml:
        (aqui / "capa.toml").write_text(
            'version = "v70"\nobjetivo = "ie1"\nlinea = "pachangas"\n'
            'base = "probe_ie1_v67"\ndescripcion = "Rótulos de las pachangas"\n',
            encoding="utf-8",
        )
    (aqui / "apply.py").write_text("# capa de prueba\n", encoding="utf-8")
    return aqui


def test_rutas_y_metadatos(tmp_path):
    aqui = _capa_falsa(tmp_path)
    capa = Capa(aqui / "apply.py", raiz=tmp_path)
    assert capa.aqui == aqui
    assert capa.raiz == tmp_path.resolve()
    assert (capa.version, capa.objetivo, capa.linea) == ("v70", "ie1", "pachangas")
    assert capa.meta["base"] == "probe_ie1_v67"

    destino = capa.extra("inazuma1/data_iz/ui.bin")
    assert destino == aqui / "extra" / "inazuma1" / "data_iz" / "ui.bin"
    assert destino.parent.is_dir()
    assert capa.eventos("eve") == aqui / "events"
    assert capa.eventos("mch").is_dir()
    assert capa.romfs("cro/ina_main1.cro").parent.is_dir()
    assert capa.informe("resumen.json").parent.is_dir()
    with pytest.raises(ValueError):
        capa.eventos("otro")


def test_metadatos_deducidos_sin_toml(tmp_path):
    aqui = _capa_falsa(tmp_path, con_toml=False)
    capa = Capa(aqui / "apply.py", raiz=tmp_path)
    assert (capa.version, capa.objetivo, capa.linea) == ("v70", "ie1", "pachangas")


def test_aportacion(tmp_path):
    aqui = _capa_falsa(tmp_path)
    capa = Capa(aqui / "apply.py", raiz=tmp_path)
    capa.extra("")
    capa.romfs("cro/ina_main2.cro").write_bytes(b"cro")
    capa.eventos("mch")
    aportacion = capa.aportacion()
    assert aportacion["objetivo"] == "ie1"
    assert aportacion["cro"] == [aqui / "romfs" / "cro" / "ina_main2.cro"]
    assert "mch" in aportacion["eventos"]


def test_ejecutar_exito_y_fallo(capsys):
    assert ejecutar(lambda: None) == 0

    def falla():
        raise ValueError("falta la entrada b/dos.bin")

    assert ejecutar(falla) == 1
    salida = capsys.readouterr()
    assert salida.err.count("\n") == 1
    assert "falta la entrada b/dos.bin" in salida.err

    def revienta():
        raise KeyError("otro fallo")

    with pytest.raises(KeyError):
        ejecutar(revienta)


# --------------------------------------------------------------------------- disposición por tema


@pytest.mark.parametrize(("partes", "esperado"), [
    (("dialogo", "saltos37"), {"tema": "dialogo", "version": "", "linea": "saltos37"}),
    (("historial", "dialogo", "v33_mch_story"), {"tema": "dialogo", "version": "v33", "linea": "mch_story"}),
    (("historial", "candidata", "v33_final"), {"tema": "candidata", "version": "v33", "linea": "final"}),
    (("v70", "pachangas"), {"tema": "", "version": "v70", "linea": "pachangas"}),
    (("v67.1", "x"), {"tema": "", "version": "v67.1", "linea": "x"}),
])
def test_ubicacion(partes, esperado):
    assert ubicacion(partes) == esperado


def test_capa_deduce_tema_de_la_ruta(tmp_path):
    aqui = tmp_path / "work" / "ie2" / "shared" / "capas" / "menus_cro" / "ancho_dialogo"
    aqui.mkdir(parents=True)
    capa = Capa(aqui, raiz=tmp_path)
    assert (capa.objetivo, capa.tema, capa.version, capa.linea) == ("ie2/shared", "menus_cro", "", "ancho_dialogo")
    antigua = tmp_path / "work" / "ie1" / "capas" / "historial" / "nombres" / "v36_nombres"
    antigua.mkdir(parents=True)
    capa = Capa(antigua, raiz=tmp_path)
    assert (capa.objetivo, capa.tema, capa.version, capa.linea) == ("ie1", "nombres", "v36", "nombres")


def test_listar_capas_omite_historial_salvo_que_se_pida(tmp_path):
    raiz = tmp_path / "capas"
    for rel in ("graficos/logo", "dialogo/saltos37", "v70/pachangas", "historial/dialogo/v33_mch_story"):
        (raiz / rel).mkdir(parents=True)
    (raiz / "graficos" / "suelto.txt").write_text("", encoding="utf-8")
    vigentes = [p.relative_to(raiz).as_posix() for p in listar_capas(raiz)]
    assert vigentes == ["dialogo/saltos37", "graficos/logo", "v70/pachangas"]
    todas = [p.relative_to(raiz).as_posix() for p in listar_capas(raiz, historial=True)]
    assert sorted(todas) == sorted([*vigentes, "historial/dialogo/v33_mch_story"])
    assert listar_capas(tmp_path / "no_existe") == []
