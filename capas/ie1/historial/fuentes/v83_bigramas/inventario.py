"""v83 · bigramas (SOLO INVESTIGACIÓN): inventario de pares de letras en los textos de paso fijo.

Campos (candidata probe_ie1_v81, solo lectura):
  rotulos       eve.pkb 0x4037 arg 3 (rótulo del minimapa), sin los espacios de centrado
  rotulos_v76   columna «Propuesta» + «Sin cambios» de v76/rotulos_largos/propuesta.md
  objetivos     eve.pkb 0x402f arg 2 (cabecera) y arg 3 (texto del objetivo)
  nombres_ficha unitbase.dat +0 (16 B)      nombres_lista unitbase.dat +16 (16 B)
  nombre_largo  unitbase.dat +32 (32 B)     descripciones unitbase.STR (u16 +94 x 32), por línea
Solo textos ya en latín (sin kana/kanji).

Partición A: pares desde el principio del texto (el último carácter impar va solo).
Partición B («relleno»): pares dentro de cada palabra; la letra impar final se empareja con el
espacio siguiente («a ») y el espacio sobrante va solo. B no cruza palabras.
Uso: python -X utf8 work/ie1/capas/historial/fuentes/v83_bigramas/inventario.py -> inventario.json
"""
from __future__ import annotations

import collections
import importlib.util
import json
import re
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[5]
_spec = importlib.util.spec_from_file_location('v76', ROOT / 'work/ie1/capas/historial/rotulos_objetivos/v76_rotulos_largos/apply.py')
V76 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(V76)
C, S, decompress, parse_index, a_texto, abrir = V76.C, V76.S, V76.decompress, V76.parse_index, V76.a_texto, V76.abrir
BASE = ROOT / 'work/shared/candidatas/probe_ie1_v81/archive.fa'
JP = re.compile('[\u3040-\u30ff\u4e00-\u9fff]')
TOKEN = re.compile(r'(\\[nf]|%[0-9]*[A-Za-z])')


def limpio(t):
    t = TOKEN.sub('', t).replace('\n', ' ').strip()
    return t if t and not JP.search(t) else None


def particion_a(t):
    return [t[i:i + 2] for i in range(0, len(t), 2)]


def particion_b(t):
    out, i = [], 0
    while i < len(t):
        if t[i] == ' ':
            out.append(' ')
            i += 1
            continue
        j = i
        while j < len(t) and t[j] != ' ':
            j += 1
        w = t[i:j]
        out += [w[k:k + 2] for k in range(0, len(w) - len(w) % 2, 2)]
        if len(w) % 2:
            if j < len(t):
                out.append(w[-1] + ' ')
                j += 1
            else:
                out.append(w[-1])
        i = j
    return out


def textos():
    get = abrir(BASE)
    campos = collections.defaultdict(list)
    pkb = get(C.PKB)
    for eid, o, s in parse_index(get(C.PKH)):
        try:
            data = decompress(pkb[o:o + s])
            _, ops, recs = S.parse(data)
        except (ValueError, KeyError):
            continue
        for r in recs:
            op = ops.get(r.instruction)
            clave = {(0x4037, 3): 'rotulos', (0x402f, 2): 'objetivos', (0x402f, 3): 'objetivos'}.get((op, r.argument))
            if not clave:
                continue
            try:
                t = limpio(a_texto(r.body))
            except UnicodeDecodeError:
                continue
            if t:
                campos[clave].append(t)
    ub = get('inazuma1/data_iz/logic/unitbase.dat')
    st = get('inazuma1/data_iz/logic/unitbase.STR')
    descs = set()
    for i in range(len(ub) // 96):
        r = ub[i * 96:(i + 1) * 96]
        for k, n, clave in ((0, 16, 'nombres_ficha'), (16, 16, 'nombres_lista'), (32, 32, 'nombre_largo')):
            try:
                t = limpio(a_texto(r[k:k + n].split(b'\0')[0]))
            except UnicodeDecodeError:
                t = None
            if t:
                campos[clave].append(t)
        descs.add(struct.unpack_from('<H', r, 94)[0] * 32)
    for off in sorted(descs):
        if not off or off >= len(st):
            continue
        body = st[off:st.index(b'\0', off)]
        try:
            s = a_texto(body)
        except UnicodeDecodeError:
            continue
        for linea in re.split(r'\\n|\n', s):
            t = limpio(linea)
            if t:
                campos['descripciones'].append(t)
    prop = (ROOT / 'work/ie1/capas/historial/rotulos_objetivos/v76_rotulos_largos/propuesta.md').read_text(encoding='utf-8')
    filas, sin = V76.leer_propuesta()
    campos['rotulos_v76'] = [f['nuevo'] for f in filas] + sorted(sin)
    return campos


def medir(lista, part):
    unicos = sorted(set(lista))
    c = collections.Counter()
    celdas = celdas_antes = 0
    for t in unicos:
        p = part(t)
        celdas += len(p)
        celdas_antes += len(t)
        c.update(x for x in p if len(x) == 2)
    return dict(textos=len(unicos), caracteres=celdas_antes, casillas=celdas, bigramas=len(c)), c


def main():
    campos = textos()
    res = {}
    total = {'A': collections.Counter(), 'B': collections.Counter()}
    for k, lista in campos.items():
        res[k] = {}
        for nom, part in (('A', particion_a), ('B', particion_b)):
            m, c = medir(lista, part)
            m['max_caracteres'] = max(len(t) for t in set(lista))
            m['textos_que_caben_10_casillas'] = sum(len(part(t)) <= 10 for t in set(lista))
            res[k][nom] = m
            total[nom].update(c)
    grupos = {'fase1_rotulos': ['rotulos', 'rotulos_v76'],
              'fase2_nombres': ['rotulos', 'rotulos_v76', 'nombres_ficha', 'nombres_lista'],
              'todo': list(campos)}
    union = {}
    for g, ks in grupos.items():
        for nom, part in (('A', particion_a), ('B', particion_b)):
            c = collections.Counter()
            for k in ks:
                c.update(medir(campos[k], part)[1])
            orden = [n for n, _ in c.most_common()]
            tot = sum(c.values())
            cobertura = {n: round(sum(c[x] for x in orden[:n]) / tot, 3) for n in (50, 100, 200, 300, 500, 1000) if tot}
            union[f'{g}_{nom}'] = dict(bigramas=len(c), apariciones=tot, cobertura_top_n=cobertura,
                                       top40=orden[:40])
    ejemplos = {t: dict(A=particion_a(t), B=particion_b(t)) for t in
                ['Instituto Wild', 'Caseta del club', 'Aurelia', 'H. de negro', 'Club manga y go']}
    out = dict(base=str(BASE.relative_to(ROOT)), por_campo=res, union=union, ejemplos=ejemplos,
               caracteres_distintos=sorted(set(''.join(t for l in campos.values() for t in l))))
    (HERE / 'inventario.json').write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
    for k, v in res.items():
        print(k, v)
    for k, v in union.items():
        print(k, v['bigramas'], v['apariciones'], v['cobertura_top_n'])
    print(len(out['caracteres_distintos']), ''.join(out['caracteres_distintos']))


if __name__ == '__main__':
    main()
