"""IE3 · paquete final de menús (`work/ie3/shared/capas/menus_cro/paquete_final`).

Sin el archive.fa (1,6 GB): comprueba que `informe.json`, `deshacer_datos.json`, la CRO final y los dos .ps1 son coherentes entre
sí, que la CRO final se reproduce desde las dos capas de CRO sobre la CRO instalada (`paso_cro` de `apply_todo.py`, que ejecuta cada
capa en una copia temporal y pasa las comprobaciones de `verificar_cro`) y que el deshacer de la CRO devuelve exactamente la base.
El archive.fa final se regenera y compara con `apply_todo.py` (ver el README del paquete).

Desde el 2026-11-09 el paquete se construye sobre el `archive.fa` de IE1 v2 (`BD1B450F…`, 26 entradas de `inazuma1/`); el del IE1 v1
(`397673B7…`) ya no es base valida y los .ps1 se niegan con el.
"""
import hashlib
import json
import re
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.requiere_rom

PAQ = Path('work/ie3/shared/capas/menus_cro/paquete_final')
CRO_BASE = Path('work/ie3/shared/capas/menus_cro/nombres_menu_jugadores/salida/romfs/cro/ina_main3ogre.cro')
BASE_CRO_SHA = '241f1c898e7ace34ffbccb08874dae50071e214c3dfdbde47f4760b3830cc635'
BASE_ARCHIVE_SHA = 'bd1b450fb203713c7e7a6c1eddc798fc67c306e139e99ef727618afa0f52c54a'  # IE1 v2 instalado (1 625 587 328 B)
BASE_ARCHIVE_TAM = 1625587328
ARCHIVE_IE1_V1_SHA = '397673b7aabe84a4a1d5dc7f74b011463af3c3536d2d228affa192ea9ea14510'  # IE1 v1: ya NO vale
SALIDA_ARCHIVE_SHA = '6878cc93c64e42e372b3b453b130cd876080417f49af46a111bc2736a3bdb3a3'
SALIDA_ARCHIVE_TAM = 1626304907
IE1_V2 = Path('work/ie1/capas/menus_cro/fundir_capas/paquete_final_v2')
SALIDA_CRO_SHA = '28c27f836c9f316370874d2f2b77f8f031b56b52bc6ed11e7a33aa9e5cb4333f'  # fichar_literales_eu v5 (67 literales)
CAPAS_CRO = ['nombres_casilla_resto', 'fichar_literales_eu']


