from cro import *
import re
SLOT={0x1ff2bc:'FONT8',0x1ff2c0:'RUBI8',0x1ff2c4:'FONT12',0x1ff2c8:'FONT12T'}
def cstr(o):
    try: return d[o:d.index(b'\0',o)][:200].decode('latin1')
    except: return '?'
litrefs={}
for loc,ty,val,ts,ss in R:
    if val in SLOT: litrefs[loc]=val
funcs=set()
res=[]
insns={}
def lit(i):
    m=re.search(r'\[pc, #(-?0x[0-9a-f]+|-?\d+)\]',i.op_str)
    if not m: return None
    p=i.address+8+int(m.group(1),0)
    return p
seen=set()
for loc,val in litrefs.items():
    f=fstart(loc) if loc<0x180+0x197d1c else None
    if f is None or f in seen: continue
    seen.add(f)
    # disasm function until next push
    end=f+4
    while end<0x198000:
        w=struct.unpack_from('<I',d,end)[0]
        if (w&0xFFFF4000)==0xE92D4000: break
        end+=4
    ins=list(CS.disasm(d[f:end],f))
    reg={}
    lastlits={}
    for k,i in enumerate(ins):
        p=lit(i)
        if i.mnemonic=='ldr' and p is not None:
            r=i.op_str.split(',')[0]
            v=PTR.get(p, struct.unpack_from('<I',d,p)[0] if p<len(d) else 0)
            lastlits[r]=v
        if i.mnemonic=='blx':
            # look back 8 insns for ldr X,[Y,#off]
            back=ins[max(0,k-12):k]
            slot=None;font=None
            for b in back:
                m=re.match(r'(\w+), \[(\w+), #(0x[0-9a-f]+|\d+)\]',b.op_str)
                if b.mnemonic=='ldr' and m and m.group(1)==i.op_str: slot=int(m.group(3),0)
                if b.mnemonic=='ldr' and b.op_str.startswith('r0, [') :
                    mm=re.match(r'r0, \[(\w+)\]$',b.op_str)
                    if mm and lastlits.get(mm.group(1)) in SLOT: font=SLOT[lastlits[mm.group(1)]]
            if font:
                fs=lastlits.get('r1'); ln=lastlits.get('r2')
                res.append((f,i.address,font,slot,cstr(fs) if fs and fs<0x198000+0x60000 else hex(fs or 0), ln))
