"""Fachadas de texto NDS y eventos de F1.4 (#45): pkb_unpack, build_glossary, ds_official y audit_dialogo_ids.

Sin ROM. Cada comprobación corre en subproceso con cwd = raíz y PYTHONPATH vacío. Desde la F2.7
no hay shims en tools/: se importa el módulo real (``ie123kit._legado.<mod>``).
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

_CABECERA = (
    "import importlib, json, os, sys\n"
    "sys.path.insert(0, 'tools/src')\n"
    "import ie123kit._legado.pkb_unpack as pkb_unpack\n"
    "import ie123kit._legado.build_glossary as build_glossary\n"
    "import ie123kit._legado.ds_official as ds_official\n"
)


def _retirados(*nombres):
    for n in nombres:
        assert not (TOOLS / f"{n}.py").exists(), f"tools/{n}.py debería estar retirado (F2.7)"


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
    _retirados(nombre)
    codigo = (
        "nombre, destino, sup = sys.argv[1:4]\n"
        "m = importlib.import_module(destino)\n"
        "faltan = [n for n in json.load(open(sup, encoding='utf-8'))[nombre] if not hasattr(m, n)]\n"
        "assert not faltan, faltan\n"
    )
    r = _python(codigo, nombre, shims.DESTINOS[nombre], str(SUPERFICIE))
    assert r.returncode == 0, r.stderr


def test_identidades():
    codigo = (
        "from ie123kit.nucleo.texto import nds_latin\n"
        "assert pkb_unpack.NDS_DEC is build_glossary.NDS_DEC is nds_latin.NDS_DEC\n"
        "assert pkb_unpack._decode_string is nds_latin.decode_cadena\n"
        "assert ds_official.DS_TABLE is nds_latin.DS_TABLE\n"
        "assert ds_official.DS_TABLE is not nds_latin.NDS_DEC\n"
    )
    r = _python(codigo)
    assert r.returncode == 0, r.stderr


def test_rutas_build_glossary():
    raiz = str(RAIZ)
    codigo = (
        "B = build_glossary\n"
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
    r = subprocess.run([sys.executable, "-X", "utf8", "-m", "ie123kit._legado.ds_official"], cwd=RAIZ,
                       env=_entorno(), capture_output=True, text=True, encoding="utf-8", timeout=120, check=False)
    assert r.returncode == 2
    assert r.stdout == ""
    assert "--legado-lo-se" in r.stderr


def test_align_requiere_autorizacion():
    codigo = (
        "D = ds_official\n"
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
        "D = ds_official\n"
        "assert D.align(['a %s', 'b', 'a %s', 'c'], ['A %s', 'B', 'A %s', 'C', 'D']) == "
        "{'a %s': 'A %s', 'b': 'B', 'c': 'C'}\n"
        "assert D.align(['x', 'y', 'x'], ['X', 'Y', 'Z']) == {'x': 'X', 'y': 'Y'}\n"
        "assert D.align([], ['X']) == {}\n"
    )
    r = _python(codigo, IE123_LEGADO_LO_SE="1")
    assert r.returncode == 0, r.stderr
