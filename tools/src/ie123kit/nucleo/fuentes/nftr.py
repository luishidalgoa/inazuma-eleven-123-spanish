"""Read NFTR character maps and advances without modifying game assets.

Usage: python -m ie123kit._legado.nftr_metrics path/to/FONT12.NFTR
NFTR map keys in the IE1 assets are Shift-JIS codes, not Unicode code points.
"""
import struct


def read_metrics(data, with_offsets=False):
    if len(data) < 44 or data[:4] != b'RTFN' or data[16:20] != b'FNIF':
        raise ValueError('unsupported NFTR header')
    if struct.unpack_from('<I', data, 8)[0] != len(data):
        raise ValueError('inconsistent NFTR file size')

    def blocks(offset, magic):
        visited = set()
        while offset:
            pos = offset - 8
            if pos in visited or pos < 0 or pos + 16 > len(data):
                raise ValueError('invalid NFTR block chain')
            visited.add(pos)
            size = struct.unpack_from('<I', data, pos + 4)[0]
            if data[pos:pos+4] != magic or size < 16 or pos + size > len(data):
                raise ValueError('invalid NFTR block')
            yield pos, size
            next_field = pos + (16 if magic == b'PAMC' else 12)
            offset = struct.unpack_from('<I', data, next_field)[0]

    cmap = {}
    for pos, size in blocks(struct.unpack_from('<I', data, 40)[0], b'PAMC'):
        begin, end, method = struct.unpack_from('<HHH', data, pos+8)
        body = pos + 20
        if method == 0:
            first = struct.unpack_from('<H', data, body)[0]
            entries = {cp: first+cp-begin for cp in range(begin, end+1)}
        elif method == 1:
            if body+2*(end-begin+1) > pos+size:
                raise ValueError('truncated NFTR map')
            entries = {cp: struct.unpack_from('<H', data, body+2*(cp-begin))[0]
                       for cp in range(begin, end+1)}
        elif method == 2:
            count = struct.unpack_from('<H', data, body)[0]
            if body+2+4*count > pos+size:
                raise ValueError('truncated NFTR scan map')
            entries = dict(struct.unpack_from('<HH', data, body+2+4*i) for i in range(count))
        else:
            raise ValueError('unknown NFTR map type')
        cmap.update({cp: gi for cp, gi in entries.items() if gi != 65535})
    widths = {}
    offsets = {}
    for pos, size in blocks(struct.unpack_from('<I', data, 36)[0], b'HDWC'):
        begin, end = struct.unpack_from('<HH', data, pos+8)
        if 16+3*(end-begin+1) > size:
            raise ValueError('truncated NFTR widths')
        widths.update({gi: struct.unpack_from('<bBB', data, pos+16+3*(gi-begin))
                       for gi in range(begin, end+1)})
        offsets.update({gi: pos+16+3*(gi-begin) for gi in range(begin, end+1)})
    metrics = {cp: widths[gi] for cp, gi in cmap.items() if gi in widths}
    if with_offsets:
        return metrics, {cp: offsets[gi] for cp, gi in cmap.items() if gi in widths}
    return metrics