@pytest.fixture(scope='module')
def raiz():
    from ie123kit.nucleo.config.raiz import find_root

    r = find_root()
    if not (r / PAQ / 'informe.json').exists():
        pytest.skip('sin el paquete final de IE3')
    return r


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def test_informe_y_datos_coherentes(raiz):
    inf = json.loads((raiz / PAQ / 'informe.json').read_text(encoding='utf-8'))
    dat = json.loads((raiz / PAQ / 'deshacer_datos.json').read_text(encoding='utf-8'))
    assert inf['runtime_verified'] is False and inf['instalada'] is False
    assert inf['base']['cro_sha256'] == BASE_CRO_SHA and inf['base']['archive_sha256'] == BASE_ARCHIVE_SHA
    assert dat['cro']['base_sha256'] == BASE_CRO_SHA and dat['archive']['base_sha256'] == BASE_ARCHIVE_SHA
    assert dat['cro']['salida_sha256'] == inf['salida']['cro_sha256'] == SALIDA_CRO_SHA
    assert len(dat['cro']['rangos']) == inf['cro']['rangos_totales'] == 90 and inf['cro']['bytes_distintos'] == 3003
    assert inf['cro']['por_capa']['fichar_literales_eu']['bytes'] == 2920 and inf['cro']['encadenada']['coincide_byte_a_byte']
    assert inf['cro']['comprobaciones']['parches_declarados']['fichar_literales_eu']['tramos'] == 67
    assert 'literales_cueva_eu' not in inf['cro']['orden_de_capas'], 'la capa de cuevas es opcional y no entra'
    assert dat['archive']['salida_sha256'] == inf['salida']['archive_sha256']
    assert dat['archive']['salida_tamano'] == inf['salida']['archive_tamano']
    assert len(dat['archive']['campos']) == inf['archive']['entradas'] == 1
    assert dat['archive']['campos'][0]['ruta'] == 'inazuma3_ogre/data_iz/a_menu/connection_b.arc'
    assert inf['cro']['orden_de_capas'] == CAPAS_CRO and 'medidor_ancho_real' in inf['cro']['excluidas']
    assert inf['cro']['por_capa']['nombres_casilla_resto']['opciones']['ancho_jinmyaku'] is False
    assert inf['archive']['hook_usearch']['sha256_sin_cambios_al_cerrar'] is True
    assert inf['archive']['hook_usearch']['antes']['verificar_rc'] == 0 and inf['archive']['hook_usearch']['verificar_rc'] == 0
    assert inf['archive']['paquete_ie1'] == {'paquete': 'paquete_final_v2', 'entradas_comprobadas': 26, 'ninguna_tocada': True,
                                             'offset_tamano_iguales': True, 'contenido_sha256_igual_en_base_y_final': True}
    assert inf['base']['archive_tamano'] == inf['archive']['base_tamano'] == BASE_ARCHIVE_TAM
    assert inf['salida']['archive_sha256'] == SALIDA_ARCHIVE_SHA and inf['salida']['archive_tamano'] == SALIDA_ARCHIVE_TAM
    assert inf['archive']['anexado'] == SALIDA_ARCHIVE_TAM - BASE_ARCHIVE_TAM == 717579
    assert inf['archive']['region_original_de_datos_identica'] and inf['archive']['tabla_solo_cambia_en_el_fileentry']
    assert dat['archive']['base_tamano'] == BASE_ARCHIVE_TAM and dat['archive']['salida_tamano'] == SALIDA_ARCHIVE_TAM
    assert dat['archive']['campos'][0]['offset_nuevo'] == BASE_ARCHIVE_TAM, 'el arc nuevo se anexa justo al final de la base'
    cro = (raiz / PAQ / 'ina_main3ogre.cro').read_bytes()
    assert _sha(cro) == inf['salida']['cro_sha256'] and len(cro) == inf['salida']['cro_tamano'] == 3481600


def test_se_apoya_en_el_paquete_ie1_v2(raiz):
    """La base de IE3 es exactamente la salida de `paquete_final_v2` de IE1 (no la del v1) y las 26 entradas coinciden."""
    inf = json.loads((raiz / PAQ / 'informe.json').read_text(encoding='utf-8'))
    ie1 = raiz / IE1_V2
    if not (ie1 / 'informe.json').exists():
        pytest.skip('sin el paquete de IE1 v2')
    i1 = json.loads((ie1 / 'informe.json').read_text(encoding='utf-8'))
    assert i1['salida']['archive_sha256'] == inf['base']['archive_sha256'] == BASE_ARCHIVE_SHA
    assert i1['salida']['archive_tamano'] == inf['base']['archive_tamano'] == BASE_ARCHIVE_TAM
    assert i1['archive']['entradas'] == inf['archive']['paquete_ie1']['entradas_comprobadas'] == 26
    campos = json.loads((ie1 / 'deshacer_datos.json').read_text(encoding='utf-8'))['archive']['campos']
    dat = json.loads((raiz / PAQ / 'deshacer_datos.json').read_text(encoding='utf-8'))['archive']['campos']
    assert len(campos) == 26 and dat[0]['campo_offset'] not in {c['campo_offset'] for c in campos}
    assert 'inazuma3_ogre' not in ''.join(c['ruta'] for c in campos)
    # apply_todo.py apunta a ese paquete y a las constantes de la base v2
    texto = (raiz / PAQ / 'apply_todo.py').read_text(encoding='utf-8')
    assert 'paquete_final_v2' in texto and BASE_ARCHIVE_SHA in texto and str(BASE_ARCHIVE_TAM) in texto
    assert 'paquete_final/deshacer_datos.json' not in texto


