"""v92 · informe (sin cambios) de otros textos de IE1 frente al port europeo de 3DS.

Formatos europeos (es/inazuma1/data_iz/logic), 1 byte con la tabla NDS:
- unitbase.dat: 96 B; nombre completo +0 (32 B), nombre corto +32 (32 B); resto igual que el japonés.
  Descripción: u16 en +94 × 128 B dentro de unitbase.STR (el japonés/actual: × 32 B).
  Actual: +0 nombre de ficha, +16 nombre de pestaña/listas, +32 nombre largo (bigramas v89 en +0/+16).
- item.dat: 40 B (nombre 27 B + los 13 B de cola japoneses); descripción u16 en +38 × 32 (japonés: 32 B, +30).
- command.dat: igual que el japonés; nombre y descripción u16 en +16/+18 × 32 en command.STR.
- games.STR: mismas 134 cadenas en el mismo orden.  rpgtitle.STR: campos de 32 B.  teamtitle.dat: 16 B.
El texto actual se decodifica con el registro de bigramas v89 (los códigos no registrados salen como ¤).
Comparación: sin saltos, espacios repetidos, apóstrofos ni comillas; guion = espacio (como en la capa).
Salida: otros_textos.json.
"""
from __future__ import annotations

import collections
import json
import struct
import sys

import comun92 as C
import objetivos as O

HERE = C.HERE
L = 'inazuma1/data_iz/logic/'


