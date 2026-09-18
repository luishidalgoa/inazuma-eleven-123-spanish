"""v88 · utilidades comunes: lectura de archive.fa con mmap (sin cargar 1,6 GB en memoria) y módulos previos."""
from __future__ import annotations

import importlib.util
import mmap
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]


def modulo(nombre, ruta):
    if nombre in sys.modules:
        return sys.modules[nombre]
    spec = importlib.util.spec_from_file_location(nombre, ruta)
    m = importlib.util.module_from_spec(spec)
    sys.modules[nombre] = m
    spec.loader.exec_module(m)
    return m


class _MM(mmap.mmap):
    def index(self, sub, start=0, end=None):
        p = self.find(sub, start, len(self) if end is None else end)
        if p < 0:
            raise ValueError('substring not found')
        return p


def indice_fa(ruta: Path):
    """{ruta: (offset absoluto, tamaño)} de un archive.fa, leído con mmap."""
    f = open(ruta, 'rb')
    d = _MM(f.fileno(), 0, access=mmap.ACCESS_READ)
    de_off, dh_off, fe_off, name_off, data_off = struct.unpack_from('<5i', d, 4)
    de_cnt = struct.unpack_from('<H', d, 24)[0]

    def name(base):
        o = name_off + base
        return d[o:d.index(b'\0', o)].decode('shift-jis', 'replace')

    out = {}
    for i in range(de_cnt):
        o = de_off + i * 24
        fc = struct.unpack_from('<H', d, o + 4)[0]
        nb = struct.unpack_from('<I', d, o + 8)[0]
        ff = struct.unpack_from('<I', d, o + 12)[0]
        dp = name(struct.unpack_from('<I', d, o + 20)[0])
        for j in range(fc):
            fo = fe_off + (ff + j) * 16
            nr, fo2, sz = struct.unpack_from('<III', d, fo + 4)
            out[dp + name(nb + nr)] = (data_off + fo2, sz)
    return d, out


def abrir(ruta: Path):
    d, idx = indice_fa(Path(ruta))

    def get(p):
        o, s = idx[p]
        return bytes(d[o:o + s])
    get.indice = idx
    return get
