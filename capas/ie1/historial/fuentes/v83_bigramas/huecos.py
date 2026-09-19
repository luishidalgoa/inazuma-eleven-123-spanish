"""v83 · bigramas (SOLO INVESTIGACIÓN): huecos en font/FONT12.bcfnt para glifos dobles.

Cruza el CMAP de FONT12 (v81) con sjis_usados.json (escaneo_sjis.py):
  - glifos, capacidad de las hojas y celdas libres;
  - códigos Shift-JIS de doble byte (cp932) con glifo que no aparecen en ningún texto:
      libre_fiable   ausente de las fuentes de texto (STR/dat/txt/eventos)
      libre_total    además ausente del escaneo ruidoso (texturas/CRO/code.bin con kana)
    separados por bloque (kanji nivel 1 0x889F-0x9872, nivel 2 0x989F-0xEAA4, otros).
Salida: huecos.json
"""
from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[5]
sys.path.insert(0, str(ROOT / 'tools'))
from bcfnt import BCFNT  # noqa: E402

FONT = ROOT / 'work/ie1/capas/fuentes/glifos_eu/extra/font/FONT12.bcfnt'   # = FONT12 de v81 (mismo SHA-1)


def bloque(code):
    if 0x889F <= code <= 0x9872:
        return 'kanji_n1'
    if 0x989F <= code <= 0xEAA4:
        return 'kanji_n2'
    if 0xED40 <= code <= 0xEEFC or 0xFA40 <= code <= 0xFC4B:
        return 'ibm_nec'
    if 0x8740 <= code <= 0x879C:
        return 'nec_especiales'
    return 'simbolos_kana_latin'


def main():
    b = BCFNT(FONT.read_bytes())
    t = b.tglp()
    cmap = {}
    for c in b.cmaps():
        cmap.update(c['entries'])
    usados = json.loads((HERE / 'sjis_usados.json').read_text(encoding='utf-8'))
    fiable = {int(k, 16) for k in usados['fiable']}
    ruido = {int(k, 16) for k in usados['ruidoso']}
    con_glifo = {}
    for cp in cmap:
        if cp < 0x80:
            continue
        try:
            enc = chr(cp).encode('cp932')
        except UnicodeEncodeError:
            continue
        if len(enc) == 2:
            con_glifo[int.from_bytes(enc, 'big')] = cp
    libres_f = {c for c in con_glifo if c not in fiable}
    libres_t = {c for c in libres_f if c not in ruido}
    por = lambda s: dict(collections.Counter(bloque(c) for c in s))
    cap = t['nsheets'] * t['ncols'] * t['nrows']
    out = dict(
        fuente=str(FONT.relative_to(ROOT)),
        glifos=len(set(cmap.values())), codepoints=len(cmap), hojas=t['nsheets'],
        celdas_por_hoja=t['ncols'] * t['nrows'], capacidad=cap, celdas_libres=cap - len(set(cmap.values())),
        celda=f"{t['cell_w']}x{t['cell_h']}", hoja=f"{t['sheet_w']}x{t['sheet_h']}", fmt=t['fmt'],
        bytes_por_hoja=t['sheet_size'],
        cmap_bloques=[(hex(c['begin']), hex(c['end']), c['method'], c['n']) for c in b.cmaps()],
        sjis_doble_con_glifo=len(con_glifo), sjis_doble_con_glifo_por_bloque=por(con_glifo),
        usados_fiable_con_glifo=len(set(con_glifo) & fiable),
        usados_cualquiera_con_glifo=len(set(con_glifo) & (fiable | ruido)),
        libre_fiable=len(libres_f), libre_fiable_por_bloque=por(libres_f),
        libre_total=len(libres_t), libre_total_por_bloque=por(libres_t),
        libre_total_n2_muestra=''.join(chr(con_glifo[c]) for c in sorted(libres_t) if bloque(c) == 'kanji_n2')[:120],
        libre_total_codigos=[f'{c:04X}' for c in sorted(libres_t)],
        distintos_por_juego=usados.get('distintos_por_juego'),
        ruidoso_por_familia=usados.get('ruidoso_por_familia'),
        fiable_por_familia={k: len(v) for k, v in usados['fiable_por_familia'].items()},
    )
    (HERE / 'huecos.json').write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
    for k, v in out.items():
        if k != 'libre_total_codigos':
            print(k, v)


if __name__ == '__main__':
    main()
