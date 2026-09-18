"""v88 · validación offline de probe_ie1_v88 frente a probe_ie1_v87.

1. Archivo: solo cambian las entradas declaradas (3 fuentes, unitbase.dat/.STR, eve.pkh/.pkb).
2. Fuentes: mismo tamaño y CMAP; cada byte distinto cae en una celda o en la entrada CWDH de un código del
   registro; los glifos del registro coinciden con registro.json (métricas).
3. unitbase.dat: solo cambian los campos +0/+16 declarados; unitbase.STR: solo las descripciones declaradas,
   sin crecer y con el mismo número de líneas y casillas por línea <= antes.
4. Eventos: solo cambian los declarados, con las mismas instrucciones y registros, sin crecer; los
   registros cambiados son los declarados; los eventos protegidos quedan idénticos.
5. Rótulos (todos los 0x4037 arg 3): <= 20 B y <= 10 casillas.
6. Solapes: todos los textos cambiados se dibujan con las fuentes reales de v88 al paso real de cada
   campo; ninguna casilla con bigrama queda a menos del hueco mínimo de su vecina.
7. Códigos: los códigos del registro solo aparecen en los textos declarados (recuento alineado en
   unitbase.dat, unitbase.STR y los eventos descomprimidos) y siguen sin glifo de kanji en ninguna fuente.
Salida: validacion.json. Uso: python -X utf8 validar.py
"""
from __future__ import annotations

import collections
import json
import struct
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import apply as A  # noqa: E402

K = A.K
V87 = A.ROOT / 'work/shared/candidatas/probe_ie1_v87/archive.fa'
V88 = A.ROOT / 'work/shared/candidatas/probe_ie1_v88/archive.fa'
PKH, PKB = A.C.PKH, A.C.PKB
DECLARADAS = {A.F12, A.F8, A.F12T, A.UNIT, A.USTR, PKH, PKB}
errores = []


def err(msg):
    errores.append(msg)
    if len(errores) < 60:
        print('ERROR', msg)


def cargar_fuente(datos, nombre):
    tmp = Path(tempfile.mkdtemp(prefix='ie123_v88v_'))
    (tmp / nombre).write_bytes(datos)
    return A.cargar(tmp / nombre)


