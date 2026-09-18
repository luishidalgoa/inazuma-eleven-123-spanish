import struct, sys, re
from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM
R='C:/Users/luish/Projects/inazuma-eleven-123-spanish/work/shared/base_3ds/romfs/cro/'
class Cro:
    def __init__(s, name):
        s.d=open(R+name,'rb').read(); d=s.d
        u=lambda o: struct.unpack_from('<I',d,o)[0]; s.u=u
        s.segs=[struct.unpack_from('<III',d,u(0xC8)+12*i) for i in range(u(0xCC))]
        s.cs,s.ce=s.segs[0][0],s.segs[0][0]+s.segs[0][1]
        s.md=Cs(CS_ARCH_ARM,CS_MODE_ARM)
        s.imps={}
        for i in range(u(0x104)):
            no,ro=struct.unpack_from('<II',d,u(0x100)+8*i)
            nm=d[no:d.index(b'\0',no)].decode(); p=ro
            while True:
                so,typ,last,_a,_p,add=struct.unpack_from('<IBBBBI',d,p)
                s.imps[s.segs[so&0xf][0]+(so>>4)]=nm
                if last: break
                p+=12
    def dis(s,a,b):
        out=[]
        for i in s.md.disasm(s.d[a:b],a):
            c=''
            if i.mnemonic.startswith('b') and i.op_str.startswith('#'):
                t=int(i.op_str[1:],16)
                if t in s.imps: c=' ; '+s.imps[t]
            if i.mnemonic.startswith('ldr') and '[pc' in i.op_str:
                m=re.search(r'#(-?0x[0-9a-f]+|\d+)\]',i.op_str); imm=int(m.group(1),0) if m else 0
                c=f' ; ={s.u(i.address+8+imm):#x}'
            out.append(f'{i.address:6x}  {i.mnemonic:8s} {i.op_str}{c}')
        return out
    def word(s,o): return s.u(o)
    def sig(s,o):
        w=s.u(o)
        if (w&0x0E000000)==0x0A000000: return w&0xFF000000, 0xFF000000
        if (w&0x0F7F0000)==0x051F0000: return w&0xFFFFF000, 0xFFFFF000   # ldr pc-rel
        return w, 0xFFFFFFFF
    def find(s, other, a, n):
        """posiciones de s donde encaja la secuencia de other[a:a+4n] (enmascarada)."""
        pat=[other.sig(a+4*k) for k in range(n)]
        res=[]
        first=pat[0]
        for o in range(s.cs, s.ce-4*n, 4):
            if (s.u(o)&first[1])!=first[0]: continue
            if all((s.u(o+4*k)&m)==v for k,(v,m) in enumerate(pat)): res.append(o)
        return res
    def callers(s,t):
        r=[]
        for o in range(s.cs,s.ce,4):
            w=s.u(o)
            if (w&0x0E000000)==0x0A000000:
                off=w&0xFFFFFF
                if off&0x800000: off-=0x1000000
                if o+8+off*4==t: r.append(o)
        return r
c1=Cro('ina_main1.cro'); c2=Cro('ina_main2.cro')
def _rel(s):
    s.rel={}
    for i in range(s.u(0x12C)):
        so,typ,sidx,_a,_b,add=struct.unpack_from('<IBBBBI',s.d,s.u(0x128)+12*i)
        s.rel[s.segs[so&0xf][0]+(so>>4)]=(sidx,add)
Cro._rel=_rel
_old=Cro.dis
def dis2(s,a,b):
    if not hasattr(s,'rel'): s._rel()
    out=[]
    for l in _old(s,a,b):
        if ' ; =' in l and '[pc' in l:
            ad=int(l.split()[0],16)
            m=re.search(r'#(-?0x[0-9a-f]+|\d+)\]',l); imm=int(m.group(1),0) if m else 0
            lit=ad+8+imm
            if lit in s.rel:
                si,add=s.rel[lit]; l+=f' seg{si}+{add:#x}'
        out.append(l)
    return out
Cro.dis=dis2
