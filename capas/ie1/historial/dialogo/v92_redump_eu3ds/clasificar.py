"""v92 · clasifica cada registro de diálogo (0x301d arg 1) del texto ACTUAL de IE1 frente al oficial.

Base: probe_ie2_v05 (eve.pkb y mch.pkb de inazuma1). Para cada registro:
  japones      = registro (id, 1) del evento japonés original
  oficial_eu3ds = registro europeo (id', 1), id' = id emparejado alineando los opcodes (directo si
                 coinciden) y validado con anclas ASCII
  oficial_nds  = frase NDS (evet/mcht) emparejada por el patrón de saltos de IDs (alineado_ids),
                 solo si la primera entrada japonesa del id es la frase (como audit_dialogo_ids)
  clase a: el texto del juego coincide con EU o NDS (sin saltos, espacios, %NF, apóstrofos ni comillas)
  clase b: hay oficial y difiere;  clase c: no hay oficial.
Salida: clasificacion.pkl (para apply.py), resumen en clasificacion.json y el CSV del escritorio.
"""
from __future__ import annotations

import collections
import csv
import json
import os
import pickle
import re
import struct
import sys
from pathlib import Path

import comun92 as C

K = C.K
HERE = C.HERE
ESCRITORIO = Path(os.path.expanduser('~')) / 'Desktop/IE1_origen_textos.csv'
NDS_DIR = C.ROOT / 'work/ie1/fuentes/nds_es/data_iz/script/sp'
NDS_FICH = {'eve': 'evet', 'mch': 'mcht'}
PCT = re.compile(r'%[0-9]*[A-EG-Za-z]')      # %s, %d... (no %NF)


def cargar_nds(tipo):
    pkb = (NDS_DIR / f'{NDS_FICH[tipo]}.pkb').read_bytes()
    idx = C.parse_index((NDS_DIR / f'{NDS_FICH[tipo]}.pkh').read_bytes())
    out = {}
    for eid, o, s in idx:
        ch = pkb[o:o + s]
        out[eid] = C.decompress(ch) if ch[:1] == b'\x10' else ch
    return out


def entradas_nds(buf):
    out, p = {}, 4
    while p + 8 <= len(buf):
        sid, typ, ln = struct.unpack_from('<HHI', buf, p)
        if ln < 8 or p + ln > len(buf):
            break
        out.setdefault((sid, typ), buf[p + 8:p + ln].split(b'\0')[0])
        p += ln
    return out


def es_ascii(b):
    return bool(b) and all(32 <= c < 127 for c in b)


def texto_juego(body):
    try:
        return K.a_espanol(body)
    except UnicodeDecodeError:
        return body.decode('cp932', 'replace')


def japones(body):
    return body.decode('cp932', 'replace')


