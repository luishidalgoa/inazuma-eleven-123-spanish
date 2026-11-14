"""IE1 + IE2 · paquete conjunto v4 (`work/ie1/capas/menus_cro/fundir_capas/paquete_final_v4`).

Sin el archive.fa (1,6 GB): comprueba que `informe.json`, `deshacer_datos.json`, la CRO de IE2 de la carpeta y los dos .ps1 son coherentes entre sí,
que la CRO de IE2 es la composición de `inablog_ie2_proporcional` y `pachanga_ie2_proporcional` sobre la instalada hoy (salida del v3) en cualquier orden,
que las 12 entradas del archive casan con las `entradas_base` de las tres capas de lugares oficiales y que el deshacer de la CRO devuelve exactamente la de HOY.
El archive.fa final se regenera y compara con `apply_todo.py` (ver el README del paquete).
"""
import hashlib
import importlib.util
import json
import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.requiere_rom

PAQ = Path('work/ie1/capas/menus_cro/fundir_capas/paquete_final_v4')
PAQ_V3 = Path('work/ie1/capas/menus_cro/fundir_capas/paquete_final_v3')
CAPA_BLOG = Path('work/ie2/shared/capas/menus_cro/inablog_ie2_proporcional')
CAPA_PACH = Path('work/ie2/shared/capas/menus_cro/pachanga_ie2_proporcional')
CAPAS_LUGARES = [Path('work/ie1/capas/rotulos_objetivos/lugares_oficiales'),
                 Path('work/ie2/shared/capas/rotulos_objetivos/lugares_oficiales'),
                 Path('work/shared/capas/lugares_oficiales_fuente')]
HOY = {
    'cro1': 'f7b3ef3f7306bfa0f0211cac2c530fb08755c127051ee7a3b1004ebfdce1dce8',
    'cro2': 'e20d93b418429b666f0922e9206c4f0327f8a84ba337ae7d131e41b41f728d8c',
    'cro3': '28c27f836c9f316370874d2f2b77f8f031b56b52bc6ed11e7a33aa9e5cb4333f',
    'archive': 'bd64626421b27c50690c188fd086d26da13140a5ae3dfd3f8cefd8067ec7e2da',
}
SALIDA = {
    'cro1': HOY['cro1'],
    'cro2': '0f7a417468181dd2f2481af994d942c775424bf4f9d1c4758d87dfec7c006a1e',
    'cro3': HOY['cro3'],
    'archive': 'f60ac92dd1090d80e7a26c4abcaca900beb93cb4cd9cdb7830e7d4a9e473b7a2',
}
HOY_ARCHIVE_TAMANO = 1626392800
SALIDA_ARCHIVE_TAMANO = 1658354080
ENTRADAS = {
    'inazuma1/data_iz/script/eve.pkh', 'inazuma1/data_iz/script/eve.pkb',
    'inazuma1/data_iz/a_data_replace/vs_stage_select/data/ie01_vs_stage_select_04.arc',
    'inazuma1/data_iz/a_data_replace/vs_stage_select/data/ie01_vs_stage_select_05.arc',
    'inazuma1/data_iz/a_data_replace/vs_stage_select/data/ie01_vs_stage_select_06.arc',
    'inazuma1/data_iz/a_data_replace/vs_stage_select/data/ie01_vs_stage_select_07.arc',
    'inazuma1/data_iz/logic/gmapbase.dat',
    'inazuma2/data_iz/script/eve.pkh', 'inazuma2/data_iz/script/eve.pkb',
    'inazuma2/data_iz_blizzard/script/eve.pkh', 'inazuma2/data_iz_blizzard/script/eve.pkb',
    'font/FONT8.bcfnt',
}


@pytest.fixture(scope='module')
def raiz():
    from ie123kit.nucleo.config.raiz import find_root

    r = find_root()
    if not (r / PAQ / 'informe.json').exists():
        pytest.skip('sin el paquete conjunto v4')
    return r


