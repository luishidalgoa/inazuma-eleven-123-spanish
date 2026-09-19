"""IE2 Fuego v10: candidata combinada probe_ie2_v10 = probe_ie2_v05 + IE1 v91/v92/v93 + IE2 v05..v09.

Capas (la última gana; mismo envoltorio que v05, nucleo.construir.candidata, sin editar tools/):
 1. Eventos IE1 (inazuma1 eve): v91 -> v92 (fichero a fichero; v92 ya parte de v91) y encima los
    registros de rótulo de v08 (cambios_registros.json) REGISTRO A REGISTRO, no fichero entero.
    mch IE1: v92/events_mch.
 2. CRO IE1: ie1/capas/menus_cro/cofres (v90 + cofres).   3. CRO IE2: ie2/shared/capas/menus_cro/cofres (v04 + cofres).
 4. Gráficos IE2: v05/graficos_snapshot/extra, v06/graficos/extra.
 5. Eventos IE2 (inazuma2 eve): registros de v08 sobre el eve de v05.
 6/7. Media v07 (común + Fuego) y extra de v08 (FONT8/FONT12/FONT12T + unitbase.dat/.STR). La
    FONT12 de v07 media la sustituye la de v08 (que parte de ella): v08 va detrás y gana.
 LayeredFS (romfs/ de la candidata): SAD IE1 (legacy ie1_media_mod 70 -> v57 voces_eu 184) y
    SAD IE2 (v07 media común 472 + Fuego 5).
Los cuatro PackNum se reempaquetan con candidata._reempaquetar (packnum.rebuild), como v03, y
entran como capa de ficheros. Crecimiento: libre salvo eventos de sistema (>= 90000000), con %NF o
protegidos (sistema: solo si v05 lo conserva al tamaño japonés, regla de v92), que no pueden crecer respecto a v05 (se comprueba aquí y en validar.py).
Uso: python -X utf8 build.py
"""
from __future__ import annotations

import collections
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[6]
from ie123kit.nucleo.compresion.lz10 import decompress  # noqa: E402
from ie123kit.nucleo.construir import candidata as C  # noqa: E402
from ie123kit.nucleo.contenedores.fa import FaArchive  # noqa: E402
from ie123kit.nucleo.eventos import ssd as S  # noqa: E402
from ie123kit.nucleo.eventos.packnum import parse_index  # noqa: E402

W = ROOT / 'work'
BASE = W / 'shared/candidatas/probe_ie2_v05/archive.fa'
BASE_JP = W / 'shared/base_3ds/romfs/archive.fa'
SALIDA_DIR = W / 'shared/candidatas/probe_ie2_v10'
SALIDA = SALIDA_DIR / 'archive.fa'

V91 = W / 'ie1/capas/historial/dialogo/v91_nombres_oficiales'
V92 = W / 'ie1/capas/historial/dialogo/v92_redump_eu3ds'
V08 = W / 'ie2/shared/capas/nombres/nombres_compactos'
CRO1 = W / 'ie1/capas/menus_cro/cofres/romfs/cro/ina_main1.cro'
CRO2 = W / 'ie2/shared/capas/menus_cro/cofres/romfs/cro/ina_main2.cro'
MEDIA = W / 'ie2/shared/capas/media/media'
MEDIA_F = W / 'ie2/tormenta_de_fuego/capas/media/media'
CAPAS = [W / 'ie2/shared/capas/historial/graficos/v05_graficos_snapshot/extra',
         W / 'ie2/shared/capas/historial/graficos/v06_graficos/extra',
         MEDIA / 'extra', MEDIA_F / 'extra',
         V08 / 'extra']
ROMFS = [W / 'ie1/legacy/volumen_1/ie1_media_mod/romfs',   # 70 SAD IE1 (14 siguen siendo estos)
         W / 'ie1/capas/media/voces_eu/romfs',                # 56 SAD EU + 128 SED/SWD
         MEDIA / 'romfs_mod', MEDIA_F / 'romfs_mod']        # 472 + 5 SAD IE2

