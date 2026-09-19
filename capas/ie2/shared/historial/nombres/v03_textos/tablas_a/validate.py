"""IE2 v03 · tablas A · validación de extra/ contra la base probe_ie2_v02.

Comprueba:
  - tamaños idénticos (JinmyakuData: se re-parsea y solo cambian los textos);
  - fuera de los huecos declarados (slots.json) los bytes son los de la base;
  - cada texto escrito se lee de vuelta (siguiendo los punteros de .dat en command/item) y es exactamente
    la codificación de ancho completo del texto (sin bigramas), con NUL, glifo en FONT12.bcfnt,
    <= 2 líneas x 20 caracteres (descripciones, sucesos, pistas) y los mismos %s/%d que el japonés;
  - los textos que se quedan en japonés no cambian;
  - los punteros de .dat solo cambian en los registros de textos reubicados.
Uso: python -X utf8 validate.py
"""
from __future__ import annotations

import collections
import json
import re
import struct
import sys

import tablas as T

_A = T.K.comun88.modulo('ie2_v03_tablas_a_apply', T.HERE / 'apply.py')   # «apply» choca con módulos de IE1
SALIDA, cuerpo = _A.SALIDA, _A.cuerpo

fallos = []


def falla(msg):
    fallos.append(msg)


def main():
    wl = json.loads((T.HERE / 'worklist.json').read_text(encoding='utf-8'))
    slots = json.loads((T.HERE / 'slots.json').read_text(encoding='utf-8'))
    out = {f: (T.EXTRA / f).read_bytes() for f in SALIDA}
    base = {f: T.base(f) for f in SALIDA}

    # 1-2 tamaños y máscara
    for f in SALIDA:
        if f == 'JinmyakuData.dat':
            continue
        if len(out[f]) != len(base[f]):
            falla(f'{f}: tamaño {len(out[f])} != {len(base[f])}')
            continue
        m = bytearray(out[f])
        for a, b in slots.get(f, []):
            m[a:b] = base[f][a:b]
        if bytes(m) != base[f]:
            d = next(i for i in range(len(m)) if m[i] != base[f][i])
            falla(f'{f}: cambia fuera de los huecos declarados (0x{d:x})')

    # 3 lectura de vuelta
    ptr = {'command.STR': ('command.dat', 28, {'nombre': 20, 'desc': 22}),
           'item.STR': ('item.dat', 36, {'desc': 34})}
    jd = T.jparse(out['JinmyakuData.dat'])
    jb = T.jparse(base['JinmyakuData.dat'])
    meta = lambda d: [{k: v for k, v in r.items() if k != 'text'} for r in d['records']]
    if meta(jd) != meta(jb) or jd['edges'] != jb['edges'] or [h['id'] for h in jd['hints']] != [h['id'] for h in jb['hints']]:
        falla('JinmyakuData: cambia algo más que los textos')
    ev = {r['kind']: r['text'] for r in jd['records'] if 'text' in r}
    evb = {r['kind']: r['text'] for r in jb['records'] if 'text' in r}
    hi = {h['id']: h['text'] for h in jd['hints']}
    hib = {h['id']: h['text'] for h in jb['hints']}
    n = collections.Counter()
    for r in wl['filas']:
        f = r['fichero']
        activo = r['texto'] is not None and r['fuente'] in ('oficial', 'recorte', 'manual')
        if f in ptr:
            dat, rec, campos = ptr[f]
            p = struct.unpack_from('<H', out[dat], r['id'] * rec + campos[r['tipo']])[0] * 32
            leido = T.at(out[f], p)
            if not activo:
                if p != r['offset'] or leido != T.at(base[f], r['offset']):
                    falla(f'{r["key"]}: el japonés ha cambiado')
                continue
        elif f == 'JinmyakuData.dat':
            k = r['id']
            if r['tipo'] == 'suceso':
                leido, antes = ev[k].rstrip(b'\0'), evb[k]
                if ev[k].endswith(b'\0') != antes.endswith(b'\0'):
                    falla(f'{r["key"]}: NUL final distinto')
            else:
                leido = hi[k]
                if T.pct(leido) != T.pct(hib[k]):
                    falla(f'{r["key"]}: %s/%d distinto del japonés')
            if not activo:
                continue
        else:
            o = r['offset']
            cap = r['capacidad']
            campo = out[f][o:o + cap]
            leido = campo.split(b'\0')[0]
            if not activo:
                if campo != base[f][o:o + cap]:
                    falla(f'{r["key"]}: el japonés ha cambiado')
                continue
            if f != 'fieldinf.dat' and b'\0' not in campo:
                falla(f'{r["key"]}: sin NUL')
        esperado = cuerpo(r)
        if leido != esperado:
            falla(f'{r["key"]}: lo escrito no es la codificación del texto')
            continue
        try:
            txt = leido.decode('cp932')
        except UnicodeDecodeError:
            falla(f'{r["key"]}: no decodifica')
            continue
        sg = T.K.M.sin_glifo(leido.replace(b'\n', b''))
        if sg:
            falla(f'{r["key"]}: sin glifo {sg}')
        if re.search('[぀-ヿ一-鿿]', txt):
            falla(f'{r["key"]}: quedan kana/kanji (¿bigrama?)')
        lineas = txt.split('\n')
        if r['tipo'] in ('desc', 'suceso', 'pista'):
            cif = r.get('cifras', 1) if r['tipo'] == 'pista' else 1
            anchos = [len(re.sub(r'%[sd]', 'X' * max(cif, 1), l)) for l in lineas]
            if len(lineas) > T.MAX_LINEAS or max(anchos) > T.MAX_LINEA:
                falla(f'{r["key"]}: {len(lineas)} líneas, ancho {max(anchos)}')
            if T.pct(txt) != T.pct(r['jp']):
                falla(f'{r["key"]}: %s/%d {T.pct(txt)} != japonés {T.pct(r["jp"])}')
        else:
            lim = {'nombre': T.MAX_NOMBRE_TEC if f == 'command.STR' else T.MAX_OBJETO, 'titulo': T.MAX_TITULO,
                   'campo': T.MAX_CAMPO, 'objetivo': T.MAX_OBJETIVO}[r['tipo']]
            if len(lineas) != 1 or len(txt) > lim:
                falla(f'{r["key"]}: {len(txt)} caracteres > {lim}')
            if r['tipo'] in ('nombre', 'titulo') and f != 'command.STR' and len(leido) > 18:
                falla(f'{r["key"]}: {len(leido)} B > 18')
        n[f] += 1

    # 4 punteros
    inf = json.loads((T.HERE / 'informe.json').read_text(encoding='utf-8'))
    for f, (dat, rec, campos) in ptr.items():
        movidos = {m['desde'] // 32: m['hasta'] // 32 for m in inf['reubicados'][f.split('.')[0]]}
        for i in range(len(out[dat]) // rec):
            for c in campos.values():
                a = struct.unpack_from('<H', base[dat], i * rec + c)[0]
                b = struct.unpack_from('<H', out[dat], i * rec + c)[0]
                if a != b and movidos.get(a) != b:
                    falla(f'{dat}: puntero {i}+{c} cambia sin reubicación declarada')
        # destinos: no pisan texto vivo de la base
        # destinos: a cero en la base o dentro de huecos japoneses ya traducidos (su cola sobrante), nunca
        # sobre el NUL de la cadena anterior ni sobre texto que se lee
        movs = inf['reubicados'][f.split('.')[0]]
        propios = set()
        for r in wl['filas']:
            if r['fichero'] == f and r['texto'] is not None and r['fuente'] in ('oficial', 'recorte', 'manual'):
                propios.update(range(r['offset'], r['offset'] + r['capacidad']))
        for m in movs:
            a, b = m['hasta'], m['hasta'] + m['bytes']
            if any(base[f][x] and x not in propios for x in range(a, b)):
                falla(f'{f}: la reubicación {m["key"]} pisa texto japonés que se conserva')
            if out[f][a - 1] != 0:
                falla(f'{f}: la reubicación {m["key"]} empieza sobre el NUL de la cadena anterior')
        vivos = set()
        for i in range(len(out[dat]) // rec):
            for c in campos.values():
                p = struct.unpack_from('<H', out[dat], i * rec + c)[0] * 32
                if p and out[f][p]:
                    vivos.update(range(p, p + len(T.at(out[f], p)) + 1))
        for m in movs:
            a, b = m['hasta'], m['hasta'] + m['bytes']
            otros = [x for x in range(a, b) if x in vivos]
            if len(otros) != b - a or T.at(out[f], a) != out[f][a:b - 1]:
                falla(f'{f}: la reubicación {m["key"]} no se lee entera')

    for x in fallos[:60]:
        print('FALLO', x)
    print('textos comprobados:', dict(n))
    print('RESULTADO:', 'OK' if not fallos else f'{len(fallos)} fallos')
    sys.exit(1 if fallos else 0)


if __name__ == '__main__':
    main()
