"""IE2 v08 · validación offline de la capa (con las fuentes y datos de extra/ y los eventos de ie1/ ie2/).

Comprueba:
- registro: sjis únicos, un codepoint por glifo en cada fuente dibujada, claves únicas, orden de v07 intacto
  (las entradas de v07 siguen en su posición; solo cambian las reutilizadas/redibujadas documentadas).
- códigos nuevos: sin aparición en texto de probe_ie2_v05 (escaneo08) ni literal en code.bin/CRO.
- nombres +16 (y +0 de los apóstrofos): decodifican al texto elegido, <= 7 casillas, <= 15 B; FONT8 sin
  solape a paso 10 y 9 (hueco >= 1 entre núcleos alfa >= 8); FONT12 a paso 15 (>= 1, alfa >= 5); FONT12T a
  paso 15 (rellenos separados: tinta con contorno >= -1).
- rótulos: decodifican al texto elegido, <= 10 casillas con el centrado, <= 20 B; FONT8 a paso 10 sin solape;
  eventos no crecen, protegidos intactos, solo cambian los registros 0x4037 arg 3 listados.
- descripciones (si existe informe_desc.json): decodifican, <= 18 casillas por línea, <= 2 líneas, caben en su
  hueco, FONT12 a paso 15 sin solape.
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
import comun08 as K  # noqa: E402

A88, A89 = K.A88, K.A89
F12, F8, F12T = K.F12, K.F8, K.F12T
STR = {'ie1': 'inazuma1/data_iz/logic/unitbase.STR', 'ie2': 'inazuma2/data_iz/logic/unitbase.STR'}


def cargar():
    tmp = Path(tempfile.mkdtemp(prefix='ie2_v08v_'))
    F = {}
    for f in K.FUENTES:
        p = tmp / Path(f).name
        p.write_bytes((HERE / 'extra' / f).read_bytes())
        F[f] = A88.cargar(p)
    return F


def cps(body):
    out, i = [], 0
    while i < len(body):
        b = body[i]
        if 0x81 <= b <= 0x9F or 0xE0 <= b <= 0xFC:
            out.append(ord(body[i:i + 2].decode('cp932')))
            i += 2
        else:
            out.append(None)
            i += 1
    return out


def huecos(F, lista, paso, caja, solido):
    res, prev, pen = [], None, 0
    for cp in lista:
        if cp is None:
            prev, pen = None, 0
            continue
        gi = F.gi(cp)
        left, _, adv = F.metrics[gi]
        x0 = pen + int((caja - adv) / 2) + left
        xs = [x0 + x for row in F.bitmap(gi) for x, v in enumerate(row) if v >= solido]
        pen += paso
        if not xs:
            continue
        if prev is not None:
            res.append(min(xs) - prev - 1)
        prev = max(xs)
    return res


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    errores, avisos = [], []
    reg = json.loads((HERE / 'registro.json').read_text(encoding='utf-8'))
    reg07 = json.loads(K.REG07.read_text(encoding='utf-8'))
    F = cargar()
    for f in K.FUENTES:
        if K.sha((HERE / 'extra' / f).read_bytes()) != reg['fuentes_dibujadas'][f]:
            errores.append(f'{f}: sha distinto del registro')
        if len((HERE / 'extra' / f).read_bytes()) != len(K.FUENTE_ORIGEN[f].read_bytes()):
            errores.append(f'{f}: tamaño distinto')
    # registro
    sj = [e['sjis'] for e in reg['bigramas']]
    if len(sj) != len(set(sj)):
        errores.append('sjis repetidos')
    cl = [A89.clave_de(e) for e in reg['bigramas']]
    if len(cl) != len(set(cl)):
        errores.append('claves repetidas: ' + str([c for c, n in collections.Counter(cl).items() if n > 1][:5]))
    if [e['sjis'] for e in reg['bigramas'][:len(reg07['bigramas'])]] != [e['sjis'] for e in reg07['bigramas']]:
        errores.append('el orden del registro v07 cambió')
    inv = K.inversos(F)
    for e in reg['bigramas']:
        for f in e['fuentes']:
            if not A89.unico(F[f], inv[f], e['sjis']):
                errores.append(f"{e['sjis']} sin glifo único en {f}")
    nuevos = set(reg.get('pares_ie2_v08', [])) | set(reg.get('pares_ie2_v08_descripciones', []))
    nuevos_sjis = {A89.clave_de(e): e['sjis'] for e in reg['bigramas']}
    esc = json.loads((HERE / 'escaneo_v05.json').read_text(encoding='utf-8'))
    lit = json.loads((HERE / 'escaneo_literales_v08.json').read_text(encoding='utf-8'))
    if (HERE / 'escaneo_v05_extra.json').exists():
        esc['codigos'].update(json.loads((HERE / 'escaneo_v05_extra.json').read_text(encoding='utf-8'))['codigos'])
        lit.update(json.loads((HERE / 'escaneo_literales_extra.json').read_text(encoding='utf-8')))
    esc88 = json.loads(A.ESC88.read_text(encoding='utf-8'))
    for c in nuevos:
        s = nuevos_sjis[c]
        v = esc['codigos'].get(s) or esc88['codigos'].get(s)
        if v is None or v.get('texto'):
            errores.append(f'código {s} con texto o sin escanear')
        if lit.get(s):
            errores.append(f'código {s} con literal')
    codec = A89.Codec(reg['bigramas'])
    inf = json.loads((HERE / 'informe.json').read_text(encoding='utf-8'))
    get = K.comun88.abrir(K.CAND)
    # nombres
    n_ok = 0
    esperado = {(x['juego'], x['registro']): x for x in inf['cambios_nombres']}
    stats = collections.Counter()
    for j in ('ie1', 'ie2'):
        ub0 = get(K.UNIT[j])
        ub = (HERE / 'extra' / K.UNIT[j]).read_bytes()
        assert len(ub) == len(ub0)
        for i in range((len(ub) - 96) // 96):
            a, b = ub0[96 + i * 96:192 + i * 96], ub[96 + i * 96:192 + i * 96]
            if a[32:] != b[32:]:
                errores.append(f'{j} #{i}: cambió más allá de +32')
            if a == b:
                continue
            for off in (0, 16):
                body = b[off:off + 16].split(bytes(1))[0]
                if a[off:off + 16] == b[off:off + 16]:
                    continue
                x = esperado.get((j, i))
                if x is None or codec.texto(body) != x['texto']:
                    errores.append(f'{j} #{i}+{off}: texto {codec.texto(body)!r} inesperado')
                if off == 0 and not (x and x.get('apostrofo_oficial')):
                    errores.append(f'{j} #{i}: +0 cambiado sin apóstrofo')
                if len(body) > 15 or len(cps(body)) > 7 or b[off + 15] != 0 and len(body) > 15:
                    errores.append(f'{j} #{i}+{off}: {len(body)} B')
                lista = cps(body)
                for nombre, (f, paso, caja, sol, minimo) in {
                        'F8@10': (F8, 10, 11, 8, 1), 'F8@9': (F8, 9, 11, 8, 1),
                        'F12@15': (F12, 15, 15, 5, 1), 'F12T@15': (F12T, 15, 16, 1, -1)}.items():
                    hs = huecos(F[f], lista, paso, caja, sol)
                    if any(g < minimo for g in hs):
                        errores.append(f'{j} #{i}+{off} {x and x["texto"]}: solape {nombre} {hs}')
                    if nombre == 'F8@10' and off == 16:
                        stats.update(hs)
                n_ok += 1
    # rótulos
    r_ok = 0
    prot = {'ie1': A.PROT_IE1, 'ie2': A.PROT_IE2}
    cambios = json.loads((HERE / 'cambios_registros.json').read_text(encoding='utf-8'))['registros']
    por_ev = collections.defaultdict(dict)
    for c in cambios:
        por_ev[(c['juego'], c['evento'])][c['indice']] = c
    elegidos = {(c['juego'], c['evento'], c['indice']): c for c in inf['cambios_rotulos']}
    for (j, eid), regs in por_ev.items():
        if eid in prot[j]:
            errores.append(f'{j} {eid}: evento protegido')
        nuevo = (HERE / j / 'events' / f'{eid}.ssd').read_bytes()
        _, ops, recs = A88.S.parse(nuevo)
        for i, c in regs.items():
            body = recs[i].body
            if body.hex() != c['cuerpo']:
                errores.append(f'{j} {eid}#{i}: cuerpo distinto del listado')
            if (ops.get(recs[i].instruction), recs[i].argument) != (0x4037, 3):
                errores.append(f'{j} {eid}#{i}: no es 0x4037 arg 3')
            t = codec.texto(body)
            e = elegidos[(j, eid, i)]
            if t.strip(' ') != e['despues'] or len(body) > 20 or len(cps(body)) > 10:
                errores.append(f'{j} {eid}#{i}: {t!r} / {len(body)} B')
            hs = huecos(F[F8], cps(body), 10, 11, 8)
            if any(g < 1 for g in hs):
                errores.append(f'{j} {eid}#{i} {t!r}: solape FONT8 {hs}')
            r_ok += 1
    for x in inf['eventos']:
        if x['bytes'] > x['bytes_antes']:
            errores.append(f"{x['juego']} {x['evento']}: crece")
    # descripciones
    d_ok = 0
    infd_p = HERE / 'informe_desc.json'
    if infd_p.exists():
        infd = json.loads(infd_p.read_text(encoding='utf-8'))
        for j in STR:
            st0 = get(STR[j])
            p = HERE / 'extra' / STR[j]
            if not p.exists():
                continue
            st = p.read_bytes()
            if len(st) != len(st0):
                errores.append(f'{j} STR: tamaño')
        for x in infd['filas']:
            st = (HERE / 'extra' / STR[x['juego']]).read_bytes()
            off = x['offset']
            body = st[off:st.index(bytes(1), off)]
            t = codec.texto(body).replace('¤', '\n')
            if t != x['texto']:
                errores.append(f"{x['juego']} STR {off}: {t!r} != {x['texto']!r}")
            if off + len(body) >= off + x['hueco']:
                errores.append(f"{x['juego']} STR {off}: no cabe")
            lineas = body.split(bytes((0x0A,)))
            if len(lineas) > 2 or any(len(cps(l)) > 18 for l in lineas):
                errores.append(f"{x['juego']} STR {off}: casillas/líneas")
            hs = huecos(F[F12], cps(body), 15, 15, 5)
            if any(g < 1 for g in hs):
                errores.append(f"{x['juego']} STR {off}: solape FONT12 {hs}")
            d_ok += 1
    out = dict(errores=errores, avisos=avisos, nombres_comprobados=n_ok, rotulos_comprobados=r_ok,
               descripciones_comprobadas=d_ok, codigos_nuevos=len(nuevos),
               huecos_font8_nombres=dict(sorted(stats.items())))
    (HERE / 'validacion.json').write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps({k: (v if not isinstance(v, list) else len(v)) for k, v in out.items()}, ensure_ascii=False))
    for e in errores[:30]:
        print(' ', e)


if __name__ == '__main__':
    main()
