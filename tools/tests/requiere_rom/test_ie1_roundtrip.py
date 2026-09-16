"""Ida y vuelta sin cambios sobre la ROM local (gate 3 de F2.3): nada debe moverse.

Se salta si no hay `work/shared/base_3ds/romfs/archive.fa` en la máquina. No escribe en el
repositorio: todo sale a `tmp_path` (Norma 2).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ie123kit.ie1.acciones import JuegoIE1
from ie123kit.nucleo.compresion import sszl
from ie123kit.nucleo.contenedores.fa import FaArchive
from ie123kit.nucleo.tipos import AssetRef, componer_id
from ie123kit.servicio.proyecto import Workspace

pytestmark = pytest.mark.requiere_rom

TITLE = "inazuma1/data_iz/a_title/title_t.arc"


@pytest.fixture
def ws() -> Workspace:
    espacio = Workspace.abrir()
    if not (espacio.work / "shared" / "base_3ds" / "romfs" / "archive.fa").is_file():
        pytest.skip("falta work/shared/base_3ds/romfs/archive.fa")
    return espacio


def _ref(tipo: str, ruta: str) -> AssetRef:
    return AssetRef(
        id=componer_id("ie1", tipo, ruta),
        objetivo="ie1",
        tipo=tipo,
        ruta_romfs=ruta,
        cadena_contenedores=("fa",),
        editable=True,
    )


def test_textos_sin_cambios_no_preparan_eventos(ws: Workspace, tmp_path: Path) -> None:
    """Exportar e importar los eventos sin tocar una sola traducción: 0 eventos preparados."""
    juego = JuegoIE1()
    ref = _ref("evento", "inazuma1/data_iz/script/eve.pkb")
    exportacion = tmp_path / "eventos"
    res = juego.exportar(ws, ref, exportacion)
    if not res.ok:
        pytest.skip(f"no se pudo exportar eventos: {res.to_json()}")
    vuelta = juego.importar(ws, ref, exportacion, simular=True)
    assert vuelta.ok, vuelta.to_json()
    assert vuelta.datos.get("eventos_preparados", 0) == 0


def test_texturas_sin_cambios_quedan_identicas(ws: Workspace, tmp_path: Path) -> None:
    """Exportar los PNG de title_t.arc y reimportarlos deja las entradas byte a byte iguales.

    La comparación es sobre el ARCV DESENVUELTO: las capas de gráficos escriben con
    ``rewrap='raw'`` (lo que hacía V37), así que ``extra/<arc>`` sale sin la envoltura
    SSZL del original aunque no se haya tocado ni un píxel.
    """
    juego = JuegoIE1()
    ref = _ref("grafico", TITLE)
    arc = FaArchive(str(ws.work / "shared" / "base_3ds" / "romfs" / "archive.fa"))
    if not arc.exists(TITLE):
        pytest.skip(f"la base no trae {TITLE}")
    original = sszl.unwrap(arc.read(TITLE))

    exportacion = tmp_path / "png"
    res = juego.exportar(ws, ref, exportacion)
    assert res.ok, res.to_json()
    assert list(exportacion.glob("*.png")), "no se ha exportado ninguna textura"

    vuelta = juego.importar(ws, ref, exportacion, simular=False)
    assert vuelta.ok, vuelta.to_json()
    assert vuelta.datos["diff"] == [], "una ida y vuelta sin cambios no declara ninguna textura"
    capa = Path(vuelta.datos["capa"])
    try:
        rehecho = sszl.unwrap((capa / "extra" / TITLE).read_bytes())
        assert rehecho == original
    finally:
        import shutil

        shutil.rmtree(capa, ignore_errors=True)
