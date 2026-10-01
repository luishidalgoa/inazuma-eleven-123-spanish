"""Equivalencia de los motores de IE1 portados en la limpieza F2.6 (#55) con las capas de ``work/``.

Mismo patrón que ``test_equivalencia_motores_ie2.py``: primero se comprueba la salida vigente de la
capa contra su hash golden (``tests/compat/golden/motores_ie1.json``: solo hashes, Norma 2), y luego
se exige que la función del paquete la reproduzca byte a byte desde la misma entrada.

Cubre:

- ``ie1.texto.cro.parchear_ancho_dialogo``: la tabla de parches de ``ina_main1.cro`` que antes vivía
  en ``work/ie1/capas/dialogo/motor_unificado/comun94.py`` (``PARCHES``/``CONTEXTO``);
- ``ie1.texto.dialogo.MODELO_IE1_ANCHO``: los límites del diálogo de IE1 con esa CRO (37 × 3, 131 B,
  247 B), comprobados como punto fijo sobre los registros que la capa ya generó.

Nunca escribe en ``work/``. En CI se deselecciona con ``-m "not requiere_rom"``.
"""

from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path

import pytest

from ie123kit.nucleo.config.raiz import find_root

pytestmark = pytest.mark.requiere_rom

CAPAS = "work/ie1/capas"
BASE_CRO = f"{CAPAS}/menus_cro/cofres/romfs/cro/ina_main1.cro"
CRO_PARCHEADA = f"{CAPAS}/dialogo/motor_unificado/romfs/cro/ina_main1.cro"
#: Salto de línea y de página tal como van en el registro (dos bytes ASCII cada uno).
SALTO, PAGINA = rb"\n", rb"\f"


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


@pytest.fixture(scope="module")
def raiz() -> Path:
    r = find_root()
    for rel in (BASE_CRO, CRO_PARCHEADA):
        if not (r / rel).exists():
            pytest.skip(f"falta recurso local: {rel}")
    return r


@pytest.fixture(scope="module")
def golden(raiz) -> dict:
    ruta = raiz / "tools/tests/compat/golden/motores_ie1.json"
    return json.loads(ruta.read_text(encoding="utf-8"))["capas"]


def test_parches_cro_ie1_reproducen_la_capa(raiz, golden):
    """La tabla del paquete da la misma ina_main1.cro que la capa motor_unificado."""
    from ie123kit.ie1.texto import cro as CRO

    base = (raiz / BASE_CRO).read_bytes()
    esperada = (raiz / CRO_PARCHEADA).read_bytes()
    assert _sha(base) == golden[BASE_CRO], "work/ ha cambiado: la CRO base no es la del golden"
    assert _sha(esperada) == golden[CRO_PARCHEADA], "work/ ha cambiado: la CRO de la capa no es la del golden"

    obtenida, informe = CRO.parchear_ancho_dialogo(base)
    assert obtenida == esperada, "la CRO del paquete no es byte a byte la de la capa"
    assert len(obtenida) == len(base), "el parche no debe cambiar el tamaño de la CRO"
    assert len(informe["parches"]) == 3
    assert not informe.get("relocalizaciones_afectadas"), informe


def test_modelo_ie1_ancho_es_punto_fijo_sobre_la_capa(raiz):
    """Los registros que la capa ya repartió no cambian al volver a repartirlos con el paquete."""
    from ie123kit.ie1.texto.dialogo import MODELO_IE1_ANCHO
    from ie123kit.nucleo.texto import paginado as P

    assert (MODELO_IE1_ANCHO.max_car, MODELO_IE1_ANCHO.lineas) == (37, 3)
    assert (MODELO_IE1_ANCHO.pagina_max, MODELO_IE1_ANCHO.registro_max) == (131, 247)

    eventos = sorted((raiz / CAPAS / "dialogo/motor_unificado/events").glob("*.ssd"))
    if not eventos:
        pytest.skip("la capa no tiene events/ local")
    revisados = 0
    for ruta in eventos[:400]:
        datos = ruta.read_bytes()
        for cuerpo in _registros(datos):
            # Lo que la capa dejó escrito ya respeta el modelo: no hay problemas ni reajuste.
            assert not P.problemas(cuerpo, MODELO_IE1_ANCHO), (ruta.name, cuerpo[:60])
            assert not P.reajusta(cuerpo, MODELO_IE1_ANCHO), (ruta.name, cuerpo[:60])
            revisados += 1
    assert revisados > 0, "no se encontró ningún registro de diálogo en la capa"


def _registros(datos: bytes):
    """Cuerpos de diálogo de un evento de la capa (los que ya llevan el reparto de la v94)."""
    from ie123kit.nucleo.eventos import ssd

    try:
        _fin, _ops, registros = ssd.parse(datos)
    except (ValueError, IndexError, UnicodeError, struct.error):
        return
    for r in registros:
        cuerpo = getattr(r, "body", b"")
        if isinstance(cuerpo, bytes) and (SALTO in cuerpo or PAGINA in cuerpo):
            yield cuerpo
