"""IE2 v13 · titulos: validación offline (runtime_verified=false). Rápida: no rehace la partición.

- extra/ contiene solo inazuma2/data_iz/logic/rpgtitle.STR, del mismo tamaño que el de probe_ie2_v10.
- Solo cambian los registros marcados «cambia» en informe.json; el resto, byte a byte como v10.
- Cada registro cambiado: <= 18 B (9 casillas de 2 B), relleno NUL hasta 32 B, decodifica (códec del
  registro v08) al texto elegido, que es el oficial NDS o el oficial sin «Equipo »/artículo, y es más completo
  que el de v10. Cada código es una letra nativa de ancho completo o una casilla existente del registro v08
  dibujada en FONT12, FONT8 y FONT12T y usada ya en nombres; ningún código nuevo.
- Las BCFNT de probe_ie2_v10 son las del registro v08 (mismo sha256): no hay que tocar fuentes.
Salida: validacion.json. Código 1 si falla algo.
"""
from __future__ import annotations

import hashlib
import json
import sys

import apply as A

M, K = A.M, A.K


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    problemas = []
    inf = json.loads((A.HERE / 'informe.json').read_text(encoding='utf-8'))
    reg = json.loads(A.K.REG07.read_text(encoding='utf-8'))
    por_sjis = {e['sjis']: e for e in reg['bigramas']}
    codec = A.A89.Codec(reg['bigramas'])
    escritos = [p for p in (A.HERE / 'extra').rglob('*') if p.is_file()]
    if [p.relative_to(A.HERE / 'extra').as_posix() for p in escritos] != [A.RUTA]:
        problemas.append(f'extra/ inesperado: {escritos}')
    v10a = M.Archivo(A.CAND)
    v10 = v10a.get(A.RUTA)
    nuevo = A.SALIDA.read_bytes()
    if len(nuevo) != len(v10):
        problemas.append('tamaño distinto')
    for f in K.FUENTES:
        if hashlib.sha256(v10a.get(f)).hexdigest() != reg['fuentes_dibujadas'][f]:
            problemas.append(f'{f} de v10 no es la del registro v08')
    cambian = {f['indice']: f for f in inf['titulos'] if f.get('cambia')}
    for i in range(len(v10) // A.REG):
        a, b = v10[i * A.REG:(i + 1) * A.REG], nuevo[i * A.REG:(i + 1) * A.REG]
        if i not in cambian:
            if a != b:
                problemas.append(f'{i}: cambio no declarado')
            continue
        f = cambian[i]
        cuerpo = b.split(b'\0')[0]
        if b[len(cuerpo):] != bytes(A.REG - len(cuerpo)) or len(cuerpo) > 2 * A.CASILLAS or len(cuerpo) % 2:
            problemas.append(f'{i}: longitud/relleno')
        if codec.texto(cuerpo) != f['elegido']:
            problemas.append(f'{i}: no decodifica a {f["elegido"]}')
        formas = [f['oficial']] + [f['oficial'][len(x):] for x in A.ARTICULOS if f['oficial'].startswith(x)]
        if f['elegido'] not in formas:
            problemas.append(f'{i}: {f["elegido"]} no es forma oficial')
        if len(f['elegido']) <= len(f['actual'].replace('.', '')):
            problemas.append(f'{i}: no es más completo que {f["actual"]}')
        for k in range(0, len(cuerpo), 2):
            c = cuerpo[k:k + 2]
            e = por_sjis.get(c.hex().upper())
            if e is None:
                try:
                    ch = c.decode('cp932')
                except UnicodeDecodeError:
                    problemas.append(f'{i}: código {c.hex()} desconocido')
                    continue
                if not (0xFF01 <= ord(ch) <= 0xFF5E or len(codec.texto(c)) == 1):
                    problemas.append(f'{i}: {c.hex()} no es letra nativa')
                continue
            if not A.TRES <= set(e['fuentes']):
                problemas.append(f'{i}: {e["sjis"]} sin dibujo en las tres fuentes')
            if not any(x.startswith('nombre') for x in e.get('campos', [])):
                problemas.append(f'{i}: {e["sjis"]} no se usa en nombres')
    res = dict(archivo=A.RUTA, cambiados={i: f['elegido'] for i, f in cambian.items()},
               problemas=problemas, resultado='PASS' if not problemas else 'FAIL', runtime_verified=False)
    (A.HERE / 'validacion.json').write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return 1 if problemas else 0


if __name__ == '__main__':
    sys.exit(main())