def cadena(buf, off):
    if off >= len(buf):
        return b''
    fin = buf.find(b'\0', off)
    return buf[off:fin if fin >= 0 else len(buf)]


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    ob = O.Objetivos()
    cod = ob.codec
    b, e, j = C._abrir(C.BASE), C._abrir(C.EU), C._abrir(C.ORIGINAL)

    def actual(x):
        """Texto actual: bigramas/ancho completo con el códec v89; bytes sueltos como latín de 1 byte
        (nombres ASCII, saltos 0x0A)."""
        out = []
        for k, v in cod.segmentos(x):
            out.append(v if k == 't' else C.decodificar_eu(v).replace('\n', ' ').replace('\r', ' '))
        return ''.join(out)

    def eu(x):
        return C.decodificar_eu(x).replace('\n', r'\n')

    def igual(a, o):
        return C.norm(a.replace('-', ' ')) == C.norm(o.replace('-', ' '))

    res = collections.OrderedDict()

    def comparar(cat, clave, a, o, jp=''):
        d = res.setdefault(cat, dict(total=0, iguales=0, distintos=[], sin_oficial=0, sin_traducir=0))
        if not o.strip() or o.strip() in ('ダミー',) or any('぀' <= ch <= '鿿' for ch in o):
            d['sin_oficial'] += 1
            return
        if not a.strip():
            d['vacio_en_juego'] = d.get('vacio_en_juego', 0) + 1
            return
        d['total'] += 1
        if any('぀' <= ch <= '鿿' for ch in a):
            d['sin_traducir'] += 1
        if igual(a, o):
            d['iguales'] += 1
        else:
            d['distintos'].append(dict(clave=clave, japones=jp, actual=a, oficial=o))

    # unitbase
    U, S = b(L + 'unitbase.dat'), b(L + 'unitbase.STR')
    EU, ES = e('es/' + L + 'unitbase.dat'), e('es/' + L + 'unitbase.STR')
    JU = j(L + 'unitbase.dat')
    vistos = set()
    for i in range((len(U) - 96) // 96 + 1):
        r, q, jr = U[i * 96:(i + 1) * 96], EU[i * 96:(i + 1) * 96], JU[i * 96:(i + 1) * 96]
        if len(r) < 96 or 'ダミー'.encode('cp932') in jr[:48]:
            continue
        jn = jr[:16].split(b'\0')[0].decode('cp932', 'replace')
        largo, corto = eu(q[:32].split(b'\0')[0]), eu(q[32:64].split(b'\0')[0])
        comparar('jugadores_nombre_largo(+32)', i, actual(r[32:64].split(b'\0')[0]), largo, jn)
        comparar('jugadores_nombre_ficha(+0)', i, actual(r[:16].split(b'\0')[0]), corto, jn)
        comparar('jugadores_nombre_pestana(+16)', i, actual(r[16:32].split(b'\0')[0]), corto, jn)
        pa, pe = struct.unpack_from('<H', r, 94)[0], struct.unpack_from('<H', q, 94)[0]
        if pa and pe and pa not in vistos:
            vistos.add(pa)
            comparar('jugadores_descripcion', i, actual(cadena(S, pa * 32)), eu(cadena(ES, pe * 128)), jn)
    # objetos
    I, IS, JI, JIS = b(L + 'item.dat'), b(L + 'item.STR'), j(L + 'item.dat'), j(L + 'item.STR')
    EI, EIS = e('es/' + L + 'item.dat'), e('es/' + L + 'item.STR')
    for i in range(len(I) // 32):
        r, q = I[i * 32:(i + 1) * 32], EI[i * 40:(i + 1) * 40]
        jn = JI[i * 32:i * 32 + 19].split(b'\0')[0].decode('cp932', 'replace')
        if not jn:
            continue
        comparar('objetos_nombre', i, actual(r[:19].split(b'\0')[0]), eu(q[:27].split(b'\0')[0]), jn)
        pa, pe = struct.unpack_from('<H', r, 30)[0], struct.unpack_from('<H', q, 38)[0]
        if pa and pe:
            comparar('objetos_descripcion', i, actual(cadena(IS, pa * 32)), eu(cadena(EIS, pe * 32)), jn)
    # técnicas
    D, CS, JCS = b(L + 'command.dat'), b(L + 'command.STR'), j(L + 'command.STR')
    ED, ECS = e('es/' + L + 'command.dat'), e('es/' + L + 'command.STR')
    for i in range(len(D) // 24):
        for k, cat in ((16, 'tecnicas_nombre'), (18, 'tecnicas_descripcion')):
            pa, pe = struct.unpack_from('<H', D, i * 24 + k)[0], struct.unpack_from('<H', ED, i * 24 + k)[0]
            if pa and pe:
                jn = cadena(JCS, pa * 32).decode('cp932', 'replace') if k == 16 else ''
                comparar(cat, i, actual(cadena(CS, pa * 32)), eu(cadena(ECS, pe * 32)), jn)
    # menús de juego (games.STR)
    G, EG = b(L + 'games.STR'), e('es/' + L + 'games.STR')
    g = [x for x in G[32:].split(b'\0') if x]
    eg = [x for x in EG[32:].split(b'\0') if x]
    if len(g) == len(eg):
        for i, (x, y) in enumerate(zip(g, eg)):
            comparar('games_STR', i, actual(x), eu(y))
    # títulos
    R, ER = b(L + 'rpgtitle.STR'), e('es/' + L + 'rpgtitle.STR')
    for i in range(len(R) // 32):
        x, y = R[i * 32:(i + 1) * 32].split(b'\0')[0], ER[i * 32:(i + 1) * 32].split(b'\0')[0]
        if x or y:
            comparar('rpgtitle_STR', i, actual(x), eu(y))
    T, ET = b(L + 'teamtitle.dat'), e('es/' + L + 'teamtitle.dat')
    for i in range(len(T) // 16):
        x, y = T[i * 16:i * 16 + 10].split(b'\0')[0], ET[i * 16:i * 16 + 10].split(b'\0')[0]
        if x or y:
            comparar('teamtitle_dat', i, actual(x), eu(y))
    resumen = {k: dict(total=v['total'], iguales=v['iguales'], distintos=len(v['distintos']),
                       sin_oficial=v['sin_oficial'], actual_en_japones=v['sin_traducir'],
                       vacio_en_juego=v.get('vacio_en_juego', 0)) for k, v in res.items()}
    (HERE / 'otros_textos.json').write_text(json.dumps(dict(resumen=resumen, detalle=res), ensure_ascii=False,
                                                       indent=1), encoding='utf-8')
    print(json.dumps(resumen, ensure_ascii=False, indent=1))
    for k, v in res.items():
        for x in v['distintos'][:4]:
            print(k, x)


if __name__ == '__main__':
    main()