PK = {('ie1', 'eve'): ('inazuma1/data_iz/script/eve.pkh', 'inazuma1/data_iz/script/eve.pkb'),
      ('ie1', 'mch'): ('inazuma1/data_iz/script/mch.pkh', 'inazuma1/data_iz/script/mch.pkb'),
      ('ie2', 'eve'): ('inazuma2/data_iz/script/eve.pkh', 'inazuma2/data_iz/script/eve.pkb'),
      ('ie2', 'mch'): ('inazuma2/data_iz/script/mch.pkh', 'inazuma2/data_iz/script/mch.pkb')}
PROT = {'ie1': set(range(92010100, 92010510)) | {81000040},
        'ie2': {22010100, 22010200, 22010300, 22010500}}
SISTEMA = 90000000
NF = re.compile(rb'%\d+F')


def eventos_base(arc, rutas):
    por = {p: (o, s) for p, o, s in arc.entries}
    o, s = por[rutas[0]]
    pkh = bytes(arc.d[o:o + s])
    o, s = por[rutas[1]]
    pkb = arc.d[o:o + s]
    idx = {e: (a, b) for e, a, b in parse_index(pkh)}

    def get(eid):
        a, b = idx[eid]
        c = bytes(pkb[a:a + b])
        return decompress(c) if c[:1] == b'\x10' else c
    return get


