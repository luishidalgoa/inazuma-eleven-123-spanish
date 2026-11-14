"""IE1 · capa `slot_guardado_eu` (slot de guardado como el EU; solo CRO, sin archive.fa de 1,6 GB).

Comprueba que las salidas se reproducen sobre 6BBE2F87 y sobre la instalada 587E2902, que cambian solo las palabras y la ventana de cueva 0x198200-0x198400
declaradas, que se funden sin solapes con el paquete instalado y con las demas capas de CRO, que la funcion real 0x71b40 ejecutada con el motor 2 real da los
avances previstos y que los informes dicen runtime_verified/instalada = false.
"""
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.requiere_rom

MC = Path('work/ie1/capas/menus_cro')
CAPA = MC / 'slot_guardado_eu'
BASE_6BBE = Path('work/shared/candidatas/probe_ie3_fuego_v17_u14/romfs/cro/ina_main1.cro')
SHA_6BBE = '6bbe2f87acc596ec7202c4e320537e6a3116901c05db72512547111bb684cd41'
SHA_INST = '587e2902ee9f46fc06b5c475cf27f57c27b375ee1049a925f24a16a5d813ba0c'
PALABRAS = {0x2F420, 0x71C74, 0x71CB0, 0x71BF0, 0x71B60, 0x71B6C, 0x71EE8, 0x71BD4, 0x71CF4, 0x71CC4, 0x71DC0, 0x72364, 0x723A8}
VENTANA = (0x198200, 0x198400)
PAQUETE = ['fichar_rotulos_ranuras', 'panel_equipo_rotulos', 'rotulos_oficiales_eu']


def _sha(b):
    return hashlib.sha256(b).hexdigest()


@pytest.fixture(scope='module')
def raiz():
    from ie123kit.nucleo.config.raiz import find_root

    r = find_root()
    if not (r / CAPA / 'informe.json').exists() or not (r / BASE_6BBE).exists():
        pytest.skip('sin la capa o la CRO base en work/')
    for d in ('fundir_capas', 'fundir_capas/paquete_final'):
        sys.path.insert(0, str(r / MC / d))
    return r


def _modulo(raiz, nombre):
    # `apply` es un nombre compartido por todas las capas: se carga con un nombre propio para no pisar a otro modulo del mismo proceso
    spec = importlib.util.spec_from_file_location(f'slot_guardado_eu_{nombre}', raiz / CAPA / f'{nombre}.py')
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


def test_informe_y_salidas(raiz):
    from ie123kit.nucleo.registros.rangos import diff_ranges

    inf = json.loads((raiz / CAPA / 'informe.json').read_text(encoding='utf-8'))
    assert inf['runtime_verified'] is False and inf['instalada'] is False
    base6 = (raiz / BASE_6BBE).read_bytes()
    assert _sha(base6) == SHA_6BBE
    s6 = (raiz / CAPA / 'salida/romfs/cro/ina_main1.cro').read_bytes()
    sp = (raiz / CAPA / 'salida/sobre_instalada/romfs/cro/ina_main1.cro').read_bytes()
    assert _sha(s6) == inf['salida_sobre_6bbe']['sha256'] and _sha(sp) == inf['salida_sobre_instalada']['sha256']
    paq = (raiz / MC / 'fundir_capas/paquete_final/ina_main1.cro').read_bytes()
    assert _sha(paq) == SHA_INST
    rangos = diff_ranges(paq, sp)
    assert rangos == diff_ranges(base6, s6) and sum(hi - lo for lo, hi in rangos) == inf['bytes_distintos']
    fuera = [(lo, hi) for lo, hi in rangos if lo >= 0x198000]
    assert fuera and all(VENTANA[0] <= lo and hi <= VENTANA[1] for lo, hi in fuera)
    assert not any(base6[VENTANA[0]:VENTANA[1]]) and not any(paq[VENTANA[0]:VENTANA[1]])
    assert {lo & ~3 for lo, _ in rangos if lo < 0x198000} == PALABRAS
    AP = _modulo(raiz, 'apply')
    assert AP.construir(paq)[0] == sp and AP.construir(base6)[0] == s6


def test_fusion_sin_solapes_con_el_paquete_y_con_las_demas(raiz):
    import fundir_cro as FC
    import verificar_cro as VC

    base6 = (raiz / BASE_6BBE).read_bytes()
    sp = (raiz / CAPA / 'salida/sobre_instalada/romfs/cro/ina_main1.cro').read_bytes()
    cuevas = list(VC.CUEVAS)
    VC.CUEVAS = sorted({*cuevas, VENTANA})
    try:
        nombres = PAQUETE + ['slot_guardado_eu']
        capas = {n: (raiz / MC / n / FC.REL).read_bytes() for n in nombres}
        fundida, _ = FC.fundir(base6, capas)
        comp = VC.comprobar(base6, capas, fundida)
        assert comp['solapes_bytes'] == 0 and comp['solapes_palabras'] == 0 and fundida == sp
        todas = [*nombres, 'blog_ie1_oficial', 'pachanga_objetivos_equipos']
        capas = {n: (raiz / MC / n / FC.REL).read_bytes() for n in todas}
        fundida, _ = FC.fundir(base6, capas)
        comp = VC.comprobar(base6, capas, fundida)
        assert comp['solapes_bytes'] == 0 and comp['solapes_palabras'] == 0
    finally:
        VC.CUEVAS = cuevas


def test_funcion_real_con_el_motor_real(raiz):
    pytest.importorskip('unicorn')
    AP = _modulo(raiz, 'apply')
    EM = _modulo(raiz, 'emulacion')

    anchos = json.loads((raiz / CAPA / 'anchos_bcfnt.json').read_text(encoding='utf-8'))

    def cw(tipo, code):
        fn = anchos['FONT12_inst' if tipo == 0 else 'FONT8_inst']
        g = fn['glifos'].get(str(code))
        return g['cw'] if g else fn['alter_cw']

    sp = (raiz / CAPA / 'salida/sobre_instalada/romfs/cro/ina_main1.cro').read_bytes()
    e = EM.Emu(sp, cw, a_ini=(5, 3), b_ini=(2, 2))
    fin = e.run_slot()
    assert fin['err'] is None and fin['sp_ok'] and fin['A'] == [5, 3] and fin['B'] == [2, 2]
    textos = [c['texto'] for c in e.calls]
    assert textos == [b'gg', b'Niv. Equipo', b'Jugadores', b'\x81@', b'Ep. 6', b'h', b'min']
    for c in e.calls:
        sl = [g['sl'] for g in c['glifos']]
        if c['texto'] in (b'Niv. Equipo', b'Jugadores'):
            assert sl == [round(AP.TABLA_ANCHOS[ch - 0x20] / 1.25) for ch in c['texto']] and c['ext14'] == 0
        elif c['mgr'] == 'A':
            assert c['ext14'] == 1
    # capitulo 10: la base dibuja «Ep.10» (numeral sin espacio) y la capa «Ep. 10» como el EU (`Ep. %d`)
    e10 = EM.Emu(sp, cw, cap=10)
    assert e10.run_slot()['err'] is None
    assert [c['texto'] for c in e10.calls if c['texto'].startswith(b'Ep.')] == [b'Ep. 10']
    base = (raiz / MC / 'fundir_capas/paquete_final/ina_main1.cro').read_bytes()
    e10b = EM.Emu(base, cw, cap=10)
    assert e10b.run_slot()['err'] is None
    assert [c['texto'] for c in e10b.calls if c['texto'].startswith(b'Ep.')] == [b'Ep.10']
