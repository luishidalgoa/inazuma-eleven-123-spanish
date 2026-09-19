"""Desensamblado mínimo de un CRO (IE1 ina_main1 / IE2 ina_main2) para localizar quién usa un literal.

Genérico: segmentos y relocaciones desde la cabecera CRO3 (como crorefs2 de IE2 v03), capstone ARM.
Solo lectura. Uso desde analisis.py de las capas v90 (IE1) y v04 (IE2).
"""
from __future__ import annotations

import re
import struct
from functools import lru_cache

import capstone

HEX = re.compile(r'#(-?0x[0-9a-f]+|-?\d+)')


class Cro:
    def __init__(self, data: bytes):
        self.d = d = data
        u = lambda o: struct.unpack_from('<I', d, o)[0]
        self.u = u
        self.segs = [struct.unpack_from('<III', d, u(0xC8) + 12 * i) for i in range(u(0xCC))]
        self.text = (self.segs[0][0], self.segs[0][0] + self.segs[0][1])
        reloff, relnum = u(0x128), u(0x12C)
        self.ptr = {}          # posición -> valor relocalizado
        self.byval = {}        # valor -> posiciones
        for i in range(relnum):
            so, typ, sidx, _a, _b, add = struct.unpack_from('<IBBBBI', d, reloff + 12 * i)
            loc = self.segs[so & 0xf][0] + (so >> 4)
            val = self.segs[sidx][0] + add
            self.ptr[loc] = val
            self.byval.setdefault(val, []).append(loc)
        # importaciones (parches con nombre)
        self.imp = {}
        pbase, pn = u(0xF8), u(0xFC)
        io, inum = u(0x100), u(0x104)
        for i in range(inum):
            no, fp = struct.unpack_from('<II', d, io + 8 * i)
            name = d[no:d.index(b'\0', no)].decode('latin1')
            if not (pbase <= fp < pbase + 12 * pn):
                continue
            k = (fp - pbase) // 12
            while k < pn:
                tg, ty, last, _x, _y, ad = struct.unpack_from('<IBBBBI', d, pbase + 12 * k)
                self.imp[self.segs[tg & 0xf][0] + (tg >> 4)] = name
                if last:
                    break
                k += 1
        self.cs = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_ARM)
        self._adr = None
        self._bl = None

    # ---------- índices
    def _indices(self):
        d = self.d
        adr, ldr, bl = {}, {}, {}
        a, b = self.text
        for off in range(a, b, 4):
            w = struct.unpack_from('<I', d, off)[0]
            if (w & 0x0FEF0000) == 0x028F0000:
                adr.setdefault(off + 8 + _rot(w), []).append(off)
            elif (w & 0x0FEF0000) == 0x024F0000:
                adr.setdefault(off + 8 - _rot(w), []).append(off)
            if (w & 0x0F7F0000) == 0x051F0000:
                imm = w & 0xfff
                ldr.setdefault(off + 8 + (imm if (w >> 23) & 1 else -imm), []).append(off)
            if (w >> 25) & 7 == 5 and (w >> 28) != 0xf:
                o = w & 0xffffff
                o = o - (1 << 24) if o & 0x800000 else o
                bl.setdefault(off + 8 + o * 4, []).append(off)
        self._adr, self._ldr, self._bl = adr, ldr, bl

    @property
    def adr(self):
        if self._adr is None:
            self._indices()
        return self._adr

    @property
    def ldr(self):
        if self._adr is None:
            self._indices()
        return self._ldr

    @property
    def bl(self):
        if self._adr is None:
            self._indices()
        return self._bl

    def refs(self, o):
        """Instrucciones que cargan la dirección o (adr directo o ldr de un pool relocalizado)."""
        out = [('adr', a, None) for a in self.adr.get(o, [])]
        for p in self.byval.get(o, []):
            us = self.ldr.get(p, [])
            out += [('ldr', x, p) for x in us] or [('ptr', None, p)]
        return out

    def cstr(self, o, n=120):
        try:
            b = self.d[o:self.d.index(b'\0', o)]
        except ValueError:
            return '?'
        try:
            return b[:n].decode('cp932')
        except UnicodeDecodeError:
            return b[:n].decode('latin1')

    def fstart(self, a):
        o = a
        while o > self.text[0]:
            w = struct.unpack_from('<I', self.d, o)[0]
            if (w & 0xFFFF4000) == 0xE92D4000:
                return o
            o -= 4
        return None

    def fend(self, f):
        o = f + 4
        while o < self.text[1]:
            w = struct.unpack_from('<I', self.d, o)[0]
            if (w & 0xFFFF4000) == 0xE92D4000:
                return o
            o += 4
        return o

    def dis(self, a, b):
        out, o = [], a
        while o < b:
            got = False
            for i in self.cs.disasm(self.d[o:b], o):
                out.append(i)
                o = i.address + 4
                got = True
            if o < b:
                o += 4
        return out

    def pool(self, i):
        """Valor cargado por ldr rX, [pc, #n] (relocalizado si procede)."""
        if not (i.mnemonic.startswith('ldr') and '[pc' in i.op_str):
            return None
        m = HEX.search(i.op_str.split('[pc')[1])
        p = i.address + 8 + (int(m.group(1), 0) if m else 0)
        return self.ptr.get(p, struct.unpack_from('<I', self.d, p)[0])

    def adrval(self, i):
        if i.mnemonic not in ('adr', 'add', 'sub') or 'pc' not in i.op_str:
            return None
        w = struct.unpack_from('<I', self.d, i.address)[0]
        if (w & 0x0FEF0000) == 0x028F0000:
            return i.address + 8 + _rot(w)
        if (w & 0x0FEF0000) == 0x024F0000:
            return i.address + 8 - _rot(w)
        return None

    def anotar(self, a, b):
        """Líneas de desensamblado con literales, cadenas, bl a importaciones."""
        lines = []
        for i in self.dis(a, b):
            ex = ''
            v = self.pool(i)
            if v is None:
                v = self.adrval(i)
            if v is not None:
                ex = f' ; ={v:#x}'
                if 0 < v < len(self.d) and self.text[1] <= v:
                    s = self.cstr(v, 40)
                    if s and s.isprintable():
                        ex += f' {s!r}'
            if i.mnemonic in ('bl', 'b', 'blx') or i.mnemonic.startswith('b'):
                m = HEX.search(i.op_str)
                if m and i.op_str.startswith('#'):
                    t = int(m.group(1), 0)
                    nm = self.stub(t)
                    if nm:
                        ex += f' <{nm}>'
            lines.append(f'{i.address:#x}: {i.mnemonic} {i.op_str}{ex}')
        return lines

    def stub(self, t):
        for k in (0, 4, 8, 12):
            if t + k in self.imp:
                return self.imp[t + k]
        return None


def _rot(w):
    rot = ((w >> 8) & 0xf) * 2
    imm = w & 0xff
    return ((imm >> rot) | (imm << (32 - rot))) & 0xffffffff
