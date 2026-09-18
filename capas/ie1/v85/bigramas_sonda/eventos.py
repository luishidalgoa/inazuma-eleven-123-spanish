"""v85 · sonda de bigramas: lectura de instrucciones SSD con sus argumentos (tipo, valor)."""
from __future__ import annotations

import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
sys.path.insert(0, str(ROOT / 'tools'))
from fa_unpack import FaArchive  # noqa: E402
from lz10 import decompress  # noqa: E402
from pkb_unpack import parse_index  # noqa: E402
import ssd_records as S  # noqa: E402

PKH = 'inazuma1/data_iz/script/eve.pkh'
PKB = 'inazuma1/data_iz/script/eve.pkb'


def abrir(fa):
    arc = FaArchive(str(fa))
    por = {p: (o, s) for p, o, s in arc.entries}
    return lambda p: bytes(arc.d[por[p][0]:por[p][0] + por[p][1]])


def instrucciones(data):
    """[(ident, opcode, [(tipo, valor)])] en orden."""
    if data[:4] != b'SSD\0':
        data = b'SSD\0' + data[4:]
    _, _, size, count, texts, code_size, text_size, _, _ = struct.unpack_from('<4sIIHHIIII', data)
    pos, out = 32, []
    for _ in range(count):
        ident, length, opcode, argc, _u = struct.unpack_from('<HHHBB', data, pos)
        ts = 4 * ((argc + 7) // 8)
        args = []
        for a in range(argc):
            kind = (data[pos + 8 + a // 2] >> (4 * (a % 2))) & 15
            args.append((kind, struct.unpack_from('<I', data, pos + 8 + ts + 4 * a)[0]))
        out.append((ident, opcode, args, pos))
        pos += length
    return out


def eventos(fa):
    get = abrir(fa)
    pkb = get(PKB)
    for eid, o, s in parse_index(get(PKH)):
        data = decompress(pkb[o:o + s])
        try:
            end, ops, recs = S.parse(data)
        except ValueError:
            continue
        yield eid, data, instrucciones(data), recs
