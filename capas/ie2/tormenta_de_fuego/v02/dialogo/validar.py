"""IE2 Fuego v02 · paso 3: validación offline (como v84/validar.py).

Sin --candidata: valida los .ssd preparados (events/, events_mch/) contra el japonés.
Con --candidata --base v89|v88: además compara probe_ie2_v02/archive.fa con la base (solo cambian los
ficheros declarados, IE1 intacto, CRO idénticas) y lee los eventos del archive construido.

Por evento: bytecode y tabla de instrucciones idénticos, mismo número e identidad de registros, solo
cambia 0x301d argumento 1 (nunca 0x4037/0x402f ni lecturas), protegidos intactos (22010100 = sonda v01).
Por registro cambiado: <= 247 B, sin %NF, %s/%d como el japonés, el motor no reajusta, <= 22 caracteres
y <= 3 líneas por caja, sin líneas vacías, glifo en FONT12.bcfnt, mismas palabras que el ajuste de apply.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter

import comun_ie2 as M

PERMITIDOS = {M.PK_EVE[0], M.PK_EVE[1], M.PK_MCH[0], M.PK_MCH[1],
              'inazuma2/data_iz/font/FONT12.NFTR', 'inazuma2/data_iz/font/FONT8.NFTR',
              'inazuma2/data_iz/logic/unitbase.dat'}


def sha(p):
    with open(p, 'rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser()
    ap.add_argument('--candidata', action='store_true')
    ap.add_argument('--base', choices=['v89', 'v88'])
    args = ap.parse_args()
    jp = M.Archivo(M.JP)
    aplicado = json.loads((M.HERE / 'aplicado.json').read_text(encoding='utf-8'))
    fallos, ejemplos = Counter(), {}
    pares = json.loads((M.HERE / 'pares.json').read_text(encoding='utf-8'))
    fuentes = {(k.split(':')[0], int(k.split(':')[1]), f['indice']): f['es'] for k, fs in pares.items() for f in fs}

    def fallo(k, x):
        fallos[k] += 1
        ejemplos.setdefault(k, str(x)[:300])

    res = dict(modo='candidata' if args.candidata else 'preparados', eventos_cambiados=Counter(),
               registros_cambiados=Counter(), crecen=0, cajas=0, max_bytes=0)
    if args.candidata:
        base_dir = M.CAND / f'probe_ie1_{args.base}'
        cand_dir = M.CAND / 'probe_ie2_v02'
        a, b = M.Archivo(base_dir / 'archive.fa'), M.Archivo(cand_dir / 'archive.fa')
        distintos = sorted(p for p in set(a.por) | set(b.por)
                           if p not in a.por or p not in b.por or a.get(p) != b.get(p))
        res['archivos_distintos'] = distintos
        if not set(distintos) <= PERMITIDOS:
            fallo('archivo_no_declarado', sorted(set(distintos) - PERMITIDOS))
        for rel in ('inazuma2/data_iz/font/FONT12.NFTR', 'inazuma2/data_iz/font/FONT8.NFTR'):
            if b.get(rel) != (M.FUENTES_V01 / rel).read_bytes():
                fallo('fuente_v01', rel)
        if b.get('inazuma2/data_iz/logic/unitbase.dat') != (M.NOMBRE_V01 / 'inazuma2/data_iz/logic/unitbase.dat').read_bytes():
            fallo('nombre_v01', 'unitbase')
        cros_a = {p.name: p.read_bytes() for p in (base_dir / 'romfs/cro').glob('*.cro')}
        cros_b = {p.name: p.read_bytes() for p in (cand_dir / 'romfs/cro').glob('*.cro')}
        res['cro_igual'] = cros_a == cros_b
        if not res['cro_igual']:
            fallo('cro', sorted(cros_b))
        leer = lambda pk, eid: b.evento(pk, eid)  # noqa: E731
        ids = {pk: b.ids(pk) for pk in ('eve', 'mch')}
        for pk in ids:
            if ids[pk] != jp.ids(pk):
                fallo('indice', pk)
    else:
        def leer(pk, eid):
            p = M.HERE / ('events' if pk == 'eve' else 'events_mch') / f'{eid}.ssd'
            return p.read_bytes() if p.exists() else jp.evento(pk, eid)
        ids = {pk: jp.ids(pk) for pk in ('eve', 'mch')}
    v01 = (M.V01_EVENTOS / '22010100.ssd').read_bytes()
    for pk, lista in ids.items():
        for eid in lista:
            da, db = jp.evento(pk, eid), leer(pk, eid)
            if pk == 'eve' and eid in M.PROTEGIDOS:
                if db != (v01 if eid == 22010100 else da):
                    fallo('protegido_tocado', eid)
                continue
            if da == db:
                continue
            res['eventos_cambiados'][pk] += 1
            ea, oa, ra = M.S.parse(da)
            eb, ob, rb = M.S.parse(db)
            if da[32:ea] != db[32:eb] or oa != ob or len(ra) != len(rb):
                fallo('bytecode', (pk, eid))
                continue
            res['crecen'] += len(db) > len(da)
            info = aplicado['eventos'].get(f'{pk}:{eid}', {})
            esperado = {r['indice']: r['texto'] for r in info.get('registros', [])}
            for i, (x, y) in enumerate(zip(ra, rb)):
                if x.raw == y.raw:
                    continue
                res['registros_cambiados'][pk] += 1
                op = oa.get(x.instruction)
                if (x.instruction, x.argument) != (y.instruction, y.argument) or op != M.OP_DIALOGO or x.argument != 1:
                    fallo('no_dialogo' if op not in M.OP_EXCLUIDOS else 'rotulo_objetivo', (pk, eid, i, hex(op or 0)))
                    continue
                t = y.body.decode('cp932')
                if len(y.body) > M.MAX_BYTES:
                    fallo('excede_247', (pk, eid, i))
                if M.FURI.search(t):
                    fallo('furigana', (pk, eid, i))
                if M.pct(t) != M.pct(x.body.decode('cp932')):
                    fallo('pct', (pk, eid, i))
                if M.sin_glifo(y.body):
                    fallo('sin_glifo', (pk, eid, i, M.sin_glifo(y.body)))
                if not M.respeta_motor(y.body):
                    fallo('motor_reajusta', (pk, eid, i))
                if i not in esperado or y.body != M.transportar(esperado[i]):
                    fallo('no_es_lo_aplicado', (pk, eid, i))
                pags = M.paginas(y.body)
                res['cajas'] += len(pags)
                res['max_bytes'] = max(res['max_bytes'], len(y.body))
                for pg in pags:
                    if not 0 < len(pg) <= M.LINEAS:
                        fallo('mas_de_3_lineas', (pk, eid, i))
                    for ln in pg:
                        if len(ln) > M.MAX_CAR:
                            fallo('mas_de_22', (pk, eid, i, ln))
                        if not ln.strip():
                            fallo('linea_vacia', (pk, eid, i))
                # sin palabras cortadas: el texto escrito, con los saltos como espacios, es la fuente NDS
                fuente = fuentes.get((pk, eid, i))
                plano = ' '.join(re.sub(r'\\[nf]', ' ', esperado.get(i, '')).split())
                fuente_plana = re.sub(r'\\[nf]', ' ', M.FURI.sub('', M.normalizar(fuente or '')))
                if fuente is None or plano != ' '.join(fuente_plana.split()):
                    fallo('palabras', (pk, eid, i))
    res['eventos_cambiados'] = dict(res['eventos_cambiados'])
    res['registros_cambiados'] = dict(res['registros_cambiados'])
    res['fallos'] = dict(fallos)
    res['ejemplos'] = ejemplos
    res['ok'] = not fallos
    if args.candidata:
        res['base'] = args.base
        res['sha256_base'] = sha(M.CAND / f'probe_ie1_{args.base}/archive.fa')
        res['sha256_v02'] = sha(M.CAND / 'probe_ie2_v02/archive.fa')
    print(json.dumps(res, indent=1, ensure_ascii=False))
    nombre = 'validacion_candidata.json' if args.candidata else 'validacion.json'
    (M.HERE / nombre).write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding='utf-8')


if __name__ == '__main__':
    main()
