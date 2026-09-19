import sys, json, tempfile
from pathlib import Path
sys.path.insert(0, r'C:\Users\luish\Projects\inazuma-eleven-123-spanish\work\ie1\capas\historial\fuentes\v88_bigramas_total')
import apply as A
import comun88 as K
get = K.abrir(K.ROOT/'work/shared/candidatas/probe_ie1_v88/archive.fa')
tmp=Path(tempfile.mkdtemp())
p=tmp/'F12.bcfnt'; p.write_bytes(get(A.F12)); F=A.cargar(p)
g=A.V85.Glifos(F)
out={}
for ch in 'abcdefghijklmnopqrstuvwxyzáéíóúñüABCDEFGHIJKLMNOPQRSTUVWXYZÁÉÍÓÚÑ.,;:!?¡¿-\'"()0123456789 　':
    try: d,w,adv,px,gi=g.letra(ch)
    except KeyError: out[ch]=None; continue
    sol=[x for (x,y),v in px.items() if v>=A.SOLIDO[A.F12]]
    allx=[x for (x,y) in px]
    out[ch]=(min(sol) if sol else None, max(sol) if sol else None, min(allx) if allx else None, max(allx) if allx else None, adv, F.metrics[gi], F.sx, F.sy)
for k,v in out.items(): print(repr(k),v)
