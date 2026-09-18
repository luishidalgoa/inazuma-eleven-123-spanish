"""v83 · bigramas (SOLO INVESTIGACIÓN): códigos Shift-JIS de doble byte que aparecen en la recopilación.

Recorre probe_ie1_v81/archive.fa (todos los juegos): descomprime LZ10 (0x10), SSZL y ARCV (un nivel
de anidamiento), trocea los .pkb con su .pkh (eve, evet, mch, act...) y escanea también las CRO de
base_3ds (+ la ina_main1.cro de v81) y exefs/code.bin (BLZ si procede). Se omiten vídeo (.moflex) y
paquetes de modelos/efectos/caras/sprites (texturas y mallas: solo generan ruido).

Dos conjuntos (el primer intento, rachas >= 2 en todo, marcaba los 11.280 códigos posibles por ruido):
  fiable   fuentes de texto (.STR/.dat/.txt/.tbl/.itx/.ini y trozos de los .pkb de script/ y logic/): toda racha >= 2
  ruidoso  resto (texturas, CRO, code.bin): solo rachas >= 3 con al menos 1/3 de kana/puntuación
Salida: sjis_usados.json  (código -> apariciones, por familia de fichero)
Uso: python -X utf8 work/ie1/capas/v83/bigramas/escaneo_sjis.py
"""
from __future__ import annotations

import collections
import json
import re
import struct
import sys
from multiprocessing import Pool
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'tools/src'))
from fa_unpack import FaArchive  # noqa: E402
from ie123kit.nucleo.compresion import lz10, sszl  # noqa: E402
from ie123kit.nucleo.contenedores import arcv  # noqa: E402

FA = ROOT / 'work/shared/candidatas/probe_ie1_v81/archive.fa'
DB = rb'[\x81-\x9f\xe0-\xfc][\x40-\x7e\x80-\xfc]'
RACHA2 = re.compile(b'(?:' + DB + b'){2,}')
PAR = re.compile(DB)
SKIP_DIRS = ('/model/', '/effect3d/', '/face2d/', '/spr/', '/pic3d/', '/map2d/', '/map3d/', '/sound/')
TEXTO = ('.str', '.dat', '.txt', '.tbl', '.itx', '.ini')


KANA = set(range(0x829F, 0x82F2)) | set(range(0x8340, 0x8397)) | {0x815B, 0x8141, 0x8142}


def escanear(buf, texto):
    """(fiable, ruidoso): en fuentes de texto toda racha >= 2; en el resto solo rachas >= 3 con kana."""
    fiable, ruido = collections.Counter(), collections.Counter()
    for m in RACHA2.finditer(buf):
        s = m.group(0)
        codes = [s[i] << 8 | s[i + 1] for i in range(0, len(s), 2)]
        if texto:
            fiable.update(codes)
        elif len(codes) >= 3 and sum(c in KANA for c in codes) * 3 >= len(codes):
            ruido.update(codes)
    return fiable, ruido


def expandir(data, prof=0):
    if data[:4] == b'SSZL':
        try:
            data = sszl.unwrap(data)
        except Exception:
            return [data]
    elif data[:1] == b'\x10' and len(data) > 8:
        try:
            size = data[1] | data[2] << 8 | data[3] << 16
            if 0 < size < 64 * 1024 * 1024:
                data = bytes(lz10.decompress(data))
        except Exception:
            pass
    out = [data]
    if data[:4] == b'ARCV' and prof < 2:
        try:
            for off, size, _ in arcv.entries(data):
                out += expandir(data[off:off + size], prof + 1)
        except ValueError:
            pass
    return out


def trabajo(args):
    ruta, blobs, texto = args
    e, l = collections.Counter(), collections.Counter()
    for b in blobs:
        for x in expandir(b):
            a, c = escanear(x, texto)
            e.update(a)
            l.update(c)
    return ruta, e, l


def tareas():
    arc = FaArchive(str(FA))
    idx = {p: (o, s) for p, o, s in arc.entries}
    for p, o, s in arc.entries:
        pl = p.lower()
        if pl.endswith(('.moflex', '.pkh', '.bcfnt', '.shbin', '.nftr')) or any(d in pl for d in SKIP_DIRS):
            continue
        data = bytes(arc.d[o:o + s])
        if pl.endswith('.pkb') and p[:-1] + 'h' in idx:
            ho, hs = idx[p[:-1] + 'h']
            pkh = bytes(arc.d[ho:ho + hs])
            n = (hs - 0x30) // 12
            blobs = []
            for i in range(n):
                _eid, eo, es = struct.unpack_from('<III', pkh, 0x30 + 12 * i)
                if eo + es <= len(data) and es:
                    blobs.append(data[eo:eo + es])
            # trocear en lotes para repartir
            for k in range(0, len(blobs), 400):
                yield (p, blobs[k:k + 400], '/script/' in pl or '/logic/' in pl)
            continue
        yield (p, [data], pl.endswith(TEXTO))
    base = ROOT / 'work/shared/base_3ds'
    for f in sorted((base / 'romfs/cro').glob('*.cr?')):
        yield ('base_3ds/cro/' + f.name, [f.read_bytes()], False)
    yield ('v81/cro/ina_main1.cro', [(FA.parent / 'romfs/cro/ina_main1.cro').read_bytes()], False)
    code = (base / 'exefs/code.bin').read_bytes()
    try:
        from ie123kit.nucleo.compresion import blz
        dec = blz.decompress(code) if hasattr(blz, 'decompress') else code
    except Exception:
        dec = code
    yield ('base_3ds/exefs/code.bin', [dec], False)


def familia(ruta):
    r = ruta.lower()
    for k in ('eve.pkb', 'evet', '.cro', 'code.bin', '.str', '.arc', '.lzs', '.dat', '.pkb', '.pac_'):
        if k in r:
            return k
    return 'otros'


def main():
    tot_e, tot_l = collections.Counter(), collections.Counter()
    por_fam = collections.defaultdict(collections.Counter)
    por_fam_r = collections.defaultdict(collections.Counter)
    por_juego = collections.defaultdict(collections.Counter)
    with Pool(8) as pool:
        for ruta, e, l in pool.imap_unordered(trabajo, tareas(), chunksize=4):
            tot_e.update(e)
            tot_l.update(l)
            por_fam[familia(ruta)].update(e)
            por_fam_r[familia(ruta)].update(l)
            por_juego[ruta.split('/')[0]].update(e + l)
    out = dict(fa=str(FA.relative_to(ROOT)),
               fiable={f'{k:04X}': v for k, v in sorted(tot_e.items())},
               ruidoso={f'{k:04X}': v for k, v in sorted(tot_l.items())},
               fiable_por_familia={f: {f'{k:04X}': v for k, v in sorted(c.items())} for f, c in por_fam.items()},
               ruidoso_por_familia={f: len(c) for f, c in por_fam_r.items()},
               distintos_por_juego={f: len(c) for f, c in por_juego.items()})
    (HERE / 'sjis_usados.json').write_text(json.dumps(out), encoding='utf-8')
    print('fiable', len(tot_e), 'ruidoso', len(tot_l), 'union', len(tot_e | tot_l))
    print({f: len(c) for f, c in por_fam.items()}, {f: len(c) for f, c in por_fam_r.items()})


if __name__ == '__main__':
    main()
