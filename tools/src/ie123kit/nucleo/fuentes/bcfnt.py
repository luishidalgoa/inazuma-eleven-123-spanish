#!/usr/bin/env python3
"""Parser del formato de fuente BCFNT (CFNT v3) de Nintendo 3DS.

Lee cabecera + bloques FINF / TGLP / CWDH / CMAP. Sirve para inspeccionar la
fuente del juego (FONT12T.bcfnt) y, despues, anadir glifos del espanol (etapa 6).
Los offsets internos apuntan al CUERPO del bloque (block_start + 8).
"""
import struct


class BCFNT:
    def __init__(self, data):
        self.d = data
        assert data[:4] == b"CFNT", "no es CFNT: " + repr(data[:4])
        (self.bom, self.hdr_size, self.version, self.file_size,
         self.nblocks) = struct.unpack_from("<HHIII", data, 4)
        self.finf_off = 0x14
        self._parse_finf()

    def u(self, fmt, off):
        return struct.unpack_from(fmt, self.d, off)

    def _parse_finf(self):
        d = self.d
        o = self.finf_off
        assert d[o:o + 4] == b"FINF", d[o:o + 4]
        self.finf_size = self.u("<I", o + 4)[0]
        self.font_type = d[o + 8]
        self.line_feed = d[o + 9]
        self.alter_char = self.u("<H", o + 10)[0]
        self.def_left, self.def_glyph_w, self.def_char_w = d[o + 12], d[o + 13], d[o + 14]
        self.encoding = d[o + 15]
        self.tglp_off, self.cwdh_off, self.cmap_off = self.u("<III", o + 16)
        self.height, self.width, self.ascent = d[o + 28], d[o + 29], d[o + 30]

    def tglp(self):
        o = self.tglp_off - 8           # volver al inicio del bloque
        d = self.d
        assert d[o:o + 4] == b"TGLP", d[o:o + 4]
        cell_w, cell_h, baseline, max_w = d[o + 8], d[o + 9], d[o + 10], d[o + 11]
        sheet_size = self.u("<I", o + 12)[0]
        nsheets, fmt = self.u("<HH", o + 16)
        ncols, nrows, sw, sh = self.u("<HHHH", o + 20)
        sheet_data = self.u("<I", o + 28)[0]
        return {"cell_w": cell_w, "cell_h": cell_h, "baseline": baseline, "max_w": max_w,
                "sheet_size": sheet_size, "nsheets": nsheets, "fmt": fmt, "ncols": ncols,
                "nrows": nrows, "sheet_w": sw, "sheet_h": sh, "sheet_data": sheet_data}

    def cmaps(self):
        out = []
        o = self.cmap_off
        while o:
            s = o - 8
            d = self.d
            assert d[s:s + 4] == b"CMAP", d[s:s + 4]
            cbeg, cend, method, _r = self.u("<HHHH", s + 8)
            nxt = self.u("<I", s + 16)[0]
            body = s + 20
            entries = {}
            if method == 0:      # direct
                offset = self.u("<H", body)[0]
                for c in range(cbeg, cend + 1):
                    gi = c - cbeg + offset
                    if gi != 0xFFFF:
                        entries[c] = gi
            elif method == 1:    # table
                for i, c in enumerate(range(cbeg, cend + 1)):
                    gi = self.u("<H", body + i * 2)[0]
                    if gi != 0xFFFF:
                        entries[c] = gi
            elif method == 2:    # scan
                n = self.u("<H", body)[0]
                for i in range(n):
                    code, gi = self.u("<HH", body + 2 + i * 4)
                    if gi != 0xFFFF:
                        entries[code] = gi
            out.append({"begin": cbeg, "end": cend, "method": method, "n": len(entries),
                        "entries": entries})
            o = nxt
        return out

    def cwdhs(self):
        out = []
        o = self.cwdh_off
        while o:
            s = o - 8
            d = self.d
            assert d[s:s + 4] == b"CWDH", d[s:s + 4]
            start, end = self.u("<HH", s + 8)
            nxt = self.u("<I", s + 12)[0]
            widths = {}
            for i in range(end - start + 1):
                left, gw, cw = struct.unpack_from("<bBB", d, s + 16 + i * 3)
                widths[start + i] = (left, gw, cw)
            out.append({"start": start, "end": end, "widths": widths})
            o = nxt
        return out
