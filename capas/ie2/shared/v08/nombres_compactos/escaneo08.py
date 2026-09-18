"""v08 · escaneo estricto de códigos candidatos (mismas reglas que work/ie1/capas/v88/bigramas_total/escaneo_kanji88.py),
acelerado con numpy: las apariciones (también solapadas) se buscan como palabras de 16 bits y solo se clasifican
con `alineada` las que pueden contar:
  texto            fichero de texto (regla v83) y aparición alineada;
  binario_textual  otro fichero, alineada, en racha >= 2 de doble byte con >= 1 kana. Una aparición sin ningún
                   kana (0x829F-0x82F1, 0x8340-0x8396, 0x815B, 0x8141, 0x8142) en +-64 B no puede serlo y se
                   cuenta como ruido sin más cálculo.
Recorre el archive.fa indicado (con el troceado de .pkb, LZ10/SSZL/ARCV de v83), las CRO de base_3ds, las CRO
de la candidata (si existen junto al archive.fa) y code.bin.
Uso: python -X utf8 escaneo08.py --fa <archive.fa> --codigos-fichero cand_nuevos.txt --salida <json>"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[5]
sys.path.insert(0, str(ROOT / 'work/ie1/capas/v88/bigramas_total'))
import escaneo_kanji88 as K88  # noqa: E402

E = K88.E
KANA = np.array(sorted(E.KANA), dtype=np.uint16)
CAND = None


def _init(codigos):
    global CAND
    CAND = np.array(sorted(codigos), dtype=np.uint16)


def trabajo(args):
    ruta, blobs, texto = args
    res = collections.defaultdict(collections.Counter)
    for b in blobs:
        for x in E.expandir(b):
            if len(x) < 2:
                continue
            a = np.frombuffer(x, dtype=np.uint8).astype(np.uint16)
            w = (a[:-1] << 8) | a[1:]
            pos = np.nonzero(np.isin(w, CAND))[0]
            if not len(pos):
                continue
            if not texto:
                es_kana = np.isin(w, KANA).astype(np.int32)
                acum = np.concatenate(([0], np.cumsum(es_kana)))
            for p in pos.tolist():
                code = int(w[p])
                if not texto:
                    lo, hi = max(0, p - 64), min(len(w), p + 66)
                    if acum[hi] - acum[lo] == 0:
                        res[code]['binario_ruido'] += 1
                        continue
                ok, largo, kana = K88.alineada(x, p)
                if not ok:
                    res[code]['desalineada'] += 1
                elif texto:
                    res[code]['texto'] += 1
                elif largo >= 2 and kana >= 1:
                    res[code]['binario_textual'] += 1
                else:
                    res[code]['binario_ruido'] += 1
    return ruta, {k: dict(v) for k, v in res.items()}


def tareas(fa: Path):
    import struct
    arc = E.FaArchive(str(fa))
    idx = {p: (o, s) for p, o, s in arc.entries}
    for p, o, s in arc.entries:
        pl = p.lower()
        if pl.endswith(('.moflex', '.pkh', '.bcfnt', '.shbin', '.nftr')):
            continue
        data = bytes(arc.d[o:o + s])
        if any(d in pl for d in E.SKIP_DIRS):
            yield (p, [data], False)          # gráficos: solo recuento binario (como v88)
            continue
        if pl.endswith('.pkb') and p[:-1] + 'h' in idx:
            ho, hs = idx[p[:-1] + 'h']
            pkh = bytes(arc.d[ho:ho + hs])
            n = (hs - 0x30) // 12
            blobs = []
            for i in range(n):
                _e, eo, es = struct.unpack_from('<III', pkh, 0x30 + 12 * i)
                if eo + es <= len(data) and es:
                    blobs.append(data[eo:eo + es])
            for k in range(0, len(blobs), 400):
                yield (p, blobs[k:k + 400], '/script/' in pl or '/logic/' in pl)
            continue
        yield (p, [data], pl.endswith(E.TEXTO))
    base = ROOT / 'work/shared/base_3ds'
    for f in sorted((base / 'romfs/cro').glob('*.cr?')):
        yield ('base_3ds/cro/' + f.name, [f.read_bytes()], False)
    cro = fa.parent / 'romfs/cro'
    if cro.is_dir():
        for f in sorted(cro.glob('*.cr?')):
            yield ('cand/cro/' + f.name, [f.read_bytes()], False)
    code = (base / 'exefs/code.bin').read_bytes()
    try:
        from ie123kit.nucleo.compresion import blz
        code = blz.decompress(code)
    except Exception:
        pass
    yield ('base_3ds/exefs/code.bin', [code], False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--fa', type=Path, required=True)
    ap.add_argument('--codigos-fichero', type=Path, required=True)
    ap.add_argument('--salida', type=Path, required=True)
    a = ap.parse_args()
    codigos = [int(c, 16) for c in a.codigos_fichero.read_text().split(',') if c]
    total = {c: collections.Counter() for c in codigos}
    donde = collections.defaultdict(list)
    with Pool(8, initializer=_init, initargs=(codigos,)) as pool:
        for ruta, r in pool.imap_unordered(trabajo, tareas(a.fa.resolve()), chunksize=2):
            for c, cnt in r.items():
                total[c].update(cnt)
                if cnt.get('texto') or cnt.get('binario_textual'):
                    donde[c].append((ruta, cnt))
    out = dict(fa=str(a.fa), codigos={f'{c:04X}': dict(v) for c, v in total.items()},
               apariciones_textuales={f'{c:04X}': v for c, v in donde.items()},
               limpios=[f'{c:04X}' for c in codigos if not total[c].get('texto') and not total[c].get('binario_textual')])
    a.salida.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
    print('limpios', len(out['limpios']), 'de', len(codigos), flush=True)


if __name__ == '__main__':
    main()
