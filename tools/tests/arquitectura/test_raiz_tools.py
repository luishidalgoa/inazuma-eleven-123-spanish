"""Fija el contenido final de la raíz de tools/: los 5 congelados, los .ps1 y ningún shim (F2.7)."""
from __future__ import annotations

import shutil
import subprocess

import pytest

from ie123kit.nucleo.compat import shims
from ie123kit.nucleo.config.raiz import find_root

RAIZ = find_root()
TOOLS = RAIZ / "tools"

PS1 = frozenset(
    {
        "build_patch.ps1",
        "extract_nds.ps1",
        "extract_romfs.ps1",
        "jugar.ps1",
        "setup_mobipeg.ps1",
        "setup_vgmstream.ps1",
    }
)
# F2.6 (#55): _archivo/ se borró; los retirados están en docs/toolkit/SCRIPTS_RETIRADOS.md.
CARPETAS_Y_META = frozenset({"src", "tests", "pyproject.toml", "README.md"})
# tools/bin/ está en .gitignore; se tolera por si una copia local no lo filtrase.
OPCIONALES = frozenset({"bin"})
# Cachés locales toleradas: hoy .gitignore ya ignora __pycache__/, .pytest_cache/,
# .ruff_cache/ y *.egg-info/, así que este conjunto queda vacío a propósito.
CACHES_TOLERADAS: frozenset[str] = frozenset()

ESPERADO = (
    frozenset(f"{n}.py" for n in shims.CONGELADOS)
    | frozenset(f"{n}.py" for n in shims.MAPA)
    | PS1
    | CARPETAS_Y_META
)


def _no_ignoradas(entradas: list[str]) -> set[str]:
    if shutil.which("git") is None:
        pytest.skip("git no está disponible")
    dentro = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"], cwd=RAIZ, capture_output=True, text=True, check=False
    )
    if dentro.returncode != 0 or dentro.stdout.strip() != "true":
        pytest.skip(f"{RAIZ} no es un repositorio git")
    rutas = {}
    for e in entradas:
        rel = f"tools/{e}/" if (TOOLS / e).is_dir() else f"tools/{e}"
        rutas[rel] = e
    entrada = "".join(f"{r}\0" for r in rutas).encode("utf-8")
    res = subprocess.run(
        ["git", "check-ignore", "--stdin", "-z"], cwd=RAIZ, input=entrada, capture_output=True, check=False
    )
    if res.returncode not in (0, 1):
        pytest.fail(f"git check-ignore falló: {res.stderr.decode('utf-8', 'replace')}")
    ignoradas = {r for r in res.stdout.decode("utf-8").split("\0") if r}
    return {e for r, e in rutas.items() if r not in ignoradas}


def test_contenido_raiz_tools():
    presentes = _no_ignoradas(sorted(p.name for p in TOOLS.iterdir())) - CACHES_TOLERADAS
    sobrantes = sorted(presentes - ESPERADO - OPCIONALES)
    faltantes = sorted(ESPERADO - presentes)
    tests_raiz = sorted(p for p in presentes if p.startswith("test_") and p.endswith(".py"))
    assert not tests_raiz, f"no debe haber tools/test_*.py: {tests_raiz}"
    assert not sobrantes and not faltantes, f"sobrantes: {sobrantes}; faltantes: {faltantes}"


def test_sin_shims_en_tools():
    """F2.7: no queda ningún shim en tools/; todo se importa como ie123kit.<...>."""
    assert shims.MAPA == {}
    reaparecidos = sorted(n for n in shims.RETIRADOS if (TOOLS / f"{n}.py").exists())
    assert not reaparecidos, f"shims retirados de vuelta en tools/: {reaparecidos}"
    con_alias = sorted(
        p.name for p in TOOLS.glob("*.py") if "sys.modules[__name__]" in p.read_bytes().decode("utf-8")
    )
    assert not con_alias, f"ficheros de tools/ que son shims: {con_alias}"


@pytest.mark.parametrize("nombre", sorted(shims.CONGELADOS))
def test_congelados_no_son_shims(nombre):
    assert nombre not in shims.MAPA
    ruta = TOOLS / f"{nombre}.py"
    assert ruta.is_file()
    assert "sys.modules[__name__]" not in ruta.read_bytes().decode("utf-8")
