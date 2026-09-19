"""Utilidades comunes de la capa v03/graficos de IE2 (issue #73).

Fuentes:
  JP    work/shared/base_3ds/romfs/archive.fa          (inazuma2/ japonés = original de IE2)
  IE1TR work/shared/candidatas/probe_ie1_v89/archive.fa (inazuma1/ ya traducido; referencia de reutilización)
  NDS   work/ie2/tormenta_de_fuego/fuentes/nds_es         (NDS española de Tormenta de Fuego)

Nunca se mueven coordenadas de atlas ni tamaños; la metadata CTPK se conserva.
"""
from __future__ import annotations

import hashlib
import struct
import sys
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[6]
sys.path.insert(0, str(ROOT / 'tools'))

from fa_unpack import FaArchive  # noqa: E402
import ui_archive as U  # noqa: E402
import ctpk_ui as T  # noqa: E402
import sszl  # noqa: E402
import legacy_sprite as L  # noqa: E402
from lz10 import decompress as lz10_decompress  # noqa: E402

JP_FA = ROOT / 'work/shared/base_3ds/romfs/archive.fa'
IE1TR_FA = ROOT / 'work/shared/candidatas/probe_ie1_v89/archive.fa'
NDS = ROOT / 'work/ie2/tormenta_de_fuego/fuentes/nds_es'
EXTRA = HERE / 'extra'
PREVIEWS = HERE / 'previews'
CACHE = HERE / '_cache'
ARIALBD = 'C:/Windows/Fonts/arialbd.ttf'
ARIAL = 'C:/Windows/Fonts/arial.ttf'


class Archivo:
    def __init__(self, ruta):
        self.fa = FaArchive(str(ruta))
        self.idx = {p: (o, n) for p, o, n in self.fa.entries}

    def __contains__(self, p):
        return p in self.idx

    def get(self, p):
        o, n = self.idx[p]
        return bytes(self.fa.d[o:o + n])

    def rutas(self, prefijo=''):
        return [p for p in self.idx if p.startswith(prefijo)]


@lru_cache(None)
def jp():
    return Archivo(JP_FA)


@lru_cache(None)
def ie1tr():
    return Archivo(IE1TR_FA)


def sha(b):
    return hashlib.sha1(b).hexdigest()


# ---------------------------------------------------------------- CTPK en ARCV

def texturas(raw):
    """[(nombre, offset, tamaño, blob)] de los CTPK de un ARCV desenvuelto."""
    out = []
    try:
        ents = U.entries(raw)
    except ValueError:
        return out
    for off, ln, _ in ents:
        b = raw[off:off + ln]
        if b[:4] == b'CTPK':
            try:
                nombre = T.metadata(b)[0]
            except ValueError:
                continue
            out.append((nombre, off, ln, b))
    return out


def clave_pixeles(blob):
    nombre, w, h, fmt, po, sz = T.metadata(blob)
    return sha(bytes([fmt]) + struct.pack('<HH', w, h) + blob[po:po + sz])


