"""Lectura y escritura de glifos por celda en las fuentes del juego (BCFNT A4/LA4 y NFTR 1 bpp).

Portado de las capas de fuentes de ``work/`` (F2.5, #51) sin cambios de comportamiento:

- :class:`FuenteBCFNT`, :class:`FuenteNFTR`, :func:`cargar`, :func:`codepoint` y :func:`tinta`
  vienen de ``work/ie1/capas/historial/fuentes/v73_espaciado_fuente/fuentes.py``;
- :class:`EscritorA4` es ``Celdas`` de ``work/ie1/capas/fuentes/glifos_eu/apply.py`` (v75) y
  :class:`EscritorLA4` es ``CeldasLA4`` de ``v88_bigramas_total/apply.py``;
- :func:`pintar` es el ``pintar`` de ``bigramas_ritmo/apply.py`` (v89): borra la celda entera y
  escribe la tinta con el margen de 1 px de la hoja.

Modelo común: cada glifo tiene un mapa de bits en coordenadas de glifo (columna 0 = primer píxel del
glifo, sin el margen de 1 px de la hoja) y la terna CWDH ``(left, width, advance)``. La tinta se pinta en
``lápiz + trunc((celda - advance) / 2) + left + x``.

El lector BCFNT usa ``Font`` y ``morton8`` de ``tools/font_patch.py`` (fichero bloqueado): se cargan
por :mod:`ie123kit.nucleo.config.congelados`, nunca se copian. Escribir aquí NO cambia ninguna fuente
del proyecto: se trabaja sobre la copia en memoria que se pasa (``Fuente*.data()`` devuelve los bytes).
"""
from __future__ import annotations

import struct
from pathlib import Path
from typing import Any

__all__ = [
    "EscritorA4",
    "EscritorLA4",
    "FuenteBCFNT",
    "FuenteNFTR",
    "cargar",
    "codepoint",
    "escritor",
    "pintar",
    "pixeles",
    "tinta",
]


def _font_patch() -> Any:
    from ie123kit.nucleo.fuentes import glifos

    return glifos.modulo()


def _acentos() -> dict[str, int]:
    return {ch: cp for ch, _, _, cp in _font_patch().PLAN}


