"""IE1 · paquete final de menús (`work/ie1/capas/menus_cro/fundir_capas/paquete_final`).

Sin el archive.fa (1,6 GB): comprueba que `informe.json`, `deshacer_datos.json`, la CRO final y los dos .ps1 son coherentes entre
sí, que la CRO final se reproduce desde las tres capas de CRO sobre la CRO 1.4 instalada, que las comprobaciones de fusión
(`verificar_cro`) pasan y que el deshacer de la CRO devuelve exactamente la base. El archive.fa final se regenera y compara
con `apply_todo.py` (ver el README del paquete).
"""
import hashlib
import json
import re
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.requiere_rom

PAQ = Path('work/ie1/capas/menus_cro/fundir_capas/paquete_final')
CRO_BASE = Path('work/shared/candidatas/probe_ie3_fuego_v17_u14/romfs/cro/ina_main1.cro')
BASE_CRO_SHA = '6bbe2f87acc596ec7202c4e320537e6a3116901c05db72512547111bb684cd41'
BASE_ARCHIVE_SHA = '2fea5dab04a546477b5d3e0d9574c1f2105f5929b44148185df57310ccbfa9f0'
CAPAS_CRO = ['fichar_rotulos_ranuras', 'panel_equipo_rotulos', 'rotulos_oficiales_eu']


@pytest.fixture(scope='module')
def raiz():
    from ie123kit.nucleo.config.raiz import find_root

    r = find_root()
    if not (r / PAQ / 'informe.json').exists():
        pytest.skip('sin el paquete final de IE1')
    sys.path.insert(0, str(r / PAQ))
    sys.path.insert(0, str(r / PAQ.parent))
    return r


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def test_informe_y_datos_coherentes(raiz):
    inf = json.loads((raiz / PAQ / 'informe.json').read_text(encoding='utf-8'))
    dat = json.loads((raiz / PAQ / 'deshacer_datos.json').read_text(encoding='utf-8'))
    assert inf['runtime_verified'] is False and inf['instalada'] is False
    assert inf['base']['cro_sha256'] == BASE_CRO_SHA and inf['base']['archive_sha256'] == BASE_ARCHIVE_SHA
    assert dat['cro']['base_sha256'] == BASE_CRO_SHA and dat['archive']['base_sha256'] == BASE_ARCHIVE_SHA
    assert dat['cro']['salida_sha256'] == inf['salida']['cro_sha256']
    assert dat['archive']['salida_sha256'] == inf['salida']['archive_sha256']
    assert dat['archive']['salida_tamano'] == inf['salida']['archive_tamano']
    assert len(dat['archive']['campos']) == inf['archive']['entradas'] == 22
    assert inf['cro']['orden_de_capas'] == CAPAS_CRO and 'estadisticas_sello_historia' in inf['cro']['excluidas']
    assert inf['archive']['hook_usearch']['sha256_sin_cambios_al_cerrar'] is True
    cro = (raiz / PAQ / 'ina_main1.cro').read_bytes()
    assert _sha(cro) == inf['salida']['cro_sha256']


def test_scripts_powershell_llevan_los_hashes_del_informe(raiz):
    inf = json.loads((raiz / PAQ / 'informe.json').read_text(encoding='utf-8'))
    esperados = {inf['base']['cro_sha256'].upper(), inf['base']['archive_sha256'].upper(),
                 inf['salida']['cro_sha256'].upper(), inf['salida']['archive_sha256'].upper()}
    for nombre in ('instalar_ie1.ps1', 'deshacer_ie1.ps1'):
        texto = (raiz / PAQ / nombre).read_text(encoding='utf-8-sig')
        assert set(re.findall(r"'([0-9A-F]{64})'", texto)) == esperados, nombre
        assert str(inf['salida']['archive_tamano']) in texto
        assert 'Copy-Item' in texto or 'Seek' in texto
        assert '.antes' not in texto and 'IE_backups' not in texto, 'sin copias de seguridad'


def test_cro_final_se_reproduce_y_pasa_las_comprobaciones(raiz):
    import fundir_cro as FC
    import verificar_cro as VC

    base_p = raiz / CRO_BASE
    if not base_p.exists():
        pytest.skip('sin la CRO 1.4 instalada de referencia en work/shared/candidatas')
    base = base_p.read_bytes()
    assert _sha(base) == BASE_CRO_SHA
    capas = {n: (raiz / 'work/ie1/capas/menus_cro' / n / FC.REL).read_bytes() for n in CAPAS_CRO}
    fundida, _ = FC.fundir(base, capas)
    assert fundida == (raiz / PAQ / 'ina_main1.cro').read_bytes()
    res = VC.comprobar(base, capas, fundida)
    assert res['solapes_bytes'] == 0 and res['solapes_palabras'] == 0 and res['independiente_del_orden']
    assert res['segmento_1']['despues'] == '0x1aec0'


def test_deshacer_cro_devuelve_la_base_exacta(raiz):
    base_p = raiz / CRO_BASE
    if not base_p.exists():
        pytest.skip('sin la CRO 1.4 instalada de referencia')
    dat = json.loads((raiz / PAQ / 'deshacer_datos.json').read_text(encoding='utf-8'))['cro']
    datos = bytearray((raiz / PAQ / 'ina_main1.cro').read_bytes())
    for r in dat['rangos']:
        o = r['offset']
        assert bytes(datos[o:o + len(r['nuevo_hex']) // 2]) == bytes.fromhex(r['nuevo_hex'])
        datos[o:o + len(r['original_hex']) // 2] = bytes.fromhex(r['original_hex'])
    assert _sha(bytes(datos)) == BASE_CRO_SHA == _sha(base_p.read_bytes())
