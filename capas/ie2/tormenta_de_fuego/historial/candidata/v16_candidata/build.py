"""IE2 Fuego v16 · candidata probe_ie2_v16 = probe_ie2_v15 + v13 cro_ranura + v12 graficos + v13 titulos
+ v13 voz_titulo + Fuego v13 inicio.

- archive.fa: el de probe_ie2_v15 con capas de ficheros (la última gana), en este orden:
  1. ie2/shared/capas/menus_cro/cro_ranura/extra (menu_slot.arc; su CRO no cambia: se queda la ina_main2.cro de v15)
  2. ie2/shared/capas/historial/graficos/v12_graficos/extra (title_t, title_b, option_b, name_b, menu_slot; va DESPUÉS de v13
     porque su menu_slot.arc ya incluye la textura de fuente de v13)
  3. ie2/shared/capas/nombres/titulos/extra (rpgtitle.STR)
  4. PackNum inazuma2 eve reempaquetado (candidata._reempaquetar) sobre el de v15 (que ya trae
     22500101/22500102) con 22010100/200/300/500 de Fuego v13 inicio.
- Crecimiento de eventos: regla de Fuego v10 (protegidos no cambian; %NF / sistema fijo no crecen),
  salvo los 4 eventos de v13 inicio, eximidos EXPRESAMENTE (informe.json de esa capa, «crecimiento»).
- romfs/: copia del de v15 (CRO incluidas) + LayeredFS de v13 voz_titulo (sound.pb/.ph/.ph_ en
  romfs/inazuma2/data_iz/sound/).
probe_ie2_v15 no se toca. No instala nada.
Uso: python -X utf8 work/ie2/tormenta_de_fuego/capas/historial/candidata/v16_candidata/build.py
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[6]
sys.path.insert(0, str(ROOT / 'tools/src'))
from ie123kit.nucleo.compresion.lz10 import decompress  # noqa: E402
from ie123kit.nucleo.construir import candidata as C  # noqa: E402
from ie123kit.nucleo.contenedores.fa import FaArchive  # noqa: E402
from ie123kit.nucleo.eventos.packnum import parse_index  # noqa: E402

W = ROOT / 'work'
V15 = W / 'shared/candidatas/probe_ie2_v15'
BASE = V15 / 'archive.fa'
BASE_JP = W / 'shared/base_3ds/romfs/archive.fa'
SALIDA_DIR = W / 'shared/candidatas/probe_ie2_v16'
SALIDA = SALIDA_DIR / 'archive.fa'
CAPAS = [W / 'ie2/shared/capas/menus_cro/cro_ranura/extra',
         W / 'ie2/shared/capas/historial/graficos/v12_graficos/extra',
         W / 'ie2/shared/capas/nombres/titulos/extra']
EVENTOS = W / 'ie2/tormenta_de_fuego/capas/dialogo/inicio/events'
VOZ = W / 'ie2/shared/capas/media/voz_titulo/romfs_mod'
PK_EVE = ('inazuma2/data_iz/script/eve.pkh', 'inazuma2/data_iz/script/eve.pkb')
PROT = {22010100, 22010200, 22010300, 22010500}
EXENTOS = {22010100, 22010200, 22010300, 22010500}   # Fuego v13 inicio: crecen a propósito
SISTEMA = 90000000
NF = re.compile(rb'%\d+F')
CRO2_SHA = '9f8e1d7c61999b735e0e5306a13ae0f2c43e9948994a901241d86487522171d1'


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def lector(arc):
    por = {p: (o, s) for p, o, s in arc.entries}
    o, s = por[PK_EVE[0]]
    idx = {e: (a, b) for e, a, b in parse_index(bytes(arc.d[o:o + s]))}
    o, s = por[PK_EVE[1]]
    pkb = arc.d[o:o + s]

    def get(eid):
        a, b = idx[eid]
        c = bytes(pkb[a:a + b])
        return decompress(c) if c[:1] == b'\x10' else c
    return get


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    assert SALIDA_DIR != V15
    assert sha(V15 / 'romfs/cro/ina_main2.cro') == CRO2_SHA
    if SALIDA_DIR.exists():
        shutil.rmtree(SALIDA_DIR)
    arc = FaArchive(str(BASE))
    # regla de crecimiento de Fuego v10 con la exención explícita
    ant, jp = lector(arc), lector(FaArchive(str(BASE_JP)))
    crec = {}
    for p in sorted(EVENTOS.glob('*.ssd')):
        eid, data = int(p.stem), p.read_bytes()
        a = ant(eid)
        assert eid in EXENTOS, eid
        exento = eid in EXENTOS
        if not exento:
            assert eid not in PROT or data == a, eid
            if NF.search(a) or (eid >= SISTEMA and len(a) == len(jp(eid))):
                assert len(data) <= len(a), eid
        crec[eid] = dict(bytes_v15=len(a), bytes=len(data), protegido=eid in PROT,
                         nf_en_v15=bool(NF.search(a)), exento=exento)
    tmp = Path(tempfile.mkdtemp(prefix='ie2_v16_'))
    try:
        extra = tmp / 'extra_eventos'
        pkh, pkb, rep_ev = C._reempaquetar(arc, C._ssd_preparados(EVENTOS), PK_EVE)
        for rel, b in zip(PK_EVE, (pkh, pkb)):
            (extra / rel).parent.mkdir(parents=True, exist_ok=True)
            (extra / rel).write_bytes(b)
        del arc
        rep = C.construir(BASE, SALIDA, capas=CAPAS + [extra],
                          cro=[V15 / 'romfs/cro/ina_main1.cro', V15 / 'romfs/cro/ina_main2.cro'])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    romfs = SALIDA_DIR / 'romfs'
    copiados = 0
    for p in sorted((V15 / 'romfs').rglob('*')):
        rel = p.relative_to(V15 / 'romfs')
        if p.is_file() and rel.parts[0] != 'cro':
            dst = romfs / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(p, dst)
            copiados += 1
    voz = []
    for p in sorted(VOZ.rglob('*')):
        if p.is_file():
            rel = p.relative_to(VOZ)
            assert rel.parts[:3] == ('inazuma2', 'data_iz', 'sound'), rel
            dst = romfs / rel
            assert not dst.exists(), rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(p, dst)
            voz.append(rel.as_posix())
    cro_out = romfs / 'cro'
    assert sorted(x.name for x in cro_out.iterdir()) == ['ina_main1.cro', 'ina_main2.cro']
    assert sha(cro_out / 'ina_main2.cro') == CRO2_SHA
    assert sha(cro_out / 'ina_main1.cro') == sha(V15 / 'romfs/cro/ina_main1.cro')
    rep['events_repack'] = {'ie2_eve': rep_ev}
    rep['crecimiento_eventos'] = {str(k): v for k, v in crec.items()}
    rep['base_v15'] = str(BASE)
    rep['capas_v16'] = [str(c) for c in CAPAS] + ['(temporal) eve IE2 reempaquetado con Fuego v13 inicio']
    rep['romfs_v15_copiados'] = copiados
    rep['romfs_voz_titulo'] = voz
    rep['sha256'] = {'archive.fa': rep['archive_sha256'],
                     'romfs/cro/ina_main1.cro': sha(cro_out / 'ina_main1.cro'),
                     'romfs/cro/ina_main2.cro': sha(cro_out / 'ina_main2.cro'),
                     **{'romfs/' + v: sha(romfs / v) for v in voz}}
    SALIDA.with_suffix('.build.json').write_text(json.dumps(rep, ensure_ascii=False, indent=2, default=str),
                                                 encoding='utf-8')
    print(json.dumps(dict(sha256=rep['sha256'], reemplazos=rep['archive_replacements'], romfs=copiados,
                          anulados=rep['overridden_by_later_overlay'], eventos=rep_ev, crecimiento=crec),
                     ensure_ascii=False, indent=1, default=str)[:4000])


if __name__ == '__main__':
    sys.exit(main())
