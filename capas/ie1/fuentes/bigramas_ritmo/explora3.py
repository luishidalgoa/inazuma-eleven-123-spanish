import sys, json, tempfile, collections
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent)); sys.path.insert(1, r'C:\Users\luish\Projects\inazuma-eleven-123-spanish\work\ie1\capas\historial\fuentes\v88_bigramas_total')
import comun88, ritmo as R
A = comun88.modulo('v88_bigramas', Path(r'C:\Users\luish\Projects\inazuma-eleven-123-spanish\work\ie1\capas\historial\fuentes\v88_bigramas_total\apply.py'))
get = A.K.abrir(A.K.ROOT/'work/shared/candidatas/probe_ie1_v88/archive.fa')
tmp=Path(tempfile.mkdtemp()); fu={}
for f in A.FUENTES:
    (tmp/Path(f).name).write_bytes(get(f)); fu[f]=A.cargar(tmp/Path(f).name)
P=A.Pares(fu); mq=R.Maqueta(fu[A.F12], A.codepoint)
print('F8 sx', fu[A.F8].sx, 'F12T sx', fu[A.F12T].sx, fu[A.F12T].sy)
for p in ['an','ha','on','do','Na','at','th','in','er','ar','li','ie']:
    print(p, 'f12new', mq.trozo(p) is not None, 'f8', P.f8(p) is not None, 'f12t', P.f12t(p) is not None,
          'f8 raw', end=' ')
    try:
        px, wc, s = A.V87.par(fu[A.F8], p[0], p[1]); print(wc, s)
    except Exception as e: print('err', e)
reg=json.load(open(A.REGISTRO,encoding='utf-8'))
codec=A.Codec(reg['bigramas'])
uni,_,_,_,_=A.recoger(get,codec)
cnt=collections.Counter()
for u in uni:
    if u['tipo']!='nombre' or u['excluido']: continue
    t=u['segs'][0][1]
    for i in range(len(t)-1):
        p=t[i:i+2]
        if ' ' in p: continue
        cnt[(mq.trozo(p) is not None, P.f8(p) is not None, P.f12t(p) is not None)]+=1
print(cnt)
