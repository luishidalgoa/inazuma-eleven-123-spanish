from cro import *
import re, pickle
from calls import res, cstr
known={a for f,a,*_ in res}
ins=disall(0x180,0x180+0x197d1c)
pickle.dump([(i.address,i.mnemonic,i.op_str) for i in ins],open('ins.pkl','wb'))
out=[]
for k,i in enumerate(ins):
    if i.mnemonic!='blx': continue
    back=ins[max(0,k-8):k]
    slot=None; fs=None
    for b in back:
        m=re.match(r'(\w+), \[(\w+), #(0x[0-9a-f]+|\d+)\]$',b.op_str)
        if b.mnemonic=='ldr' and m and m.group(1)==i.op_str and m.group(2)!='pc': slot=int(m.group(3),0)
        mm=re.match(r'r1, \[pc, #(-?0x[0-9a-f]+|-?\d+)\]',b.op_str)
        if b.mnemonic=='ldr' and mm:
            p=b.address+8+int(mm.group(1),0)
            if p in PTR:
                s=cstr(PTR[p])
                if s.endswith('.cpp'): fs=s
    if slot==8 and fs and i.address not in known:
        out.append((i.address, fs.replace(chr(92),'/').split('/')[-1]))
for a,f in out: print(hex(a),f)
print(len(out))
