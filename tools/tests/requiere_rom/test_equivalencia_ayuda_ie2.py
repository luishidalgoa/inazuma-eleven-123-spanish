"""Equivalencia del motor de capturas de ayuda de IE2 con la salida vigente de su capa.

Mismo patrón que ``test_equivalencia_motores_ie2.py``: primero cada salida de
``work/ie2/shared/capas/graficos/ayuda/extra`` se compara con su hash golden
(``tests/compat/golden/ayuda_ie2.json``: solo hashes, Norma 2) para detectar que work/ cambió;
después el paquete (``ie2.comun.ayuda`` sobre ``nucleo.graficos.regiones``) reproduce esa salida byte
a byte desde las mismas entradas: el ``archive.fa`` japonés y las capturas de la NDS española.

Las pestañas de ``a_menu/system_b.arc`` se comprueban igual, pasándole a ``pestanas_arc`` el motor de
rótulos de la capa ``historial/graficos/v03_graficos`` (``pintado_menus.pintar``), que no está
portado: lo que se prueba aquí es el porteo de las cajas, la deducción de colores y el montaje del
CTPK, no ese motor.

Nunca escribe en work/. Requiere work/ local; en CI se deselecciona con ``-m "not requiere_rom"``.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

from ie123kit.nucleo.config.raiz import find_root

pytestmark = pytest.mark.requiere_rom

CAPA = "work/ie2/shared/capas/graficos/ayuda"
V03 = "work/ie2/shared/capas/historial/graficos/v03_graficos"
V06 = "work/ie2/shared/capas/historial/graficos/v06_graficos"
JP = "work/shared/base_3ds/romfs/archive.fa"
NDS_SP = "work/ie2/tormenta_de_fuego/fuentes/nds_es/data_iz/pic3d/script/sp"


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


@pytest.fixture(scope="module")
def raiz() -> Path:
    r = find_root()
    for rel in (f"{CAPA}/extra", JP, NDS_SP):
        if not (r / rel).exists():
            pytest.skip(f"falta recurso local: {rel}")
    return r


@pytest.fixture(scope="module")
def golden(raiz: Path) -> dict:
    return json.loads((raiz / "tools/tests/compat/golden/ayuda_ie2.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def japones(raiz: Path):
    from ie123kit.nucleo.contenedores.fa import FaArchive

    return FaArchive(str(raiz / JP))


def _capa(raiz: Path, ruta: str, sha_golden: str) -> bytes:
    datos = (raiz / CAPA / "extra" / ruta).read_bytes()
    assert _sha(datos) == sha_golden, f"{ruta}: work/ ha cambiado respecto al golden"
    return datos


def test_las_capturas_de_ayuda_son_las_de_la_capa(raiz: Path, golden: dict, japones) -> None:
    """Las 74 capturas (68 tt de la pantalla inferior y 3+3 syup_bg de la superior) salen idénticas."""
    pytest.importorskip("scipy")
    from ie123kit.ie2.comun import ayuda as A

    caps = A.capturas(p for p, _o, _n in japones.entries if p.startswith(A.AR))
    assert len(caps) == len(golden["capturas"]) == 74
    inferiores = paneles = 0
    for ruta, nombre in caps:
        nds = (raiz / NDS_SP / f"{nombre}.pac_").read_bytes()
        datos, informe = A.captura_arc(japones.read(ruta), nds, nombre)
        assert datos == _capa(raiz, ruta, golden["capturas"][ruta]), ruta
        if A.es_panel(nombre):
            paneles += 1
            assert sorted(informe["dx"]) == ["panel_3ds", "panel_nds"]
        else:
            inferiores += 1
            assert informe["zona_px"] > 1000
    assert (inferiores, paneles) == (68, 6)


#: Guion que monta las pestañas en un intérprete limpio y escribe el sha256 del .arc resultante.
#:
#: El motor de rótulos de la capa v03 (`pintado_menus`) arrastra `nombres.py`, que hace `import comun`.
#: Ese nombre es genérico y otras capas tienen el suyo, así que importarlo dentro de la suite lo mezcla
#: en `sys.modules` y el resultado depende del orden de los tests (fallaba con
#: «module 'comun' has no attribute 'jp'»). En un proceso nuevo se importa como cuando se ejecuta la
#: capa de verdad. La comprobación byte a byte no se relaja: se compara el sha del .arc montado.
_GUION_PESTANAS = """
import hashlib, json, sys
raiz, v06, v03, jp_fa, base = sys.argv[1:6]
sys.path.insert(0, sys.argv[6])
for ruta in (v06, v03):
    sys.path.insert(0, ruta)
import pintado_menus as PM
from ie123kit.ie2.comun import ayuda as A
from ie123kit.nucleo.contenedores.fa import FaArchive
jp = FaArchive(jp_fa)
with open(base, 'rb') as fh:
    datos, informe = A.pestanas_arc(jp.read(A.SYSTEM_B), fh.read(), pintar=PM.pintar)
print(json.dumps({'sha': hashlib.sha256(datos).hexdigest(), 'cambios': informe['cambios'],
                  'fallos': informe['fallos'], 'pestanas': list(A.PESTANAS)}))
"""


def test_las_pestanas_de_system_b_son_las_de_la_capa(raiz: Path, golden: dict) -> None:
    """``window_b02`` (Controles/Recursos en 4 estados) y ``panel_b04`` (Controles básicos), idénticas."""
    import subprocess

    from ie123kit.ie2.comun import ayuda as A

    base_v06 = raiz / V06 / "extra" / A.SYSTEM_B
    if not base_v06.is_file():
        pytest.skip("falta la base v06 de system_b.arc")
    assert _sha(base_v06.read_bytes()) == golden["system_b"]["base_v06"]

    r = subprocess.run(
        [sys.executable, "-X", "utf8", "-c", _GUION_PESTANAS, str(raiz), str(raiz / V06), str(raiz / V03),
         str(raiz / JP), str(base_v06), str(raiz / "tools/src")],
        capture_output=True, text=True, encoding="utf-8", check=False,
    )
    if r.returncode != 0:
        if "pintado_menus" in r.stderr or "ModuleNotFoundError" in r.stderr:
            pytest.skip(f"no se puede cargar el motor de rótulos de v03: {r.stderr.strip()[-300:]}")
        pytest.fail("el montaje de las pestañas ha fallado:\n" + r.stderr[-1500:])
    salida = json.loads(r.stdout.strip().splitlines()[-1])

    assert salida["cambios"] == salida["pestanas"] and not salida["fallos"]
    # Byte a byte: el sha del .arc montado por el paquete es el de la salida vigente de la capa.
    esperado = _capa(raiz, A.SYSTEM_B, golden["system_b"]["salida"])
    assert salida["sha"] == _sha(esperado)


def test_la_reversion_de_mastutorial_sigue_siendo_el_japones(raiz: Path, golden: dict, japones) -> None:
    """La capa revierte el paquete DS de tutorial: su salida es el japonés tal cual."""
    from ie123kit.ie2.comun import ayuda as A

    assert _capa(raiz, A.MASTUTORIAL, golden["mastutorial"]) == japones.read(A.MASTUTORIAL)
