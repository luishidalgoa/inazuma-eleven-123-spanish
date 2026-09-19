"""Ayudas de desensamblado de ina_main1.cro (solo lectura)."""
import struct, sys
from pathlib import Path
from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM
ROOT = Path(__file__).resolve().parents[7]
P = ROOT / 'work/shared/candidatas/probe_ie1_v81/romfs/cro/ina_main1.cro'
data = P.read_bytes()
u32 = lambda o: struct.unpack_from('<I', data, o)[0]
segs = [struct.unpack_from('<III', data, u32(0xC8) + 12 * i) for i in range(u32(0xCC))]
code_s, code_e = segs[0][0], segs[0][0] + segs[0][1]
md = Cs(CS_ARCH_ARM, CS_MODE_ARM); md.detail = False
# relocaciones: destino -> valor
rel = {}
for i in range(u32(0x12C)):
    so, typ, sidx, _a, _b, add = struct.unpack_from('<IBBBBI', data, u32(0x128) + 12 * i)
    rel[segs[so & 0xf][0] + (so >> 4)] = (typ, sidx, add)
# importaciones con nombre: 0x100/0x104 -> (nameoff, relocoff)
imps = {}
for i in range(u32(0x104)):
    no, ro = struct.unpack_from('<II', data, u32(0x100) + 8 * i)
    name = data[no:data.index(b'\0', no)].decode()
    # cadena de relocaciones (formato: <segoff u32, type u8, last u8, all u8, pad, addend u32>)
    p = ro
    while True:
        so, typ, last, _al, _p, add = struct.unpack_from('<IBBBBI', data, p)
        imps[segs[so & 0xf][0] + (so >> 4)] = name
        if last: break
        p += 12
def dis(s, e):
    out = []
    for ins in md.disasm(data[s:e], s):
        c = ''
        if ins.mnemonic.startswith('bl') or ins.mnemonic == 'b':
            try:
                t = int(ins.op_str.lstrip('#'), 16)
                if t in imps: c = ' ; ' + imps[t]
            except ValueError: pass
        if 'pc' in ins.op_str and ins.mnemonic.startswith('ldr') and '[pc' in ins.op_str:
            try:
                imm = int(ins.op_str.split('#')[-1].rstrip(']'), 16) if '#' in ins.op_str else 0
                lit = ins.address + 8 + imm
                v = u32(lit)
                c = f' ; ={v:#x}' + (f' reloc{rel[lit]}' if lit in rel else '')
            except Exception: pass
        out.append(f'{ins.address:6x}  {ins.mnemonic:8s} {ins.op_str}{c}')
    return out
def callers(t):
    r = []
    for o in range(code_s, code_e, 4):
        w = u32(o)
        if (w & 0x0E000000) == 0x0A000000:
            off = w & 0xFFFFFF
            if off & 0x800000: off -= 0x1000000
            if o + 8 + off * 4 == t: r.append(o)
    return r
if __name__ == '__main__':
    a, b = int(sys.argv[1], 16), int(sys.argv[2], 16)
    print('\n'.join(dis(a, b)))
