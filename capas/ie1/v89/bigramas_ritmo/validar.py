"""v89 · validación offline de probe_ie1_v89 frente a probe_ie1_v88.

1. Archivo: solo cambian FONT12, unitbase.STR y eve.pkh/.pkb; FONT8, FONT12T y unitbase.dat idénticos.
2. FONT12: mismo tamaño; cada byte distinto cae en la celda o en la entrada CWDH de un código del registro;
   cada código tiene glifo propio y su dibujo coincide con registro.json (métricas y sha1 de píxeles).
3. Textos: descripciones, objetivos, nombres y rótulos de v89 decodifican (registro v89) igual que los de v88
   (registro v88). Casillas por segmento <= caracteres. STR: mismo tamaño, cambios solo dentro de la
   capacidad de v87 de cada descripción.
4. Solapes: descripciones, objetivos y nombres dibujados con la FONT12 real de v89 a 15 px: hueco sólido
   (alfa >= 5) >= 1 px entre casillas contiguas; se cuenta aparte cualquier contacto de tinta débil.
5. Eventos: solo cambian los de events/, mismas instrucciones y registros, solo los registros declarados,
   tamaño <= v87; eventos protegidos idénticos; rótulos (0x4037 arg 3) idénticos y <= 20 B / 10 casillas.
6. Códigos: todos los del registro se usan en algún texto (su ausencia en otros ficheros la comprueba el
   escaneo estricto escaneo_v89.json + comprobar_escaneo.py).
Salida: validacion.json.  Uso: python -X utf8 validar.py
"""
from __future__ import annotations

import collections
import hashlib
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import apply as A  # noqa: E402
import ritmo as R  # noqa: E402

A88, K = A.A88, A.K
V88 = A.BASE
V89 = K.ROOT / 'work/shared/candidatas/probe_ie1_v89/archive.fa'
PKH, PKB = A88.C.PKH, A88.C.PKB
errores = []


def err(m):
    errores.append(m)
    if len(errores) < 50:
        print('ERROR', m)


