"""Glifos de las fuentes NFTR del juego (IE2 japonés, sin modificar) para pintar rótulos nítidos.

Solo lectura. Claves del mapa = códigos Shift-JIS (ASCII de 1 byte para latín). Las vocales acentuadas y la
ñ se componen con la letra base y una tilde de píxeles (las NFTR japonesas no las traen).
Pintado a 1 bit, a tamaño nativo, sin reescalar. `negrita` engruesa 1 px en horizontal (el japonés de
las técnicas tiene trazo de 2 px).
"""
import struct
from functools import lru_cache

import numpy as np

import comun as C
from ie123kit.nucleo.fuentes.nftr import read_metrics

ACENTOS = {'ä': 'a', 'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u', 'Á': 'A', 'É': 'E', 'Í': 'I', 'Ó': 'O', 'Ú': 'U',
           'ñ': 'n', 'Ñ': 'N', 'ü': 'u', 'Ü': 'U'}


class Fuente:
    def __init__(self, nombre='FONT12'):
        d = C.jp().get(f'inazuma2/data_iz/font/{nombre}.NFTR')
        self.metricas = read_metrics(d)
        plgc = struct.unpack_from('<I', d, 32)[0]
        self.cw, self.ch = d[plgc], d[plgc + 1]
        self.tam = struct.unpack_from('<H', d, plgc + 2)[0]
        self.base = d[plgc + 4]
        self.bpp = d[plgc + 6]
        self.datos = d
        self.inicio = plgc + 8
        self._gi = self._mapa(d)

    def _mapa(self, d):
        # reutiliza read_metrics para el cmap: índice de glifo = orden en HDWC
        from ie123kit.nucleo.fuentes import nftr
        cmap = {}
        import inspect  # noqa: F401
        off = struct.unpack_from('<I', d, 40)[0]
        while off:
            pos = off - 8
            begin, end, method = struct.unpack_from('<HHH', d, pos + 8)
            body = pos + 20
            if method == 0:
                first = struct.unpack_from('<H', d, body)[0]
                cmap.update({cp: first + cp - begin for cp in range(begin, end + 1)})
            elif method == 1:
                cmap.update({cp: struct.unpack_from('<H', d, body + 2 * (cp - begin))[0] for cp in range(begin, end + 1)})
            else:
                n = struct.unpack_from('<H', d, body)[0]
                cmap.update(dict(struct.unpack_from('<HH', d, body + 2 + 4 * i) for i in range(n)))
            off = struct.unpack_from('<I', d, pos + 16)[0]
        del nftr
        return {k: v for k, v in cmap.items() if v != 0xFFFF}

    def _bitmap(self, gi):
        o = self.inicio + gi * self.tam
        bits = np.unpackbits(np.frombuffer(self.datos[o:o + self.tam], np.uint8))
        n = self.cw * self.ch
        vals = bits[:n * self.bpp].reshape(n, self.bpp)
        v = vals.dot(1 << np.arange(self.bpp)[::-1])
        return (v.reshape(self.ch, self.cw) > 0)

    @lru_cache(None)
    def glifo(self, ch):
        """(máscara bool (ch+4)×ancho, avance); la fila 2 es la cima de la celda original."""
        if ch in 'ºª':
            g = np.zeros((self.ch + 4, 4), bool)
            g[2, 1:3] = g[5, 1:3] = True
            g[3:5, 0] = g[3:5, 3] = True
            if ch == 'ª':
                g[2:6] = False
                g[2, 1:3] = g[4, 0:3] = g[5, 0:4] = True
                g[3, 3] = g[4, 3] = True
            g[7, 0:4] = True
            return g, 5
        if ch in '¡¿':
            g, adv = self.glifo('!' if ch == '¡' else '?')
            filas = np.where(g.any(1))[0]
            f0, f1 = filas[0], filas[-1] + 1
            r = np.zeros_like(g)
            bloque = g[f0:f1][::-1, ::-1]
            desc = min(2, r.shape[0] - f1)
            r[f0 + desc:f1 + desc] = bloque
            return r, adv
        base = ACENTOS.get(ch, ch)
        code = ord(base)
        if code not in self._gi:
            ancho = chr(ord(base) + 0xFEE0) if 0x21 <= ord(base) <= 0x7E else base
            ancho = {'-': '－', '~': '〜'}.get(base, ancho)
            code = int.from_bytes(ancho.encode('cp932'), 'big')
        gi = self._gi[code]
        left, gw, adv = self.metricas[code]
        bm = self._bitmap(gi)
        out = np.zeros((self.ch + 4, max(adv, left + gw, 1)), bool)
        out[2:2 + self.ch, max(left, 0):max(left, 0) + gw] = bm[:, :gw]
        if base != ch:
            out = self._tilde(out, ch)
        return out, adv

    def _tilde(self, m, ch):
        m = m.copy()
        filas = np.where(m.any(1))[0]
        cols = np.where(m.any(0))[0]
        top = filas[0]
        cx = (cols[0] + cols[-1]) // 2
        w = m.shape[1]
        pon = lambda y, x: (0 <= x < w and 0 <= y) and m.__setitem__((y, x), True)
        if ch in 'ñÑ':
            y = top - 3
            for dx, dy in ((-2, 1), (-1, 0), (0, 0), (1, 1), (2, 0)):
                pon(y + dy, cx + dx - 0)
        elif ch in 'üÜ':
            for dx in (-1, 2):
                pon(top - 2, cx + dx)
        elif top >= 5:
            y = top - 3
            pon(y, cx + 2)
            pon(y, cx + 1)
            pon(y + 1, cx)
        else:
            pon(top - 2, cx + 1)
            pon(top - 2, cx)
        return m

    def texto(self, s, espacio=3, tracking=1):
        """Espaciado proporcional: cada glifo ocupa su tinta + tracking."""
        partes, x = [], 0
        for ch in s:
            if ch == ' ':
                x += espacio
                continue
            g, _ = self.glifo(ch)
            cols = np.where(g.any(0))[0]
            g = g[:, cols[0]:cols[-1] + 1] if len(cols) else g[:, :1]
            partes.append((x, g))
            x += g.shape[1] + tracking
        ancho = max([x] + [px + g.shape[1] for px, g in partes]) + 1
        m = np.zeros((self.ch + 4, ancho), bool)
        for px, g in partes:
            m[:, px:px + g.shape[1]] |= g
        return columnas(m)


