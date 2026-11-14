"""IE1 · capas `blog_ie1_oficial` y `pachanga_objetivos_equipos` (sin archive.fa de 1,6 GB).

Comprueba que las salidas de CRO se reproducen sobre 6BBE2F87 y sobre la instalada 587E2902, que cambian solo las palabras declaradas, que no tocan cuevas,
cola ni campo 0x1b401c, que se funden sin solapes con el resto de capas de CRO y que los informes dicen runtime_verified/instalada = false.
"""
import hashlib
import json
import struct
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.requiere_rom

MC = Path('work/ie1/capas/menus_cro')
BASE_6BBE = Path('work/shared/candidatas/probe_ie3_fuego_v17_u14/romfs/cro/ina_main1.cro')
SHA_6BBE = '6bbe2f87acc596ec7202c4e320537e6a3116901c05db72512547111bb684cd41'
SHA_INST = '587e2902ee9f46fc06b5c475cf27f57c27b375ee1049a925f24a16a5d813ba0c'
ZONAS_PROHIBIDAS = [(0x198800, 0x1988B8), (0x198F00, 0x198F54), (0x198F60, 0x198FB4), (0x1B3D00, 0x1B3EC0), (0x1B401C, 0x1B4020)]
PALABRAS = {'blog_ie1_oficial': {0x1179F0, 0x119D70, 0x117A30, 0x1175E8}, 'pachanga_objetivos_equipos': {0x12CEF4, 0x12CF60}}


def _sha(b):
    return hashlib.sha256(b).hexdigest()


@pytest.fixture(scope='module')
def raiz():
    from ie123kit.nucleo.config.raiz import find_root

    r = find_root()
    if not (r / MC / 'blog_ie1_oficial/informe.json').exists() or not (r / BASE_6BBE).exists():
        pytest.skip('sin las capas o la CRO base en work/')
    for d in ('fundir_capas', 'fundir_capas/paquete_final'):
        sys.path.insert(0, str(r / MC / d))
    return r


@pytest.mark.parametrize('capa', sorted(PALABRAS))
def test_informe_y_salidas(raiz, capa):
    from ie123kit.nucleo.registros.rangos import diff_ranges

    inf = json.loads((raiz / MC / capa / 'informe.json').read_text(encoding='utf-8'))
    assert inf['runtime_verified'] is False and inf['instalada'] is False
    base6 = (raiz / BASE_6BBE).read_bytes()
    assert _sha(base6) == SHA_6BBE
    s6 = (raiz / MC / capa / 'salida/romfs/cro/ina_main1.cro').read_bytes()
    sp = (raiz / MC / capa / 'salida/sobre_instalada/romfs/cro/ina_main1.cro').read_bytes()
    assert _sha(s6) == inf['cro']['salida_sobre_6bbe']['sha256'] and _sha(sp) == inf['cro']['salida_sobre_instalada']['sha256']
    rangos = diff_ranges(base6, s6)
    assert {lo & ~3 for lo, _ in rangos} == PALABRAS[capa]      # diff_ranges es por bytes: cada palabra cambia en un rango
    assert all((hi - 1) & ~3 == lo & ~3 for lo, hi in rangos)
    for lo, hi in rangos:
        assert all(hi <= z0 or lo >= z1 for z0, z1 in ZONAS_PROHIBIDAS)
    paq = (raiz / MC / 'fundir_capas/paquete_final/ina_main1.cro').read_bytes()
    assert _sha(paq) == SHA_INST
    assert diff_ranges(paq, sp) == rangos
    for pal in PALABRAS[capa]:
        assert struct.unpack_from('<I', s6, pal)[0] != struct.unpack_from('<I', base6, pal)[0]


def test_fusion_sin_solapes_con_todas_las_capas(raiz):
    import fundir_cro as FC
    import verificar_cro as VC

    base6 = (raiz / BASE_6BBE).read_bytes()
    nombres = ['fichar_rotulos_ranuras', 'panel_equipo_rotulos', 'rotulos_oficiales_eu', 'blog_bufer_texto', 'blog_ie1_oficial', 'pachanga_objetivos_equipos']
    capas = {n: (raiz / MC / n / FC.REL).read_bytes() for n in nombres}
    fundida, _ = FC.fundir(base6, capas)
    comp = VC.comprobar(base6, capas, fundida)
    assert comp['solapes_bytes'] == 0 and comp['solapes_palabras'] == 0
