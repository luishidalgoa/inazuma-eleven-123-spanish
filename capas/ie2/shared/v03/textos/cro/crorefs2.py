"""Referencias (ADR PC-relativo y pools con relocacion) a literales de un CRO (adaptado de IE1 v33 crorefs.py)."""
import struct, re
from pathlib import Path

JPRE = re.compile('[\u3040-\u30ff\u4e00-\u9fff\uff01-\uff5e]')


def rotimm(w):
    rot = ((w >> 8) & 0xf) * 2; imm = w & 0xff
    return ((imm >> rot) | (imm << (32 - rot))) & 0xffffffff


class Refs:
    def __init__(self, data):
        self.d = d = data
        u = self.u = lambda o: struct.unpack_from('<I', d, o)[0]
        self.segs = [struct.unpack_from('<III', d, u(0xC8) + 12 * i) for i in range(u(0xCC))]
        cs, ce = self.segs[0][0], self.segs[0][0] + self.segs[0][1]
        reloff, relnum = u(0x128), u(0x12C)
        self.rel_table = (reloff, relnum * 12)
        self.byval = {}
        self.reltargets = set()
        for i in range(relnum):
            so, typ, sidx, _a, _b, add = struct.unpack_from('<IBBBBI', d, reloff + 12 * i)
            t = self.segs[so & 0xf][0] + (so >> 4)
            self.reltargets.add(t)
            self.byval.setdefault(self.segs[sidx][0] + add, []).append(t)
        self.adr, self.ldrs = {}, {}
        self.adr_ins = set()
        for off in range(cs, ce, 4):
            w = u(off)
            if (w & 0x0FEF0000) == 0x028F0000:
                self.adr.setdefault(off + 8 + rotimm(w), []).append(off)
            elif (w & 0x0FEF0000) == 0x024F0000:
                self.adr.setdefault(off + 8 - rotimm(w), []).append(off)
            if (w & 0x0F7F0000) == 0x051F0000:
                imm = w & 0xfff
                self.ldrs.setdefault(off + 8 + (imm if (w >> 23) & 1 else -imm), []).append(off)
        # todos los destinos referenciados (para cortar huecos)
        self.targets = set(self.adr) | set(self.byval)

    def refs(self, o):
        out = ['adr@%x' % a for a in self.adr.get(o, [])]
        for t in self.byval.get(o, []):
            us = self.ldrs.get(t, [])
            out += ['pool@%x<-ldr@%x' % (t, x) for x in us] or ['ptr@%x' % t]
        return out

    def literales(self):
        """Literales cp932 con japones que empiezan en un destino referenciado.

        Si el byte anterior no es NUL (sufijo compartido o dato pegado), solo se acepta
        cuando todo el literal es japones / ancho completo."""
        d = self.d
        res = []
        for o in sorted(self.targets):
            if not (0 < o < len(d)) or d[o] == 0:
                continue
            pegado = d[o - 1] != 0
            e = d.find(b'\0', o)
            b = d[o:e]
            try:
                t = b.decode('cp932')
            except UnicodeDecodeError:
                continue
            if not JPRE.search(t) or any(ord(c) < 0x20 and c != '\n' for c in t):
                continue
            res.append((o, t, len(b)))
        return res

    def hueco(self, o):
        """Fin del hueco: siguiente byte no NUL o siguiente destino referenciado tras el NUL."""
        d = self.d
        e = d.find(b'\0', o)
        f = e
        while f < len(d) and d[f] == 0 and f not in self.targets and f not in self.reltargets:
            f += 1
        return e, f
