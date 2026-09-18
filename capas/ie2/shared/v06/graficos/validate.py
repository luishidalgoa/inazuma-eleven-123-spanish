"""Validación offline de v06/graficos (runtime_verified=false).

- extra/ contiene exactamente las rutas de informe.json, todas bajo inazuma2/data_iz/.
- Cada .arc: unwrap ida y vuelta, misma tabla ARCV que el japonés, envoltura SSZL igual a la del japonés.
- Respecto a su base (v03 si existe, si no el japonés) solo cambian las texturas declaradas; metadata CTPK
  idéntica y códec ida y vuelta.
- Ningún fichero de extra/ es idéntico a su base (el overlay solo trae mejoras).
Uso: python validate.py
"""
import json
import sys

import base as B

C = B.C


def main():
    inf = json.loads((B.HERE / 'informe.json').read_text(encoding='utf-8'))
    problemas, esperadas = [], set()
    for r in inf:
        ruta = r['ruta']
        esperadas.add(ruta)
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
    escritos = {str(p.relative_to(B.EXTRA)).replace('\\', '/') for p in B.EXTRA.rglob('*') if p.is_file()} \
        if B.EXTRA.exists() else set()
    if escritos != esperadas:
        problemas.append(f'extra/ no coincide con el informe: {sorted(escritos ^ esperadas)[:10]}')
    fuera = [e for e in escritos if not e.startswith('inazuma2/data_iz/')]
    if fuera:
        problemas.append(f'rutas fuera de inazuma2/data_iz: {fuera}')
    res = dict(ficheros=len(escritos), texturas=sum(len(r['cambios']) for r in inf), problemas=problemas,
               resultado='PASS' if not problemas else 'FAIL', runtime_verified=False)
    (B.HERE / 'validate.json').write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(res, ensure_ascii=False, indent=1))
    sys.exit(1 if problemas else 0)


if __name__ == '__main__':
    main()
