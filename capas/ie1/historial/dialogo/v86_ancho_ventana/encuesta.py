"""Encuesta de 0x301c (y de las otras aperturas) en todos los eventos de un archive.fa (solo lectura)."""
import sys, json
from collections import Counter
from pathlib import Path
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[5]
sys.path.insert(0, str(ROOT/'work/ie1/capas/historial/dialogo/v82_saltos_dialogo/diagnostico'))
import ventanas as V
K = V.K
fa = Path(sys.argv[1])
base = K.Archivo(fa)
cnt = Counter(); argc = Counter(); por_arg = [Counter() for _ in range(8)]; ej = {}; nz = []
otros = Counter(); n_ev = 0
for eid in sorted(base.indice):
    try: d = base.evento(eid)
    except Exception: continue
    if len(d) < 32: continue
    n_ev += 1
    try:
        for ident, op, k, v in V.instrucciones(d):
            if op in (0x308d, 0x308f, 0x3090, 0x3091): otros[(hex(op), len(v))] += 1
            if op != 0x301c: continue
            argc[(len(v), tuple(k))] += 1
            for i, x in enumerate(v[:8]): por_arg[i][x] += 1
            if len(v) > 5 and (v[4] or v[5]): nz.append((eid, ident, v))
            if eid == 0x81000090 or str(eid) == '81000090': ej.setdefault('81000090', []).append((ident, k, v))
    except Exception as e:
        pass
print('eventos', n_ev)
print('argc/tipos', argc.most_common())
for i, c in enumerate(por_arg):
    if c: print('arg', i, c.most_common(8))
print('arg4/arg5 != 0:', len(nz), nz[:10])
print('81000090:', ej)
print('otras aperturas (aprox.):', otros.most_common())
print('tipo indice', type(next(iter(base.indice))), list(base.indice)[:3])