def test_scripts_powershell_llevan_los_hashes_del_informe(raiz):
    inf = json.loads((raiz / PAQ / 'informe.json').read_text(encoding='utf-8'))
    esperados = {inf['base']['cro_sha256'].upper(), inf['base']['archive_sha256'].upper(),
                 inf['salida']['cro_sha256'].upper(), inf['salida']['archive_sha256'].upper()}
    for nombre in ('instalar_ie3.ps1', 'deshacer_ie3.ps1'):
        texto = (raiz / PAQ / nombre).read_text(encoding='utf-8-sig')
        v1 = ARCHIVE_IE1_V1_SHA.upper()
        # el unico sha256 de mas es el del archive.fa de IE1 v1, que el instalador solo usa para negarse con un mensaje claro
        extra = {v1} if nombre == 'instalar_ie3.ps1' else set()
        assert set(re.findall(r"'([0-9A-F]{64})'", texto)) == esperados | extra, nombre
        assert str(inf['base']['archive_tamano']) in texto or nombre == 'instalar_ie3.ps1'
        assert (f"$V1_ARC   = '{v1}'" in texto) == (nombre == 'instalar_ie3.ps1')
        assert "$BASE_ARC = '" + BASE_ARCHIVE_SHA.upper() + "'" in texto, 'la base del .ps1 es la de IE1 v2'
        assert not re.search(r"\$(BASE|OUT)_ARC\s*=\s*'" + v1, texto), 'el v1 nunca puede ser base ni salida'
        assert str(inf['salida']['archive_tamano']) in texto
        assert 'Copy-Item' in texto or 'Seek' in texto
        assert '.antes' not in texto and 'IE_backups' not in texto, 'sin copias de seguridad'
        assert 'cro\\ina_main3ogre.cro' in texto and 'cro\\ina_main1.cro' not in texto, 'solo se instala la CRO de IE3'
        if nombre == 'instalar_ie3.ps1':
            # sin escribir: el v1 se rechaza ANTES de preparar ningun .nuevo, y solo la base v2 o la salida llegan a la rama de escritura
            assert texto.index('$shaArc -eq $V1_ARC') < texto.index("$tmp = $n[1] + '.nuevo'") < texto.index('Move-Item')
            assert "elseif ($shaArc -eq $V1_ARC) { throw" in texto and '26F953BC' in texto


def _constantes_ps1(ruta: Path) -> dict[str, str]:
    """Constantes `$NOMBRE = 'sha256'` de un .ps1 (en mayusculas)."""
    texto = ruta.read_text(encoding='utf-8-sig')
    return {k: v.upper() for k, v in re.findall(r"^\$(\w+)\s*=\s*'([0-9A-Fa-f]{64})'", texto, re.MULTILINE)}