class FuenteBCFNT:
    """BCFNT (CFNT) de la 3DS en memoria: mapas de bits por glifo, CMAP y CWDH editables."""

    def __init__(self, path: str | Path):
        fp = _font_patch()
        self.path = Path(path)
        self.f = fp.Font(self.path)
        self._morton8 = fp.morton8
        self.t = self.f.t
        self.fmt = self.t["fmt"]
        self.cmap = self.f.cmap
        self.sx = self.f.sx
        self.sy = self.t["sheet_h"] // self.t["nrows"]
        self.metrics: dict[int, tuple[int, int, int]] = {}
        for blk in self.f.b.cwdhs():
            self.metrics.update(blk["widths"])
        self._cache: dict[int, list[list[int]]] = {}

    @classmethod
    def desde_bytes(cls, datos: bytes, nombre: str = "fuente.bcfnt") -> FuenteBCFNT:
        """Abre una BCFNT desde bytes (se vuelca a un temporal que se borra al momento)."""
        import tempfile

        with tempfile.TemporaryDirectory(prefix="ie123_bcfnt_") as tmp:
            ruta = Path(tmp) / Path(nombre).name
            ruta.write_bytes(datos)
            return cls(ruta)

    def _px(self, sheet: int, X: int, Y: int) -> int:
        t = self.t
        tw = t["sheet_w"] // 8
        tile = (Y // 8) * tw + (X // 8)
        m = self._morton8(X % 8, Y % 8)
        base = self.f.doff + sheet * t["sheet_size"]
        if self.fmt == 11:            # A4: dos píxeles por byte
            b = self.f.data[base + tile * 32 + m // 2]
            return (b >> ((m % 2) * 4)) & 0xF
        if self.fmt == 9:             # LA4: un byte por píxel; tinta visible = cualquier nibble
            b = self.f.data[base + tile * 64 + m]
            return max(b >> 4, b & 0xF)
        raise ValueError(f"formato TGLP no soportado: {self.fmt}")

    def bitmap(self, gi: int) -> list[list[int]]:
        """Mapa de bits del glifo (sin el margen de 1 px de la celda), valores 0..15."""
        if gi not in self._cache:
            sheet, cell = divmod(gi, self.f.PER)
            ox = (cell % self.t["ncols"]) * self.sx
            oy = (cell // self.t["ncols"]) * self.sy
            self._cache[gi] = [[self._px(sheet, ox + 1 + x, oy + 1 + y)
                                for x in range(self.sx - 1)] for y in range(self.sy - 1)]
        return self._cache[gi]

    def gi(self, cp: int) -> int | None:
        return self.cmap.get(cp)

    def set_metrics(self, gi: int, left: int, width: int, advance: int) -> None:
        off = self.f.cwdh_entry_off(gi)
        if off is None:
            raise KeyError(gi)
        struct.pack_into("<bBB", self.f.data, off, left, width, advance)
        self.metrics[gi] = (left, width, advance)

    def data(self) -> bytes:
        return bytes(self.f.data)


class FuenteNFTR:
    """NFTR (NDS) de 1 bpp: lectura de glifos y CWDH editable."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.d = bytearray(self.path.read_bytes())
        d = self.d
        if d[:4] != b"RTFN" or d[16:20] != b"FNIF":
            raise ValueError("NFTR no reconocido")
        self.cglp_off, self.cwdh_off, self.cmap_off = struct.unpack_from("<III", d, 0x20)
        p = self.cglp_off - 8
        self.cell_w, self.cell_h, self.bytes_glyph, _, _, self.bpp, _ = struct.unpack_from("<BBHBBBB", d, p + 8)
        if self.bpp != 1:
            raise ValueError("solo NFTR de 1 bpp")
        self.fmt = "nftr"
        self.cmap = self._cmap()
        self.metrics: dict[int, tuple[int, int, int]] = {}
        self._offs: dict[int, int] = {}
        o = self.cwdh_off
        while o:
            p = o - 8
            begin, end = struct.unpack_from("<HH", d, p + 8)
            for gi in range(begin, end + 1):
                self._offs[gi] = p + 16 + 3 * (gi - begin)
                self.metrics[gi] = struct.unpack_from("<bBB", d, self._offs[gi])
            o = struct.unpack_from("<I", d, p + 12)[0]
        self._cache: dict[int, list[list[int]]] = {}

    def _cmap(self) -> dict[int, int]:
        d, out = self.d, {}
        o = struct.unpack_from("<I", d, 40)[0]
        while o:
            p = o - 8
            b, e, meth = struct.unpack_from("<HHH", d, p + 8)
            body = p + 20
            if meth == 0:
                first = struct.unpack_from("<H", d, body)[0]
                out.update({cp: first + cp - b for cp in range(b, e + 1)})
            elif meth == 1:
                out.update({cp: struct.unpack_from("<H", d, body + 2 * (cp - b))[0] for cp in range(b, e + 1)})
            else:
                n = struct.unpack_from("<H", d, body)[0]
                out.update(dict(struct.unpack_from("<HH", d, body + 2 + 4 * i) for i in range(n)))
            o = struct.unpack_from("<I", d, p + 16)[0]
        return {k: v for k, v in out.items() if v != 0xFFFF}

    def gi(self, cp: int) -> int | None:
        """cp Unicode -> índice de glifo (las claves del NFTR son códigos Shift-JIS)."""
        try:
            code = int.from_bytes(chr(cp).encode("shift_jis"), "big")
        except UnicodeEncodeError:
            return None
        return self.cmap.get(code)

    def bitmap(self, gi: int) -> list[list[int]]:
        if gi not in self._cache:
            base = self.cglp_off + 8 + gi * self.bytes_glyph
            bits = "".join(f"{b:08b}" for b in self.d[base:base + self.bytes_glyph])
            W, H = self.cell_w, self.cell_h
            self._cache[gi] = [[15 * int(bits[y * W + x]) for x in range(W)] for y in range(H)]
        return self._cache[gi]

    def set_metrics(self, gi: int, left: int, width: int, advance: int) -> None:
        struct.pack_into("<bBB", self.d, self._offs[gi], left, width, advance)
        self.metrics[gi] = (left, width, advance)

    def data(self) -> bytes:
        return bytes(self.d)


def tinta(bitmap: list[list[int]], umbral: int = 1) -> tuple[int, int] | None:
    """(x0, x1) de las columnas con tinta (alpha >= umbral) o None si el glifo está vacío."""
    xs = [x for row in bitmap for x, v in enumerate(row) if v >= umbral]
    return (min(xs), max(xs)) if xs else None


def codepoint(ch: str) -> int:
    """Carácter español -> codepoint que emite el transporte de ancho completo."""
    acentos = _acentos()
    if ch in acentos:
        return acentos[ch]
    if ch == " ":
        return 0x3000
    if "!" <= ch <= "~":
        return ord(ch) + 0xFEE0
    return ord(ch)


def cargar(path: str | Path) -> FuenteBCFNT | FuenteNFTR:
    path = Path(path)
    return FuenteNFTR(path) if path.suffix.upper() == ".NFTR" else FuenteBCFNT(path)


def pixeles(fuente: Any, gi: int) -> dict[tuple[int, int], int]:
    """``{(x, y): alfa}`` con la tinta del glifo ``gi`` (solo alfa > 0)."""
    return {(x, y): v for y, row in enumerate(fuente.bitmap(gi)) for x, v in enumerate(row) if v}


class EscritorA4:
    """Acceso a los píxeles de la celda completa de la hoja A4 (sin suponer margen)."""

    def __init__(self, fuente: FuenteBCFNT):
        self.fu = fuente
        self.f = fuente.f
        self.t = fuente.t
        if self.t["fmt"] != 11:
            raise ValueError("EscritorA4: solo A4 (fmt 11)")

    def _origen(self, gi: int) -> tuple[int, int, int]:
        sheet, cell = divmod(gi, self.f.PER)
        return sheet, (cell % self.t["ncols"]) * self.fu.sx, (cell // self.t["ncols"]) * self.fu.sy

    def leer(self, gi: int) -> list[list[int]]:
        s, ox, oy = self._origen(gi)
        return [[self.fu._px(s, ox + x, oy + y) for x in range(self.fu.sx)] for y in range(self.fu.sy)]

    def escribir(self, gi: int, x: int, y: int, v: int) -> None:
        s, ox, oy = self._origen(gi)
        X, Y = ox + x, oy + y
        tile = (Y // 8) * (self.t["sheet_w"] // 8) + (X // 8)
        m = self.fu._morton8(X % 8, Y % 8)
        off = self.f.doff + s * self.t["sheet_size"] + tile * 32 + m // 2
        sh = (m % 2) * 4
        self.f.data[off] = (self.f.data[off] & ~(0xF << sh) & 0xFF) | ((v & 0xF) << sh)
        self.fu._cache.pop(gi, None)


class EscritorLA4:
    """Escritura de un byte LA4 por píxel (FONT12T: nibble alto = luminancia, bajo = alfa)."""

    def __init__(self, fuente: FuenteBCFNT):
        self.fu, self.f, self.t = fuente, fuente.f, fuente.t
        if self.t["fmt"] != 9:
            raise ValueError("EscritorLA4: solo LA4 (fmt 9)")

    def escribir(self, gi: int, x: int, y: int, v: int) -> None:
        sheet, cell = divmod(gi, self.f.PER)
        X = (cell % self.t["ncols"]) * self.fu.sx + x
        Y = (cell // self.t["ncols"]) * self.fu.sy + y
        tile = (Y // 8) * (self.t["sheet_w"] // 8) + (X // 8)
        off = self.f.doff + sheet * self.t["sheet_size"] + tile * 64 + self.fu._morton8(X % 8, Y % 8)
        self.f.data[off] = v & 0xFF
        self.fu._cache.pop(gi, None)


def escritor(fuente: FuenteBCFNT) -> EscritorA4 | EscritorLA4:
    """El escritor que corresponde al formato de la hoja (A4 o LA4)."""
    return EscritorLA4(fuente) if fuente.fmt == 9 else EscritorA4(fuente)


def pintar(fuente: FuenteBCFNT, gi: int, px: dict[tuple[int, int], int],
           esc: EscritorA4 | EscritorLA4 | None = None) -> None:
    """Borra la celda ``gi`` entera y pinta ``px`` (coordenadas de glifo) con el margen de 1 px."""
    esc = esc if esc is not None else escritor(fuente)
    for y in range(fuente.sy):
        for x in range(fuente.sx):
            esc.escribir(gi, x, y, 0)
    for (x, y), v in px.items():
        if not (0 <= x < fuente.sx - 1 and 0 <= y < fuente.sy - 1):
            raise ValueError(f"píxel fuera de la celda del glifo {gi}: {(x, y)}")
        esc.escribir(gi, 1 + x, 1 + y, v)
