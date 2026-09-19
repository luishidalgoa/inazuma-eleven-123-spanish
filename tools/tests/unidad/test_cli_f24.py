"""CLI completa de la F2.4 (#50): verbos nuevos, alias en inglés y salida `--json` validada contra el esquema.

Con un servicio falso (sin disco) se prueba el reparto 1:1 de argumentos; con el servicio real se
prueban las órdenes que no necesitan ROM (motor paginar/listar, compat equivalencias, extraer nds
sobre una ROM sintética). Toda salida `--json` se valida con `servicio.esquemas` (resultado).
"""

from __future__ import annotations

import json
import struct
from pathlib import Path

import pytest

from ie123kit.cli import main as cli
from ie123kit.nucleo.tipos import Incidencia, Resultado
from ie123kit.servicio import esquemas
from ie123kit.servicio.api import MOTORES, ServicioToolkit


class ServicioFalso:
    def __init__(self, resultado: Resultado) -> None:
        self.resultado = resultado
        self.llamadas: list[tuple[str, tuple, dict]] = []

    def __getattr__(self, nombre: str):
        def llamar(*args, **kw):
            self.llamadas.append((nombre, args, kw))
            return self.resultado

        return llamar


@pytest.fixture
def falso(monkeypatch: pytest.MonkeyPatch):
    servicio = ServicioFalso(Resultado.correcto())
    monkeypatch.setattr(cli, "abrir_servicio", lambda raiz=None: servicio)
    return servicio


@pytest.mark.parametrize(("argv", "llamada"), [
    (["extraer", "romfs"], ("extraer", ("romfs",), {"rom": None, "salida": None})),
    (["extract", "nds", "--rom", "a.nds", "--salida", "d"], ("extraer", ("nds",), {"rom": "a.nds", "salida": "d"})),
    (["verificar", "--candidata", "v34", "--golden"], ("verificar", ("v34",), {"golden": True})),
    (["verify", "--candidata", "v34"], ("verificar", ("v34",), {"golden": False})),
    (["instalar", "--candidata", "v34", "--lanzar"], ("instalar", ("v34",), {"lanzar": True})),
    (["install", "--candidata", "v34"], ("instalar", ("v34",), {"lanzar": False})),
    (["compat", "comprobar"], ("compat", (), {"golden": False})),
    (["compat", "check", "--golden"], ("compat", (), {"golden": True})),
    (["compat", "equivalencias"], ("equivalencias", (), {})),
    (["registro", "--sesion", "v34"], ("registro", (), {"sesion": "v34", "logdir": None, "forzar": False})),
    (["log", "--forzar"], ("registro", (), {"sesion": None, "logdir": None, "forzar": True})),
    (["motor", "listar"], ("motores", (), {})),
    (["engine", "list"], ("motores", (), {})),
    (["motor", "paginar", "--juego", "ie1", "--texto", "Hola"], ("motor", ("ie1", "paginar", {"texto": "Hola"}), {})),
    (["motor", "teclado", "--archive", "a.fa", "--salida", "x"],
     ("motor", ("ie2", "teclado", {"archive": "a.fa", "salida": "x"}), {})),
    (["motor", "cro-ancho-dialogo", "--cro", "c", "--salida", "s"],
     ("motor", ("ie2", "cro-ancho-dialogo", {"cro": "c", "salida": "s"}), {})),
    (["motor", "voces", "--sonido-3ds", "a", "--sonido-nds", "b", "--bancos", "X, Y", "--salida", "s"],
     ("motor", ("ie2", "voces", {"sonido_3ds": "a", "sonido_nds": "b", "bancos": ["X", "Y"], "salida": "s",
                                 "base": None}), {})),
    (["motor", "subtitles", "--dat", "a.dat", "--fotogramas", "10"],
     ("motor", ("ie2", "subtitulos", {"dat": "a.dat", "fotogramas": 10}), {})),
    (["project", "migrate-main-game"], ("migrar_juego_principal", (), {"simular": True})),
])
def test_verbos_f24_llaman_al_metodo_de_la_fachada(falso, argv, llamada) -> None:
    assert cli.main(argv) == 0
    assert falso.llamadas[-1] == llamada


def test_motor_con_juego_no_admitido_es_uso_incorrecto(falso) -> None:
    assert cli.main(["motor", "teclado", "--juego", "ie1", "--archive", "a", "--salida", "b"]) == 2


def test_la_cli_cubre_todos_los_motores_del_servicio() -> None:
    assert {n for _, n in MOTORES} == set(cli._MOTORES)
    assert {(j, n) for n, (_, js) in cli._MOTORES.items() for j in js} == set(MOTORES)


def test_aviso_no_cambia_el_codigo_de_salida(falso) -> None:
    falso.resultado = Resultado.correcto(incidencias=(Incidencia("BLOQUEO_V20", "aviso", "pendiente #80"),))
    assert cli.main(["compat", "comprobar"]) == 0
    falso.resultado = Resultado.fallo([Incidencia("GATE_FALLIDO", "error", "capa distinta")])
    assert cli.main(["compat", "comprobar"]) == 1


# --- con el servicio real (sin ROM) ---------------------------------------------------------


def _json_valido(capsys) -> dict:
    datos = json.loads(capsys.readouterr().out)
    assert esquemas.validar(datos, "resultado") == []
    return datos


