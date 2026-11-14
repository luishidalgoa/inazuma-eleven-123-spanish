"""IE2 · paquete final de Fichar (`work/ie2/shared/capas/menus_cro/paquete_final`).

Sin el archive.fa (1,6 GB; el paquete no lo cambia): comprueba que `informe.json`, `deshacer_datos.json`, la CRO final y los dos .ps1 son
coherentes entre sí, que la CRO final se reproduce (dos veces, idéntica) desde la CRO 1.4 instalada con la capa `fichar_unido_completo`,
que las comprobaciones de `apply_todo.comprobar_cro` pasan y que el deshacer devuelve exactamente la base. La comprobación contra el
archive.fa instalado (y el hook de usearch) la hace `apply_todo.py --base-archive` (ver el README del paquete).

Desde 2026-11-09 el archive.fa de referencia es el del paquete final de IE1 v2 (`BD1B450F...`); el paquete acepta ademas el que deja el paquete
IE3 regenerado sobre el v2 y el v1 de IE1 (`397673B7...`), porque las 4 entradas que usa la capa son byte a byte las mismas (evidencia en
`informe.json`, `archive.evidencia_v1_v2`).
"""
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.requiere_rom

PAQ = Path('work/ie2/shared/capas/menus_cro/paquete_final')
CRO_BASE = Path('work/shared/candidatas/probe_ie3_fuego_v17_u14/romfs/cro/ina_main2.cro')
BASE_CRO_SHA = 'a281f2be73bebcdcc66e042d28340fe7abd6002d3705568da339a2482c39dec8'
SALIDA_CRO_SHA = 'ce0449bf5045b997782db50d6eae80cd067bb2f27a833410d349f6ea409de008'
ARCHIVE_SHA = 'bd1b450fb203713c7e7a6c1eddc798fc67c306e139e99ef727618afa0f52c54a'  # IE1 v2 (instalado el 2026-11-09)
ARCHIVE_TAM = 1625587328
ARCHIVE_SHA_V1 = '397673b7aabe84a4a1d5dc7f74b011463af3c3536d2d228affa192ea9ea14510'  # IE1 v1
ARCHIVE_TAM_V1 = 1625457264
ARCHIVE_SHA_TRAS_IE3 = '6878cc93c64e42e372b3b453b130cd876080417f49af46a111bc2736a3bdb3a3'  # IE1 v2 + paquete IE3 regenerado
ARCHIVE_TAM_TRAS_IE3 = 1626304907
ACEPTADOS = {ARCHIVE_SHA: ARCHIVE_TAM, ARCHIVE_SHA_TRAS_IE3: ARCHIVE_TAM_TRAS_IE3, ARCHIVE_SHA_V1: ARCHIVE_TAM_V1}
ANTIGUO_IE3_SOBRE_V1 = 'e4c1697a0a69ce32a96ee54234054ec15ca1e278695313307cc63490f9e6b976'  # ya no se acepta (no verificado, paquete IE3 superado)


@pytest.fixture(scope='module')
def raiz():
    from ie123kit.nucleo.config.raiz import find_root

    r = find_root()
    if not (r / PAQ / 'informe.json').exists():
        pytest.skip('sin el paquete final de IE2')
    return r


