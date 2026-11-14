"""IE2 · paquete conjunto v5 (`work/ie1/capas/menus_cro/fundir_capas/paquete_final_v5`).

Sin el archive.fa (1,6 GB): comprueba que `informe.json`, `deshacer_datos.json`, la CRO de IE2 de la carpeta y los dos .ps1 son coherentes entre sí,
que la CRO de IE2 es la composición (disjunta) de las capas sobre la base E20D93B4 (se regenera con `apply_todo.paso_cro2`), que las 9 entradas del archive
casan con las `entradas_base` de las capas gráficas y con su registro, y que el deshacer de la CRO devuelve exactamente la del v4.
El archive.fa final se regenera y compara con `apply_todo.py` (ver el README del paquete).
"""
import hashlib
import importlib.util
import json
import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.requiere_rom

PAQ = Path('work/ie1/capas/menus_cro/fundir_capas/paquete_final_v5')
PAQ_V4 = Path('work/ie1/capas/menus_cro/fundir_capas/paquete_final_v4')
GRA = Path('work/ie2/shared/capas/graficos')
CAPAS_ARC = ['trasplantes_ie1_ie3', 'quit_b_oficial', 'guardado_oficial_ie2', 'tienda_oficial_ie2']
HOY = {   # = salida del v4
    'cro1': 'f7b3ef3f7306bfa0f0211cac2c530fb08755c127051ee7a3b1004ebfdce1dce8',
    'cro2': '0f7a417468181dd2f2481af994d942c775424bf4f9d1c4758d87dfec7c006a1e',
    'cro3': '28c27f836c9f316370874d2f2b77f8f031b56b52bc6ed11e7a33aa9e5cb4333f',
    'archive': 'f60ac92dd1090d80e7a26c4abcaca900beb93cb4cd9cdb7830e7d4a9e473b7a2',
}
SALIDA = {
    'cro1': HOY['cro1'],
    'cro2': '1e46fb0963e6b93a42a85523b9ef5dbe554d475bc5db0101925dcfd81489e743',
    'cro3': HOY['cro3'],
    'archive': '2770f9d2184da38c0f71f2388441e617ce0af00280837534834ebdfa00c96c9b',
}
HOY_ARCHIVE_TAMANO = 1658354080
SALIDA_ARCHIVE_TAMANO = 1658769808
ENTRADAS = {
    'inazuma2/data_iz/a_menu/shop_b.arc', 'inazuma2/data_iz/a_menu/item_b.arc', 'inazuma2/data_iz/a_menu/wireless_member_b.arc',
    'inazuma2/data_iz/a_game/game_result_b.arc', 'inazuma2/data_iz/a_common/wireless_common_b.arc',
    'inazuma2/data_iz/a_menu/battle_member_t.arc', 'inazuma2/data_iz/a_menu/battle_member_b.arc',
    'inazuma2/data_iz/a_menu/quit_b.arc', 'inazuma2/data_iz/a_menu/menu_slot.arc',
}
CRECEN = {'inazuma2/data_iz/a_menu/quit_b.arc', 'inazuma2/data_iz/a_menu/menu_slot.arc',
          'inazuma2/data_iz/a_menu/wireless_member_b.arc', 'inazuma2/data_iz/a_common/wireless_common_b.arc'}


@pytest.fixture(scope='module')
def raiz():
    from ie123kit.nucleo.config.raiz import find_root

    r = find_root()
    if not (r / PAQ / 'informe.json').exists():
        pytest.skip('sin el paquete conjunto v5')
    return r