def test_matriz_de_compatibilidad_entre_los_tres_paquetes(raiz):
    """El `archive.fa` es compartido: lo que dicen los README y el BACKLOG sobre IE1 v2, IE3 e IE2, comprobado en los .ps1."""
    ie1 = raiz / IE1_V2
    ie2 = raiz / 'work/ie2/shared/capas/menus_cro/paquete_final'
    if not ((ie1 / 'instalar_ie1.ps1').exists() and (ie2 / 'instalar_ie2.ps1').exists()):
        pytest.skip('sin los paquetes de IE1 v2 o de IE2')
    i1, d1 = _constantes_ps1(ie1 / 'instalar_ie1.ps1'), _constantes_ps1(ie1 / 'deshacer_ie1.ps1')
    i3, d3 = _constantes_ps1(raiz / PAQ / 'instalar_ie3.ps1'), _constantes_ps1(raiz / PAQ / 'deshacer_ie3.ps1')
    i2 = _constantes_ps1(ie2 / 'instalar_ie2.ps1')
    v2, v1, ie3 = i1['OUT_ARC'], i1['V1_ARC'], i3['OUT_ARC']
    assert v2 == BASE_ARCHIVE_SHA.upper() and v1 == ARCHIVE_IE1_V1_SHA.upper() and ie3 == SALIDA_ARCHIVE_SHA.upper()
    # IE3 parte exactamente del archive.fa que deja IE1 v2 y devuelve exactamente ese (su deshacer)
    assert i3['BASE_ARC'] == d3['BASE_ARC'] == v2 and d3['OUT_ARC'] == ie3 != v2
    # IE3 conoce el v1 solo para negarse; IE1 v2 NO conoce el archive.fa de IE3: con IE3 instalado sus instalar/deshacer se niegan
    assert i3['V1_ARC'] == v1 and v1 not in {i3['BASE_ARC'], i3['OUT_ARC']}
    assert ie3 not in {i1['BASE_ARC'], i1['V1_ARC'], i1['OUT_ARC']}, 'instalar_ie1.ps1 (v2) debe negarse con el archive.fa de IE3'
    assert ie3 not in {d1['BASE_ARC'], d1['V1_ARC'], d1['OUT_ARC']}, 'deshacer_ie1.ps1 (v2) debe negarse con el archive.fa de IE3'
    # IE2 solo lee el archive.fa y acepta los tres
    assert {i2['ARC_REQ'], i2['ARC_REQ_IE3'], i2['ARC_REQ_V1']} == {v2, ie3, v1}


def test_cro_final_se_reproduce_y_pasa_las_comprobaciones(raiz, tmp_path):
    base_p = raiz / CRO_BASE
    if not base_p.exists():
        pytest.skip('sin la CRO instalada de referencia en work/')
    assert _sha(base_p.read_bytes()) == BASE_CRO_SHA
    import importlib.util

    spec = importlib.util.spec_from_file_location('apply_todo_ie3', raiz / PAQ / 'apply_todo.py')
    AT = importlib.util.module_from_spec(spec)
    sys.modules['apply_todo_ie3'] = AT
    spec.loader.exec_module(AT)
    res = AT.paso_cro(base_p, tmp_path, tmp_path)
    assert (tmp_path / 'ina_main3ogre.cro').read_bytes() == (raiz / PAQ / 'ina_main3ogre.cro').read_bytes()
    c = res['comprobaciones']
    assert c['solapes_bytes'] == 0 and c['solapes_palabras'] == 0 and c['independiente_del_orden']
    assert c['relocaciones']['identicas_a_la_base'] and c['difiere_de_la_base_solo_en_los_parches_de_las_capas']
    assert res['bytes_distintos'] == 83 + 2920 == 3003 and res['rangos_totales'] == 90
    assert res['sha256'] == SALIDA_CRO_SHA
    assert res['comprobaciones']['parches_declarados']['fichar_literales_eu']['tramos'] == 67


def test_deshacer_cro_devuelve_la_base_exacta(raiz):
    base_p = raiz / CRO_BASE
    if not base_p.exists():
        pytest.skip('sin la CRO instalada de referencia')
    dat = json.loads((raiz / PAQ / 'deshacer_datos.json').read_text(encoding='utf-8'))['cro']
    datos = bytearray((raiz / PAQ / 'ina_main3ogre.cro').read_bytes())
    for r in dat['rangos']:
        o = r['offset']
        assert bytes(datos[o:o + len(r['nuevo_hex']) // 2]) == bytes.fromhex(r['nuevo_hex'])
        datos[o:o + len(r['original_hex']) // 2] = bytes.fromhex(r['original_hex'])
    assert _sha(bytes(datos)) == BASE_CRO_SHA == _sha(base_p.read_bytes())
