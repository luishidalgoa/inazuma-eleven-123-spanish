"""Validación de IE2 v03 · tablas B (extra/ frente a probe_ie2_v02).

- Solo cambian los huecos declarados en informe.json (cambios); el resto del fichero es idéntico.
- Tamaño idéntico en los formatos fijos; ShopName.dat conserva el número de líneas.
- team.pkb vuelve a leerse con el índice PackNum (tipo 3, 320 B por registro) de la base.
- Cada hueco = cuerpo de ancho completo + NUL de relleno; se descodifica al español declarado;
  todos los caracteres tienen glifo en FONT12.bcfnt; sin bigramas (solo cp932 estándar); %s como el japonés.
Uso: python -X utf8 validate.py  (escribe validate.json)
"""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import apply as A  # noqa: E402

K = A.K


def huecos(fichero: str, clave, data: bytes):
    """[(offset, tamaño)] del texto declarado."""
    if fichero == 'logic/team.pkb':
        h = A.get('logic/team.pkh')
        n = struct.unpack_from('<H', h, 0x16)[0]
        ids = list(struct.unpack_from(f'<{n}I', h, 0x30))
        return [(ids.index(clave) * 320, 32)]
    if fichero == 'logic/schinfo.dat':
        return [(clave * 32, 19)]
    if fichero.startswith('logic/BinderData'):
        return [(clave * 28 + 4, 20)]
    if fichero == 'logic/teamtitle.dat':
        return [(clave * 32, 26)]
    if fichero == 'logic/clubinfo.dat':
        return [(clave * 32, 19)]
    if fichero == 'logic/livetalk.dat':
        return [(clave * 16, 16)]
    if fichero == 'logic/ClearCondition.dat':
        return [(clave * 81 + 1, 80)]
    if fichero == 'logic/gamerule.dat':
        return [(clave * 0x120 + 0x20, 0x100)]
    if fichero == 'logic/movie_view.dat':
        return [(clave * 96 + 57, 39)]
    if fichero == 'script/blogpost.dat':
        i, parte = clave.split('.')
        return [(int(i) * 292 + 2, 66)] if parte == 'titulo' else [(int(i) * 292 + 68, 224)]
    if fichero == 'script/blogres.dat':
        return [(clave * 264 + 3, 261)]
    raise KeyError(fichero)


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    inf = json.loads((HERE / 'informe.json').read_text(encoding='utf-8'))
    errores, resumen = [], {}
    por_fichero = {}
    for c in inf['cambios']:
        por_fichero.setdefault(c['fichero'], []).append(c)
    salidas = {p.relative_to(HERE / 'extra' / A.RAIZ).as_posix()
               for p in (HERE / 'extra').rglob('*') if p.is_file()}
    if salidas != set(por_fichero):
        errores.append(f'salidas {sorted(salidas)} != declaradas {sorted(por_fichero)}')
    for rel, lista in sorted(por_fichero.items()):
        base = A.get(rel)
        nuevo = (HERE / 'extra' / A.RAIZ / rel).read_bytes()
        cuenta = 0
        if rel == 'logic/ShopName.dat':
            lb, ln = base.split(b'\r\n'), nuevo.split(b'\r\n')
            if len(lb) != len(ln):
                errores.append(f'{rel}: líneas {len(lb)} -> {len(ln)}')
            dec = {c['clave']: c for c in lista}
            for i, (x, y) in enumerate(zip(lb, ln)):
                if i in dec:
                    if A.desde(y) != dec[i]['espanol'] or K.M.sin_glifo(y):
                        errores.append(f'{rel}[{i}] no descodifica')
                    cuenta += 1
                elif x != y:
                    errores.append(f'{rel}[{i}] cambia sin declarar')
            resumen[rel] = {'lineas': len(ln), 'textos': cuenta, 'bytes': [len(base), len(nuevo)]}
            continue
        if len(base) != len(nuevo):
            errores.append(f'{rel}: tamaño {len(base)} -> {len(nuevo)}')
            continue
        mascara = bytearray(len(base))
        for c in lista:
            for off, size in huecos(rel, c['clave'], base):
                mascara[off:off + size] = b'\1' * size
                campo = nuevo[off:off + size]
                cuerpo = campo.split(b'\0')[0]
                if campo[len(cuerpo):] != bytes(size - len(cuerpo)):
                    errores.append(f'{rel} {c["clave"]}: relleno no nulo')
                try:
                    texto = A.desde(cuerpo)
                except UnicodeDecodeError:
                    errores.append(f'{rel} {c["clave"]}: no es cp932')
                    continue
                if texto != c['espanol']:
                    errores.append(f'{rel} {c["clave"]}: {texto!r} != {c["espanol"]!r}')
                if K.M.sin_glifo(cuerpo.replace(bytes([10]), b'')):
                    errores.append(f'{rel} {c["clave"]}: sin glifo')
                jp = A.visible_jp(A.sj(base[off:off + size]))
                if K.M.pct(texto) != K.M.pct(jp):
                    errores.append(f'{rel} {c["clave"]}: %s/%d distinto del japonés')
                cuenta += 1
        fuera = [i for i in range(len(base)) if base[i] != nuevo[i] and not mascara[i]]
        if fuera:
            errores.append(f'{rel}: {len(fuera)} bytes cambiados fuera de los huecos (primero {fuera[0]:#x})')
        resumen[rel] = {'textos': cuenta, 'bytes_cambiados': sum(x != y for x, y in zip(base, nuevo)),
                        'tamano': len(nuevo)}
    # team.pkb: índice de la base sigue sirviendo
    pkh = A.get('logic/team.pkh')
    n, rs = struct.unpack_from('<H', pkh, 0x16)[0], struct.unpack_from('<I', pkh, 0x1c)[0]
    team = (HERE / 'extra' / A.RAIZ / 'logic/team.pkb').read_bytes()
    if n * rs != len(team):
        errores.append('team.pkb no encaja con team.pkh')
    for k in range(n):
        nombre = team[k * rs:k * rs + 32].split(b'\0')[0]
        if len(nombre) > 18:
            errores.append(f'team.pkb registro {k}: {len(nombre)} B')
    resumen['logic/team.pkb']['packnum'] = f'{n} registros de {rs} B; team.pkh sin cambios (no se escribe)'
    out = {'ok': not errores, 'errores': errores, 'resumen': resumen}
    (HERE / 'validate.json').write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(out, ensure_ascii=False, indent=1))
    sys.exit(0 if not errores else 1)


if __name__ == '__main__':
    main()