def _cargar(raiz, nombre):
    """Carga `paquete_final_v5/<nombre>.py` con un nombre propio: `deshacer_local` e `instalar_local` existen tambien en otros paquetes."""
    spec = importlib.util.spec_from_file_location(f'{nombre}__conjunto_v5', raiz / PAQ / f'{nombre}.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def test_informe_y_datos_coherentes(raiz):
    inf = json.loads((raiz / PAQ / 'informe.json').read_text(encoding='utf-8'))
    dat = json.loads((raiz / PAQ / 'deshacer_datos.json').read_text(encoding='utf-8'))
    assert inf['paquete'] == 'ie_conjunto_v5'
    assert inf['runtime_verified'] is False and inf['instalada'] is False
    h, s = inf['hoy_v4'], inf['salida']
    assert (h['cro1_sha256'], h['cro2_sha256'], h['cro3_sha256'], h['archive_sha256']) == (HOY['cro1'], HOY['cro2'], HOY['cro3'], HOY['archive'])
    assert h['archive_tamano'] == HOY_ARCHIVE_TAMANO and s['archive_tamano'] == SALIDA_ARCHIVE_TAMANO
    assert (s['cro1_sha256'], s['cro2_sha256'], s['cro3_sha256'], s['archive_sha256']) == (SALIDA['cro1'], SALIDA['cro2'], SALIDA['cro3'], SALIDA['archive'])
    assert inf['cro1']['cambia'] is False and inf['cro3']['cambia'] is False
    assert s['archive_tamano'] - HOY_ARCHIVE_TAMANO == inf['archive']['anexado'] > 0
    assert dat['cro2']['hoy_sha256'] == HOY['cro2'] and dat['cro2']['salida_sha256'] == SALIDA['cro2']
    assert dat['archive']['hoy_sha256'] == HOY['archive'] and dat['archive']['hoy_tamano'] == HOY_ARCHIVE_TAMANO
    assert dat['archive']['salida_sha256'] == SALIDA['archive'] and dat['archive']['salida_tamano'] == SALIDA_ARCHIVE_TAMANO
    assert {c['ruta'] for c in dat['archive']['campos']} == ENTRADAS == set(inf['archive']['rutas'])
    assert len(dat['archive']['campos']) == inf['archive']['entradas_reemplazadas'] == len(inf['entradas_archive']) == 9
    for c in dat['archive']['campos']:
        assert len(c['original_hex']) == len(c['nuevo_hex']) == 16 and c['offset_nuevo'] >= HOY_ARCHIVE_TAMANO
    assert set(inf['archive']['crecen']) == CRECEN == {e['ruta'] for e in inf['entradas_archive'] if e['crece']}
    c2 = inf['cro2']
    assert c2['con_variantes_f5'] is True and c2['sha256'] == c2['sha256_con_variantes_f5'] != c2['sha256_sin_variantes_f5']
    assert c2['disjuntas'] and c2['independiente_del_orden'] and c2['parseable']
    assert c2['estructura_respecto_de_la_base']['importaciones_iguales'] and c2['estructura_respecto_del_v4']['segmentos_iguales']
    assert set(c2['variantes_f5']) == {'estrategias_ancho', 'titulo_superficie_6', 'datos_en_letras'}
    hk = inf['archive']['hook_usearch']
    assert hk['verificar_rc'] == 0 and hk['cerrar_rc'] == 0 and hk['sha256_sin_cambios_al_cerrar'] is True
    assert inf['archive']['region_original_de_datos_identica'] and inf['archive']['tabla_solo_cambia_en_los_campos'] and inf['archive']['solo_crece_por_el_final']
    assert all(v['runtime_verified'] is False and v['instalada'] is False for v in inf['archive']['capas_version'].values())
    assert all(v['runtime_verified'] is False and v['instalada'] is False for v in c2['capas_version'].values())
    cro2 = (raiz / PAQ / 'ina_main2.cro').read_bytes()
    assert _sha(cro2) == s['cro2_sha256'] and len(cro2) == s['cro2_tamano']
    assert not (raiz / PAQ / 'ina_main1.cro').exists(), 'la CRO de IE1 no cambia: no se guarda'


def test_cro_ie2_se_regenera_de_las_capas(raiz, tmp_path):
    AT = _cargar(raiz, 'apply_todo')
    v4_p = raiz / PAQ_V4 / 'ina_main2.cro'
    if not v4_p.exists() or not (raiz / AT.PAQUETE_V3 / 'ina_main2.cro').exists():
        pytest.skip('sin la CRO de IE2 de los paquetes v3/v4')
    res, _ = AT.paso_cro2(v4_p, tmp_path, True)      # lanza SystemExit si las capas se solapan, no componen igual en todos los órdenes o cambian de hash
    assert res['sha256'] == SALIDA['cro2']
    assert (tmp_path / 'ina_main2.cro').read_bytes() == (raiz / PAQ / 'ina_main2.cro').read_bytes()
    (tmp_path / 'sin').mkdir()
    sin, _ = AT.paso_cro2(v4_p, tmp_path / 'sin', False)
    assert sin['sha256'] == AT.SAL_CRO2_SIN_VARIANTES_SHA == 'd0552dd0a1bab5805f83b93358bd35b6e301d1fe0256e6430cc97810e34d26ed'


def test_las_9_entradas_casan_con_las_capas(raiz):
    entradas = {}
    for n in CAPAS_ARC:
        d = raiz / GRA / n
        inf = json.loads((d / 'informe.json').read_text(encoding='utf-8'))
        assert inf['runtime_verified'] is False and inf['instalada'] is False
        for e in inf['entradas_base']:
            entradas[e['ruta']] = e
    assert ENTRADAS <= set(entradas)
    inf5 = json.loads((raiz / PAQ / 'informe.json').read_text(encoding='utf-8'))
    dat = json.loads((raiz / PAQ / 'deshacer_datos.json').read_text(encoding='utf-8'))
    for c in dat['archive']['campos']:
        e = entradas[c['ruta']]
        assert (c['sha256_hoy'], c['tamano_hoy']) == (e['sha256'], e['tamano'])
    # las salidas entregadas son las de las capas (shop_b: la de tienda; quit_b: la variante compacta)
    esperado = {
        'inazuma2/data_iz/a_menu/shop_b.arc': raiz / GRA / 'tienda_oficial_ie2/salida/extra/inazuma2/data_iz/a_menu/shop_b.arc',
        'inazuma2/data_iz/a_menu/quit_b.arc': raiz / GRA / 'quit_b_oficial/alternativas/btn02_compacto/inazuma2/data_iz/a_menu/quit_b.arc',
        'inazuma2/data_iz/a_menu/menu_slot.arc': raiz / GRA / 'guardado_oficial_ie2/salida/extra/inazuma2/data_iz/a_menu/menu_slot.arc',
    }
    for r in ENTRADAS - set(esperado):
        esperado[r] = raiz / GRA / 'trasplantes_ie1_ie3/salida/extra' / r
    por_ruta = {e['ruta']: e for e in inf5['entradas_archive']}
    for r, f in esperado.items():
        b = f.read_bytes()
        assert _sha(b) == por_ruta[r]['sha256_v5'] and len(b) == por_ruta[r]['tamano_v5'], r


def test_scripts_powershell_llevan_los_hashes_del_informe(raiz):
    inf = json.loads((raiz / PAQ / 'informe.json').read_text(encoding='utf-8'))
    h, s = inf['hoy_v4'], inf['salida']
    esperados = {v.upper() for d in (h, s) for k, v in d.items() if k.endswith('_sha256')}
    assert len(esperados) == 6                      # las CRO de IE1 e IE3 son las mismas en hoy y salida
    for nombre in ('instalar_v5.ps1', 'deshacer_v5.ps1'):
        crudo = (raiz / PAQ / nombre).read_bytes()
        assert crudo.startswith(b'\xef\xbb\xbf'), 'BOM'
        assert crudo.count(b'\r\n') == crudo.count(b'\n'), 'CRLF'
        texto = crudo.decode('utf-8-sig')
        assert set(re.findall(r"'([0-9A-F]{64})'", texto)) <= esperados, nombre
        assert str(s['archive_tamano']) in texto
        assert 'Copy-Item' in texto or 'Seek' in texto
        assert '.antes' not in texto and 'IE_backups' not in texto, 'sin copias de seguridad'
    instalar = (raiz / PAQ / 'instalar_v5.ps1').read_text(encoding='utf-8-sig')
    assert set(re.findall(r"'([0-9A-F]{64})'", instalar)) == esperados
    assert 'AvailableFreeSpace' in instalar and 'SoloComprobar' in instalar and '$HOY_CRO3' in instalar and "Get-Process -Name 'azahar*'" in instalar
    assert 'Move-Item' in instalar and ".nuevo" in instalar
    assert str(s['cro2_tamano']) in instalar and 'C:\\IE_work\\paquete_v5' in instalar
    deshacer = (raiz / PAQ / 'deshacer_v5.ps1').read_text(encoding='utf-8-sig')
    assert str(h['archive_tamano']) in deshacer and 'SetLength($TAM_HOY_ARC)' in deshacer
    assert set(re.findall(r"'([0-9A-F]{64})'", deshacer)) == esperados


def test_instalar_local_lee_las_constantes_del_ps1(raiz):
    IL = _cargar(raiz, 'instalar_local')
    c = IL.constantes()
    assert c['HOY_CRO1'].lower() == HOY['cro1'] and c['OUT_CRO1'] == c['HOY_CRO1']
    assert c['HOY_CRO2'].lower() == HOY['cro2'] and c['OUT_CRO2'].lower() == SALIDA['cro2']
    assert c['HOY_CRO3'] == c['OUT_CRO3'] and c['HOY_ARC'].lower() == HOY['archive'] and c['OUT_ARC'].lower() == SALIDA['archive']
    assert c['TAM_OUT_CRO2'] == 2748416 and c['TAM_OUT_ARC'] == SALIDA_ARCHIVE_TAMANO


def test_deshacer_cro_devuelve_la_del_v4(raiz):
    dat = json.loads((raiz / PAQ / 'deshacer_datos.json').read_text(encoding='utf-8'))
    datos = bytearray((raiz / PAQ / 'ina_main2.cro').read_bytes())
    assert len(dat['cro2']['rangos']) == 157
    for r in dat['cro2']['rangos']:
        o = r['offset']
        assert bytes(datos[o:o + len(r['nuevo_hex']) // 2]) == bytes.fromhex(r['nuevo_hex'])
        datos[o:o + len(r['original_hex']) // 2] = bytes.fromhex(r['original_hex'])
    assert _sha(bytes(datos)) == HOY['cro2']
    v4 = raiz / PAQ_V4 / 'ina_main2.cro'
    if v4.exists():
        assert bytes(datos) == v4.read_bytes()


def test_deshacer_local_se_niega_con_un_hash_desconocido(raiz, tmp_path):
    DL = _cargar(raiz, 'deshacer_local')
    dat = json.loads((raiz / PAQ / 'deshacer_datos.json').read_text(encoding='utf-8'))
    cro = tmp_path / 'ina_main2.cro'
    cro.write_bytes((raiz / PAQ / 'ina_main2.cro').read_bytes() + b'x')
    with pytest.raises(SystemExit):
        DL.plan_cro(cro, dat['cro2'], 'ina_main2.cro')
    cro.write_bytes((raiz / PAQ / 'ina_main2.cro').read_bytes())
    v4 = DL.plan_cro(cro, dat['cro2'], 'ina_main2.cro')
    assert v4 is not None and _sha(v4) == HOY['cro2']
    cro.write_bytes(v4)
    assert DL.plan_cro(cro, dat['cro2'], 'ina_main2.cro') is None   # ya es la del v4
