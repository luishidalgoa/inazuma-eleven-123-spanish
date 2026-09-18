import sys
from explorar import CROS, Cro
j=sys.argv[1]; c=Cro(CROS[j][0].read_bytes()); slots=CROS[j][1]
a=int(sys.argv[2],16); b=int(sys.argv[3],16)
for l in c.anotar(a,b):
    for s,n in slots.items():
        if f'={s:#x}' in l: l+=f'  [{n}]'
    print(l)
