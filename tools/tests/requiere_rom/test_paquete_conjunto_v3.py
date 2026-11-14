"""IE1 + IE2 · paquete conjunto v3 (`work/ie1/capas/menus_cro/fundir_capas/paquete_final_v3`).

Sin el archive.fa (1,6 GB): comprueba que `informe.json`, `deshacer_datos.json`, las CRO de la carpeta y los dos .ps1 son coherentes entre sí,
que la CRO de IE1 se reproduce desde las 7 capas (v3 del blog y de la pachanga) sobre la CRO 1.4 ORIGINAL, que las comprobaciones de fusión
(`verificar_cro`, copia del v3) pasan, que la de IE2 es la salida completa de `slot_guardado_ie2` sobre la instalada hoy y que el deshacer de las dos
CRO devuelve exactamente las de HOY. El archive.fa final se regenera y compara con `apply_todo.py` (ver el README del paquete).
"""
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.requiere_rom

PAQ = Path('work/ie1/capas/menus_cro/fundir_capas/paquete_final_v3')
PAQ_V2 = Path('work/ie1/capas/menus_cro/fundir_capas/paquete_final_v2')
CAPAS_IE1 = Path('work/ie1/capas/menus_cro')
CAPA_IE2 = Path('work/ie2/shared/capas/menus_cro/slot_guardado_ie2')
CRO_BASE = Path('work/shared/candidatas/probe_ie3_fuego_v17_u14/romfs/cro/ina_main1.cro')
BASE_CRO_SHA = '6bbe2f87acc596ec7202c4e320537e6a3116901c05db72512547111bb684cd41'
HOY = {
    'cro1': '26f953bc76e31e9af9b26175d2f9b975696cda44cb5ea7c8a26dbbee891d839a',
    'cro2': 'ce0449bf5045b997782db50d6eae80cd067bb2f27a833410d349f6ea409de008',
    'cro3': '28c27f836c9f316370874d2f2b77f8f031b56b52bc6ed11e7a33aa9e5cb4333f',
    'archive': '6878cc93c64e42e372b3b453b130cd876080417f49af46a111bc2736a3bdb3a3',
}
SALIDA = {
    'cro1': 'f7b3ef3f7306bfa0f0211cac2c530fb08755c127051ee7a3b1004ebfdce1dce8',
    'cro2': 'e20d93b418429b666f0922e9206c4f0327f8a84ba337ae7d131e41b41f728d8c',
    'cro3': HOY['cro3'],
}
HOY_ARCHIVE_TAMANO = 1626304907
CAPAS_CRO = ['fichar_rotulos_ranuras', 'panel_equipo_rotulos', 'rotulos_oficiales_eu', 'blog_bufer_texto', 'blog_ie1_oficial_v3',
             'pachanga_objetivos_equipos_v3', 'slot_guardado_eu']
CAPAS_CRO_V2 = ['fichar_rotulos_ranuras', 'panel_equipo_rotulos', 'rotulos_oficiales_eu', 'blog_bufer_texto', 'blog_ie1_oficial',
                'pachanga_objetivos_equipos', 'slot_guardado_eu']
ENTRADAS = {'inazuma1/data_iz/script/blogpost.dat', 'inazuma1/data_iz/script/blogres.dat'}


@pytest.fixture(scope='module')
def raiz():
    from ie123kit.nucleo.config.raiz import find_root

    r = find_root()
    if not (r / PAQ / 'informe.json').exists():
        pytest.skip('sin el paquete conjunto v3')
    sys.path.insert(0, str(r / PAQ.parent))   # fundir_cro / fundir_arcs (los modulos de esta carpeta se cargan con nombre propio)
    return r


