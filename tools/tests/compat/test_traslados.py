"""Traslados de F1.3 (#44): los 16 módulos de motor de tools/ pasan a ie123kit con shims de alias.

Sin ROM. Un módulo cuyo tools/<nombre>.py todavía no es un shim se salta
(«aún sin trasladar»), para que cada commit intermedio de la subfase pase.
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

import ie123kit
from ie123kit.nucleo.compat import shims
from ie123kit.nucleo.config.raiz import find_root

# Orden del issue #44. Los CLI con salida van a fachadas _legado (nucleo no imprime).
TRASLADOS = {
    "lz10": "ie123kit.nucleo.compresion.lz10",
    "blz": "ie123kit._legado.blz",
    "sszl": "ie123kit.nucleo.compresion.sszl",
    "ui_archive": "ie123kit._legado.ui_archive",
    "nds_unpack": "ie123kit._legado.nds_unpack",
    "qna_regions": "ie123kit.nucleo.graficos.qna",
    "legacy_sprite": "ie123kit.nucleo.graficos.pac_sprite",
    "nftr_metrics": "ie123kit._legado.nftr_metrics",
    "bcfnt": "ie123kit._legado.bcfnt",
    "ctpk_ui": "ie123kit.nucleo.graficos.ctpk",
    "ssd_records": "ie123kit.nucleo.eventos.ssd",
    "fa_unpack": "ie123kit._legado.fa_unpack",
    "fa_repack": "ie123kit._legado.fa_repack",
    "patch_smdh_title": "ie123kit._legado.patch_smdh_title",
    "harvest_log": "ie123kit._legado.harvest_log",
    "limpiar_work": "ie123kit._legado.limpiar_work",
}

RAIZ = find_root()
TOOLS = RAIZ / "tools"
SRC_PAQUETE = Path(ie123kit.__file__).resolve().parent
SUPERFICIE = Path(__file__).resolve().parent / "superficie_v0.json"

_SUBPROCESO_SHIM = """\
import importlib, json, sys
sys.path.insert(0, 'tools')
nombre, destino, superficie = sys.argv[1], sys.argv[2], sys.argv[3]
m = importlib.import_module(nombre)
real = importlib.import_module(destino)
assert m is real, (m, real)
assert sys.modules[nombre] is real
faltan = []
with open(superficie, encoding='utf-8') as fh:
    nombres = json.load(fh)[nombre]
for n in nombres:
    obj = m
    try:
        for parte in n.split('.'):
            obj = getattr(obj, parte)
    except AttributeError:
        faltan.append(n)
assert not faltan, f'{nombre}: faltan nombres de superficie_v0.json: {faltan}'
"""


def _trasladado(nombre: str) -> bool:
    ruta = TOOLS / f"{nombre}.py"
    return ruta.is_file() and "sys.modules[__name__]" in ruta.read_text(encoding="utf-8", errors="replace")


def _python(codigo: str, *args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["PYTHONPATH"] = ""
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.pop("IE123_ROOT", None)
    return subprocess.run(
        [sys.executable, "-X", "utf8", "-c", codigo, *args],
        cwd=RAIZ,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def test_mapa_coincide_con_traslados():
    assert len(TRASLADOS) == 16
    distintos = {n: (shims.MAPA.get(n), d) for n, d in TRASLADOS.items()
                 if n not in shims.RETIRADOS and shims.MAPA.get(n) != d}
    assert not distintos, f"MAPA difiere de TRASLADOS (actual, esperado): {distintos}"
    assert not set(TRASLADOS) & shims.CONGELADOS


@pytest.mark.parametrize("nombre", sorted(shims.RETIRADOS))
def test_shims_de_cli_retirados_en_f24(nombre):
    """F2.4 (#50): el shim de CLI ya no está en tools/ ni en MAPA, pero el módulo real sigue."""
    assert not (TOOLS / f"{nombre}.py").exists(), f"tools/{nombre}.py debería estar retirado"
    assert nombre not in shims.MAPA
    r = _python(f"import sys; sys.path.insert(0, 'tools/src'); import ie123kit._legado.{nombre}")
    assert r.returncode == 0, r.stderr


@pytest.mark.parametrize("nombre", [n for n in TRASLADOS if n not in shims.RETIRADOS])
def test_shim_trasladado(nombre):
    ruta = TOOLS / f"{nombre}.py"
    if not _trasladado(nombre):
        pytest.skip("aún sin trasladar")
    ok, motivo = shims.es_shim_sin_logica(ruta)
    assert ok is True, f"{ruta}: {motivo}"
    assert shims.destino_de_shim(ruta) == TRASLADOS[nombre]
    r = _python(_SUBPROCESO_SHIM, nombre, TRASLADOS[nombre], str(SUPERFICIE))
    assert r.returncode == 0, r.stderr


def test_lz10_mutacion_de_globales():
    if not _trasladado("lz10"):
        pytest.skip("aún sin trasladar")
    codigo = (
        "import sys\n"
        "sys.path.insert(0, 'tools')\n"
        "import lz10\n"
        "import ie123kit.nucleo.compresion.lz10 as real\n"
        "assert lz10 is real\n"
        "original = real.MAX_CAND\n"
        "lz10.MAX_CAND = original + 1\n"
        "assert real.MAX_CAND == original + 1, (real.MAX_CAND, original)\n"
    )
    r = _python(codigo)
    assert r.returncode == 0, r.stderr


def test_font_patch_y_build_ui_revision_resuelven_al_paquete():
    if not (_trasladado("bcfnt") and _trasladado("fa_unpack")):
        pytest.skip("bcfnt o fa_unpack aún sin trasladar")
    comprobar_repack = _trasladado("fa_repack")
    codigo = (
        "import importlib.util, sys\n"
        "sys.path.insert(0, 'tools')\n"
        "import font_patch, bcfnt\n"
        "assert font_patch.BCFNT is bcfnt.BCFNT\n"
        "import ie123kit.nucleo.contenedores.fa as fa\n"
        "spec = importlib.util.spec_from_file_location('build_ui_revision_importado', 'tools/build_ui_revision.py')\n"
        "mod = importlib.util.module_from_spec(spec)\n"
        "spec.loader.exec_module(mod)\n"  # sin __main__: no ejecuta main() ni ningún build
        "assert mod.FaArchive is fa.FaArchive, (mod.FaArchive, fa.FaArchive)\n"
        f"if {comprobar_repack!r}:\n"
        "    assert mod.fe_offset_of is fa.fe_offset_of, (mod.fe_offset_of, fa.fe_offset_of)\n"
    )
    r = _python(codigo)
    assert r.returncode == 0, r.stderr
    assert r.stdout == ""


def test_src_sin_parents_indexado():
    fallos = []
    for ruta in sorted(SRC_PAQUETE.rglob("*.py")):
        if "__pycache__" in ruta.parts:
            continue
        for n, linea in enumerate(ruta.read_text(encoding="utf-8").splitlines(), 1):
            if "parents[" in linea or "dirname(dirname" in linea:
                fallos.append(f"{ruta.relative_to(RAIZ).as_posix()}:{n}: {linea.strip()}")
    assert not fallos, "\n".join(fallos)
