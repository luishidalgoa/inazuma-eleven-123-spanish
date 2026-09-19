from cro import *
import pickle,re
from calls import cstr
BL=pickle.load(open('bl.pkl','rb'))
ins=pickle.load(open('ins.pkl','rb'))
addrs=[a for a,_,_ in ins]
import bisect
def near_file(a):
    k=bisect.bisect_left(addrs,a)
    for j in range(k-60,k+60):
        if 0<=j<len(ins):
            ad,mn,op=ins[j]
            mm=re.match(r'\w+, \[pc, #(-?0x[0-9a-f]+|-?\d+)\]',op)
            if mn=='ldr' and mm:
                p=ad+8+int(mm.group(1),0)
                if p in PTR:
                    s=cstr(PTR[p])
                    if s.endswith('.cpp'): return s.replace(chr(92),'/').split('/')[-1]
            if mn=='add' and 'pc, #' in op:
                try:
                    s=cstr(ad+8+int(op.split('#')[-1],0))
                    if s.endswith('.cpp'): return s.replace(chr(92),'/').split('/')[-1]
                except: pass
for c in BL[0xe6214]: print(hex(c), near_file(c))
