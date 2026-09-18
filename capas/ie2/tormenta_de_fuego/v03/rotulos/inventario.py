"""IE2 Fuego v03 · rótulos: inventario JP de rótulos (0x4037 a3) y objetivos (0x2017/18/1c/23 a3) con su par NDS.
Salida: inventario.json. Uso: python -X utf8 inventario.py"""
from __future__ import annotations
import json, struct, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[5]
sys.path.insert(0, str(ROOT / 'work/ie2/tormenta_de_fuego/capas/v02/dialogo'))
import comun_ie2 as M  # noqa: E402

OPS_OBJ = (0x2017, 0x2018, 0x201c, 0x2023)


def refs(data):
    head = data[:32]
    count = struct.unpack_from('<H', head, 12)[0]
    pos, out = 32, {}
    for _ in range(count):
        ident, length, opcode, argc, _ = struct.unpack_from('<HHHBB', data, pos)
        types = 4 * ((argc + 7) // 8)
        for a in range(argc):
            kind = (data[pos + 8 + a // 2] >> (4 * (a % 2))) & 15
            if kind == 3:
                v = struct.unpack_from('<I', data, pos + 8 + types + 4 * a)[0]
                out.setdefault(v, []).append((ident, opcode, a + 1))
        pos += length
    return out


def main():
    A = M.Archivo(M.JP)
    nds = M.nds_eventos('eve')
    rot, obj, cab = [], [], 0
    for eid in A.ids('eve'):
        if eid in M.PROTEGIDOS:
            continue
        data = A.evento('eve', eid)
        _, ins, recs = M.S.parse(data)
        r = refs(data)
        par = None
        for i, rec in enumerate(recs):
            op = ins.get(rec.instruction)
            rr = [(o, p) for _, o, p in r.get(i, [])]
            try:
                jp = rec.body.decode('cp932')
            except UnicodeDecodeError:
                continue
            if op == 0x4037 and rec.argument == 3 and (0x4037, 3) in rr:
                rot.append({'evento': eid, 'indice': i, 'jp': jp})
            elif op == 0x402f and rec.argument == 2 and jp == 'もくてき':
                cab += 1
            elif op in OPS_OBJ and rec.argument == 3 and (op, 3) in rr and jp:
                es = None
                if eid in nds:
                    if par is None:
                        par = M.emparejar_evento(data, nds[eid])
                    m, ok, mal, tb = par
                    if (mal <= ok or mal == 0) and rec.instruction in m and m[rec.instruction] in tb:
                        t, b, o = tb[m[rec.instruction]]
                        if t == 3 and o == 0:
                            es = M.decode_nds(b)
                obj.append({'evento': eid, 'indice': i, 'op': hex(op), 'jp': jp, 'es_nds': es,
                            'nds': eid in nds})
    (HERE / 'inventario.json').write_text(json.dumps({'cabeceras': cab, 'rotulos': rot, 'objetivos': obj},
                                                     ensure_ascii=False, indent=1), encoding='utf-8')
    print(len(rot), len({x['jp'] for x in rot}), cab, len(obj), sum(1 for x in obj if x['es_nds'] is None))


if __name__ == '__main__':
    main()