def celda_de_byte(F, off):
    """Glifos (gi) cuyas celdas contienen el byte `off` de la fuente, o None si está fuera de las hojas."""
    t = F.t
    rel = off - F.f.doff
    if not 0 <= rel < t['nsheets'] * t['sheet_size']:
        return None
    sheet, r = divmod(rel, t['sheet_size'])
    bpp_bytes = 32 if t['fmt'] == 11 else 64
    tile, sub = divmod(r, bpp_bytes)
    tw = t['sheet_w'] // 8
    ty, tx = divmod(tile, tw)
    ms = [sub * 2, sub * 2 + 1] if t['fmt'] == 11 else [sub]
    out = set()
    for m in ms:
        x = y = 0
        for i in range(3):
            x |= ((m >> (2 * i)) & 1) << i
            y |= ((m >> (2 * i + 1)) & 1) << i
        X, Y = tx * 8 + x, ty * 8 + y
        col, row = X // F.sx, Y // F.sy
        out.add(sheet * F.f.PER + row * t['ncols'] + col)
    return out


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    reg = json.loads(A.REGISTRO.read_text(encoding='utf-8'))
    inf = json.loads((HERE / 'informe.json').read_text(encoding='utf-8'))
    d7, i7 = K.indice_fa(V87)
    d8, i8 = K.indice_fa(V88)
    g7 = lambda p: bytes(d7[i7[p][0]:i7[p][0] + i7[p][1]])  # noqa: E731
    g8 = lambda p: bytes(d8[i8[p][0]:i8[p][0] + i8[p][1]])  # noqa: E731

    # 1) entradas
    assert set(i7) == set(i8)
    cambiadas = sorted(p for p in i7 if i7[p] != i8[p] and g7(p) != g8(p))
    movidas_iguales = sorted(p for p in i7 if i7[p] != i8[p] and g7(p) == g8(p))
    if set(cambiadas) != DECLARADAS:
        err(f'entradas cambiadas {cambiadas} != declaradas')
    print('entradas cambiadas', cambiadas, 'movidas sin cambio', movidas_iguales)

    # 2) fuentes
    codigos = {int(e['unicode'][2:], 16): e for e in reg['bigramas']}
    fuentes8 = {}
    for f in (A.F12, A.F8, A.F12T):
        a, b = g7(f), g8(f)
        if len(a) != len(b):
            err(f'{f}: tamaño')
            continue
        Fa, Fb = cargar_fuente(a, 'a_' + Path(f).name), cargar_fuente(b, 'b_' + Path(f).name)
        fuentes8[f] = Fb
        if Fa.cmap != Fb.cmap:
            err(f'{f}: CMAP')
        gis = {Fb.gi(cp) for cp in codigos}
        cwdh = {Fb.f.cwdh_entry_off(gi): gi for gi in gis}
        fuera = 0
        for off in (i for i in range(len(a)) if a[i] != b[i]):
            c = celda_de_byte(Fb, off)
            if c is not None and c <= gis:
                continue
            if any(o <= off < o + 3 for o in cwdh):
                continue
            fuera += 1
        if fuera:
            err(f'{f}: {fuera} bytes cambiados fuera de celdas/CWDH del registro')
        for cp, e in codigos.items():
            gi = Fb.gi(cp)
            info = e['fuentes'].get(f)
            if info is None:
                if Fb.metrics[gi] != Fa.metrics[gi] or Fb.bitmap(gi) != Fa.bitmap(gi):
                    err(f'{f}: {e["par"]} cambiado sin declararse')
            elif list(Fb.metrics[gi]) != info['cwdh']:
                err(f'{f}: {e["par"]} métricas {Fb.metrics[gi]} != {info["cwdh"]}')
        print(f, 'ok' if not fuera else fuera)

    # 3) unitbase
    ub7, ub8 = g7(A.UNIT), g8(A.UNIT)
    decl = {(n['registro'], n['campo']) for n in inf['nombres']}
    for i in range((len(ub7) - 96) // 96):
        r7, r8 = ub7[96 + i * 96:192 + i * 96], ub8[96 + i * 96:192 + i * 96]
        if r7 == r8:
            continue
        if r7[32:] != r8[32:]:
            err(f'unitbase {i}: cambia fuera de +0/+16')
        for c in (0, 16):
            if r7[c:c + 16] != r8[c:c + 16] and (i, c) not in decl:
                err(f'unitbase {i} +{c}: no declarado')
    if ub7[:96] != ub8[:96]:
        err('unitbase: cabecera')
    st7, st8 = g7(A.USTR), g8(A.USTR)
    rangos = {}
    reg8 = A.Codec(reg['bigramas'])
    for dsc in inf['descripciones']:
        o = dsc['offset']
        rangos[o] = dsc['bytes_antes']
        a = st7[o:o + dsc['bytes_antes']]
        b = st8[o:st8.index(b'\0', o)]
        if len(b) > len(a) or any(st8[o + len(b):o + len(a) + 1]):
            err(f'STR {o}: tamaño/relleno')
        la = [x for x in reg8.segmentos(a)]
        lb = [x for x in reg8.segmentos(b)]
        if reg8.texto(a) != reg8.texto(b):
            err(f'STR {o}: el texto cambia {reg8.texto(a)!r} -> {reg8.texto(b)!r}')
        ca = [len(reg8.tokens(x)) for x in a.split(b'\n')]
        cb = [len(reg8.tokens(x)) for x in b.split(b'\n')]
        if len(ca) != len(cb) or any(y > x for x, y in zip(ca, cb)):
            err(f'STR {o}: líneas/casillas {ca} -> {cb}')
    for off in (i for i in range(len(st7)) if st7[i] != st8[i]):
        if not any(o <= off < o + n for o, n in rangos.items()):
            err(f'STR: byte {off} fuera de lo declarado')
            break

    # 4) eventos
    ev7 = {e: A.decompress(g7(PKB)[o:o + s]) for e, o, s in A.parse_index(g7(PKH))}
    ev8 = {e: A.decompress(g8(PKB)[o:o + s]) for e, o, s in A.parse_index(g8(PKH))}
    assert list(ev7) == list(ev8)
    decl_ev = collections.defaultdict(set)
    for t in inf['textos_evento']:
        decl_ev[t['evento']].add(t['indice'])
    for e in ev7:
        if ev7[e] == ev8[e]:
            continue
        if e in A.PROTEGIDOS or e in A.DONT_TOUCH:
            err(f'evento protegido {e} cambiado')
        if e not in decl_ev:
            err(f'evento {e} no declarado')
            continue
        if len(ev8[e]) > len(ev7[e]):
            err(f'evento {e} crece')
        _, o7, r7 = A.S.parse(ev7[e])
        _, o8, r8 = A.S.parse(ev8[e])
        if o7 != o8 or len(r7) != len(r8):
            err(f'evento {e}: estructura')
            continue
        dif = {i for i, (x, y) in enumerate(zip(r7, r8)) if x.body != y.body}
        if dif != decl_ev[e]:
            err(f'evento {e}: registros {sorted(dif)} != {sorted(decl_ev[e])}')
        for i in dif:
            op = o8.get(r8[i].instruction)
            if (op, r8[i].argument) not in ((0x4037, 3), (0x402f, 2), (0x402f, 3)):
                err(f'evento {e}/{i}: opcode {op:#x}')
            if op == 0x402f and reg8.texto(r7[i].body) != reg8.texto(r8[i].body):
                err(f'evento {e}/{i}: el objetivo cambia de texto')
    print('eventos cambiados', sum(ev7[e] != ev8[e] for e in ev7), 'declarados', len(decl_ev))

    # 5) rótulos
    n_rot = 0
    for e, data in ev8.items():
        try:
            _, ops, recs = A.S.parse(data)
        except (ValueError, KeyError):
            continue
        for r in recs:
            if ops.get(r.instruction) == 0x4037 and r.argument == 3:
                n_rot += 1
                cas = len(reg8.tokens(r.body))
                if len(r.body) > 20 or cas > 10:
                    err(f'rótulo {e}: {len(r.body)} B, {cas} casillas')
    print('rótulos revisados', n_rot)

    # 6) solapes con las fuentes reales
    def celdas_px(f, body, paso):
        F = fuentes8[f]
        col = []
        k = 0
        for tok, t in reg8.tokens(body):
            if len(tok) != 2:
                continue
            ch = tok.decode('cp932')
            gi = F.gi(ord(ch))
            left, _, adv = F.metrics[gi]
            x0 = int((A.CELDA[f] - adv) / 2) + left + k * paso
            px = {(x + x0, y): v for y, row in enumerate(F.bitmap(gi)) for x, v in enumerate(row) if v}
            col.append(dict(c=t or ch, par=tok in reg8.por_codigo, px=px))
            k += 1
        return col

    def revisar(campo, body, donde):
        for f, paso in A.CAMPOS[campo][1]:
            col = celdas_px(f, body, paso)
            for i in range(len(col) - 1):
                if not (col[i]['par'] or col[i + 1]['par']):
                    continue
                a = [x for (x, _), v in col[i]['px'].items() if v >= A.SOLIDO[f]]
                b = [x for (x, _), v in col[i + 1]['px'].items() if v >= A.SOLIDO[f]]
                if a and b and min(b) - max(a) - 1 < A.HUECO_MIN[f]:
                    err(f'solape {donde} {f} paso {paso}: {col[i]["c"]!r}|{col[i + 1]["c"]!r}')
    n_sol = 0
    for n in inf['nombres']:
        off = 96 + n['registro'] * 96 + n['campo']
        revisar('nombre', ub8[off:off + 16].split(b'\0')[0], f"nombre {n['registro']}+{n['campo']}")
        n_sol += 1
    for dsc in inf['descripciones']:
        o = dsc['offset']
        for linea in st8[o:st8.index(b'\0', o)].split(b'\n'):
            revisar('descripcion', linea, f'STR {o}')
        n_sol += 1
    for t in inf['textos_evento']:
        _, ops, recs = A.S.parse(ev8[t['evento']])
        revisar(t['tipo'], recs[t['indice']].body, f"{t['evento']}/{t['indice']}")
        n_sol += 1
    print('textos dibujados', n_sol)

    # 7) códigos del registro en los textos
    por_codigo = {bytes.fromhex(e['sjis']): e['par'] for e in reg['bigramas']}
    real = collections.Counter()
    reg7 = A.Codec(json.loads(A.REG_V87.read_text(encoding='utf-8'))['bigramas'])

    def contar(body):
        n = 0
        for tok, _ in reg8.tokens(body):
            if tok in por_codigo:
                real[por_codigo[tok]] += 1
                n += 1
        return n

    DUM = 'ダミー'.encode('cp932')
    for i in range((len(ub8) - 96) // 96):
        r8, r7 = ub8[96 + i * 96:192 + i * 96], ub7[96 + i * 96:192 + i * 96]
        for c in (0, 16):
            b8, b7 = r8[c:c + 16].split(b'\0')[0], r7[c:c + 16].split(b'\0')[0]
            if contar(b8) and (i in A.EXCLUIR_UNIDADES or DUM in r8[:32]):
                err(f'unitbase {i}+{c}: bigramas en un registro excluido')
            if reg8.texto(b8) != reg7.texto(b7):
                err(f'unitbase {i}+{c}: texto {reg7.texto(b7)!r} -> {reg8.texto(b8)!r}')
        if contar(r8[32:64].split(b'\0')[0]):
            err(f'unitbase {i}+32: bigramas en el nombre largo')
    desc_ok = {int.from_bytes(ub8[96 + i * 96 + 94:96 + i * 96 + 96], 'little') * 32
               for i in range((len(ub8) - 96) // 96)}
    idx = 0
    while idx < len(st8):
        fin = st8.find(b'\0', idx)
        fin = len(st8) if fin < 0 else fin
        if st8[idx:fin] and contar(st8[idx:fin]) and idx not in desc_ok:
            err(f'STR {idx}: bigramas en una cadena que no es descripción')
        idx = fin + 1
    for e, data in ev8.items():
        try:
            _, ops, recs = A.S.parse(data)
        except (ValueError, KeyError):
            continue
        for i, r in enumerate(recs):
            if contar(r.body):
                clave = (ops.get(r.instruction), r.argument)
                if clave not in ((0x4037, 3), (0x402f, 2), (0x402f, 3)) or e in A.PROTEGIDOS or e in A.DONT_TOUCH:
                    err(f'evento {e}/{i}: bigramas fuera de rótulo/objetivo {clave}')
    sin_uso = [e['par'] for e in reg['bigramas'] if not real[e['par']]]
    if sin_uso:
        err(f'pares del registro sin uso: {sin_uso}')
    # los códigos siguen siendo kanji en la tabla (no se ha tocado el CMAP) y cada uno tiene su glifo propio
    for f, F in fuentes8.items():
        inv = collections.Counter(F.cmap.values())
        for cp in codigos:
            if inv[F.gi(cp)] != 1:
                err(f'{f}: el glifo de U+{cp:04X} lo comparten varios códigos')
    print('apariciones de códigos', sum(real.values()), 'pares usados', len(real))

    out = dict(base=str(V87), candidata=str(V88), entradas_cambiadas=cambiadas,
               eventos_cambiados=sum(ev7[e] != ev8[e] for e in ev7), rotulos_revisados=n_rot,
               textos_dibujados=n_sol, apariciones_codigos=sum(real.values()), pares_usados=len(real),
               errores=errores, resultado='PASS' if not errores else 'FAIL')
    (HERE / 'validacion.json').write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
    print(out['resultado'], len(errores))


if __name__ == '__main__':
    main()
