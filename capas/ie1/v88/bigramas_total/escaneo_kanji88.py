"""v88 (copia de v85/bigramas_sonda/escaneo_kanji.py con búsqueda solapada) · sonda de bigramas: comprobación estricta de que ciertos códigos Shift-JIS no aparecen en ningún texto.

Complementa work/ie1/capas/v83/bigramas/escaneo_sjis.py (que solo contaba rachas de >= 2 caracteres de
doble byte): aquí se busca cada código candidato byte a byte y se valida la alineación de cada aparición
retrocediendo hasta el NUL anterior (o 512 B) y tokenizando Shift-JIS hacia delante. Una aparición
alineada cuenta como:
  texto    si el fichero es fuente de texto (misma regla que v83: .STR/.dat/.txt/.tbl/.itx/.ini y
           trozos de .pkb de script/ y logic/), sea cual sea su contexto (también un kanji suelto);
  binario  si está en otro fichero (texturas, CRO, code.bin) y forma parte de una racha de >= 2 códigos
           de doble byte con al menos un kana (contexto textual); el resto es ruido de datos.
Recorre el archive.fa indicado (los cuatro juegos: inazuma1, inazuma2, inazuma3, inazuma3_ogre, más
menu/, import/, message/), las CRO de base_3ds, la ina_main1.cro de la candidata y code.bin.

Uso: python -X utf8 escaneo_kanji.py --fa <archive.fa> --codigos 9A40,9A41 --salida <json>
     python -X utf8 escaneo_kanji.py --fa <archive.fa> --pool 80 --salida <json>
       (--pool N: los N primeros kanji de nivel 2 de huecos.json → libre_total_codigos)
"""
from __future__ import annotations

import argparse
import collections
import importlib.util
import json
import re
import sys
from multiprocessing import Pool
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
V83 = ROOT / 'work/ie1/capas/v83/bigramas'
_spec = importlib.util.spec_from_file_location('escaneo_sjis_v83', V83 / 'escaneo_sjis.py')
E = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(E)

LEAD = set(range(0x81, 0xA0)) | set(range(0xE0, 0xFD))
KANA = E.KANA
PATRON = None
CODIGOS = ()
CONJUNTO = frozenset()


def _init(codigos):
    global PATRON, CODIGOS, CONJUNTO
    CODIGOS = tuple(codigos)
    CONJUNTO = frozenset(codigos)
    PATRON = re.compile(b'|'.join(re.escape(c.to_bytes(2, 'big')) for c in CODIGOS))


def tokens(buf, ini, fin):
    """Posiciones de inicio de token de buf[ini:fin] y el código de cada uno (None si es de 1 byte)."""
    i, out = ini, []
    while i < fin:
        b = buf[i]
        if b in LEAD and i + 1 < len(buf):
            out.append((i, b << 8 | buf[i + 1]))
            i += 2
        else:
            out.append((i, None))
            i += 1
    return out


def alineada(buf, p):
    ini = buf.rfind(b'\0', max(0, p - 512), p) + 1 if p else 0
    if ini == 0 and p > 512:
        ini = p - 512
    toks = tokens(buf, ini, p + 2)
    starts = {s: c for s, c in toks}
    if p not in starts:
        return False, 0, 0
    # racha de doble byte alrededor (hacia delante hasta 16 tokens más)
    fin = min(len(buf), p + 64)
    siguientes = tokens(buf, p, fin)
    racha = []
    for s, c in reversed([t for t in toks if t[0] < p]):
        if c is None:
            break
        racha.append(c)
    for s, c in siguientes:
        if c is None:
            break
        racha.append(c)
    return True, len(racha), sum(c in KANA for c in racha)


def trabajo(args):
    ruta, blobs, texto = args
    res = collections.defaultdict(lambda: collections.Counter())
    for b in blobs:
        for x in E.expandir(b):
            # v88: finditer no solapa; un código que empieza en el 2.º byte de otra coincidencia (p + 1)
            # quedaba oculto. Se añade explícitamente (p + 2 ya lo revisa finditer).
            posiciones = []
            for m in PATRON.finditer(x):
                posiciones.append(m.start())
                if (x[m.start() + 1] << 8 | x[m.start() + 2] if m.start() + 2 < len(x) else -1) in CONJUNTO:
                    posiciones.append(m.start() + 1)
            for p in posiciones:
                code = x[p] << 8 | x[p + 1]
                ok, largo, kana = alineada(x, p)
                if not ok:
                    res[code]['desalineada'] += 1
                elif texto:
                    res[code]['texto'] += 1
                elif largo >= 2 and kana >= 1:
                    res[code]['binario_textual'] += 1
                else:
                    res[code]['binario_ruido'] += 1
    return ruta, {k: dict(v) for k, v in res.items()}


def tareas(fa):
    E.FA = Path(fa)
    for t in E.tareas():
        yield t
    arc = E.FaArchive(str(fa))
    for p, o, s in arc.entries:        # lo que v83 omitía por ser gráfico: solo para el recuento binario
        pl = p.lower()
        if any(d in pl for d in E.SKIP_DIRS) and not pl.endswith(('.moflex',)):
            yield (p, [bytes(arc.d[o:o + s])], False)


def escanear(fa, codigos, procesos=8):
    total = {c: collections.Counter() for c in codigos}
    donde = collections.defaultdict(list)
    with Pool(procesos, initializer=_init, initargs=(codigos,)) as pool:
        for ruta, r in pool.imap_unordered(trabajo, tareas(fa), chunksize=2):
            for c, cnt in r.items():
                total[c].update(cnt)
                if cnt.get('texto') or cnt.get('binario_textual'):
                    donde[c].append((ruta, cnt))
    return total, donde


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--fa', type=Path, required=True)
    ap.add_argument('--codigos')
    ap.add_argument('--pool', type=int)
    ap.add_argument('--salida', type=Path, required=True)
    args = ap.parse_args()
    if args.codigos:
        codigos = [int(c, 16) for c in args.codigos.split(',')]
    else:
        h = json.loads((V83 / 'huecos.json').read_text(encoding='utf-8'))
        codigos = [int(c, 16) for c in h['libre_total_codigos'] if 0x989F <= int(c, 16) <= 0xEAA4][:args.pool]
    total, donde = escanear(args.fa, codigos)
    out = dict(fa=str(args.fa), codigos={f'{c:04X}': dict(v) for c, v in total.items()},
               apariciones_textuales={f'{c:04X}': v for c, v in donde.items()},
               limpios=[f'{c:04X}' for c in codigos if not total[c].get('texto') and not total[c].get('binario_textual')])
    args.salida.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
    print('limpios', len(out['limpios']), 'de', len(codigos))
    for c in codigos:
        print(f'{c:04X}', bytes.fromhex(f'{c:04X}').decode('cp932'), dict(total[c]))


if __name__ == '__main__':
    main()