def clasificar(tipo, stats, anclas):
    base = C.Guion(C.BASE, tipo)
    jp = C.Guion(C.ORIGINAL, tipo)
    eu = C.Guion(C.EU, tipo, 'es/')
    nds = cargar_nds(tipo)
    filas = []
    for eid in sorted(base.eventos()):
        d = base.evento(eid)
        _, ops, recs = K.S.parse(d)
        jd = jp.evento(eid)
        _, jops, jrecs = K.S.parse(jd)
        jtxt = {}
        for r in jrecs:
            jtxt.setdefault((r.instruction, r.argument), r.body)
        # --- EU
        eumap, directo, eutxt, ev_ok = {}, None, {}, False
        if eid in eu.eventos():
            ed = eu.evento(eid)
            eumap, directo = C.mapa_ids(C.instrucciones(jd), C.instrucciones(ed))
            for sid, arg, idx, b in C.textos_v2(ed):
                eutxt.setdefault((sid, arg), b)
            ok = mal = 0
            for (sid, arg), jb in jtxt.items():
                if sid in eumap and es_ascii(jb):
                    eb = eutxt.get((eumap[sid], arg))
                    if eb == jb:
                        ok += 1
                    elif eb is not None and es_ascii(eb):
                        mal += 1
            anclas[tipo]['ok'] += ok
            anclas[tipo]['mal'] += mal
            anclas[tipo]['directo' if directo else 'alineado'] += 1
            ev_ok = mal == 0
            if not ev_ok:
                # anclas distintas (voz J10->J12, variable de depuración): se acepta el evento solo si
                # el texto EU casa con el NDS en la mayoría de frases (comprobación posterior)
                ev_ok = 'pendiente'
        # --- NDS
        nmap, nent, primeros = None, None, {}
        if eid in nds:
            a = C.tabla_3ds(jd)
            if a is not None:
                nmap, _, nmal = C.emparejar(a, C.tabla_nds(nds[eid]))
                nent = entradas_nds(nds[eid])
                for r in jrecs:
                    primeros.setdefault(r.instruction, r.argument)
        vistos = set()
        for i, r in enumerate(recs):
            if ops.get(r.instruction) != C.OP_DIALOGO or r.argument != 1:
                continue
            if (r.instruction, 1) in vistos:
                continue
            vistos.add((r.instruction, 1))
            jb = jtxt.get((r.instruction, 1))
            if jb is None:
                stats['sin_japones'] += 1
                continue
            of_eu = None
            if ev_ok and r.instruction in eumap:
                eb = eutxt.get((eumap[r.instruction], 1))
                if eb is not None:
                    of_eu = C.decodificar_eu(eb)
            of_nds = None
            if nmap and r.instruction in nmap and primeros.get(r.instruction) == 1:
                nb = nent.get((nmap[r.instruction], 1))
                if nb is not None:
                    of_nds = C.decodificar_eu(nb).replace('\n', r'\n')
            # descartar "oficiales" que no son texto español (japonés sin traducir, vacíos, ASCII técnico)
            jt = japones(jb)
            for nombre in ('eu', 'nds'):
                v = of_eu if nombre == 'eu' else of_nds
                if v is None:
                    continue
                malo = (not v.strip() or v == jt or re.search(r'[぀-ヿ一-鿿]', v)
                        or es_ascii(jb) or '<' in v)
                if malo:
                    stats[f'{nombre}_descartado'] += 1
                    if nombre == 'eu':
                        of_eu = None
                    else:
                        of_nds = None
            juego = texto_juego(r.body)
            nj = C.norm(juego)
            if of_eu is None and of_nds is None:
                clase = 'c'
            elif (of_eu is not None and C.norm(of_eu) == nj) or (of_nds is not None and C.norm(of_nds) == nj):
                clase = 'a'
            else:
                clase = 'b'
            pct_ok = sorted(PCT.findall(jt)) == sorted(PCT.findall(of_eu or '')) if of_eu else None
            filas.append(dict(tipo=tipo, evento=eid, indice=i, id=r.instruction, japones=jt, texto_juego=juego,
                              oficial_eu3ds=of_eu, oficial_nds=of_nds, clase=clase, pct_eu_ok=pct_ok,
                              protegido=eid in C.PROTEGIDOS or eid in C.DONT_TOUCH, eu_pendiente=ev_ok == 'pendiente'))
        if ev_ok == 'pendiente':
            mias = [f for f in filas if f['evento'] == eid and f['tipo'] == tipo]
            dos = [f for f in mias if f['oficial_eu3ds'] and f['oficial_nds']]
            iguales = sum(C.norm(f['oficial_eu3ds']) == C.norm(f['oficial_nds']) for f in dos)
            aceptado = len(dos) >= 5 and iguales >= 0.8 * len(dos)
            anclas[tipo]['eventos_con_ancla_distinta'].append(dict(evento=eid, frases_eu_nds=len(dos),
                                                                    iguales=iguales, aceptado=aceptado))
            if not aceptado:
                for f in mias:
                    f['oficial_eu3ds'] = None
                    nj = C.norm(f['texto_juego'])
                    f['clase'] = ('c' if f['oficial_nds'] is None else
                                  'a' if C.norm(f['oficial_nds']) == nj else 'b')
    for f in filas:
        stats[f"{tipo}_{f['clase']}"] += 1
    return filas


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    stats = collections.Counter()
    anclas = {'eve': None, 'mch': None}
    for t in anclas:
        anclas[t] = {'ok': 0, 'mal': 0, 'directo': 0, 'alineado': 0, 'eventos_con_ancla_distinta': []}
    anclas = {t: collections.defaultdict(int, v) for t, v in anclas.items()}
    filas = []
    for tipo in ('eve', 'mch'):
        filas += clasificar(tipo, stats, anclas)
    tot = collections.Counter(f['clase'] for f in filas)
    fuente_b = collections.Counter('eu' if f['oficial_eu3ds'] else 'nds' for f in filas if f['clase'] == 'b')
    res = dict(total=dict(tot), por_tipo=dict(stats), clase_b_por_fuente=dict(fuente_b),
               anclas={t: dict(v) for t, v in anclas.items()},
               protegidos=dict(collections.Counter(f['clase'] for f in filas if f['protegido'])))
    print(json.dumps(res, ensure_ascii=False, indent=1))
    (HERE / 'clasificacion.pkl').write_bytes(pickle.dumps(filas))
    (HERE / 'clasificacion.json').write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding='utf-8')
    with open(ESCRITORIO, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f, delimiter=';')
        w.writerow(['evento', 'indice', 'japones', 'texto_juego', 'oficial_eu3ds', 'oficial_nds', 'clase'])
        for x in filas:
            ev = x['evento'] if x['tipo'] == 'eve' else f"mch:{x['evento']}"
            w.writerow([ev, x['indice'], x['japones'], x['texto_juego'], x['oficial_eu3ds'] or '',
                        x['oficial_nds'] or '', x['clase']])
    print('CSV:', ESCRITORIO)


if __name__ == '__main__':
    main()
