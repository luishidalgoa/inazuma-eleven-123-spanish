import struct
P='C:/Users/luish/Projects/inazuma-eleven-123-spanish/work/ie1/capas/historial/candidata/v33_base/orig/romfs/cro/ina_main1.cro'
d=open(P,'rb').read()
SEG=[struct.unpack_from('<3I',d,0x1b300c+12*i) for i in range(4)]
def rel():
    out=[]
    for i in range(0x5002):
        tg,ty,ss,_,_,ad=struct.unpack_from('<IBBBBI',d,0x1c31e0+12*i)
        tseg=tg&0xf; toff=tg>>4
        out.append((SEG[tseg][0]+toff, ty, SEG[ss][0]+ad, tseg, ss))
    return out
R=rel()
PTR={}  # location -> value
for loc,ty,val,ts,ss in R:
    PTR[loc]=val
import capstone
CS=capstone.Cs(capstone.CS_ARCH_ARM,capstone.CS_MODE_ARM)
def bl_index():
    idx={}
    for o in range(0x180,0x180+0x197d1c,4):
        w=struct.unpack_from('<I',d,o)[0]
        if (w>>24)&0xf in (0xb,) and (w>>28)!=0xf:
            off=(w&0xffffff); off = off-(1<<24) if off&0x800000 else off
            t=o+8+off*4
            idx.setdefault(t,[]).append(o)
    return idx
def dis(a,n=40):
    for i in CS.disasm(d[a:a+n*4],a):
        extra=''
        if i.mnemonic.startswith('ldr') and 'pc' in i.op_str:
            import re
            m=re.search(r'#(0x[0-9a-f]+|\d+)\]',i.op_str)
            if m:
                p=i.address+8+int(m.group(1),0)
                extra=f' ; ={hex(PTR[p]) if p in PTR else hex(struct.unpack_from("<I",d,p)[0])}'
        print(f'{i.address:#x}: {i.mnemonic} {i.op_str}{extra}')
def fstart(a):
    # walk back to push {.. lr}
    o=a
    while o>0x180:
        w=struct.unpack_from('<I',d,o)[0]
        if (w&0xFFFF4000)==0xE92D4000: return o
        o-=4
IMP={}
def _imp():
    base=0x1b3094; n=0x951
    for i in range(0x395):
        no,fp=struct.unpack_from('<II',d,0x1ba060+8*i)
        name=d[no:d.index(b'\0',no)].decode('latin1')
        # fp is offset into patch table (segment tag?) -> find index
        k=(fp-base)//12 if base<=fp<base+12*n else None
        if k is None: continue
        while k<n:
            tg,ty,last,_,_,ad=struct.unpack_from('<IBBBBI',d,base+12*k)
            IMP[SEG[tg&0xf][0]+(tg>>4)]=(name,ad)
            if last: break
            k+=1
_imp()
def stub(t):
    for k in (4,8,0,12):
        if t+k in IMP: return IMP[t+k][0]
    return None
def disall(a,b):
    out=[]
    o=a
    while o<b:
        got=False
        for i in CS.disasm(d[o:b],o):
            out.append(i); o=i.address+4; got=True
        if o<b and (not got or out[-1].address+4==o): o+=4
    return out
