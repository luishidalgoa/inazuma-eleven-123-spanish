"""IE1 · paquete final v2 de menús (`work/ie1/capas/menus_cro/fundir_capas/paquete_final_v2`).

Sin el archive.fa (1,6 GB): comprueba que `informe.json`, `deshacer_datos.json`, la CRO final y los dos .ps1 son coherentes entre
sí, que la CRO final se reproduce desde las 7 capas de CRO sobre la CRO 1.4 ORIGINAL, que las comprobaciones de fusión
(`verificar_cro`, copia del v2) pasan y que el deshacer de la CRO devuelve exactamente el original. Si está la CRO del v1
(`paquete_final/ina_main1.cro`, la instalada hoy), comprueba la diferencia v2 - v1 (la unión de los rangos de las 4 capas nuevas).
El archive.fa final se regenera y compara con `apply_todo.py` (ver el README del paquete).
"""
import hashlib
import json
import re
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.requiere_rom

PAQ = Path('work/ie1/capas/menus_cro/fundir_capas/paquete_final_v2')
PAQ_V1 = Path('work/ie1/capas/menus_cro/fundir_capas/paquete_final')
CRO_BASE = Path('work/shared/candidatas/probe_ie3_fuego_v17_u14/romfs/cro/ina_main1.cro')
BASE_CRO_SHA = '6bbe2f87acc596ec7202c4e320537e6a3116901c05db72512547111bb684cd41'
BASE_ARCHIVE_SHA = '2fea5dab04a546477b5d3e0d9574c1f2105f5929b44148185df57310ccbfa9f0'
V1_CRO_SHA = '587e2902ee9f46fc06b5c475cf27f57c27b375ee1049a925f24a16a5d813ba0c'
V1_ARCHIVE_SHA = '397673b7aabe84a4a1d5dc7f74b011463af3c3536d2d228affa192ea9ea14510'
CAPAS_V1 = ['fichar_rotulos_ranuras', 'panel_equipo_rotulos', 'rotulos_oficiales_eu']
CAPAS_NUEVAS = ['blog_bufer_texto', 'blog_ie1_oficial', 'pachanga_objetivos_equipos', 'slot_guardado_eu']
CAPAS_CRO = CAPAS_V1 + CAPAS_NUEVAS
ARCS_V1 = ['guardado_oficial_eu', 'equipo_oficial_eu', 'rotulos_menus_eu', 'salir_abandonar']
ARCS_NUEVAS = ['blog_ie1_oficial', 'pachanga_objetivos_equipos']
ENTRADAS_NUEVAS = {'inazuma1/data_iz/script/blogpost.dat', 'inazuma1/data_iz/script/blogres.dat',
                   'inazuma1/data_iz/logic/games.dat', 'inazuma1/data_iz/logic/games.STR'}


@pytest.fixture(scope='module')
def raiz():
    from ie123kit.nucleo.config.raiz import find_root

    r = find_root()
    if not (r / PAQ / 'informe.json').exists():
        pytest.skip('sin el paquete final v2 de IE1')
    sys.path.insert(0, str(r / PAQ))
    sys.path.insert(0, str(r / PAQ.parent))
    return r


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def test_informe_y_datos_coherentes(raiz):
    inf = json.loads((raiz / PAQ / 'informe.json').read_text(encoding='utf-8'))
    dat = json.loads((raiz / PAQ / 'deshacer_datos.json').read_text(encoding='utf-8'))
    assert inf['paquete'] == 'ie1_menus_final_v2'
    assert inf['runtime_verified'] is False and inf['instalada'] is False
    assert inf['base']['cro_sha256'] == BASE_CRO_SHA and inf['base']['archive_sha256'] == BASE_ARCHIVE_SHA
    assert inf['instalada_v1']['cro_sha256'] == V1_CRO_SHA and inf['instalada_v1']['archive_sha256'] == V1_ARCHIVE_SHA
    assert dat['cro']['base_sha256'] == BASE_CRO_SHA and dat['archive']['base_sha256'] == BASE_ARCHIVE_SHA
    assert dat['cro']['salida_sha256'] == inf['salida']['cro_sha256']
    assert dat['archive']['salida_sha256'] == inf['salida']['archive_sha256']
    assert dat['archive']['salida_tamano'] == inf['salida']['archive_tamano']
    assert dat['archive']['base_tamano'] == inf['base']['archive_tamano'] == 1617907144
    assert len(dat['archive']['campos']) == inf['archive']['entradas'] == 26
    assert inf['cro']['orden_de_capas'] == CAPAS_CRO
    assert 'estadisticas_sello_historia' in inf['cro']['excluidas'] and 'slot_gemela_eu' in inf['cro']['excluidas']
    assert any('lugares_oficiales' in k for k in inf['cro']['excluidas'])
    assert inf['archive']['orden_de_capas'] == ARCS_V1 + ARCS_NUEVAS
    assert inf['archive']['hook_usearch']['sha256_sin_cambios_al_cerrar'] is True
    assert {c['ruta'] for c in dat['archive']['campos']} >= ENTRADAS_NUEVAS
    assert all(v['runtime_verified'] is False and v['instalada'] is False for v in inf['capas_version'].values())
    cro = (raiz / PAQ / 'ina_main1.cro').read_bytes()
    assert _sha(cro) == inf['salida']['cro_sha256']
    assert len(cro) == inf['salida']['cro_tamano']


