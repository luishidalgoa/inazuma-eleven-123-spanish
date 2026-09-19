"""Validación offline de v03/graficos (runtime_verified=false).

- extra/ contiene exactamente las rutas de informe.json (+ pkh de paquetes).
- .arc: unwrap ida y vuelta, misma tabla ARCV; solo cambian las texturas declaradas; metadata CTPK
  idéntica y códec ida y vuelta; SSZL si el original lo era.
- sprites: decodifican con las mismas medidas que el japonés.
Uso: python validate.py
"""
import json
import sys

import comun as C
from apply import dec_pac


def main():
    inf = json.loads((C.HERE / 'informe.json').read_text(encoding='utf-8'))
    jp = C.jp()
    problemas, esperadas = [], set()
    for r in inf:
        ruta = r['ruta']
        esperadas.add(ruta)
        nuevo = (C.EXTRA / ruta).read_bytes()
        orig = jp.get(ruta)
        if r['clase'] == 'textura':
            if (nuevo[:4] == b'SSZL') != (orig[:4] == b'SSZL'):
                problemas.append(f'{ruta}: envoltura SSZL distinta')
            a, b = C.U.unwrap(orig), C.U.unwrap(nuevo)
            if len(a) != len(b) or C.U.entries(a) != C.U.entries(b):
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
        elif r['clase'] == 'sprite_nds':
            if dec_pac(orig).size != dec_pac(nuevo).size:
                problemas.append(f'{ruta}: medidas')
        elif r['clase'] == 'paquete_nds':
            esperadas.add(ruta[:-1] + 'h')
    escritos = {str(p.relative_to(C.EXTRA)).replace('\\', '/') for p in C.EXTRA.rglob('*') if p.is_file()}
    if escritos != esperadas:
        problemas.append(f'extra/ no coincide con el informe: {sorted(escritos ^ esperadas)[:10]}')
    fuera = [e for e in escritos if not e.startswith('inazuma2/data_iz/')]
    if fuera:
        problemas.append(f'rutas fuera de inazuma2/data_iz: {fuera}')
    res = dict(ficheros=len(escritos), problemas=problemas, resultado='PASS' if not problemas else 'FAIL',
               runtime_verified=False)
    (C.HERE / 'validate.json').write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(res, ensure_ascii=False, indent=1))
    sys.exit(1 if problemas else 0)


if __name__ == '__main__':
    main()
