"""Traslados de F1.4 (#45): divisiones, fachadas _legado, cuarentena y archivado.

Sin ROM. Describe el ESTADO FINAL de la subfase: la parte estricta (MAPA completo,
raíz de tools/, archivados) no se salta. Solo la comprobación por módulo se salta si
tools/<nombre>.py todavía no es un shim.
"""

import hashlib
import os
import subprocess
import sys
from pathlib import Path

import pytest

from ie123kit.nucleo.compat import shims
from ie123kit.nucleo.config.raiz import find_root

TRASLADOS_F14 = {
    "pkb_unpack": "ie123kit._legado.pkb_unpack",
    "build_glossary": "ie123kit._legado.build_glossary",
    "ds_official": "ie123kit._legado.ds_official",
    "reinsert": "ie123kit._legado.reinsert",
    "translate_ui_textures": "ie123kit._legado.translate_ui_textures",
    "mods_to_moflex": "ie123kit._legado.mods_to_moflex",
    "audit_dialogo_ids": "ie123kit._legado.audit_dialogo_ids",
    "ds_roster": "ie123kit._legado.ds_roster",
    "reinsert_var": "ie123kit._legado.reinsert_var",
    "ssd_reinsert": "ie123kit._legado.ssd_reinsert",
    "validate": "ie123kit._legado.validate",
    "verify_candidate": "ie123kit._legado.verify_candidate",
    "ie1_keyboard": "ie123kit.ie1.graficos.teclado",
}
ARCHIVADOS_F14 = ["ie1_tables", "ie1_media", "validate_ie1_media", "patch_exefs", "patch_code", "patch_cro"]
CONGELADOS = {"dialogue_typography", "font_patch", "dialogue_lock", "build_ie1_probe", "build_ui_revision"}
# F1.5 (#46): los tests heredados de la raíz de tools/ viven ahora en tools/tests/unidad.
TESTS_TRASLADADOS_F15 = {
    "test_dialogue_lock": ["tools/tests/unidad/texto/test_dialogue_lock.py"],
    "test_dialogue_typography": ["tools/tests/unidad/texto/test_ancho_completo.py"],
    "test_probe_layout": ["tools/tests/unidad/texto/test_tipografia_v20.py"],
    "test_legacy_sprite": [
        "tools/tests/unidad/graficos/test_pac_sprite.py",
        "tools/tests/unidad/compresion/test_lz10.py",
    ],
    "test_ssd_records": ["tools/tests/unidad/eventos/test_ssd.py"],
    "test_ui_formats": ["tools/tests/unidad/graficos/test_formatos_ui.py"],
}

RAIZ = find_root()
TOOLS = RAIZ / "tools"
COMPAT = Path(__file__).resolve().parent
SUPERFICIE = COMPAT / "superficie_v0.json"
GOLDEN_CONGELADOS = COMPAT / "golden" / "congelados.sha256"

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


def test_mapa():
    assert len(TRASLADOS_F14) == 13
    distintos = {n: (shims.MAPA.get(n), d) for n, d in TRASLADOS_F14.items()
                 if n not in shims.RETIRADOS and shims.MAPA.get(n) != d}
    assert not distintos, f"MAPA difiere de TRASLADOS_F14 (actual, esperado): {distintos}"
    # 29 shims hasta la F2.4; ese día se retiraron los 5 de CLI (shims.RETIRADOS, #50).
    assert len(shims.MAPA) == 29 - len(shims.RETIRADOS) == 24


@pytest.mark.parametrize("nombre", [n for n in TRASLADOS_F14 if n not in shims.RETIRADOS])
def test_shim_trasladado_f14(nombre):
    ruta = TOOLS / f"{nombre}.py"
    if not _trasladado(nombre):
        pytest.skip("aún sin trasladar")
    ok, motivo = shims.es_shim_sin_logica(ruta)
    assert ok is True, f"{ruta}: {motivo}"
    assert shims.destino_de_shim(ruta) == TRASLADOS_F14[nombre]
    r = _python(_SUBPROCESO_SHIM, nombre, TRASLADOS_F14[nombre], str(SUPERFICIE))
    assert r.returncode == 0, r.stderr


@pytest.mark.parametrize("nombre", ARCHIVADOS_F14)
def test_archivados_f14(nombre):
    assert not (TOOLS / f"{nombre}.py").exists(), f"tools/{nombre}.py debería estar archivado"
    assert (TOOLS / "_archivo" / f"{nombre}.py").is_file(), f"falta tools/_archivo/{nombre}.py"
    codigo = (
        "import sys\n"
        "sys.path.insert(0, 'tools')\n"
        "try:\n"
        f"    import {nombre}\n"
        "except ModuleNotFoundError:\n"
        "    sys.exit(0)\n"
        "sys.exit(3)\n"
    )
    r = _python(codigo)
    assert r.returncode == 0, f"import {nombre} no dio ModuleNotFoundError: {r.stderr}"


def test_raiz_tools_final():
    presentes = {p.stem for p in TOOLS.glob("*.py")}
    esperados = CONGELADOS | set(shims.MAPA)
    assert presentes == esperados, {
        "sobran": sorted(presentes - esperados),
        "faltan": sorted(esperados - presentes),
    }
    fallos = {}
    for nombre in shims.MAPA:
        ok, motivo = shims.es_shim_sin_logica(TOOLS / f"{nombre}.py")
        if ok is not True:
            fallos[nombre] = motivo
    assert not fallos, fallos


def test_tests_trasladados_f15():
    assert not sorted(p.name for p in TOOLS.glob("test_*.py")), "quedan tests heredados en tools/"
    faltan = [r for rutas in TESTS_TRASLADADOS_F15.values() for r in rutas if not (RAIZ / r).is_file()]
    assert not faltan, f"faltan tests trasladados: {faltan}"


def test_congelados_intactos():
    esperados = {}
    for linea in GOLDEN_CONGELADOS.read_text(encoding="utf-8").splitlines():
        if linea.strip():
            digest, ruta = linea.split(maxsplit=1)
            esperados[ruta.strip()] = digest
    assert len(esperados) == 5
    for ruta, digest in esperados.items():
        actual = hashlib.sha256((RAIZ / ruta).read_bytes()).hexdigest()
        assert actual == digest, f"{ruta} ha cambiado"


def test_identidades_texto():
    codigo = (
        "import sys\n"
        "sys.path.insert(0, 'tools')\n"
        "import build_ie1_probe, dialogue_typography, pkb_unpack\n"
        "import ie123kit.nucleo.texto.tipografia_v20 as tipografia_v20\n"
        "import ie123kit.nucleo.texto.ancho_completo as ancho_completo\n"
        "import ie123kit.nucleo.texto.nds_latin as nds_latin\n"
        "assert tipografia_v20.layout is build_ie1_probe.layout\n"
        "assert ancho_completo.encode_fullwidth is dialogue_typography.encode_fullwidth\n"
        "assert pkb_unpack.NDS_DEC is nds_latin.NDS_DEC\n"
        "assert nds_latin.NDS_DEC is not nds_latin.DS_TABLE\n"
    )
    r = _python(codigo)
    assert r.returncode == 0, r.stderr