def fusionar(arc):
    """{(juego, pk): {eid: bytes}} e informe de la fusión."""
    base = {k: eventos_base(arc, r) for k, r in PK.items()}
    out = collections.defaultdict(dict)
    origen = {}
    # 1. IE1: v91 y v92 fichero a fichero
    for capa, sub, pk in ((V91, 'events', 'eve'), (V92, 'events', 'eve'), (V92, 'events_mch', 'mch')):
        d = capa / sub
        if d.is_dir():
            for p in sorted(d.glob('*.ssd')):
                out[('ie1', pk)][int(p.stem)] = p.read_bytes()
                origen[('ie1', pk, int(p.stem))] = capa.parent.name
    # v08: registro a registro
    cambios = json.loads((V08 / 'cambios_registros.json').read_text(encoding='utf-8'))['registros']
    por_ev = collections.defaultdict(dict)
    for r in cambios:
        assert r['paquete'] == PK[(r['juego'], 'eve')][1], r['paquete']
        por_ev[(r['juego'], r['evento'])][r['indice']] = r
    inf = dict(v08_eventos=len(por_ev), v08_registros=len(cambios), solape_v92=[], solape_v91=[],
               ya_aplicados=0, conflictos=[])
    for (juego, eid), regs in sorted(por_ev.items()):
        k = (juego, 'eve')
        partida = out[k].get(eid)
        if partida is None:
            partida = base[k](eid)
        else:
            inf['solape_' + origen[(juego, 'eve', eid)][:3]].append(eid)
        _, ops, recs = S.parse(partida)
        repl = {}
        for i, r in regs.items():
            assert (ops[recs[i].instruction], recs[i].argument) == (int(r['opcode'], 16), r['arg']), (juego, eid, i)
            actual = recs[i].body.hex()
            if actual == r['cuerpo']:
                inf['ya_aplicados'] += 1
            elif actual == r['cuerpo_antes']:
                repl[i] = bytes.fromhex(r['cuerpo'])
            else:
                inf['conflictos'].append(dict(juego=juego, evento=eid, indice=i))
        if inf['conflictos']:
            continue
        nuevo = S.replace(partida, repl)
        # el fichero de v08 (hecho sobre v05) debe coincidir con la fusión si no había otra capa
        f08 = V08 / juego / 'events' / f'{eid}.ssd'
        if (juego, 'eve', eid) not in origen:
            assert nuevo == f08.read_bytes(), (juego, eid)
        out[k][eid] = nuevo
        origen[(juego, 'eve', eid)] = (origen.get((juego, 'eve', eid), 'v05') + '+v08')
    if inf['conflictos']:
        raise SystemExit(f"conflictos v08: {inf['conflictos'][:10]}")
    # crecimiento: sistema / %NF / protegidos no crecen; protegidos no cambian
    # (regla de v92: un evento de sistema solo es fijo si v05 lo conserva al tamaño japonés)
    jp_arc = FaArchive(str(BASE_JP))
    jp = {k: eventos_base(jp_arc, r) for k, r in PK.items()}
    inf['crecen'] = collections.Counter()
    for (juego, pk), evs in out.items():
        for eid, data in evs.items():
            ant = base[(juego, pk)](eid)
            assert eid not in PROT[juego] or data == ant, (juego, pk, eid)
            fijo = NF.search(ant) or (eid >= SISTEMA and len(ant) == len(jp[(juego, pk)](eid)))
            if fijo:
                assert len(data) <= len(ant), (juego, pk, eid, len(data), len(ant))
            if len(data) > len(ant):
                inf['crecen'][f'{juego}/{pk}' + ('/sistema' if eid >= SISTEMA else '')] += 1
    inf['origen'] = collections.Counter(f'{k[0]}/{k[1]}:{v}' for k, v in origen.items())
    return out, inf


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    if SALIDA_DIR.exists():
        shutil.rmtree(SALIDA_DIR)
    arc = FaArchive(str(BASE))
    evs, inf = fusionar(arc)
    tmp = Path(tempfile.mkdtemp(prefix='ie2_v10_'))
    try:
        extra_ev = tmp / 'extra_eventos'
        rep_ev = {}
        for (juego, pk), datos in sorted(evs.items()):
            d = tmp / f'{juego}_{pk}'
            d.mkdir()
            for eid, b in datos.items():
                (d / f'{eid}.ssd').write_bytes(b)
            pkh, pkb, rep = C._reempaquetar(arc, C._ssd_preparados(d), PK[(juego, pk)])
            for rel, b in zip(PK[(juego, pk)], (pkh, pkb)):
                (extra_ev / rel).parent.mkdir(parents=True, exist_ok=True)
                (extra_ev / rel).write_bytes(b)
            rep_ev[f'{juego}_{pk}'] = rep
        del arc
        rep = C.construir(BASE, SALIDA, capas=CAPAS + [extra_ev], cro=[CRO1, CRO2])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # LayeredFS: SAD y bancos de sonido
    romfs_out = SALIDA_DIR / 'romfs'
    sustituidos, copiados = [], collections.Counter()
    for r in ROMFS:
        for p in sorted(r.rglob('*')):
            if p.is_file():
                rel = p.relative_to(r)
                assert rel.parts[0] in ('inazuma1', 'inazuma2') and rel.parts[2] == 'sound', rel
                dst = romfs_out / rel
                if dst.exists():
                    sustituidos.append(dict(rel=rel.as_posix(), capa=str(r)))
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(p, dst)
                copiados[str(r)] += 1

    rep['events_repack'] = rep_ev
    rep['fusion_eventos'] = inf
    rep['capas_v10'] = [str(c) for c in CAPAS] + ['(temporal) eventos reempaquetados con packnum']
    rep['romfs_layeredfs'] = dict(copiados=dict(copiados), sustituidos=sustituidos,
                                  total={j: len(list((romfs_out / j).rglob('*.SAD'))) for j in ('inazuma1', 'inazuma2')})
    rep['base_ie2'] = 'probe_ie2_v05'
    SALIDA.with_suffix('.build.json').write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding='utf-8')
    print('archive', rep['archive_sha256'], 'reemplazos', rep['archive_replacements'])
    print('eventos', {k: len(v) for k, v in rep_ev.items()}, 'fusión', {k: (v if not isinstance(v, list) else len(v))
                                                                     for k, v in inf.items()})
    print('romfs', rep['romfs_layeredfs']['total'], 'anulados', len(rep['overridden_by_later_overlay']))


if __name__ == '__main__':
    sys.exit(main())