def _cargar(raiz, nombre):
    """Carga `paquete_final_v3/<nombre>.py` con un nombre propio: `verificar_cro`, `deshacer_local` e `instalar_local` existen tambien en otros paquetes."""
    spec = importlib.util.spec_from_file_location(f'{nombre}__conjunto_v3', raiz / PAQ / f'{nombre}.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def test_informe_y_datos_coherentes(raiz):
    inf = json.loads((raiz / PAQ / 'informe.json').read_text(encoding='utf-8'))
    dat = json.loads((raiz / PAQ / 'deshacer_datos.json').read_text(encoding='utf-8'))
    assert inf['paquete'] == 'ie_conjunto_v3'
    assert inf['runtime_verified'] is False and inf['instalada'] is False
    h, s = inf['hoy'], inf['salida']
    assert (h['cro1_sha256'], h['cro2_sha256'], h['cro3_sha256'], h['archive_sha256']) == (HOY['cro1'], HOY['cro2'], HOY['cro3'], HOY['archive'])
    assert h['archive_tamano'] == HOY_ARCHIVE_TAMANO
    assert (s['cro1_sha256'], s['cro2_sha256'], s['cro3_sha256']) == (SALIDA['cro1'], SALIDA['cro2'], SALIDA['cro3'])
    assert s['cro3_sha256'] == h['cro3_sha256'] and inf['cro3']['cambia'] is False
    assert s['archive_tamano'] > HOY_ARCHIVE_TAMANO and s['archive_tamano'] - HOY_ARCHIVE_TAMANO == inf['archive']['anexado']
    assert dat['cro1']['hoy_sha256'] == HOY['cro1'] and dat['cro1']['salida_sha256'] == s['cro1_sha256']
    assert dat['cro2']['hoy_sha256'] == HOY['cro2'] and dat['cro2']['salida_sha256'] == s['cro2_sha256']
    assert dat['cro3']['sha256'] == HOY['cro3']
    assert dat['archive']['hoy_sha256'] == HOY['archive'] and dat['archive']['hoy_tamano'] == HOY_ARCHIVE_TAMANO
    assert dat['archive']['salida_sha256'] == s['archive_sha256'] and dat['archive']['salida_tamano'] == s['archive_tamano']
    assert {c['ruta'] for c in dat['archive']['campos']} == ENTRADAS == set(inf['archive']['rutas'])
    assert len(dat['archive']['campos']) == inf['archive']['entradas_reemplazadas'] == 2
    for c in dat['archive']['campos']:
        assert len(c['original_hex']) == len(c['nuevo_hex']) == 16 and c['offset_nuevo'] >= HOY_ARCHIVE_TAMANO
    assert inf['cro1']['orden_de_capas'] == CAPAS_CRO
    assert inf['cro1']['igual_a_la_salida_sobre_v2_de_la_pachanga_v3'] is True
    assert inf['cro1']['la_de_hoy_es_la_fusion_de_las_7_capas_del_v2'] is True
    assert inf['cro1']['cambia_solo_en_bytes_de_la_pachanga'] is True
    assert (inf['cro1']['bytes_distintos_respecto_de_hoy'], inf['cro1']['rangos_respecto_de_hoy']) == (309, 23)
    assert (inf['cro2']['bytes_distintos_respecto_de_hoy'], inf['cro2']['rangos_respecto_de_hoy'], inf['cro2']['palabras']) == (38, 17, 14)
    assert 'blog_ie1_oficial (v2)' in inf['excluidas'] and 'pachanga_objetivos_equipos (v2)' in inf['excluidas']
    assert any('solo_modo0' in k for k in inf['excluidas'])
    assert inf['archive']['hook_usearch']['verificar_rc'] == 0 and inf['archive']['hook_usearch']['cerrar_rc'] == 0
    assert inf['archive']['hook_usearch']['sha256_sin_cambios_al_cerrar'] is True
    assert inf['archive']['region_original_de_datos_identica'] and inf['archive']['tabla_solo_cambia_en_los_campos']
    assert inf['archive']['solo_crece_por_el_final'] and inf['archive']['entradas_reemplazadas'] == 2
    assert all(v['runtime_verified'] is False and v['instalada'] is False for v in inf['cro1']['capas_version'].values())
    assert inf['cro2']['capa_version']['runtime_verified'] is False and inf['cro2']['capa_version']['instalada'] is False
    assert all(v['runtime_verified'] is False and v['instalada'] is False for v in inf['capas_arcs_version'].values())
    cro1 = (raiz / PAQ / 'ina_main1.cro').read_bytes()
    cro2 = (raiz / PAQ / 'ina_main2.cro').read_bytes()
    assert _sha(cro1) == s['cro1_sha256'] and len(cro1) == s['cro1_tamano']
    assert _sha(cro2) == s['cro2_sha256'] and len(cro2) == s['cro2_tamano']


def test_comprobaciones_del_informe(raiz):
    inf = json.loads((raiz / PAQ / 'informe.json').read_text(encoding='utf-8'))
    comp = inf['cro1']['comprobaciones']
    assert comp['solapes_bytes'] == 0 and comp['solapes_palabras'] == 0
    assert comp['independiente_del_orden'] is True and comp['ordenes_probados'] == 5040
    rel = comp['relocaciones']['registros_cambiados_por_capa']
    assert rel == {n: (45 if n == 'fichar_rotulos_ranuras' else 0) for n in CAPAS_CRO}
    assert comp['cuevas']['0x198200-0x198400'] == 'slot_guardado_eu'
    assert comp['cuevas']['0x198500-0x198660'] == 'pachanga_objetivos_equipos_v3'
    assert comp['segmento_1']['duenos'] == ['fichar_rotulos_ranuras']
    assert inf['cro1']['estructura']['importaciones_iguales'] and inf['cro2']['estructura']['segmentos_iguales']


def test_scripts_powershell_llevan_los_hashes_del_informe(raiz):
    inf = json.loads((raiz / PAQ / 'informe.json').read_text(encoding='utf-8'))
    h, s = inf['hoy'], inf['salida']
    esperados = {v.upper() for d in (h, s) for k, v in d.items() if k.endswith('_sha256')}
    assert len(esperados) == 7                      # la CRO de IE3 es la misma en hoy y salida
    for nombre in ('instalar_v3.ps1', 'deshacer_v3.ps1'):
        crudo = (raiz / PAQ / nombre).read_bytes()
        assert crudo.startswith(b'\xef\xbb\xbf'), 'BOM'
        assert crudo.count(b'\r\n') == crudo.count(b'\n'), 'CRLF'
        texto = crudo.decode('utf-8-sig')
        assert set(re.findall(r"'([0-9A-F]{64})'", texto)) == esperados, nombre
        assert str(s['archive_tamano']) in texto
        assert 'Copy-Item' in texto or 'Seek' in texto
        assert '.antes' not in texto and 'IE_backups' not in texto, 'sin copias de seguridad'
    instalar = (raiz / PAQ / 'instalar_v3.ps1').read_text(encoding='utf-8-sig')
    assert 'AvailableFreeSpace' in instalar and 'SoloComprobar' in instalar and '$HOY_CRO3' in instalar
    assert str(s['cro1_tamano']) in instalar and str(s['cro2_tamano']) in instalar and 'C:\\IE_work\\paquete_v3' in instalar
    deshacer = (raiz / PAQ / 'deshacer_v3.ps1').read_text(encoding='utf-8-sig')
    assert str(h['archive_tamano']) in deshacer and 'SetLength($TAM_HOY_ARC)' in deshacer


def test_instalar_local_lee_las_constantes_del_ps1(raiz):
    IL = _cargar(raiz, 'instalar_local')
    c = IL.constantes()
    assert c['HOY_CRO1'].lower() == HOY['cro1'] and c['OUT_CRO1'].lower() == SALIDA['cro1']
    assert c['HOY_CRO2'].lower() == HOY['cro2'] and c['OUT_CRO2'].lower() == SALIDA['cro2']
    assert c['HOY_CRO3'] == c['OUT_CRO3'] and c['HOY_ARC'].lower() == HOY['archive']
    assert c['TAM_OUT_CRO1'] == 2109440 and c['TAM_OUT_CRO2'] == 2748416 and c['TAM_OUT_ARC'] > HOY_ARCHIVE_TAMANO


def test_cro_ie1_se_reproduce_y_pasa_las_comprobaciones(raiz):
    import fundir_cro as FC

    VC = _cargar(raiz, 'verificar_cro')
    assert (0x198500, 0x198660) in VC.CUEVAS_DUENO, 'debe ser la copia del v3'
    base_p = raiz / CRO_BASE
    if not base_p.exists():
        pytest.skip('sin la CRO 1.4 original de referencia en work/shared/candidatas')
    base = base_p.read_bytes()
    assert _sha(base) == BASE_CRO_SHA
    # la de hoy es la fusion de las 7 capas del v2
    v2 = {n: (raiz / CAPAS_IE1 / n / FC.REL).read_bytes() for n in CAPAS_CRO_V2}
    hoy, _ = FC.fundir(base, v2)
    assert _sha(hoy) == HOY['cro1']
    capas = {n: (raiz / CAPAS_IE1 / n / FC.REL).read_bytes() for n in CAPAS_CRO}
    fundida, _ = FC.fundir(base, capas)
    assert _sha(fundida) == SALIDA['cro1']
    assert fundida == (raiz / PAQ / 'ina_main1.cro').read_bytes()
    assert fundida == (raiz / CAPAS_IE1 / 'pachanga_objetivos_equipos_v3/salida/sobre_v2/romfs/cro/ina_main1.cro').read_bytes()
    assert capas['blog_ie1_oficial_v3'] == v2['blog_ie1_oficial']
    res = VC.comprobar(base, capas, fundida)
    assert res['solapes_bytes'] == 0 and res['solapes_palabras'] == 0 and res['independiente_del_orden']
    assert res['cuevas']['0x198500-0x198660'] == 'pachanga_objetivos_equipos_v3'
    # v2 y v3 de la pachanga son excluyentes
    mal = dict(capas)
    mal['pachanga_objetivos_equipos'] = v2['pachanga_objetivos_equipos']
    with pytest.raises(SystemExit):
        FC.fundir(base, mal)


def test_cro_ie1_cambia_respecto_de_hoy_solo_en_la_pachanga(raiz):
    from ie123kit.nucleo.registros.rangos import diff_ranges

    base_p = raiz / CRO_BASE
    hoy_p = raiz / PAQ_V2 / 'ina_main1.cro'
    if not base_p.exists() or not hoy_p.exists():
        pytest.skip('sin la CRO original o la del paquete v2')
    base, hoy = base_p.read_bytes(), hoy_p.read_bytes()
    assert _sha(hoy) == HOY['cro1']
    v3 = (raiz / PAQ / 'ina_main1.cro').read_bytes()
    pos = set()
    for n in ('pachanga_objetivos_equipos', 'pachanga_objetivos_equipos_v3'):
        c = (raiz / CAPAS_IE1 / n / 'salida/romfs/cro/ina_main1.cro').read_bytes()
        pos |= {x for lo, hi in diff_ranges(base, c) for x in range(lo, hi)}
    cambia = {x for lo, hi in diff_ranges(hoy, v3) for x in range(lo, hi)}
    assert cambia and cambia <= pos and len(cambia) == 309


def test_cro_ie2_es_la_salida_completa_de_la_capa(raiz):
    from ie123kit.nucleo.registros.rangos import diff_ranges

    hoy_p = raiz / 'work/ie2/shared/capas/menus_cro/paquete_final/ina_main2.cro'
    if not hoy_p.exists():
        pytest.skip('sin la CRO de IE2 del paquete final')
    hoy = hoy_p.read_bytes()
    assert _sha(hoy) == HOY['cro2']
    v3 = (raiz / PAQ / 'ina_main2.cro').read_bytes()
    capa = (raiz / CAPA_IE2 / 'salida/romfs/cro/ina_main2.cro').read_bytes()
    assert v3 == capa and _sha(v3) == SALIDA['cro2']
    assert sum(hi - lo for lo, hi in diff_ranges(hoy, v3)) == 38 and len(diff_ranges(hoy, v3)) == 17
    variante = (raiz / CAPA_IE2 / 'salida/variante_solo_modo0/romfs/cro/ina_main2.cro').read_bytes()
    assert variante != v3 and _sha(variante).startswith('3de2daed')


def test_deshacer_cro_devuelve_las_de_hoy(raiz):
    dat = json.loads((raiz / PAQ / 'deshacer_datos.json').read_text(encoding='utf-8'))
    for clave, fichero in (('cro1', 'ina_main1.cro'), ('cro2', 'ina_main2.cro')):
        datos = bytearray((raiz / PAQ / fichero).read_bytes())
        for r in dat[clave]['rangos']:
            o = r['offset']
            assert bytes(datos[o:o + len(r['nuevo_hex']) // 2]) == bytes.fromhex(r['nuevo_hex'])
            datos[o:o + len(r['original_hex']) // 2] = bytes.fromhex(r['original_hex'])
        assert _sha(bytes(datos)) == HOY[clave]


def test_deshacer_local_se_niega_con_un_hash_desconocido(raiz, tmp_path):
    DL = _cargar(raiz, 'deshacer_local')
    dat = json.loads((raiz / PAQ / 'deshacer_datos.json').read_text(encoding='utf-8'))
    cro = tmp_path / 'ina_main1.cro'
    cro.write_bytes((raiz / PAQ / 'ina_main1.cro').read_bytes() + b'x')
    with pytest.raises(SystemExit):
        DL.plan_cro(cro, dat['cro1'], 'ina_main1.cro')
    cro.write_bytes((raiz / PAQ / 'ina_main1.cro').read_bytes())
    hoy = DL.plan_cro(cro, dat['cro1'], 'ina_main1.cro')
    assert hoy is not None and _sha(hoy) == HOY['cro1']
    cro.write_bytes(hoy)
    assert DL.plan_cro(cro, dat['cro1'], 'ina_main1.cro') is None   # ya es la de HOY