def columnas(m):
    c = np.where(m.any(0))[0]
    return m[:, c[0]:c[-1] + 1] if len(c) else m[:, :0]


def recortar(m):
    if not m.any():
        return m[:0, :0]
    f = np.where(m.any(1))[0]
    c = np.where(m.any(0))[0]
    return m[f[0]:f[-1] + 1, c[0]:c[-1] + 1]


def negrita(m, px=1):
    m = np.pad(m, ((0, 0), (0, px)))
    out = m.copy()
    for k in range(1, px + 1):
        out[:, k:] |= m[:, :-k]
    return out


def dilatar(m, ocho=True):
    p = np.pad(m, 1)
    out = p.copy()
    vecinos = [(-1, 0), (1, 0), (0, -1), (0, 1)] + ([(-1, -1), (-1, 1), (1, -1), (1, 1)] if ocho else [])
    for dy, dx in vecinos:
        out |= np.roll(np.roll(p, dy, 0), dx, 1)
    return out


def ttf(texto, ruta, tam, variacion=None, umbral=None):
    """Máscara bool de una fuente TrueType renderizada a 1 bit (hinting, sin suavizado ni reescalado)."""
    from PIL import Image, ImageDraw, ImageFont
    f = ImageFont.truetype(ruta, tam)
    if variacion:
        f.set_variation_by_name(variacion)
    l, t, r, b = f.getbbox(texto)
    im = Image.new('L', (r - l + 4, b - t + 4), 0)
    d = ImageDraw.Draw(im)
    if umbral is None:
        d.fontmode = '1'
        d.text((2 - l, 2 - t), texto, font=f, fill=255)
        m = np.array(im) > 0
    else:
        d.text((2 - l, 2 - t), texto, font=f, fill=255)
        m = np.array(im) >= umbral
    return recortar(m)


def ttf_linea(texto, ruta, tam, variacion=None):
    """Como ttf() pero con alto fijo (ascendente+descendente+2): conserva la línea base."""
    from PIL import Image, ImageDraw, ImageFont
    f = ImageFont.truetype(ruta, tam)
    if variacion:
        f.set_variation_by_name(variacion)
    asc, desc = f.getmetrics()
    l, _, r, _ = f.getbbox(texto)
    im = Image.new('L', (r - l + 4, asc + desc + 4), 0)
    d = ImageDraw.Draw(im)
    d.fontmode = '1'
    d.text((2 - l, 2), texto, font=f, fill=255)
    return columnas(np.array(im) > 0)
