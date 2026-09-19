"""IE2 Fuego v22 · candidata probe_ie2_v22 = probe_ie2_v21 + v22 menus_objetivos + ayuda + graficos_faltantes.

archive.fa: el de v21 con estas capas (no se solapan):
  1. ie2/shared/capas/rotulos_objetivos/menus_objetivos: extra/font/FONT12.bcfnt y FONT8.bcfnt; eventos ie2/eve/*.ssd
     fusionados registro a registro sobre el eve de v21 y reempaquetados por PackNum (como v19).
     ie2/mch está vacío: mch queda como en v21.
  2. ie2/shared/capas/graficos/ayuda/extra: 74 capturas de ayuda, a_menu/system_b.arc y MASTutorial.SPF_
     japonés (revierte v21/tutorial).
  3. ie2/shared/capas/graficos/graficos_faltantes/extra: a_game/battle_start_b.arc.
CRO: ina_main1 de v21; ina_main2 de v22/menus_objetivos (con los tres parches de ancho de v15).
romfs/: el de v21 tal cual (salvo la CRO).
No instala nada.
Uso: python -X utf8 work/ie2/tormenta_de_fuego/capas/historial/candidata/v22_candidata/build.py
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[6]
sys.path.insert(0, str(ROOT / 'tools/src'))
from ie123kit.nucleo.construir import candidata as C  # noqa: E402
from ie123kit.nucleo.contenedores.fa import FaArchive  # noqa: E402
from ie123kit.nucleo.eventos import ssd as S  # noqa: E402

W = ROOT / 'work'
V21 = W / 'shared/candidatas/probe_ie2_v21'
BASE = V21 / 'archive.fa'
SALIDA_DIR = W / 'shared/candidatas/probe_ie2_v22'
SALIDA = SALIDA_DIR / 'archive.fa'
CAPAS_SH = W / 'ie2/shared/capas'
MENUS = CAPAS_SH / 'rotulos_objetivos/menus_objetivos'
EVE = MENUS / 'ie2/eve'
MCH = MENUS / 'ie2/mch'
CAPAS_FIJAS = [MENUS / 'extra', CAPAS_SH / 'graficos/ayuda/extra', CAPAS_SH / 'graficos/graficos_faltantes/extra']
CRO1 = V21 / 'romfs/cro/ina_main1.cro'
CRO2 = MENUS / 'romfs/cro/ina_main2.cro'
ANCHO = {0x66a24: 0xE3A01E1A, 0x4cabc: 0xE3A02E1A, 0x4d6a0: 0xE3A02D07}   # v15 ancho_dialogo
PK_EVE = ('inazuma2/data_iz/script/eve.pkh', 'inazuma2/data_iz/script/eve.pkb')
PK_MCH = ('inazuma2/data_iz/script/mch.pkh', 'inazuma2/data_iz/script/mch.pkb')
MAX_REG, MAX_PAG = 247, 131


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def _modulo(nombre, ruta):
    spec = importlib.util.spec_from_file_location(nombre, ruta)
    m = importlib.util.module_from_spec(spec)
    sys.modules[nombre] = m
    spec.loader.exec_module(m)
    return m


C19 = _modulo('comun19_v22', W / 'ie2/shared/capas/dialogo/saltos37/comun19.py')
M = C19.M


def fusionar(original: bytes, capa: bytes, eid: int):
    """Registro a registro: se toman de la capa solo los cuerpos que difieren del de v21."""
    end0, ins0, r0 = S.parse(original)
    end1, ins1, r1 = S.parse(capa)
    assert ins0 == ins1 and original[32:end0] == capa[32:end1], f'{eid}: tabla de instrucciones'
    assert len(r0) == len(r1), f'{eid}: número de registros'
    rep = {}
    for i, (a, b) in enumerate(zip(r0, r1)):
        assert (a.instruction, a.argument) == (b.instruction, b.argument), f'{eid}: identidad {i}'
        if a.body != b.body:
            rep[i] = b.body
    return S.replace(original, rep), sorted(rep)


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    d = CRO2.read_bytes()
    for a, w in ANCHO.items():
        assert int.from_bytes(d[a:a + 4], 'little') == w, hex(a)
    assert not (MCH.exists() and any(MCH.glob('*.ssd'))), 'mch no declarado'
    if SALIDA_DIR.exists():
        shutil.rmtree(SALIDA_DIR)
    declarados = set()
    for c in CAPAS_FIJAS:
        for p in c.rglob('*'):
            if p.is_file():
                rel = p.relative_to(c).as_posix()
                assert rel not in declarados, rel
                declarados.add(rel)
    base = M.Archivo(BASE)
    arc = FaArchive(str(BASE))
    tmp = Path(tempfile.mkdtemp(prefix='ie2_v22_'))
    fusion = {}
    try:
        prep = tmp / 'eve'
        prep.mkdir()
        for p in sorted(EVE.glob('*.ssd')):
            eid = int(p.stem)
            merged, idx = fusionar(base.evento('eve', eid), p.read_bytes(), eid)
            (prep / p.name).write_bytes(merged)
            fusion[eid] = idx
        pkh, pkb, rep_ev = C._reempaquetar(arc, C._ssd_preparados(prep), PK_EVE)
        extra = tmp / 'extra_eventos'
        for rel, b in zip(PK_EVE, (pkh, pkb)):
            assert rel not in declarados
            (extra / rel).parent.mkdir(parents=True, exist_ok=True)
            (extra / rel).write_bytes(b)
        del arc
        capas = [CAPAS_FIJAS[0], extra, *CAPAS_FIJAS[1:]]
        rep = C.construir(BASE, SALIDA, capas=capas, cro=[CRO1, CRO2])
        # eventos de salida contra v21 y la fusión
        out = M.Archivo(SALIDA)
        assert out.ids('eve') == base.ids('eve') and out.ids('mch') == base.ids('mch')
        malos, mayores, raros, dialogos = [], [], [], 0
        for pk in ('eve', 'mch'):
            for eid in out.ids(pk):
                a, b = base.evento(pk, eid), out.evento(pk, eid)
                if pk == 'eve' and eid in fusion:
                    if b != (prep / f'{eid}.ssd').read_bytes():
                        raros.append((pk, eid, 'distinto de la fusión'))
                elif a != b:
                    raros.append((pk, eid, 'cambiado sin estar en la capa'))
                end, ins, ra, dl = M.dialogos(a)
                endb, insb, rb = S.parse(b)
                if insb != ins or len(ra) != len(rb) or b[32:endb] != a[32:end]:
                    raros.append((pk, eid, 'instrucciones/registros'))
                for j, r in enumerate(rb):
                    if len(r.body) > MAX_REG:
                        mayores.append((pk, eid, j, len(r.body)))
                for j in dl:
                    dialogos += 1
                    for k, pg in enumerate(C19.paginas(rb[j].body)):
                        if len(pg) > MAX_PAG:
                            malos.append((pk, eid, j, k, len(pg)))
        assert not raros, raros[:20]
        assert not mayores, mayores[:20]
        assert not malos, malos[:20]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    # romfs
    romfs = SALIDA_DIR / 'romfs'
    copiados = 0
    for p in sorted((V21 / 'romfs').rglob('*')):
        rel = p.relative_to(V21 / 'romfs')
        if not p.is_file() or rel.parts[0] == 'cro':
            continue
        dst = romfs / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p, dst)
        copiados += 1
    cro = romfs / 'cro'
    assert sorted(x.name for x in cro.iterdir()) == ['ina_main1.cro', 'ina_main2.cro']
    assert sha(cro / 'ina_main1.cro') == sha(CRO1) and sha(cro / 'ina_main2.cro') == sha(CRO2)
    d = (cro / 'ina_main2.cro').read_bytes()
    assert all(int.from_bytes(d[a:a + 4], 'little') == w for a, w in ANCHO.items())
    sad = sum(1 for p in romfs.rglob('*') if p.is_file() and p.suffix.lower() == '.sad')
    assert sad == 547, sad
    a, b = FaArchive(str(BASE)), FaArchive(str(SALIDA))
    pa = {p: (o, s) for p, o, s in a.entries}
    pb = {p: (o, s) for p, o, s in b.entries}
    assert set(pa) == set(pb)
    cambiados = sorted(p for p in pa if pa[p][1] != pb[p][1]
                       or bytes(a.d[pa[p][0]:pa[p][0] + pa[p][1]]) != bytes(b.d[pb[p][0]:pb[p][0] + pb[p][1]]))
    no_decl = sorted(set(cambiados) - declarados - set(PK_EVE))
    assert not no_decl, no_decl
    assert not set(PK_MCH) & set(cambiados)
    rep['events_repack'] = rep_ev
    rep['eve_fusion_registros'] = {str(k): v for k, v in fusion.items()}
    rep['base_v21'] = str(BASE)
    rep['capas_v22'] = [str(c) for c in CAPAS_FIJAS] + [f'(temporal) eve fusionado de {EVE}']
    rep['archive_cambiados'] = cambiados
    rep['declarados_sin_cambio'] = sorted(declarados - set(cambiados))
    rep['dialogos_revisados'] = dialogos
    rep['romfs_v21_copiados'] = copiados
    rep['romfs_sad'] = sad
    rep['sha256'] = {'archive.fa': sha(SALIDA),
                     'romfs/cro/ina_main1.cro': sha(cro / 'ina_main1.cro'),
                     'romfs/cro/ina_main2.cro': sha(cro / 'ina_main2.cro')}
    SALIDA.with_suffix('.build.json').write_text(
        json.dumps(rep, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    print(json.dumps(dict(sha256=rep['sha256'], cambiados=len(cambiados),
                          declarados_sin_cambio=rep['declarados_sin_cambio'],
                          eventos=len(fusion), registros=sum(map(len, fusion.values())),
                          dialogos=dialogos, romfs=copiados, sad=sad), ensure_ascii=False, indent=1))


if __name__ == '__main__':
    sys.exit(main())
