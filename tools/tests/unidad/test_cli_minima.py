"""CLI mínima de F2.2: parseo, salida `--json` y códigos de salida.

No toca disco ni ROMs: se inyecta un ServicioToolkit falso en lugar de `main.abrir_servicio`.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from ie123kit.cli import main as cli
from ie123kit.nucleo.tipos import Incidencia, Resultado


class ServicioFalso:
    """Registra la llamada recibida y devuelve el Resultado preparado."""

    def __init__(self, resultado: Resultado) -> None:
        self.resultado = resultado
        self.llamadas: list[tuple[str, tuple, dict]] = []

    def _anotar(self, nombre: str, *args, **kw) -> Resultado:
        self.llamadas.append((nombre, args, kw))
        return self.resultado

    def construir(self, solicitud, **kw) -> Resultado:
        return self._anotar("construir", solicitud, **kw)

    def parche(self, *args, **kw) -> Resultado:
        return self._anotar("parche", *args, **kw)

    def doctor(self, **kw) -> Resultado:
        return self._anotar("doctor", **kw)

    def objetivos(self, **kw) -> Resultado:
        return self._anotar("objetivos", **kw)

    def activos(self, *args, **kw) -> Resultado:
        return self._anotar("activos", *args, **kw)

    def init(self, *args, **kw) -> Resultado:
        return self._anotar("init", *args, **kw)

    def migrar_juego_principal(self, *args, **kw) -> Resultado:
        return self._anotar("migrar_juego_principal", *args, **kw)

    def limpiar(self, *args, **kw) -> Resultado:
        return self._anotar("limpiar", *args, **kw)


@pytest.fixture
def falso(monkeypatch: pytest.MonkeyPatch):
    def fabricar(resultado: Resultado) -> ServicioFalso:
        servicio = ServicioFalso(resultado)
        monkeypatch.setattr(cli, "abrir_servicio", lambda raiz=None: servicio)
        return servicio

    return fabricar


def test_construir_json_devuelve_cero_e_imprime_el_resultado(falso, capsys) -> None:
    esperado = Resultado.correcto(datos={"archive": "x/archive.fa", "archive_sha256": "ab" * 32})
    servicio = falso(esperado)
    codigo = cli.main(["--json", "construir", "--base", "probe_ie1_v66",
                       "--capas", "work/ie1/capas/v67/titulo_logo", "--salida", "probe_ie1_v67"])
    assert codigo == 0
    datos = json.loads(capsys.readouterr().out)
    assert datos == esperado.to_json()
    nombre, (solicitud,), _ = servicio.llamadas[0]
    assert nombre == "construir"
    assert solicitud.base == "probe_ie1_v66"
    assert solicitud.capas == ("work/ie1/capas/v67/titulo_logo",)
    assert solicitud.salida == "probe_ie1_v67"
    assert solicitud.objetivos == ()


def test_objetivos_se_parten_por_comas(falso) -> None:
    servicio = falso(Resultado.correcto())
    assert cli.main(["construir", "--base", "v66", "--objetivos", "ie1, juego_principal",
                     "--salida", "v67"]) == 0
    assert servicio.llamadas[0][1][0].objetivos == ("ie1", "juego_principal")


def test_incidencia_de_validacion_devuelve_uno(falso, capsys) -> None:
    falso(Resultado.fallo([Incidencia("EXCEDE_PX", "error", "no cabe")]))
    assert cli.main(["construir", "--base", "v66", "--salida", "v67"]) == 1
    assert "EXCEDE_PX" in capsys.readouterr().out


def test_no_soportado_devuelve_cinco(falso) -> None:
    falso(Resultado.no_soportado("construir: falta el núcleo"))
    assert cli.main(["construir", "--base", "v66", "--salida", "v67"]) == 5


def test_bloqueo_y_herramienta_tienen_sus_codigos(falso) -> None:
    falso(Resultado.fallo([Incidencia("BLOQUEO_V20", "error", "hash distinto")]))
    assert cli.main(["construir", "--base", "v66", "--salida", "v67"]) == 3
    falso(Resultado.fallo([Incidencia("HERRAMIENTA_AUSENTE", "error", "falta xdelta3")]))
    assert cli.main(["parche", "--rom-base", "a", "--rom-parcheada", "b", "--salida", "c"]) == 4


def test_parche_y_doctor_delegan_en_la_fachada(falso) -> None:
    servicio = falso(Resultado.correcto())
    assert cli.main(["parche", "--rom-base", "a.3ds", "--rom-parcheada", "b.3ds", "--salida", "c.xdelta"]) == 0
    assert servicio.llamadas[-1][:2] == ("parche", ("a.3ds", "b.3ds", "c.xdelta"))
    assert cli.main(["doctor"]) == 0
    assert servicio.llamadas[-1][0] == "doctor"


@pytest.mark.parametrize("argv", [[], ["construir"], ["construir", "--base", "v66"], ["inventado"]])
def test_uso_incorrecto_devuelve_dos(falso, argv) -> None:
    falso(Resultado.correcto())
    assert cli.main(argv) == 2


def test_modulo_ejecutable_responde_a_help() -> None:
    src = Path(cli.__file__).resolve()
    while src.name != "src" and src.parent != src:
        src = src.parent
    entorno = {**os.environ, "PYTHONPATH": str(src), "PYTHONIOENCODING": "utf-8"}
    orden = [sys.executable, "-X", "utf8", "-m", "ie123kit.cli", "--help"]
    proceso = subprocess.run(orden, capture_output=True, text=True, encoding="utf-8",
                             env=entorno, timeout=120, check=False)
    assert proceso.returncode == 0, proceso.stderr
    for verbo in ("construir", "parche", "doctor", "objetivos", "proyecto", "work", "juego_principal"):
        assert verbo in proceso.stdout


# --- F2.3: verbos nuevos (proyecto, objetivos, work limpiar y <objetivo> activos) ---


def test_activos_por_objetivo_con_json_despues_del_verbo(falso, capsys) -> None:
    """El gate ejecuta literalmente `ie123 juego_principal activos --json`."""
    esperado = Resultado.correcto(datos={"activos": [{"id": "juego_principal:literal_cro:cro/ina_menu.cro"}]})
    servicio = falso(esperado)
    assert cli.main(["juego_principal", "activos", "--json"]) == 0
    datos = json.loads(capsys.readouterr().out)
    assert datos == esperado.to_json()
    nombre, args, kw = servicio.llamadas[-1]
    assert nombre == "activos" and args == ("juego_principal",)
    assert kw == {"tipo": None, "filtro": None}


def test_json_vale_antes_y_despues_del_verbo(falso, capsys) -> None:
    falso(Resultado.correcto(datos={"activos": []}))
    assert cli.main(["--json", "juego_principal", "activos"]) == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True
    assert cli.main(["juego_principal", "activos"]) == 0
    assert "ok" == capsys.readouterr().out.splitlines()[0]


def test_hay_un_subparser_por_cada_objetivo(falso) -> None:
    from ie123kit.servicio.api import OBJETIVOS

    servicio = falso(Resultado.correcto(datos={"activos": []}))
    for objetivo in OBJETIVOS:
        assert cli.main([objetivo, "activos", "--tipo", "texto", "--filtro", "uno"]) == 0
        assert servicio.llamadas[-1][1] == (objetivo,)
        assert servicio.llamadas[-1][2] == {"tipo": "texto", "filtro": "uno"}


def test_objetivos_y_work_limpiar_delegan(falso) -> None:
    servicio = falso(Resultado.correcto())
    assert cli.main(["objetivos"]) == 0
    assert servicio.llamadas[-1][0] == "objetivos"
    assert cli.main(["work", "limpiar"]) == 0
    assert servicio.llamadas[-1][:3] == ("limpiar", (), {"borrar": False})
    assert cli.main(["work", "limpiar", "--borrar"]) == 0
    assert servicio.llamadas[-1][2] == {"borrar": True}


def test_proyecto_init_y_migrar(falso) -> None:
    servicio = falso(Resultado.correcto())
    assert cli.main(["proyecto", "init", "--rom3ds", "a.3ds", "--nds-es-ie1", "b.nds"]) == 0
    assert servicio.llamadas[-1][2] == {"rom_3ds": "a.3ds", "roms": {"nds_es_ie1": "b.nds"},
                                        "simular": False}
    assert cli.main(["proyecto", "init", "--simular"]) == 0
    assert servicio.llamadas[-1][2]["simular"] is True
    assert cli.main(["proyecto", "migrar-juego-principal"]) == 0
    assert servicio.llamadas[-1][:3] == ("migrar_juego_principal", (), {"simular": True})


def test_migrar_de_verdad_propaga_el_cinco(falso) -> None:
    falso(Resultado.no_soportado("mover capas no está soportado"))
    assert cli.main(["proyecto", "migrar-juego-principal", "--no-simular"]) == 5


def test_alias_en_ingles_llegan_al_mismo_metodo(falso) -> None:
    servicio = falso(Resultado.correcto())
    assert cli.main(["targets"]) == 0
    assert servicio.llamadas[-1][0] == "objetivos"
    assert cli.main(["work", "clean"]) == 0
    assert servicio.llamadas[-1][0] == "limpiar"
    assert cli.main(["ie1", "assets"]) == 0
    assert servicio.llamadas[-1][:2] == ("activos", ("ie1",))


@pytest.mark.parametrize("argv", [["proyecto"], ["work"], ["juego_principal"],
                                  ["juego_principal", "inventado"], ["proyecto", "inventado"]])
def test_subverbo_ausente_o_inventado_es_uso_incorrecto(falso, argv) -> None:
    falso(Resultado.correcto())
    assert cli.main(argv) == 2