def test_motor_paginar_real_json_valido(capsys) -> None:
    texto = "Hola, Mark. Hoy vamos a entrenar muy duro en la ribera del río porque el partido es pronto."
    assert cli.main(["--json", "motor", "paginar", "--texto", texto]) == 0
    datos = _json_valido(capsys)["datos"]
    assert datos["max_car"] == 37
    assert " ".join(" ".join(p) for p in datos["paginas"]).split() == texto.split()
    assert cli.main(["--json", "motor", "paginar", "--juego", "ie1", "--texto", texto]) == 0
    assert all(len(x) <= 22 for p in _json_valido(capsys)["datos"]["paginas"] for x in p)


def test_motor_listar_y_equivalencias_reales(capsys) -> None:
    assert cli.main(["--json", "motor", "listar"]) == 0
    assert "teclado" in _json_valido(capsys)["datos"]["motores"]["ie2"]
    assert cli.main(["--json", "compat", "equivalencias"]) == 0
    antiguas = {f["antigua"] for f in _json_valido(capsys)["datos"]["equivalencias"]}
    assert {"tools/verify_candidate.py", "tools/nds_unpack.py", "tools/blz.py", "tools/harvest_log.py",
            "tools/limpiar_work.py", "tools/extract_nds.ps1"} <= antiguas


def test_motor_desconocido_es_no_soportado(capsys) -> None:
    res = ServicioToolkit.abrir().motor("ie3", "teclado")
    assert not res.ok and res.incidencias[0].codigo == "NOT_SUPPORTED"


def _rom_nds(tmp_path: Path) -> Path:
    """ROM NDS mínima: un directorio raíz con un fichero «a.bin»."""
    rom = bytearray(0x400)
    rom[0:12] = b"PRUEBA".ljust(12, b"\0")
    rom[12:16] = b"TEST"
    fnt, fat = 0x200, 0x300
    struct.pack_into("<IIII", rom, 0x40, fnt, 0x20, fat, 8)
    struct.pack_into("<IHH", rom, fnt, 8, 0, 1)                     # raíz: subtabla en +8, primer id 0
    rom[fnt + 8:fnt + 8 + 7] = bytes([5]) + b"a.bin" + b"\0"
    struct.pack_into("<II", rom, fat, 0x380, 0x384)
    rom[0x380:0x384] = b"HOLA"
    ruta = tmp_path / "x.nds"
    ruta.write_bytes(bytes(rom))
    return ruta


def test_extraer_nds_real(tmp_path: Path, capsys) -> None:
    rom = _rom_nds(tmp_path)
    salida = tmp_path / "salida"
    assert cli.main(["--json", "extraer", "nds", "--rom", str(rom), "--salida", str(salida)]) == 0
    datos = _json_valido(capsys)["datos"]
    assert datos["ficheros"] == 1 and datos["codigo"] == "TEST"
    assert (salida / "a.bin").read_bytes() == b"HOLA"
    assert cli.main(["--json", "extraer", "nds", "--rom", str(tmp_path / "no.nds"), "--salida", str(salida)]) == 5
    _json_valido(capsys)


def test_motor_no_sobrescribe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    from ie123kit.ie2.comun import motores

    salida = tmp_path / "out.cro"
    salida.write_bytes(b"ya")
    with pytest.raises(FileExistsError):
        motores._escribir(salida, b"nuevo")
    assert salida.read_bytes() == b"ya"

    def falla(**kw):
        raise FileExistsError(f"ya existe: {kw['salida']}")

    monkeypatch.setattr(motores, "cro_ancho_dialogo", falla)
    assert cli.main(["--json", "motor", "cro-ancho-dialogo", "--cro", "c", "--salida", str(salida)]) == 5
    datos = _json_valido(capsys)
    assert datos["incidencias"][0]["pista"] == "La salida no se sobrescribe."


def test_cosechar_registro_de_azahar(tmp_path: Path) -> None:
    from ie123kit.nucleo.construir import registro_azahar as R

    logdir = tmp_path / "log"
    logdir.mkdir()
    (logdir / "azahar_log.txt").write_text(
        "[  1.000] Core.ARM11 <Error> core/arm.cpp:10: unmapped Read32 @ 0x00000000 at PC 0x001C8D68\n",
        encoding="utf-8")
    reg, inf = tmp_path / "reg.json", tmp_path / "inf.md"
    datos = R.cosechar(sesion="v99", logdir=str(logdir), registro=str(reg), informe_md=str(inf))
    assert datos["firmas"] == 1 and reg.is_file() and inf.is_file()
    assert R.cosechar(sesion="v99", logdir=str(logdir), registro=str(reg), informe_md=str(inf))["procesados"] == []


def test_extraer_romfs_repite_los_pasos_de_3dstool(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from ie123kit.nucleo.construir import extraer, rom

    llamadas = []
    monkeypatch.setattr(rom, "_ejecutar", lambda args: llamadas.append(args) or {"returncode": 0, "stdout": "",
                                                                                "stderr": ""})
    fichero = tmp_path / "x.3ds"
    fichero.write_bytes(b"\0")
    datos = extraer.romfs_3ds(fichero, tmp_path / "base", herramienta=tmp_path / "3dstool.exe")
    assert [a[1:3] for a in llamadas] == [["-xtf", "3ds"], ["-xtf", "cxi"], ["-xtf", "romfs"], ["-xtf", "exefs"]]
    assert datos["romfs"].endswith("romfs") and datos["pasos"] == 4


def test_extraer_no_sobrescribe_una_extraccion(tmp_path: Path, capsys) -> None:
    rom = _rom_nds(tmp_path)
    salida = tmp_path / "ocupada"
    salida.mkdir()
    (salida / "algo").write_bytes(b"x")
    assert cli.main(["--json", "extraer", "nds", "--rom", str(rom), "--salida", str(salida)]) == 5
    assert "no se sobrescribe" in _json_valido(capsys)["incidencias"][0]["pista"].lower()
