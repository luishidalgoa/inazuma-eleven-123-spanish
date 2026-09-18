"""Argumentos de las instrucciones 0x301c (abrir ventana) en todos los eventos de una candidata."""
import sys, struct, json
from collections import Counter
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / 'v77/saltos_dialogo'))
import comun as K
def instrucciones(data):
    if data[:4] != b'SSD\0': data = b'SSD\0' + data[4:]
    _, _, size, count, texts, code_size, *_ = struct.unpack_from('<4sIIHHIIII', data)
    pos = 32
    for _ in range(count):
        ident, length, opcode, argc, _u = struct.unpack_from('<HHHBB', data, pos)
        ts = 4 * ((argc + 7) // 8)
        kinds = [(data[pos + 8 + a // 2] >> (4 * (a % 2))) & 15 for a in range(argc)]
        vals = list(struct.unpack_from('<%dI' % argc, data, pos + 8 + ts))
        yield ident, opcode, kinds, vals
        pos += length
if __name__ == '__main__':
    base = K.Archivo(Path(sys.argv[1]) if len(sys.argv) > 1 else K.ROOT / 'work/shared/candidatas/probe_ie1_v81/archive.fa')
    c = Counter(); ej = {}
    for eid in sorted(base.indice):
        try:
            d = base.evento(eid)
        except Exception:
            continue
        if len(d) < 32: continue
        try:
            for ident, op, k, v in instrucciones(d):
                if op == 0x301c:
                    key = (tuple(k), tuple(v[4:6]) if len(v) > 5 else tuple(v))
                    c[key] += 1; ej.setdefault(key, eid)
        except struct.error:
            pass
    for key, n in c.most_common():
        print(n, key, 'ej', ej[key])