def test_comprobaciones_del_informe(raiz):
    inf = json.loads((raiz / PAQ / 'informe.json').read_text(encoding='utf-8'))
    comp = inf['cro']['comprobaciones']
    assert comp['solapes_bytes'] == 0 and comp['solapes_palabras'] == 0
    assert comp['independiente_del_orden'] is True and comp['ordenes_probados'] == 5040
    rel = comp['relocaciones']['registros_cambiados_por_capa']
    assert rel == {n: (45 if n == 'fichar_rotulos_ranuras' else 0) for n in CAPAS_CRO}
    assert comp['cuevas']['0x198200-0x198400'] == 'slot_guardado_eu'
    assert comp['segmento_1']['duenos'] == ['fichar_rotulos_ranuras']
    cruz = inf['comprobacion_cruzada_con_la_instalada_v1']
    assert set(cruz['cro']['por_capa']) == set(CAPAS_NUEVAS) and cruz['cro']['v1_mas_4_capas_igual_a_v2'] is True
    assert cruz['archive']['entradas_del_v1_identicas'] == 22
    assert set(cruz['archive']['entradas_nuevas_igual_a_su_extra']) == ENTRADAS_NUEVAS
    assert cruz['archive']['datos_de_la_instalada_v1_son_el_prefijo_del_v2'] is True


def test_scripts_powershell_llevan_los_hashes_del_informe(raiz):
    inf = json.loads((raiz / PAQ / 'informe.json').read_text(encoding='utf-8'))
    esperados = {inf['base']['cro_sha256'].upper(), inf['base']['archive_sha256'].upper(),
                 inf['instalada_v1']['cro_sha256'].upper(), inf['instalada_v1']['archive_sha256'].upper(),
                 inf['salida']['cro_sha256'].upper(), inf['salida']['archive_sha256'].upper()}
    for nombre in ('instalar_ie1.ps1', 'deshacer_ie1.ps1'):
        crudo = (raiz / PAQ / nombre).read_bytes()
        assert crudo.startswith(b'\xef\xbb\xbf'), 'BOM'
        assert crudo.count(b'\r\n') == crudo.count(b'\n'), 'CRLF'
        texto = crudo.decode('utf-8-sig')
        assert set(re.findall(r"'([0-9A-F]{64})'", texto)) == esperados, nombre
        assert str(inf['salida']['archive_tamano']) in texto
        assert 'Copy-Item' in texto or 'Seek' in texto
        assert '.antes' not in texto and 'IE_backups' not in texto, 'sin copias de seguridad'
    instalar = (raiz / PAQ / 'instalar_ie1.ps1').read_text(encoding='utf-8-sig')
    assert 'AvailableFreeSpace' in instalar and 'SoloComprobar' in instalar and '$V1_CRO' in instalar


def test_cro_final_se_reproduce_y_pasa_las_comprobaciones(raiz):
    import fundir_cro as FC
    import verificar_cro as VC

    assert VC.__file__.startswith(str(raiz / PAQ)), 'debe ser la copia del v2'
    base_p = raiz / CRO_BASE
    if not base_p.exists():
        pytest.skip('sin la CRO 1.4 original de referencia en work/shared/candidatas')
    base = base_p.read_bytes()
    assert _sha(base) == BASE_CRO_SHA
    capas = {n: (raiz / 'work/ie1/capas/menus_cro' / n / FC.REL).read_bytes() for n in CAPAS_CRO}
    fundida, _ = FC.fundir(base, capas)
    assert fundida == (raiz / PAQ / 'ina_main1.cro').read_bytes()
    res = VC.comprobar(base, capas, fundida)
    assert res['solapes_bytes'] == 0 and res['solapes_palabras'] == 0 and res['independiente_del_orden']
    assert res['segmento_1']['despues'] == '0x1aec0'


def test_cro_v2_menos_v1_es_la_union_de_las_capas_nuevas(raiz):
    from ie123kit.nucleo.registros.rangos import diff_ranges

    base_p = raiz / CRO_BASE
    v1_p = raiz / PAQ_V1 / 'ina_main1.cro'
    if not base_p.exists() or not v1_p.exists():
        pytest.skip('sin la CRO original o la del v1')
    base, v1 = base_p.read_bytes(), v1_p.read_bytes()
    assert _sha(v1) == V1_CRO_SHA
    v2 = (raiz / PAQ / 'ina_main1.cro').read_bytes()
    pos = set()
    for n in CAPAS_NUEVAS:
        c = (raiz / 'work/ie1/capas/menus_cro' / n / 'salida/romfs/cro/ina_main1.cro').read_bytes()
        pos |= {x for lo, hi in diff_ranges(base, c) for x in range(lo, hi)}
    assert {x for lo, hi in diff_ranges(v1, v2) for x in range(lo, hi)} == pos


def test_deshacer_cro_devuelve_la_base_exacta(raiz):
    base_p = raiz / CRO_BASE
    if not base_p.exists():
        pytest.skip('sin la CRO 1.4 original de referencia')
    dat = json.loads((raiz / PAQ / 'deshacer_datos.json').read_text(encoding='utf-8'))['cro']
    datos = bytearray((raiz / PAQ / 'ina_main1.cro').read_bytes())
    for r in dat['rangos']:
        o = r['offset']
        assert bytes(datos[o:o + len(r['nuevo_hex']) // 2]) == bytes.fromhex(r['nuevo_hex'])
        datos[o:o + len(r['original_hex']) // 2] = bytes.fromhex(r['original_hex'])
    assert _sha(bytes(datos)) == BASE_CRO_SHA == _sha(base_p.read_bytes())
