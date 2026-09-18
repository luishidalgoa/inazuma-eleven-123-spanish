from cro import *
import pickle,re,bisect,json
from calls import res
ins=pickle.load(open('ins.pkl','rb'))
addrs=[a for a,_,_ in ins]
extra=[0x71b94,0xbf06c,0x1317c4,0x13fd00,0x1443d8,0x1446f8,0x1447c4,0x154a64]
sites=[(a,font,fs.replace(chr(92),'/').split('/')[-1],ln) for f,a,font,slot,fs,ln in res]
from run3 import near_file
sites+=[(a,'?',near_file(a),None) for a in extra]
out=[]
for a,font,fs,ln in sorted(sites):
    k=bisect.bisect_left(addrs,a)
    reg={}
    sp={}
    for ad,m,o in ins[max(0,k-40):k]:
        mm=re.match(r'(\w+), #(0x[0-9a-f]+|\d+)$',o)
        if m=='mov' and mm: reg[mm.group(1)]=int(mm.group(2),0)
        elif m in('mov','add','sub','ldr','ldrb','ldrh','orr','and','lsl') :
            r=o.split(',')[0]; reg.pop(r,None)
        mm=re.match(r'(\w+), \[sp, #(0x[0-9a-f]+|\d+)\]$',o)
        if m=='str' and mm: sp[int(mm.group(2),0)]=reg.get(mm.group(1))
        mm=re.match(r'(\w+), \{(.*)\}$',o)
        if m=='stm' and mm:
            base=mm.group(1)
            # base = sp+off if 'add base, sp, #off' seen
            pass
        mm=re.match(r'(\w+), sp, #(0x[0-9a-f]+|\d+)$',o)
        if m=='add' and mm: reg['sp+'+mm.group(1)]=int(mm.group(2),0)
        if m=='stm':
            b=o.split(',')[0]; off=reg.get('sp+'+b)
            if off is not None:
                for j,r in enumerate(re.findall(r'\w+',o.split('{')[1])):
                    sp[off+4*j]=reg.get(r)
    w,h=sp.get(0x18),sp.get(0x1c)
    cells=(w*h//2)//0x20 if w and h else None
    out.append(dict(llamada=hex(a),gestor=font,fichero=fs,linea=ln,ancho=w,alto=h,celdas=cells))
    print(hex(a),font,fs,ln,w,h,cells)
json.dump(out,open('llamadas.json','w'),ensure_ascii=False,indent=1)
