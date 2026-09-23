"""Cuarentena de los módulos obsolete_dangerous y fachada de reinsert (F1.4, T2).

Desde la F2.6 (#55) los cuatro en cuarentena ya no tienen shim plano en ``tools/`` (nadie los
importaba): se comprueban directamente sobre ``ie123kit._legado.<mod>`` y su CLI se lanza con
``python -m ie123kit._legado.<mod>``.
"""
from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys

import pytest

from ie123kit.nucleo.compat import shims
from ie123kit.nucleo.config.raiz import find_root

RAIZ = find_root()
TOOLS = RAIZ / "tools"
CUARENTENA = ("ds_roster", "reinsert_var", "ssd_reinsert", "validate")
SUPERFICIE = json.loads((TOOLS / "tests/compat/superficie_v0.json").read_text(encoding="utf-8"))


def _importar(nombre: str):
    return importlib.import_module(f"ie123kit._legado.{nombre}")


@pytest.mark.parametrize("nombre", CUARENTENA)
def test_cli_se_niega_sin_bandera(nombre):
    entorno = {k: v for k, v in os.environ.items() if not k.startswith("IE123_")}
    r = subprocess.run([sys.executable, "-X", "utf8", "-m", f"ie123kit._legado.{nombre}"],
                       cwd=RAIZ, env=entorno,
                       capture_output=True, text=True, encoding="utf-8", check=False)
    assert r.returncode == 2
    assert r.stdout == ""
    assert "--legado-lo-se" in r.stderr and "cuarentena" in r.stderr


@pytest.mark.parametrize("nombre", CUARENTENA + ("reinsert",))
def test_superficie(nombre):
    """La superficie pública del módulo real sigue siendo la del script original de tools/."""
    if nombre in CUARENTENA:
        assert nombre in shims.RETIRADOS and not (TOOLS / f"{nombre}.py").exists()
    else:
        assert shims.MAPA[nombre] == f"ie123kit._legado.{nombre}"
    mod = _importar(nombre)
    for atributo in SUPERFICIE[nombre]:
        getattr(mod, atributo)


def test_funciones_de_libreria():
    assert _importar("reinsert_var").DONT_TOUCH == {81000040}
    assert callable(_importar("validate").run)
    assert callable(_importar("ds_roster").patch_unitbase)
    from ie123kit import _legado
    assert _legado.CUARENTENA == frozenset(CUARENTENA)
    assert _legado.EXCLUIDOS_DEL_REGISTRO == _legado.CUARENTENA | {"ds_official"}
    assert _legado.BANDERA_LEGADO == "--legado-lo-se"