def celdas_de_byte(F, off):
    t = F.t
    rel = off - F.f.doff
    if not 0 <= rel < t['nsheets'] * t['sheet_size']:
        return None
    sheet, r = divmod(rel, t['sheet_size'])
    bpb = 32 if t['fmt'] == 11 else 64
    tile, sub = divmod(r, bpb)
    ty, tx = divmod(tile, t['sheet_w'] // 8)
    out = set()
    for m in ([sub * 2, sub * 2 + 1] if t['fmt'] == 11 else [sub]):
        x = y = 0
        for i in range(3):
            x |= ((m >> (2 * i)) & 1) << i
            y |= ((m >> (2 * i + 1)) & 1) << i
        X, Y = tx * 8 + x, ty * 8 + y
        out.add(sheet * F.f.PER + (Y // F.sy) * t['ncols'] + X // F.sx)
    return out


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    reg = json.loads((HERE / 'registro.json').read_text(encoding='utf-8'))
    inf = json.loads((HERE / 'informe.json').read_text(encoding='utf-8'))
    reg88 = json.loads(A.REG88.read_text(encoding='utf-8'))
    inf88 = json.loads(A.INF88.read_text(encoding='utf-8'))
    d8, i8 = K.indice_fa(V88)
    d9, i9 = K.indice_fa(V89)
    g8 = lambda p: bytes(d8[i8[p][0]:i8[p][0] + i8[p][1]])  # noqa: E731
    g9 = lambda p: bytes(d9[i9[p][0]:i9[p][0] + i9[p][1]])  # noqa: E731

    # 1 -------------------------------------------------------------------------------------------------
    if set(i8) != set(i9):
        err('entradas distintas')
    declaradas = {A.F12, A.USTR, PKH, PKB}
    cambiadas = sorted(p for p in i8 if i8[p][1] != i9[p][1] or g8(p) != g9(p))
    for p in cambiadas:
        if p not in declaradas:
            err(f'cambia {p} sin declarar')
    for p in (A.F8, A.F12T, A.UNIT):
        if g8(p) != g9(p):
            err(f'{p} cambia')
    if (HERE / 'extra' / A.F12).read_bytes() != g9(A.F12):
        err('FONT12 del archivo != capa')
    if (HERE / 'extra' / A.USTR).read_bytes() != g9(A.USTR):
        err('unitbase.STR del archivo != capa')

    # 2 -------------------------------------------------------------------------------------------------
    tmp = Path(tempfile.mkdtemp(prefix='ie123_v89v_'))
    fu = {}
    for nombre, datos in (('v88', g8(A.F12)), ('v89', g9(A.F12))):
        (tmp / f'{nombre}.bcfnt').write_bytes(datos)
        fu[nombre] = A88.cargar(tmp / f'{nombre}.bcfnt')
    F9 = fu['v89']
    if hashlib.sha256(g9(A.F12)).hexdigest() != reg['fuentes_dibujadas'][A.F12]:
        err('sha FONT12 != registro')
    inv = collections.defaultdict(list)
    for cp, gi in F9.cmap.items():
        inv[gi].append(cp)
    gis = {}
    for e in reg['bigramas']:
        cp = int(e['unicode'][2:], 16)
        gi = F9.gi(cp)
        if gi is None or inv[gi] != [cp]:
            err(f'{e["sjis"]} sin glifo propio')
            continue
        gis[gi] = e
        f12 = e['fuentes'][A.F12]
        if list(F9.metrics[gi]) != f12['cwdh']:
            err(f'métricas {e["sjis"]}')
        if 'pixeles_sha1' in f12:
            px = {(x, y): v for y, row in enumerate(F9.bitmap(gi)) for x, v in enumerate(row) if v}
            if hashlib.sha1(json.dumps(sorted(px.items())).encode()).hexdigest() != f12['pixeles_sha1']:
                err(f'píxeles {e["sjis"]}')
    b8, b9 = g8(A.F12), g9(A.F12)
    if len(b8) != len(b9):
        err('FONT12 cambia de tamaño')
    fuera = 0
    cwdh = [F9.f.cwdh_entry_off(gi) for gi in gis]
    for off in (i for i in range(len(b8)) if b8[i] != b9[i]):
        c = celdas_de_byte(F9, off)
        if c is not None:
            if not c & set(gis):
                fuera += 1
        elif not any(o <= off < o + 3 for o in cwdh):
            fuera += 1
    if fuera:
        err(f'FONT12: {fuera} bytes cambiados fuera de los códigos del registro')

    # 3 -------------------------------------------------------------------------------------------------
    codec88, codec9 = A.Codec(reg88['bigramas']), A.Codec(reg['bigramas'])
    u88, ev88, ub88, st88, _ = A88.recoger(K.abrir(V88), codec88)
    u89, ev89, ub89, st89, _ = A88.recoger(K.abrir(V89), codec9)
    if len(u88) != len(u89):
        err('número de unidades distinto')
    mq = A.Maqueta(F9, A88.codepoint)
    for e in reg['bigramas']:
        mq.fijos[A.clave_de(e)] = A.medir(F9, F9.gi(int(e['unicode'][2:], 16)))
    cap = {d['offset']: d['bytes_antes'] for d in inf88['descripciones']}
    huecos, contactos, revisados = collections.Counter(), collections.Counter(), 0
    for a, b in zip(u88, u89):
        clave = {k: a.get(k) for k in ('tipo', 'registro', 'campo', 'offset', 'evento', 'indice')}
        if clave != {k: b.get(k) for k in clave}:
            err(f'unidad desalineada {clave}')
            continue
        if codec88.texto(a['body']) != codec9.texto(b['body']):
            err(f'texto distinto {clave}: {codec88.texto(a["body"])!r} / {codec9.texto(b["body"])!r}')
        if a['tipo'] == 'rotulo' or a['excluido']:
            if a['body'] != b['body']:
                err(f'cambia {clave} (rótulo/excluido)')
            continue
        if a['tipo'] == 'nombre' and a['body'] != b['body']:
            err(f'cambia nombre {clave}')
        if a['tipo'] == 'descripcion':
            c = cap.get(a['offset'], len(a['body']))
            if len(b['body']) > c:
                err(f'descripción crece {clave}')
        # casillas por segmento <= letras
        cel = [c for c in codec9.claves(b['body'])]
        segs, cur = [], []
        for c in cel:
            if c is None:
                if cur:
                    segs.append(cur)
                cur = []
            else:
                cur.append(c)
        if cur:
            segs.append(cur)
        for s, (k, v) in zip(segs, [x for x in codec9.segmentos(b['body']) if x[0] == 't']):
            if len(s) > len(v):
                err(f'más casillas que letras {clave}')
        # solapes con la fuente real
        revisados += 1
        for g, pal in R.huecos(cel, mq):
            huecos[g] += 1
            if g < 1:
                err(f'hueco {g} en {clave} {codec9.texto(b["body"])!r}')
        # contacto de tinta débil (cualquier alfa)
        prev = None
        for k_, c in enumerate(cel):
            if c is None:
                prev = None
                continue
            if c == ' ':
                continue
            gi = F9.gi(ord(codec9.por_par[c].decode('cp932'))) if len(c) >= 2 else F9.gi(A88.codepoint(c))
            left, _, adv = F9.metrics[gi]
            x0 = int((15 - adv) / 2) + left
            xs = [x + x0 for y, row in enumerate(F9.bitmap(gi)) for x, v in enumerate(row) if v]
            if prev is not None and xs:
                dx = (k_ - prev[0]) * 15
                gd = min(xs) + dx - prev[1] - 1
                if gd < 1:
                    contactos[gd] += 1
                if gd < 0:
                    err(f'tinta débil solapada ({gd}) en {clave} {codec9.texto(b["body"])!r}')
            if xs:
                prev = (k_, max(xs))
    if st88 is not None and len(st88) != len(st89):
        err('unitbase.STR cambia de tamaño')
    if ub88 != ub89:
        err('unitbase.dat cambia')

    # 5 -------------------------------------------------------------------------------------------------
    staged = {int(p.stem) for p in (HERE / 'events').glob('*.ssd')}
    tam87 = {d['evento']: d['bytes_antes'] for d in inf88['eventos']}
    declarados = {(o['evento'], o['indice']) for o in inf['objetivo']}
    pk8, pk9 = g8(PKB), g9(PKB)
    idx8 = {e: (o, s) for e, o, s in A88.parse_index(g8(PKH))}
    idx9 = {e: (o, s) for e, o, s in A88.parse_index(g9(PKH))}
    if set(idx8) != set(idx9):
        err('índice de eventos distinto')
    cambiados = 0
    for eid in idx8:
        o8, s8 = idx8[eid]
        o9, s9 = idx9[eid]
        x8, x9 = pk8[o8:o8 + s8], pk9[o9:o9 + s9]
        if x8 == x9:
            if eid in staged:
                err(f'evento {eid} preparado pero igual')
            continue
        a, b = A88.decompress(x8), A88.decompress(x9)
        if a == b:
            continue
        cambiados += 1
        if eid not in staged:
            err(f'evento {eid} cambia sin declarar')
        if eid in A88.PROTEGIDOS or eid in A88.DONT_TOUCH:
            err(f'evento protegido {eid} cambia')
        _, op1, r1 = A88.S.parse(a)
        _, op2, r2 = A88.S.parse(b)
        if op1 != op2 or len(r1) != len(r2):
            err(f'evento {eid}: estructura')
            continue
        for i, (p, q) in enumerate(zip(r1, r2)):
            if (p.instruction, p.argument, p.body) != (q.instruction, q.argument, q.body):
                if (eid, i) not in declarados:
                    err(f'evento {eid} registro {i} sin declarar')
                if (op1.get(p.instruction), p.argument) not in ((0x402f, 2), (0x402f, 3)):
                    err(f'evento {eid} registro {i}: no es objetivo')
        if len(b) > tam87.get(eid, len(a)):
            err(f'evento {eid} crece sobre v87')
    for u in u89:
        if u['tipo'] == 'rotulo':
            n = len(codec9.tokens(u['body']))
            if len(u['body']) > 20 or n > 10:
                err(f'rótulo largo {u["evento"]} {u["indice"]}')

    # 6 -------------------------------------------------------------------------------------------------
    codigos = {bytes.fromhex(e['sjis']) for e in reg['bigramas']}
    usados = collections.Counter()
    for u in u89:
        for tok, _ in codec9.tokens(u['body']):
            if tok in codigos:
                usados[tok] += 1
    sin_uso = [e['sjis'] for e in reg['bigramas'] if usados[bytes.fromhex(e['sjis'])] == 0]
    if sin_uso:
        err(f'códigos sin uso {sin_uso[:10]}')

    val = dict(base=str(V88), candidata=str(V89),
               candidata_sha256=hashlib.sha256(Path(V89).read_bytes()).hexdigest(),
               entradas_cambiadas=cambiadas, eventos_cambiados=cambiados, unidades_revisadas=revisados,
               huecos_solidos=dict(sorted(huecos.items())), contactos_tinta_debil={str(k): v for k, v in sorted(contactos.items())},
               codigos=len(reg['bigramas']), apariciones_codigos=sum(usados.values()),
               errores=errores, resultado='PASS' if not errores else 'FAIL')
    (HERE / 'validacion.json').write_text(json.dumps(val, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps({k: v for k, v in val.items() if k != 'huecos_solidos'}, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
