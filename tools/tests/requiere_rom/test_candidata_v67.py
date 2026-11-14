"""Gate 4: la candidata probe_ie1_v67 se reconstruye idéntica desde v66 + capa v67.

a) con el script congelado tools/build_ui_revision.py (vía golden.comprobar_candidata);
b) con el paquete (ie123kit.nucleo.construir.candidata.construir).
Todo se escribe en temporales del sistema; nunca en work/shared/candidatas.
"""
import json
import shutil
import tempfile
from pathlib import Path

import pytest

pytestmark = pytest.mark.requiere_rom

ARCHIVE_V67 = '72ef7133924e981e4736e240368f716140ca35f62a5c131d7f01c1ead9cffa91'
CAPA = 'work/ie1/capas/v67/titulo_logo'
V66 = 'work/shared/candidatas/probe_ie1_v66'
V67 = 'work/shared/candidatas/probe_ie1_v67'
CRO_REL = Path('romfs/cro/ina_main1.cro')
MIN_LIBRE = 4 * 1024 ** 3


@pytest.fixture
def raiz():
    from ie123kit.nucleo.config.raiz import find_root

    r = find_root()
    for rel in (f'{V66}/archive.fa', f'{V67}/archive.fa', f'{V67}/archive.build.json',
                f'{V67}/{CRO_REL.as_posix()}', f'{CAPA}/extra'):
        if not (r / rel).exists():
            pytest.skip(f'falta recurso local: {rel}')
    libre = shutil.disk_usage(tempfile.gettempdir()).free
    if libre < MIN_LIBRE:
        pytest.skip(f'menos de 4 GB libres en {tempfile.gettempdir()} ({libre // 1024 ** 2} MB)')
    return r


def test_build_json_v67_registra_archive_esperado(raiz):
    meta = json.loads((raiz / V67 / 'archive.build.json').read_text(encoding='utf-8'))
    assert meta['archive_sha256'] == ARCHIVE_V67


def test_candidata_v67_via_script_congelado(raiz):
    from ie123kit.nucleo.compat.golden import comprobar_candidata

    assert comprobar_candidata(raiz, 'probe_ie1_v67', CAPA) == 0


def test_candidata_v67_via_paquete(raiz):
    from ie123kit.nucleo.compat.golden import sha
    from ie123kit.nucleo.construir.candidata import construir

    capa = raiz / CAPA
    cro_base = raiz / V66 / CRO_REL
    # Misma regla que golden.comprobar_candidata: CRO de la base solo si la capa no trae el suyo.
    cro = cro_base if not (capa / CRO_REL).is_file() and cro_base.is_file() else None
    tmp = Path(tempfile.mkdtemp(prefix='ie123_gate4_'))
    try:
        salida = tmp / 'probe_ie1_v67' / 'archive.fa'
        # v67 es anterior al hook de usearch: su hash se reproduce con el opt-out nombrado del constructor
        report = construir(raiz / V66 / 'archive.fa', salida, ui=capa, cro=cro, sincronia_usearch=False)
        assert sha(salida) == ARCHIVE_V67
        assert report['archive_sha256'] == ARCHIVE_V67
        cro_out = salida.parent / CRO_REL
        assert cro_out.is_file(), 'construir no dejó la CRO'
        assert sha(cro_out) == sha(raiz / V67 / CRO_REL)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
