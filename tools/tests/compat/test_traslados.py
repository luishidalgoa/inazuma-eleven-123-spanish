"""Traslados de F1.3 (#44): los 16 módulos de motor de tools/ pasaron a ie123kit con shims de alias.

Sin ROM. Desde la F2.7 ya no queda ningún shim: se comprueba que el módulo real conserva la
superficie del script original y que los congelados resuelven sus nombres planos al paquete
mediante ``ie123kit.nucleo.config.congelados.preparar``.
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

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
SUPERFICIE = Path(__file__).resolve().parent / "superficie_v0.json"

_SUBPROCESO_MODULO = """import importlib, json, sys
sys.path.insert(0, 'tools/src')
nombre, destino, superficie = sys.argv[1], sys.argv[2], sys.argv[3]
m = importlib.import_module(destino)
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


def test_destinos_coinciden_con_traslados():
    assert len(TRASLADOS) == 16
    distintos = {n: (shims.DESTINOS.get(n), d) for n, d in TRASLADOS.items() if shims.DESTINOS.get(n) != d}
    assert not distintos, f"DESTINOS difiere de TRASLADOS (actual, esperado): {distintos}"
    assert set(TRASLADOS) <= shims.RETIRADOS
    assert not set(TRASLADOS) & shims.CONGELADOS


@pytest.mark.parametrize("nombre", sorted(TRASLADOS))
def test_shim_retirado_y_modulo_real(nombre):
    """F2.4 (#50) y F2.7: el shim ya no está en tools/ ni en MAPA; el módulo real conserva la superficie."""
    assert not (TOOLS / f"{nombre}.py").exists(), f"tools/{nombre}.py debería estar retirado"
    assert nombre not in shims.MAPA
    r = _python(_SUBPROCESO_MODULO, nombre, TRASLADOS[nombre], str(SUPERFICIE))
    assert r.returncode == 0, r.stderr


def test_nombre_plano_ya_no_importa():
    r = _python("import sys; sys.path.insert(0, 'tools'); import lz10")
    assert r.returncode != 0 and "ModuleNotFoundError" in r.stderr


def test_lz10_mutacion_de_globales_por_alias_de_congelados():
    """El alias que usan los congelados es el mismo objeto módulo: mutar uno muta el otro."""
    codigo = (
        "import sys\n"
        "sys.path.insert(0, 'tools/src')\n"
        "from ie123kit.nucleo.config.congelados import preparar\n"
        "preparar()\n"
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
    codigo = (
        "import importlib.util, sys\n"
        "sys.path.insert(0, 'tools/src')\n"
        "from ie123kit.nucleo.config.congelados import preparar\n"
        "preparar()\n"
        "import font_patch\n"
        "import ie123kit._legado.bcfnt as bcfnt\n"
        "assert font_patch.BCFNT is bcfnt.BCFNT\n"
        "import ie123kit.nucleo.contenedores.fa as fa\n"
        "spec = importlib.util.spec_from_file_location('build_ui_revision_importado', 'tools/build_ui_revision.py')\n"
        "mod = importlib.util.module_from_spec(spec)\n"
        "spec.loader.exec_module(mod)\n"  # sin __main__: no ejecuta main() ni ningún build
        "assert mod.FaArchive is fa.FaArchive, (mod.FaArchive, fa.FaArchive)\n"
        "assert mod.fe_offset_of is fa.fe_offset_of, (mod.fe_offset_of, fa.fe_offset_of)\n"
    )
    r = _python(codigo)
    assert r.returncode == 0, r.stderr
    assert r.stdout == ""


def test_congelado_sin_preparar_no_importa():
    """Sin preparar(), los nombres planos de los congelados ya no existen (no hay shims)."""
    r = _python("import sys; sys.path.insert(0, 'tools'); import build_ie1_probe")
    assert r.returncode != 0 and "ModuleNotFoundError" in r.stderr