@lru_cache(None)
def _morton(w, h):
    xs, ys = np.meshgrid(np.arange(w), np.arange(h))
    m = np.zeros_like(xs)
    for b in range(3):
        m |= ((xs >> b) & 1) << (2 * b) | ((ys >> b) & 1) << (2 * b + 1)
    return (((ys // 8) * (w // 8) + xs // 8) * 64 + m).astype(np.int64)


def decodificar(blob):
    """Decodificador numpy equivalente a ctpk_ui.decode (verificado en verificar_decodificador)."""
    _, w, h, fmt, off, size = T.metadata(blob)
    if fmt == 13 or w < 8 or h < 8:
        return T.decode(blob)
    idx = _morton(w, h)
    d = np.frombuffer(blob, np.uint8, offset=off)
    if fmt == 0:
        p = d[:4 * w * h].reshape(-1, 4)[idx]
        a, b, g, r = p[..., 0], p[..., 1], p[..., 2], p[..., 3]
    elif fmt == 1:
        p = d[:3 * w * h].reshape(-1, 3)[idx]
        b, g, r = p[..., 0], p[..., 1], p[..., 2]
        a = np.full_like(r, 255)
    elif fmt == 5:
        p = d[:2 * w * h].reshape(-1, 2)[idx]
        a, r = p[..., 0], p[..., 1]
        g = b = r
    elif fmt == 9:
        v = d[:w * h][idx].astype(np.int32)
        r = g = b = ((v >> 4) * 17)
        a = (v & 15) * 17
    elif fmt in (2, 3, 4):
        v = np.frombuffer(blob, '<u2', count=w * h, offset=off)[idx].astype(np.int32)
        if fmt == 2:
            r, g, b = [((v >> s) & 31) * 255 // 31 for s in (11, 6, 1)]
            a = (v & 1) * 255
        elif fmt == 3:
            r, g, b = ((v >> 11) & 31) * 255 // 31, ((v >> 5) & 63) * 255 // 63, (v & 31) * 255 // 31
            a = np.full_like(v, 255)
        else:
            r, g, b, a = [((v >> s) & 15) * 17 for s in (12, 8, 4, 0)]
    elif fmt == 11:
        v = d[:(w * h + 1) // 2]
        a = ((v[idx // 2] >> (4 * (idx % 2))) & 15).astype(np.int32) * 17
        r = g = b = np.full_like(a, 255)
    elif fmt == 7:      # L8 (solo lectura: ctpk_ui no lo codifica)
        r = g = b = d[:w * h][idx].astype(np.int32)
        a = np.full_like(r, 255)
    elif fmt == 8:      # A8 (solo lectura)
        a = d[:w * h][idx].astype(np.int32)
        r = g = b = np.full_like(a, 255)
    elif fmt == 10:     # L4 (solo lectura)
        v = d[:(w * h + 1) // 2]
        r = g = b = ((v[idx // 2] >> (4 * (idx % 2))) & 15).astype(np.int32) * 17
        a = np.full_like(r, 255)
    else:
        return T.decode(blob)
    arr = np.stack([np.asarray(c).astype(np.uint8) for c in (r, g, b, a)], -1)
    return Image.fromarray(arr, 'RGBA')


EDITABLES = {0, 1, 2, 3, 4, 5, 9, 11, 13}


def codificar(blob, imagen):
    nuevo = T.encode(blob, imagen.convert('RGBA'))
    assert len(nuevo) == len(blob) and T.metadata(nuevo) == T.metadata(blob)
    return nuevo


def cuantizar(blob, imagen):
    """Imagen tal como quedará tras codificar (para comparar/previsualizar)."""
    return decodificar(codificar(blob, imagen))


def reenvolver(original, raw):
    """Política 'keep': si el original venía en SSZL se comprime de verdad (lección .lzs)."""
    if original[:4] == b'SSZL':
        return sszl.compress(raw)
    return raw


# ---------------------------------------------------------------- imágenes

def ampliar(im, s=4, fondo=(40, 44, 70, 255)):
    base = Image.new('RGBA', im.size, fondo)
    base.alpha_composite(im.convert('RGBA'))
    return base.resize((im.width * s, im.height * s), Image.NEAREST)


def par(antes, despues, s=None, titulo=None):
    if s is None:
        s = max(1, min(4, 512 // max(antes.width, antes.height, 1)))
    a, d = ampliar(antes, s), ampliar(despues, s)
    lienzo = Image.new('RGBA', (a.width * 2 + 12, a.height + (14 if titulo else 0)), (16, 16, 24, 255))
    y = 0
    if titulo:
        from PIL import ImageDraw
        ImageDraw.Draw(lienzo).text((2, 1), titulo, fill=(230, 230, 230, 255))
        y = 14
    lienzo.alpha_composite(a, (0, y))
    lienzo.alpha_composite(d, (a.width + 12, y))
    return lienzo


def hoja(pares, ancho=1800, sep=8):
    """Apila imágenes en filas (contact sheet)."""
    filas, fila, x, alto = [], [], 0, 0
    for im in pares:
        if fila and x + im.width > ancho:
            filas.append((fila, alto))
            fila, x, alto = [], 0, 0
        fila.append((x, im))
        x += im.width + sep
        alto = max(alto, im.height)
    if fila:
        filas.append((fila, alto))
    total = sum(a for _, a in filas) + sep * len(filas)
    lienzo = Image.new('RGB', (ancho, max(total, 1)), (8, 8, 12))
    y = 0
    for fila, a in filas:
        for x, im in fila:
            lienzo.paste(im.convert('RGB'), (x, y))
        y += a + sep
    return lienzo


# ---------------------------------------------------------------- NDS

def nds(rel):
    return (NDS / rel).read_bytes()


def ds_decomp(d):
    return lz10_decompress(d) if d[:1] == b'\x10' else d


def qna_cajas(ruta, arc=None):
    """{textura: {(x0,y0,x1,y1), ...}} de todos los maquetados QNA del .arc (cajas redondeadas)."""
    import struct as _st
    from collections import defaultdict as _dd
    raw = U.unwrap((arc or jp()).get(ruta))
    out = _dd(set)
    for off, ln, _ in U.entries(raw):
        b = raw[off:off + ln]
        if b[:8] != b' QNA 051':
            continue
        n_tex, _, n_partes = _st.unpack_from('<III', b, 8)
        noff, _, poff = _st.unpack_from('<III', b, 36)
        nombres = [b[noff + i * 32:noff + (i + 1) * 32].split(b'\0')[0].decode('ascii', 'replace') for i in range(n_tex)]
        for i in range(n_partes):
            o = poff + i * 128
            t = _st.unpack_from('<I', b, o + 88)[0]
            if t >= n_tex:
                continue
            caja = tuple(int(round(v)) for v in _st.unpack_from('<4f', b, o))
            n = nombres[t]
            out[n if n.endswith('.tga') else n + '.tga'].add(caja)
    return out


@lru_cache(None)
def qna_global():
    """{textura: {(arc, caja), ...}} de todos los QNA de inazuma2."""
    import pickle
    cache = HERE / '_qna_global.pkl'
    if cache.exists():
        return pickle.loads(cache.read_bytes())
    from collections import defaultdict as _dd
    out = _dd(set)
    for r in jp().rutas('inazuma2/'):
        if not r.endswith(('.arc', '.lzs')):
            continue
        try:
            for t, cs in qna_cajas(r).items():
                for c in cs:
                    out[t].add((r, c))
        except Exception:  # noqa: BLE001
            continue
    out = dict(out)
    cache.write_bytes(pickle.dumps(out))
    return out
