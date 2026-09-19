"""IE2 v03 · validación independiente de romfs/cro/ina_main2.cro frente a la base y a literales.json.

Comprueba: mismo tamaño; solo cambian los huecos declarados; cada hueco = texto no vacío + NUL de relleno,
texto <= límite (bytes del japonés o hueco acotado) e idéntico a la codificación de la tabla; mismos %s/%d;
glifos en FONT12.NFTR de inazuma2; ninguna referencia dentro de un hueco; cabecera, segmentos, importaciones,
exportaciones y relocaciones intactos; reutilizaciones de IE1 iguales al texto de probe_ie1_v89; sha256 del informe.

Uso: python -X utf8 validate.py
"""
from __future__ import annotations

import json
import struct
import sys

import comun_cro as C


# Tablas CRO3 (offset, número/tamaño) y tamaño de entrada; 1 = el campo ya es un tamaño en bytes.
TABLAS = {0xC0: 1, 0xC8: 12, 0xD0: 8, 0xD8: 4, 0xE0: 1, 0xE8: 8, 0xF0: 20, 0xF8: 12, 0x100: 8,
          0x108: 8, 0x110: 8, 0x118: 1, 0x120: 8, 0x128: 12, 0x130: 12}


def tablas_cro(d: bytes):
    """Cabecera + tablas de segmentos, exportaciones, importaciones, parches y relocaciones."""
    rangos = [(0, 0x138)]
    for campo, tam in TABLAS.items():
        o, n = struct.unpack_from('<II', d, campo)
        if n:
            rangos.append((o, o + n * tam))
    return rangos


def main():
    base = C.BASE.read_bytes()
    out = C.OUT.read_bytes()
    t = C.tabla()
    v89, ie1o = C.IE1_V89.read_bytes(), C.IE1_ORIG.read_bytes()
    refs = C.Refs(base)
    fallos = []
    assert len(out) == len(base), 'tamaño distinto'

    huecos = set()
    for e in t['literales']:
        o, cap = int(e['offset'], 16), C.capacidad(e)
        k = e['offset']
        hueco = out[o:o + cap]
        cuerpo = hueco.split(b'\0', 1)[0]
        if hueco[len(cuerpo):] != b'\0' * (cap - len(cuerpo)):
            fallos.append(f'{k}: relleno no NUL')
        if not cuerpo:
            fallos.append(f'{k}: vacío')
        if len(cuerpo) > C.limite(e):
            fallos.append(f'{k}: {len(cuerpo)} B > {C.limite(e)}')
        if len(cuerpo) > len(C.jp_bytes(e)) and e.get('clase') != 'formato':
            fallos.append(f'{k}: supera los bytes del japonés')
        if cuerpo != C.codificar(e):
            fallos.append(f'{k}: no coincide con la tabla')
        if base[o:o + len(C.jp_bytes(e))] != C.jp_bytes(e):
            fallos.append(f'{k}: el japonés de la tabla no está en la base')
        txt = cuerpo.decode('cp932')
        if C.FMT.findall(txt) != C.FMT.findall(e['japones']):
            fallos.append(f'{k}: especificadores printf distintos')
        if C.sin_glifo(cuerpo):
            fallos.append(f'{k}: sin glifo {C.sin_glifo(cuerpo)}')
        dentro = [x for x in refs.targets | refs.reltargets if o < x < o + cap - 1]
        if dentro:
            fallos.append(f'{k}: referencias dentro {[hex(x) for x in dentro]}')
        if e['origen'] == 'ie1_v89':
            i = int(e['ie1'], 16)
            if C.a_espanol(C.cuerpo(v89, i)) != e['espanol']:
                fallos.append(f'{k}: no es el texto de IE1 v89 en {e["ie1"]}')
            if C.cuerpo(v89, i) == C.cuerpo(ie1o, i):
                fallos.append(f'{k}: IE1 {e["ie1"]} no está traducido en v89')
        solape = huecos.intersection(range(o, o + cap))
        if solape:
            fallos.append(f'{k}: solapa otro hueco')
        huecos.update(range(o, o + cap))

    cambios = [i for i in range(len(base)) if base[i] != out[i]]
    fuera = [i for i in cambios if i not in huecos]
    if fuera:
        fallos.append(f'{len(fuera)} bytes cambiados fuera de los huecos (primero {fuera[0]:#x})')
    for a, b in tablas_cro(base):
        if base[a:b] != out[a:b]:
            fallos.append(f'tabla CRO {a:#x}-{b:#x} modificada')
    ro, rn = struct.unpack_from('<II', base, 0x128)
    if base[ro:ro + rn * 12] != out[ro:ro + rn * 12]:
        fallos.append('tabla de relocaciones modificada')

    inf = json.loads(C.INFORME.read_text(encoding='utf-8'))
    if inf['salida_sha256'] != C.sha(out) or inf['base_sha256'] != C.sha(base):
        fallos.append('sha256 distinto del informe')

    res = dict(ok=not fallos, fallos=fallos, literales=len(t['literales']), bytes_cambiados=len(cambios),
               relocaciones=rn, salida_sha256=C.sha(out))
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return 0 if not fallos else 1


if __name__ == '__main__':
    sys.exit(main())