@pytest.fixture(scope='module')
def apply_todo(raiz):
    spec = importlib.util.spec_from_file_location('ie2_paquete_apply_todo', raiz / PAQ / 'apply_todo.py')
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def test_informe_y_datos_coherentes(raiz):
    inf = json.loads((raiz / PAQ / 'informe.json').read_text(encoding='utf-8'))
    dat = json.loads((raiz / PAQ / 'deshacer_datos.json').read_text(encoding='utf-8'))
    assert inf['runtime_verified'] is False and inf['instalada'] is False
    assert inf['base']['cro_sha256'] == BASE_CRO_SHA and inf['base']['archive_sha256'] == ARCHIVE_SHA
    assert inf['base']['archive_tamano'] == ARCHIVE_TAM
    assert inf['salida']['cro_sha256'] == SALIDA_CRO_SHA and inf['salida']['archive_sha256'] == ARCHIVE_SHA
    assert inf['archive']['cambia'] is False and inf['archive']['sin_cambios'] is True
    assert {x['sha256']: x['tamano'] for x in inf['archive_aceptados']} == ACEPTADOS
    ev = inf['archive']['evidencia_v1_v2']
    assert len(ev['entradas_con_par_distinto']) == 4 and all(k.startswith('inazuma1/') for k in ev['entradas_con_par_distinto'])
    assert ev['region_de_datos_v1_intacta_en_v2'] is True and ev['anexado_bytes'] == ARCHIVE_TAM - ARCHIVE_TAM_V1
    assert len(ev['entradas_de_ie2']) == 4 and all(v['iguales'] is True for v in ev['entradas_de_ie2'].values())
    assert dat['cro']['base_sha256'] == BASE_CRO_SHA and dat['cro']['salida_sha256'] == SALIDA_CRO_SHA
    assert dat['archive']['cambia'] is False and dat['archive']['sha256_requerido'] == ARCHIVE_SHA
    assert {x['sha256']: x['tamano'] for x in dat['archive']['aceptados']} == ACEPTADOS
    assert sum(len(r['nuevo_hex']) // 2 for r in dat['cro']['rangos']) == inf['cro']['bytes_distintos'] == 2706
    assert len(dat['cro']['rangos']) == inf['cro']['rangos_totales']
    assert inf['cro']['opciones']['titulo_hh'] == 'Fichar' and inf['cro']['opciones']['nombres'] == 'letras'
    assert inf['cro']['determinista_en_dos_generaciones'] is True
    assert inf['archive']['hook_usearch']['verificar_rc'] == 0
    assert _sha((raiz / PAQ / 'ina_main2.cro').read_bytes()) == SALIDA_CRO_SHA


def test_scripts_powershell_llevan_los_hashes_del_informe(raiz):
    esperados = {BASE_CRO_SHA.upper(), SALIDA_CRO_SHA.upper()}
    for nombre in ('instalar_ie2.ps1', 'deshacer_ie2.ps1'):
        texto = (raiz / PAQ / nombre).read_text(encoding='utf-8-sig')
        hashes = set(re.findall(r"'([0-9A-F]{64})'", texto))
        # el archive.fa puede ser el v2 de IE1, el que deja el paquete IE3 regenerado sobre el v2 o el v1 (no afecta a IE2)
        assert esperados <= hashes <= esperados | {h.upper() for h in ACEPTADOS}, nombre
        assert ANTIGUO_IE3_SOBRE_V1.upper() not in hashes, nombre
        assert '2748416' in texto
        assert '.antes' not in texto and 'IE_backups' not in texto, 'sin copias de seguridad'
        assert '.nuevo' in texto and 'SoloComprobar' in texto and "'azahar*'" in texto
    inst = (raiz / PAQ / 'instalar_ie2.ps1').read_text(encoding='utf-8-sig')
    assert {h.upper() for h in ACEPTADOS} <= set(re.findall(r"'([0-9A-F]{64})'", inst))
    for tam in ACEPTADOS.values():
        assert str(tam) in inst
    assert '$ARC_OK' in inst and 'No se escribe nada' in inst
    # BOM y CRLF conservados
    crudo = (raiz / PAQ / 'instalar_ie2.ps1').read_bytes()
    assert crudo.startswith(b'\xef\xbb\xbf') and crudo.count(b'\r\n') == crudo.count(b'\n')


def test_apply_todo_acepta_solo_los_archive_verificados(raiz, apply_todo, tmp_path):
    assert apply_todo.ARCHIVE_SHA == ARCHIVE_SHA and apply_todo.ARCHIVE_TAM == ARCHIVE_TAM
    assert {h: t for h, (t, _r) in apply_todo.ARCHIVES_ACEPTADOS.items()} == ACEPTADOS
    assert ANTIGUO_IE3_SOBRE_V1 not in apply_todo.ARCHIVES_ACEPTADOS
    # un fichero que no es ninguno de los aceptados se rechaza (sin tocarlo)
    falso = tmp_path / 'archive.fa'
    falso.write_bytes(b'B123' + bytes(100))
    with pytest.raises(SystemExit, match='no es uno de los verificados'):
        apply_todo.comprobar_archive(falso, False)
    assert falso.read_bytes() == b'B123' + bytes(100)


def test_cro_final_se_reproduce_dos_veces_y_pasa_las_comprobaciones(raiz, apply_todo, tmp_path):
    base_p = raiz / CRO_BASE
    if not base_p.exists():
        pytest.skip('sin la CRO 1.4 instalada de referencia en work/shared/candidatas')
    base = base_p.read_bytes()
    assert _sha(base) == BASE_CRO_SHA
    A = apply_todo.cargar_capa()
    g1 = apply_todo.generar(A, base_p, tmp_path / 'g1')
    g2 = apply_todo.generar(A, base_p, tmp_path / 'g2')
    assert g1 == g2 == (raiz / PAQ / 'ina_main2.cro').read_bytes()
    inf_capa = json.loads((raiz / 'work/ie2/shared/capas/menus_cro/fichar_unido_completo/informe.json').read_text(encoding='utf-8'))
    res = apply_todo.comprobar_cro(base, g1, inf_capa)
    assert res['bytes_distintos'] == 2706 and res['relocaciones']['registros_cambiados'] == 34
    assert res['segmento_1']['despues'] == '0x24000'


def test_comprobar_cro_rechaza_una_salida_alterada(raiz, apply_todo):
    base_p = raiz / CRO_BASE
    if not base_p.exists():
        pytest.skip('sin la CRO 1.4 instalada de referencia')
    inf_capa = json.loads((raiz / 'work/ie2/shared/capas/menus_cro/fichar_unido_completo/informe.json').read_text(encoding='utf-8'))
    mala = bytearray((raiz / PAQ / 'ina_main2.cro').read_bytes())
    mala[0x100000] ^= 1
    with pytest.raises(SystemExit):
        apply_todo.comprobar_cro(base_p.read_bytes(), bytes(mala), inf_capa)


def test_deshacer_cro_devuelve_la_base_exacta(raiz):
    base_p = raiz / CRO_BASE
    if not base_p.exists():
        pytest.skip('sin la CRO 1.4 instalada de referencia')
    dat = json.loads((raiz / PAQ / 'deshacer_datos.json').read_text(encoding='utf-8'))['cro']
    datos = bytearray((raiz / PAQ / 'ina_main2.cro').read_bytes())
    for r in dat['rangos']:
        o = r['offset']
        assert bytes(datos[o:o + len(r['nuevo_hex']) // 2]) == bytes.fromhex(r['nuevo_hex'])
        datos[o:o + len(r['original_hex']) // 2] = bytes.fromhex(r['original_hex'])
    assert _sha(bytes(datos)) == BASE_CRO_SHA == _sha(base_p.read_bytes())
