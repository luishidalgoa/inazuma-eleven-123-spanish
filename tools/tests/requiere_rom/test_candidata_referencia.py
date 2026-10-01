"""Gate 4: work/shared/base_3ds + la capa de referencia se construye con el sha de referencia.

a) con el script congelado tools/build_ui_revision.py (vía golden.comprobar_referencia);
b) con el paquete (ie123kit.nucleo.construir.candidata.construir), que además solo cambia la entrada
   de la capa.
Sustituye a la reconstrucción de probe_ie1_v67 desde v66 (candidatas borradas el 2026-09-16).
Todo se escribe en temporales del sistema; nunca en work/shared/candidatas.
"""
import shutil
import tempfile
from pathlib import Path

import pytest

from ie123kit.nucleo.compat import golden

pytestmark = pytest.mark.requiere_rom

CRO_REL = Path('romfs/cro/ina_main1.cro')
MIN_LIBRE = 4 * 1024 ** 3


@pytest.fixture
def raiz():
    from ie123kit.nucleo.config.raiz import find_root

    r = find_root()
    for rel in (f'{golden.BASE_REFERENCIA}/archive.fa', f'{golden.BASE_REFERENCIA}/cro/ina_main1.cro',
                f'{golden.CAPA}/extra'):
        if not (r / rel).exists():
            pytest.skip(f'falta recurso local: {rel}')
    libre = shutil.disk_usage(tempfile.gettempdir()).free
    if libre < MIN_LIBRE:
        pytest.skip(f'menos de 4 GB libres en {tempfile.gettempdir()} ({libre // 1024 ** 2} MB)')
    return r


def test_referencia_via_script_congelado(raiz):
    assert golden.comprobar_referencia(raiz) == 0


def test_referencia_via_paquete(raiz):
    from ie123kit.nucleo.construir.candidata import construir
    from ie123kit.nucleo.contenedores.fa import FaArchive

    base = raiz / golden.BASE_REFERENCIA
    tmp = Path(tempfile.mkdtemp(prefix='ie123_gate4_'))
    try:
        salida = tmp / 'referencia' / 'archive.fa'
        report = construir(base / 'archive.fa', salida, ui=raiz / golden.CAPA, cro=base / 'cro' / 'ina_main1.cro')
        assert golden.sha(salida) == golden.ARCHIVE_REFERENCIA
        assert report['archive_sha256'] == golden.ARCHIVE_REFERENCIA
        cro_out = salida.parent / CRO_REL
        assert cro_out.is_file(), 'construir no dejó la CRO'
        assert golden.sha(cro_out) == golden.sha(base / 'cro' / 'ina_main1.cro')
        a, b = FaArchive(str(base / 'archive.fa')), FaArchive(str(salida))
        assert [p for p, _, _ in a.entries] == [p for p, _, _ in b.entries]
        cambiadas = [p for (p, o, s), (_, o2, s2) in zip(a.entries, b.entries)
                     if bytes(a.d[o:o + s]) != bytes(b.d[o2:o2 + s2])]
        assert cambiadas == [golden.RUTA_ARC]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