def _cargar(raiz, nombre):
    """Carga `paquete_final_v4/<nombre>.py` con un nombre propio: `deshacer_local` e `instalar_local` existen tambien en otros paquetes."""
    spec = importlib.util.spec_from_file_location(f'{nombre}__conjunto_v4', raiz / PAQ / f'{nombre}.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def test_informe_y_datos_coherentes(raiz):
    inf = json.loads((raiz / PAQ / 'informe.json').read_text(encoding='utf-8'))
    dat = json.loads((raiz / PAQ / 'deshacer_datos.json').read_text(encoding='utf-8'))
    assert inf['paquete'] == 'ie_conjunto_v4'
    assert inf['runtime_verified'] is False and inf['instalada'] is False
    h, s = inf['hoy'], inf['salida']
    assert (h['cro1_sha256'], h['cro2_sha256'], h['cro3_sha256'], h['archive_sha256']) == (HOY['cro1'], HOY['cro2'], HOY['cro3'], HOY['archive'])
    assert h['archive_tamano'] == HOY_ARCHIVE_TAMANO and s['archive_tamano'] == SALIDA_ARCHIVE_TAMANO
    assert (s['cro1_sha256'], s['cro2_sha256'], s['cro3_sha256'], s['archive_sha256']) == (SALIDA['cro1'], SALIDA['cro2'], SALIDA['cro3'], SALIDA['archive'])
    assert inf['cro1']['cambia'] is False and inf['cro3']['cambia'] is False
    assert s['archive_tamano'] - HOY_ARCHIVE_TAMANO == inf['archive']['anexado'] > 0
    assert dat['cro1']['sha256'] == HOY['cro1'] and dat['cro3']['sha256'] == HOY['cro3']
    assert dat['cro2']['hoy_sha256'] == HOY['cro2'] and dat['cro2']['salida_sha256'] == SALIDA['cro2']
    assert dat['archive']['hoy_sha256'] == HOY['archive'] and dat['archive']['hoy_tamano'] == HOY_ARCHIVE_TAMANO
    assert dat['archive']['salida_sha256'] == SALIDA['archive'] and dat['archive']['salida_tamano'] == SALIDA_ARCHIVE_TAMANO
    assert {c['ruta'] for c in dat['archive']['campos']} == ENTRADAS == set(inf['archive']['rutas'])
    assert len(dat['archive']['campos']) == inf['archive']['entradas_reemplazadas'] == len(inf['entradas_archive']) == 12
    for c in dat['archive']['campos']:
        assert len(c['original_hex']) == len(c['nuevo_hex']) == 16 and c['offset_nuevo'] >= HOY_ARCHIVE_TAMANO
    assert (inf['cro2']['bytes_distintos_respecto_de_hoy'], inf['cro2']['palabras']) == (43, 12)
    assert inf['cro2']['disjuntas'] and inf['cro2']['independiente_del_orden'] and inf['cro2']['cambia_solo_lo_declarado_por_las_capas']
    assert inf['cro2']['estructura']['importaciones_iguales'] and inf['cro2']['estructura']['segmentos_iguales']
    assert set(inf['cro2']['alternativas_no_usadas']) == {'inablog_solo_titulo', 'inablog_sin_separacion', 'regla_contenido_opcional'}
    assert any('regla_contenido' in k for k in inf['excluidas']) and any('solo_titulo' in k for k in inf['excluidas'])
    hk = inf['archive']['hook_usearch']
    assert hk['verificar_rc'] == 0 and hk['cerrar_rc'] == 0 and hk['sha256_sin_cambios_al_cerrar'] is True
    assert inf['archive']['region_original_de_datos_identica'] and inf['archive']['tabla_solo_cambia_en_los_campos'] and inf['archive']['solo_crece_por_el_final']
    assert all(v['runtime_verified'] is False and v['instalada'] is False for v in inf['archive']['capas_version'].values())
    assert all(v['runtime_verified'] is False and v['instalada'] is False for v in inf['cro2']['capas_version'].values())
    cro2 = (raiz / PAQ / 'ina_main2.cro').read_bytes()
    assert _sha(cro2) == s['cro2_sha256'] and len(cro2) == s['cro2_tamano']
    assert not (raiz / PAQ / 'ina_main1.cro').exists(), 'la CRO de IE1 no cambia: no se guarda'


def test_cro_ie2_es_la_composicion_de_las_dos_capas(raiz):
    from ie123kit.nucleo.registros.rangos import diff_ranges

    hoy_p = raiz / PAQ_V3 / 'ina_main2.cro'
    if not hoy_p.exists():
        pytest.skip('sin la CRO de IE2 del paquete v3')
    hoy = hoy_p.read_bytes()
    assert _sha(hoy) == HOY['cro2']
    blog = (raiz / CAPA_BLOG / 'salida/romfs/cro/ina_main2.cro').read_bytes()
    pach = (raiz / CAPA_PACH / 'salida/romfs/cro/ina_main2.cro').read_bytes()
    r_blog, r_pach = diff_ranges(hoy, blog), diff_ranges(hoy, pach)
    assert sum(hi - lo for lo, hi in r_blog) == 42 and r_pach == [(0x17B8BD, 0x17B8BE)]
    assert not ({x for lo, hi in r_blog for x in range(lo, hi)} & {0x17B8BD})

    def aplicar(base, capa, rs):
        o = bytearray(base)
        for lo, hi in rs:
            o[lo:hi] = capa[lo:hi]
        return bytes(o)

    ab = aplicar(aplicar(hoy, blog, r_blog), pach, r_pach)
    ba = aplicar(aplicar(hoy, pach, r_pach), blog, r_blog)
    assert ab == ba and _sha(ab) == SALIDA['cro2']
    assert ab == (raiz / PAQ / 'ina_main2.cro').read_bytes()
    assert len(diff_ranges(hoy, ab)) == 9 and sum(hi - lo for lo, hi in diff_ranges(hoy, ab)) == 43
    # las alternativas no se usan
    for ruta in ('salida/variante_solo_titulo', 'salida/variante_sin_separacion'):
        assert (raiz / CAPA_BLOG / ruta / 'romfs/cro/ina_main2.cro').read_bytes() != blog
    regla = raiz / 'work/ie2/shared/capas/menus_cro/fuente_ie2_regla_contenido_opcional/salida/romfs/cro/ina_main2.cro'
    if regla.exists():
        rr = {x for lo, hi in diff_ranges(hoy, regla.read_bytes()) for x in range(lo, hi)}
        assert rr & {x for lo, hi in r_blog for x in range(lo, hi)}, 'la regla opcional es excluyente con el Inablog'


def test_las_12_entradas_casan_con_las_capas(raiz):
    entradas = {}
    for d in CAPAS_LUGARES:
        inf = json.loads((raiz / d / 'informe.json').read_text(encoding='utf-8'))
        assert inf['runtime_verified'] is False and inf['instalada'] is False
        assert inf['base_archive_sha256'] == HOY['archive']
        extra = raiz / d / 'salida/extra'
        for f in sorted(p for p in extra.rglob('*') if p.is_file()):
            ruta = f.relative_to(extra).as_posix()
            assert ruta not in entradas
            assert _sha(f.read_bytes()) == inf['salida_sha256'][ruta]
            entradas[ruta] = {e['ruta']: e for e in inf['entradas_base']}[ruta]
    assert set(entradas) == ENTRADAS
    dat = json.loads((raiz / PAQ / 'deshacer_datos.json').read_text(encoding='utf-8'))
    for c in dat['archive']['campos']:
        e = entradas[c['ruta']]
        assert (c['sha256_hoy'], c['tamano_hoy']) == (e['sha256'], e['tamano'])


def test_scripts_powershell_llevan_los_hashes_del_informe(raiz):
    inf = json.loads((raiz / PAQ / 'informe.json').read_text(encoding='utf-8'))
    h, s = inf['hoy'], inf['salida']
    esperados = {v.upper() for d in (h, s) for k, v in d.items() if k.endswith('_sha256')}
    assert len(esperados) == 6                      # las CRO de IE1 e IE3 son las mismas en hoy y salida
    for nombre in ('instalar_v4.ps1', 'deshacer_v4.ps1'):
        crudo = (raiz / PAQ / nombre).read_bytes()
        assert crudo.startswith(b'\xef\xbb\xbf'), 'BOM'
        assert crudo.count(b'\r\n') == crudo.count(b'\n'), 'CRLF'
        texto = crudo.decode('utf-8-sig')
        assert set(re.findall(r"'([0-9A-F]{64})'", texto)) <= esperados, nombre
        assert str(s['archive_tamano']) in texto
        assert 'Copy-Item' in texto or 'Seek' in texto
        assert '.antes' not in texto and 'IE_backups' not in texto, 'sin copias de seguridad'
    instalar = (raiz / PAQ / 'instalar_v4.ps1').read_text(encoding='utf-8-sig')
    assert set(re.findall(r"'([0-9A-F]{64})'", instalar)) == esperados
    assert 'AvailableFreeSpace' in instalar and 'SoloComprobar' in instalar and '$HOY_CRO3' in instalar
    assert str(s['cro2_tamano']) in instalar and 'C:\\IE_work\\paquete_v4' in instalar
    deshacer = (raiz / PAQ / 'deshacer_v4.ps1').read_text(encoding='utf-8-sig')
    assert str(h['archive_tamano']) in deshacer and 'SetLength($TAM_HOY_ARC)' in deshacer
    assert set(re.findall(r"'([0-9A-F]{64})'", deshacer)) == esperados


def test_instalar_local_lee_las_constantes_del_ps1(raiz):
    IL = _cargar(raiz, 'instalar_local')
    c = IL.constantes()
    assert c['HOY_CRO1'].lower() == HOY['cro1'] and c['OUT_CRO1'] == c['HOY_CRO1']
    assert c['HOY_CRO2'].lower() == HOY['cro2'] and c['OUT_CRO2'].lower() == SALIDA['cro2']
    assert c['HOY_CRO3'] == c['OUT_CRO3'] and c['HOY_ARC'].lower() == HOY['archive'] and c['OUT_ARC'].lower() == SALIDA['archive']
    assert c['TAM_OUT_CRO2'] == 2748416 and c['TAM_OUT_ARC'] == SALIDA_ARCHIVE_TAMANO


def test_deshacer_cro_devuelve_la_de_hoy(raiz):
    dat = json.loads((raiz / PAQ / 'deshacer_datos.json').read_text(encoding='utf-8'))
    datos = bytearray((raiz / PAQ / 'ina_main2.cro').read_bytes())
    assert len(dat['cro2']['rangos']) == 9
    for r in dat['cro2']['rangos']:
        o = r['offset']
        assert bytes(datos[o:o + len(r['nuevo_hex']) // 2]) == bytes.fromhex(r['nuevo_hex'])
        datos[o:o + len(r['original_hex']) // 2] = bytes.fromhex(r['original_hex'])
    assert _sha(bytes(datos)) == HOY['cro2']


def test_deshacer_local_se_niega_con_un_hash_desconocido(raiz, tmp_path):
    DL = _cargar(raiz, 'deshacer_local')
    dat = json.loads((raiz / PAQ / 'deshacer_datos.json').read_text(encoding='utf-8'))
    cro = tmp_path / 'ina_main2.cro'
    cro.write_bytes((raiz / PAQ / 'ina_main2.cro').read_bytes() + b'x')
    with pytest.raises(SystemExit):
        DL.plan_cro(cro, dat['cro2'], 'ina_main2.cro')
    cro.write_bytes((raiz / PAQ / 'ina_main2.cro').read_bytes())
    hoy = DL.plan_cro(cro, dat['cro2'], 'ina_main2.cro')
    assert hoy is not None and _sha(hoy) == HOY['cro2']
    cro.write_bytes(hoy)
    assert DL.plan_cro(cro, dat['cro2'], 'ina_main2.cro') is None   # ya es la de HOY
