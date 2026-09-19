"""Inventario de texto japonés (Shift-JIS) en los ficheros de datos de inazuma2/data_iz (IE2 v03, tablas B).

Recorre logic/, script/ y los ficheros sueltos no gráficos ni de sonido; descomprime LZ10 y abre PackNum.
Uso: python -X utf8 survey.py [--json salida]
"""
from __future__ import annotations

import json
import re
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import comun_v03 as K  # noqa: E402
from ie123kit.nucleo.compresion.lz10 import decompress  # noqa: E402
from ie123kit.nucleo.eventos.packnum import parse_index  # noqa: E402

RAIZ = 'inazuma2/data_iz/'
EXCLUIR_DIRS = {'pic3d', 'pic2d', 'model', 'map2d', 'movie', 'spr', 'obj2d', 'face2d', 'font', 'effect3d',
                'tex3ds_game', 'sound'}
YA_HECHOS = {'script/eve.pkb', 'script/eve.pkh', 'script/mch.pkb', 'script/mch.pkh'}
JAP = re.compile(r'[぀-ヿ一-鿿]')


def runs(b: bytes, minimo=2):
    """[(offset, texto)] de tramos Shift-JIS de doble byte con algún carácter japonés."""
    out, i, n = [], 0, len(b)
    while i < n - 1:
        j, chars = i, []
        while j < n - 1:
            c = b[j]
            if (0x81 <= c <= 0x9F or 0xE0 <= c <= 0xFC) and (0x40 <= b[j + 1] <= 0xFC and b[j + 1] != 0x7F):
                try:
                    chars.append(b[j:j + 2].decode('cp932'))
                except UnicodeDecodeError:
                    break
                j += 2
            else:
                break
        if len(chars) >= minimo and JAP.search(''.join(chars)):
            out.append((i, ''.join(chars)))
            i = j
        else:
            i += 1
    return out


def piezas(rel: str, data: bytes, get):
    """[(subclave, bytes)] a analizar."""
    if rel.endswith('.pkh'):
        return []
    if rel.endswith('.pkb'):
        pkh = get(RAIZ + rel[:-1] + 'h')
        out = []
        for eid, o, s in parse_index(pkh):
            c = data[o:o + s]
            if c[:1] == b'\x10':
                try:
                    c = decompress(c)
                except Exception:
                    pass
            out.append((str(eid), c))
        return out
    if data[:1] == b'\x10' and len(data) > 4:
        try:
            d = decompress(data)
            if len(d) == struct.unpack_from('<I', data)[0] >> 8:
                return [('lz10', d)]
        except Exception:
            pass
    return [('', data)]


def inventario():
    get = K.base()
    res = {}
    for k in sorted(get.indice):
        if not k.startswith(RAIZ):
            continue
        rel = k[len(RAIZ):]
        top = rel.split('/')[0]
        if top in EXCLUIR_DIRS or top.startswith('a_') or rel in YA_HECHOS:
            continue
        data = get(k)
        n, ej, sub = 0, [], 0
        for clave, d in piezas(rel, data, get):
            r = runs(d)
            if r:
                sub += 1
            n += len(r)
            ej.extend(t for _, t in r[:3])
        if n:
            res[rel] = {'tramos': n, 'piezas_con_texto': sub, 'bytes': len(data), 'ejemplos': ej[:6]}
    return res


if __name__ == '__main__':
    inv = inventario()
    for k, v in inv.items():
        print(f"{k:45s} {v['tramos']:6d} {v['piezas_con_texto']:4d}  {' / '.join(v['ejemplos'][:4])}")
    if '--json' in sys.argv:
        Path(sys.argv[sys.argv.index('--json') + 1]).write_text(json.dumps(inv, ensure_ascii=False, indent=1),
                                                             encoding='utf-8')
