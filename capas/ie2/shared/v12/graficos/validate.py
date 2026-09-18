"""Validación offline de v12/graficos (runtime_verified=false).

- extra/ = exactamente las rutas de informe.json, todas entradas existentes de inazuma2/data_iz/.
- Cada .arc: misma tabla ARCV que el japonés y que su base (v06 > v03 > jp), misma envoltura SSZL,
  solo cambian las texturas declaradas, metadata CTPK idéntica y códec ida y vuelta.
- Teclado: hira01/kana01 iguales píxel a píxel (salvo cuantización) al teclado latino de IE1 y con la
  flecha de borrar en su celda (x 200-224, y 60-80) en los dos modos.
- Los logos se leen de fuentes/ (no de Descargas).
Uso: python validate.py
"""
import json
import sys

import numpy as np

import base12 as B
import planes_v12 as P

C = B.C


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    inf = json.loads((B.HERE / 'informe.json').read_text(encoding='utf-8'))['ficheros']
    problemas, esperadas = [], set()
    known = set(C.jp().idx)
    for r in inf:
        ruta = r['ruta']
        esperadas.add(ruta)
        if ruta not in known:
            problemas.append(f'{ruta}: no es entrada del archive')
        nuevo = (B.EXTRA / ruta).read_bytes()
        orig = C.jp().get(ruta)
        base = B.base_arc(ruta)
        if nuevo == base:
            problemas.append(f'{ruta}: igual a la base')
        if (nuevo[:4] == b'SSZL') != (orig[:4] == b'SSZL'):
            problemas.append(f'{ruta}: envoltura SSZL distinta')
        a, b, j = C.U.unwrap(base), C.U.unwrap(nuevo), C.U.unwrap(orig)
        if len(a) != len(b) or C.U.entries(a) != C.U.entries(b) or C.U.entries(j) != C.U.entries(b):
            problemas.append(f'{ruta}: ARCV distinto')
            continue
        decl = {c['textura'] for c in r['cambios']}
        for off, ln, _ in C.U.entries(a):
            x, y = a[off:off + ln], b[off:off + ln]
            if x == y:
                continue
            nombre = C.T.metadata(x)[0] if x[:4] == b'CTPK' else None
            if nombre not in decl:
                problemas.append(f'{ruta}: entrada no declarada {nombre}')
            elif C.T.metadata(x) != C.T.metadata(y):
                problemas.append(f'{ruta}:{nombre}: metadata')
            elif C.T.encode(y, C.T.decode(y)) != y:
                problemas.append(f'{ruta}:{nombre}: códec')
    # teclado
    nb = B.texturas_de((B.EXTRA / 'inazuma2/data_iz/a_menu/name_b.arc').read_bytes())
    ie1 = B.texturas_de(C.Archivo(B.IE1_FA).get('inazuma1/data_iz/a_menu/name_b.arc'))
    for k in ('hira01', 'kana01'):
        x = np.array(C.decodificar(nb[f'ie02_menu_name_b_font_{k}.tga']).convert('RGBA')).astype(int)
        y = np.array(C.decodificar(ie1[f'ie01_menu_name_b_font_{k}.tga']).convert('RGBA')).astype(int)
        vis = (x[..., 3] > 0) | (y[..., 3] > 0)
        if np.abs(x - y)[vis].max() > 17:
            problemas.append(f'teclado {k}: difiere del de IE1')
        if (x[60:80, 200:224, 3] > 0).sum() < 10:
            problemas.append(f'teclado {k}: falta la flecha de borrar')
    # menu_slot: font01 idéntica a la de v13/cro_ranura, y v13 solo cambia font01 respecto a v06
    ruta = 'inazuma2/data_iz/a_menu/menu_slot.arc'
    v13 = B.HERE.parents[1] / 'v13/cro_ranura/extra' / ruta
    t13, t12, t06 = (B.texturas_de(x) for x in (v13.read_bytes(), (B.EXTRA / ruta).read_bytes(), B.base_arc(ruta)))
    if t12['ie02_slot_b_font01.tga'] != t13['ie02_slot_b_font01.tga']:
        problemas.append('menu_slot: font01 distinta de v13')
    otras = sorted(n for n in t13 if t13[n] != t06[n] and n != 'ie02_slot_b_font01.tga')
    if otras:
        problemas.append(f'v13 cambia además {otras}: no integradas')
    for f in ('logo_tormenta_de_fuego.png', 'logo_ventisca_eterna.png'):
        if not (B.FUENTES / f).exists():
            problemas.append(f'falta fuentes/{f}')
    escritos = {str(p.relative_to(B.EXTRA)).replace('\\', '/') for p in B.EXTRA.rglob('*') if p.is_file()}
    if escritos != esperadas:
        problemas.append(f'extra/ no coincide con el informe: {sorted(escritos ^ esperadas)}')
    if any(not e.startswith('inazuma2/data_iz/') for e in escritos):
        problemas.append('rutas fuera de inazuma2/data_iz')
    res = dict(ficheros=len(escritos), texturas=sum(len(r['cambios']) for r in inf), problemas=problemas,
               resultado='PASS' if not problemas else 'FAIL', runtime_verified=False)
    (B.HERE / 'validate.json').write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(res, ensure_ascii=False, indent=1))
    sys.exit(1 if problemas else 0)


if __name__ == '__main__':
    main()
