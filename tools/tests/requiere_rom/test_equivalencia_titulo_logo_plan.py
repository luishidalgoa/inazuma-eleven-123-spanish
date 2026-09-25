"""Equivalencia: el PLAN de la capa titulo_logo (antes v67) pasado por texturas.apply_plan da el mismo .arc.

Tercer punto del issue #48: la primitiva nueva tiene que reproducir byte a byte lo que ya
produjo la capa, no solo «algo parecido». Se reconstruye aquí el plan de
``work/ie1/capas/graficos/titulo_logo/apply.py`` (una sola entrada, la textura
``ie01_title_t_tlogo.tga``, caja (0, 0, 352, 112), logo recortado por el bbox de su alfa,
escalado LANCZOS con 1 px de margen por lado, centrado sobre un lienzo RGBA transparente y con
el RGB de los píxeles de alfa 0 puesto a negro) y se compara con ``extra/`` .

La capa comprime su salida con SSZL, así que aquí ``rewrap='sszl'``; el defecto de apply_plan
es ``'raw'``, que es lo que hace V37.

Todo lo que toca la ROM se escribe en un directorio temporal del sistema: nunca dentro de work/.
Las rutas (base, logo, caja) se leen por AST del propio apply.py para no fijar aquí ninguna ruta
de máquina.
"""

from __future__ import annotations

import ast
import shutil
import tempfile
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from ie123kit.nucleo.config.raiz import find_root
from ie123kit.nucleo.graficos import texturas

pytestmark = pytest.mark.requiere_rom

CAPA = "work/ie1/capas/graficos/titulo_logo"
# probe_ie1_v66 se borró. El title_t.arc de la capa solo difiere del de la base extraída en la
# textura del logo (golden.regenerar_capa lo comprueba), así que la base es work/shared/base_3ds.
BASE = "work/shared/base_3ds/romfs/archive.fa"
RUTA_ARC = "inazuma1/data_iz/a_title/title_t.arc"
TEXTURA = "ie01_title_t_tlogo.tga"


def _constantes(apply_py: Path) -> dict:
    """Lee por AST las asignaciones de nivel superior con valor literal (o Path('...')) de apply.py."""
    salida = {}
    for nodo in ast.parse(apply_py.read_text(encoding="utf-8")).body:
        if not (isinstance(nodo, ast.Assign) and len(nodo.targets) == 1
                and isinstance(nodo.targets[0], ast.Name)):
            continue
        valor = nodo.value
        if (isinstance(valor, ast.Call) and isinstance(valor.func, ast.Name)
                and valor.func.id == "Path" and len(valor.args) == 1):
            valor = valor.args[0]
        try:
            salida[nodo.targets[0].id] = ast.literal_eval(valor)
        except ValueError:
            continue
    return salida


@pytest.fixture
def entorno():
    raiz = find_root()
    capa = raiz / CAPA
    apply_py = capa / "apply.py"
    if not apply_py.is_file():
        pytest.skip(f"falta {CAPA}/apply.py")
    constantes = _constantes(apply_py)
    base = raiz / BASE
    esperado = capa / "extra" / RUTA_ARC
    logo = Path(constantes.get("LOGO", ""))
    caja = constantes.get("CAJA")
    if not base.is_file():
        pytest.skip(f"falta {BASE}")
    if not esperado.is_file():
        pytest.skip(f"falta {CAPA}/extra/{RUTA_ARC}")
    if caja is None or not logo.is_file():
        pytest.skip(f"falta el PNG de origen de la capa: {logo}")
    return base, esperado, logo, tuple(caja)


def _edicion(logo_png: Path, caja: tuple[int, int, int, int]):
    def poner_logo(antes: Image.Image) -> Image.Image:
        logo = Image.open(logo_png).convert("RGBA")
        logo = logo.crop(logo.getchannel("A").getbbox())
        x0, y0, x1, y1 = caja
        f = min((x1 - x0 - 2) / logo.width, (y1 - y0 - 2) / logo.height)
        pieza = logo.resize((round(logo.width * f), round(logo.height * f)), Image.LANCZOS)
        nueva = Image.new("RGBA", antes.size, (0, 0, 0, 0))
        nueva.alpha_composite(pieza, (x0 + (x1 - x0 - pieza.width) // 2, y0 + (y1 - y0 - pieza.height) // 2))
        a = np.array(nueva)
        a[a[..., 3] == 0, :3] = 0
        return Image.fromarray(a, "RGBA")

    return poner_logo


def test_apply_plan_reproduce_el_extra_de_titulo_logo(entorno) -> None:
    base, esperado, logo_png, caja = entorno
    salida = Path(tempfile.mkdtemp(prefix="ie123_titulo_logo_"))
    try:
        plan = {RUTA_ARC: {TEXTURA: _edicion(logo_png, caja)}}
        registro = texturas.apply_plan(base, plan, salida, rewrap="sszl")
        assert registro == [{"archivo": RUTA_ARC, "textura": TEXTURA, "cambio": "poner_logo"}]
        obtenido = (salida / RUTA_ARC).read_bytes()
        referencia = esperado.read_bytes()
        assert len(obtenido) == len(referencia), (
            f"tamaño distinto: apply_plan {len(obtenido)} B, capa {len(referencia)} B"
        )
        assert obtenido == referencia
    finally:
        shutil.rmtree(salida, ignore_errors=True)
