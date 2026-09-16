"""Gate 3 del juego principal: inventario real y ida y vuelta de las texturas de menu/title.arc.

Requiere work/ local (ROM extraída); en CI se deselecciona con -m "not requiere_rom".
"""

from pathlib import Path

import pytest

pytestmark = pytest.mark.requiere_rom

BASE = Path("work/shared/base_3ds")
ARCHIVE = BASE / "romfs" / "archive.fa"
ARC = "menu/title.arc"
ESPERADOS = (
    "menu/title.arc",
    "menu/common.arc",
    "menu/data_replace",
    "movie/OP.moflex",
    "movie/logo_l5.moflex",
    "cro/ina_menu.cro",
)


@pytest.fixture
def raiz():
    from ie123kit.nucleo.config.raiz import find_root

    r = find_root()
    if not (r / ARCHIVE).is_file():
        pytest.skip(f"falta {ARCHIVE} (base extraída local)")
    return r


def _rutas_del_inventario(raiz):
    from ie123kit.servicio.api import ServicioToolkit

    servicio = ServicioToolkit.abrir(raiz)
    res = servicio.activos("juego_principal")
    assert res.ok, res.to_json()
    rutas = {a["ruta_romfs"] for a in res.datos["activos"]}
    juego = servicio.juegos["juego_principal"]
    rutas |= {r.ruta_romfs for r in juego.activos(servicio.ws)}  # CRO y ExeFS (fusión del servicio)
    return rutas


def test_el_inventario_cubre_el_alcance_del_menu(raiz):
    rutas = _rutas_del_inventario(raiz)
    for esperado in ESPERADOS:
        assert any(ruta == esperado or ruta.startswith(esperado) for ruta in rutas), esperado


def test_el_smdh_del_exefs_aparece(raiz):
    exefs = raiz / BASE / "exefs"
    if not exefs.is_dir():
        pytest.skip("falta el ExeFS extraído (soporte experimental)")
    rutas = _rutas_del_inventario(raiz)
    assert {"banner.bnr", "icon.icn"} & rutas


def test_exportar_e_importar_sin_cambios_deja_las_texturas_identicas(raiz, tmp_path):
    from ie123kit.juego_principal.acciones import OBJETIVO, JuegoPrincipal
    from ie123kit.nucleo.compresion import sszl
    from ie123kit.nucleo.contenedores.fa import FaArchive
    from ie123kit.nucleo.graficos import texturas
    from ie123kit.nucleo.tipos import AssetRef, componer_id
    from ie123kit.servicio.proyecto import Workspace

    ws = Workspace.abrir(raiz)
    juego = JuegoPrincipal()
    ref = AssetRef(
        id=componer_id(OBJETIVO, "grafico", ARC),
        objetivo=OBJETIVO,
        tipo="grafico",
        ruta_romfs=ARC,
        cadena_contenedores=("fa", "arcv", "ctpk"),
    )
    exportado = juego.exportar(ws, ref, tmp_path / "exp")
    assert exportado.ok, exportado.to_json()

    importado = juego.importar(ws, ref, tmp_path / "exp" / Path(ARC).stem, simular=False)
    assert importado.ok, importado.to_json()

    arc = FaArchive(raiz / ARCHIVE)
    original = sszl.unwrap(arc.read(ARC))
    nuevo = sszl.unwrap(Path(importado.artefactos[0]).read_bytes())
    assert texturas.texture_map(nuevo) == texturas.texture_map(original)
    assert nuevo == original, "una ida y vuelta sin cambios debe dejar el .arc byte a byte igual"
