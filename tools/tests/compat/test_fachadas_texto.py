"""Fachadas de texto NDS y eventos de F1.4 (#45): pkb_unpack, build_glossary, ds_official y audit_dialogo_ids.

Sin ROM. Cada comprobación corre en subproceso con cwd = raíz y PYTHONPATH vacío. Un
módulo cuyo tools/<nombre>.py todavía no es un shim se salta.
"""
import os
import subprocess
import sys

import pytest

from ie123kit.nucleo.compat import shims
from ie123kit.nucleo.config.raiz import find_root

RAIZ = find_root()
TOOLS = RAIZ / "tools"
SUPERFICIE = RAIZ / "tools" / "tests" / "compat" / "superficie_v0.json"
MODULOS = ["pkb_unpack", "build_glossary", "ds_official", "audit_dialogo_ids"]

_CABECERA = "import importlib, json, os, sys\nsys.path.insert(0, 'tools')\n"


def _trasladado(nombre):
    ruta = TOOLS / f"{nombre}.py"
    return ruta.is_file() and "sys.modules[__name__]" in ruta.read_text(encoding="utf-8", errors="replace")


def _exigir(*nombres):
    for n in nombres:
        if not _trasladado(n):
            pytest.skip(f"{n}: aún sin trasladar")


def _entorno(**extra):
    env = dict(os.environ)
    env["PYTHONPATH"] = ""
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.pop("IE123_ROOT", None)
    env.pop("IE123_LEGADO_LO_SE", None)
    env.update(extra)
    return env


def _python(codigo, *args, **extra):
    return subprocess.run([sys.executable, "-X", "utf8", "-c", _CABECERA + codigo, *args],
                          cwd=RAIZ, env=_entorno(**extra), capture_output=True, text=True,
                          encoding="utf-8", timeout=120, check=False)


@pytest.mark.parametrize("nombre", MODULOS)
def test_modulo_y_superficie(nombre):
    _exigir(nombre)
    codigo = (
        "nombre, destino, sup = sys.argv[1:4]\n"
        "m = importlib.import_module(nombre)\n"
        "assert m is importlib.import_module(destino)\n"
        "faltan = [n for n in json.load(open(sup, encoding='utf-8'))[nombre] if not hasattr(m, n)]\n"
        "assert not faltan, faltan\n"
    )
    r = _python(codigo, nombre, shims.MAPA[nombre], str(SUPERFICIE))
    assert r.returncode == 0, r.stderr


def test_identidades():
    _exigir("pkb_unpack", "build_glossary", "ds_official")
    codigo = (
        "import pkb_unpack, build_glossary, ds_official\n"
        "from ie123kit.nucleo.texto import nds_latin\n"
        "assert pkb_unpack.NDS_DEC is build_glossary.NDS_DEC is nds_latin.NDS_DEC\n"
        "assert pkb_unpack._decode_string is nds_latin.decode_cadena\n"
        "assert ds_official.DS_TABLE is nds_latin.DS_TABLE\n"
        "assert ds_official.DS_TABLE is not nds_latin.NDS_DEC\n"
    )
    r = _python(codigo)
    assert r.returncode == 0, r.stderr


def test_rutas_build_glossary():
    _exigir("build_glossary")
    raiz = str(RAIZ)
    codigo = (
        "import build_glossary as B\n"
        "print(json.dumps([B.REPO, B.DS, B.ES, B.OUT]))\n"
    )
    r = _python(codigo)
    assert r.returncode == 0, r.stderr
    import json
    assert json.loads(r.stdout) == [
        raiz,
        os.path.join(raiz, "work", "shared", "fa_extract", "inazuma1", "data_iz", "logic"),
        os.path.join(raiz, "work", "ie1", "fuentes", "nds_es", "data_iz", "logic", "sp"),
        os.path.join(raiz, "translation", "shared", "glossary"),
    ]


def test_ds_official_cli_retirado():
    _exigir("ds_official")
    r = subprocess.run([sys.executable, "-X", "utf8", "tools/ds_official.py"], cwd=RAIZ, env=_entorno(),
                       capture_output=True, text=True, encoding="utf-8", timeout=120, check=False)
    assert r.returncode == 2
    assert r.stdout == ""
    assert "--legado-lo-se" in r.stderr


def test_align_requiere_autorizacion():
    _exigir("ds_official")
    codigo = (
        "import ds_official as D\n"
        "try:\n"
        "    D.align(['a'], ['A'])\n"
        "except RuntimeError as e:\n"
        "    assert '--legado-lo-se' in str(e)\n"
        "else:\n"
        "    raise AssertionError('align sin autorización no lanzó RuntimeError')\n"
    )
    r = _python(codigo)
    assert r.returncode == 0, r.stderr
    # Salidas capturadas del ds_official original (0af2abd) sobre listas de juguete.
    codigo = (
        "import ds_official as D\n"
        "assert D.align(['a %s', 'b', 'a %s', 'c'], ['A %s', 'B', 'A %s', 'C', 'D']) == "
        "{'a %s': 'A %s', 'b': 'B', 'c': 'C'}\n"
        "assert D.align(['x', 'y', 'x'], ['X', 'Y', 'Z']) == {'x': 'X', 'y': 'Y'}\n"
        "assert D.align([], ['X']) == {}\n"
    )
    r = _python(codigo, IE123_LEGADO_LO_SE="1")
    assert r.returncode == 0, r.stderr
