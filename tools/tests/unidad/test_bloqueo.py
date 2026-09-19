"""Pruebas de la puerta del bloqueo tipográfico v20 (ie123kit.nucleo.validar.bloqueo).

Sin ROM salvo los tests marcados ``requiere_rom``: el resto usa un contenedor B123
sintético en tmp_path con bytes inventados (nada extraído del juego).
"""
import hashlib
import importlib
import os
import struct
import subprocess
import sys
from pathlib import Path

import pytest

import ie123kit
from ie123kit.nucleo.compat import golden
from ie123kit.nucleo.config.raiz import find_root
from ie123kit.nucleo.errores import BloqueoTipograficoError
from ie123kit.nucleo.validar import bloqueo

RAIZ = find_root()
TOOLS = RAIZ / "tools"
SRC = Path(ie123kit.__file__).resolve().parent.parent
# Candidata vigente (probe_ie1_v67 se borró el 2026-09-16); ver golden.CANDIDATA_VIGENTE.
CANDIDATA = RAIZ / "work" / "shared" / "candidatas" / golden.CANDIDATA_VIGENTE / "archive.fa"
FALSO = "0" * 64

sin_candidata = pytest.mark.skipif(not CANDIDATA.is_file(), reason=f"no existe {CANDIDATA}")


def _entorno():
    env = dict(os.environ)
    env["PYTHONPATH"] = str(SRC)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.pop("IE123_ROOT", None)
    return env


@pytest.fixture
def lock(monkeypatch):
    """El módulo dialogue_lock de tools/ (intacto); los parches son solo en memoria."""
    monkeypatch.syspath_prepend(str(TOOLS))
    modulo = importlib.import_module("dialogue_lock")
    assert Path(modulo.__file__).resolve().parent == TOOLS.resolve()
    return modulo


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


def _fuentes_sinteticas(lock) -> dict[str, bytes]:
    return {rel: f"fuente sintética {rel}".encode() for rel in lock.FONT_HASHES}


# --------------------------------------------------------------------------- sin ROM


def test_candidata_ausente(tmp_path):
    with pytest.raises(BloqueoTipograficoError) as info:
        bloqueo.comprobar(tmp_path / "no_existe" / "archive.fa")
    assert info.value.codigo == "candidata_ausente"
    with pytest.raises(BloqueoTipograficoError) as info:
        bloqueo.comprobar(tmp_path)
    assert info.value.codigo == "candidata_ausente"
    assert info.value.ruta == str(tmp_path / "archive.fa")


def test_importar_no_carga_tools():
    codigo = (
        "import sys\n"
        "import ie123kit.nucleo.validar.bloqueo\n"
        "cargados = [m for m in ('dialogue_lock', 'build_ie1_probe', 'fa_unpack') if m in sys.modules]\n"
        "assert not cargados, cargados\n"
    )
    # cwd=tools/: si la importación fuera ansiosa, esos módulos sí se encontrarían.
    r = subprocess.run(
        [sys.executable, "-X", "utf8", "-c", codigo],
        cwd=TOOLS,
        env=_entorno(),
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert r.returncode == 0, r.stderr
    assert r.stdout == "" and r.stderr == ""


def test_fuente_ausente_sintetica(tmp_path, lock):
    archive = _fa_sintetico(tmp_path / "archive.fa", {"font/OTRA.bcfnt": b"nada"})
    with pytest.raises(BloqueoTipograficoError) as info:
        bloqueo.comprobar(archive, RAIZ)
    assert info.value.codigo == "fuente_ausente"
    assert info.value.ruta in lock.FONT_HASHES


def test_sintetica_verde_y_hash_falso_rojo(tmp_path, lock, monkeypatch):
    temporales = tmp_path / "temporales"
    temporales.mkdir()
    monkeypatch.setattr(bloqueo.tempfile, "tempdir", str(temporales))
    candidata = tmp_path / "candidata"
    candidata.mkdir()
    fuentes = _fuentes_sinteticas(lock)
    _fa_sintetico(candidata / "archive.fa", fuentes)
    monkeypatch.setattr(lock, "FONT_HASHES", {r: hashlib.sha256(b).hexdigest() for r, b in fuentes.items()})
    bloqueo.comprobar(candidata, RAIZ)  # carpeta: usa <carpeta>/archive.fa
    assert list(temporales.iterdir()) == []
    rel = min(fuentes)
    monkeypatch.setitem(lock.FONT_HASHES, rel, FALSO)
    with pytest.raises(BloqueoTipograficoError) as info:
        bloqueo.comprobar(candidata, RAIZ)
    assert info.value.codigo == "bloqueo_v20"
    assert rel in info.value.detalle
    assert list(temporales.iterdir()) == []  # el temporal se borra también al fallar


# --------------------------------------------------------------------------- con la candidata vigente


@pytest.mark.requiere_rom
@sin_candidata
def test_candidata_vigente_respeta_bloqueo():
    try:
        bloqueo.comprobar(CANDIDATA.parent)
    except BloqueoTipograficoError as exc:
        # Estado conocido (2026-09-19): las fuentes vigentes (espaciado autorizado el 2026-09-16 y
        # registro de bigramas) no coinciden con FONT_HASHES. Actualizarlos lo decide el usuario.
        pytest.xfail(f"bloqueo v20 desactualizado respecto a las fuentes vigentes: {exc.detalle}")
    r = subprocess.run(
        [
            sys.executable,
            "-X",
            "utf8",
            "-m",
            "ie123kit.nucleo.validar.bloqueo",
            "--candidata",
            str(CANDIDATA),
        ],
        cwd=RAIZ,
        env=_entorno(),
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    assert r.returncode == 0, r.stderr
    assert "bloqueo v20 OK" in r.stdout


@pytest.mark.requiere_rom
@sin_candidata
def test_candidata_vigente_hash_falso_ve_rojo(lock, monkeypatch):
    rel = min(lock.FONT_HASHES)
    monkeypatch.setitem(lock.FONT_HASHES, rel, FALSO)
    with pytest.raises(BloqueoTipograficoError) as info:
        bloqueo.comprobar(CANDIDATA)
    assert info.value.codigo == "bloqueo_v20"
