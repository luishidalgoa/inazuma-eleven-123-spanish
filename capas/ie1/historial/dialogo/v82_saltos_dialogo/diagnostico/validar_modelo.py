"""Aplica el modelo del motor (comun82.motor) a todos los diálogos españoles de una candidata y cuenta
en cuántos el motor reajustaría el texto (insertaría o convertiría saltos)."""
import sys, json
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import comun82 as M
K = M.K
base = K.Archivo(Path(sys.argv[1]))
c = Counter(); ej = {}
for eid in sorted(base.indice):
    try:
        end, ops, recs = K.S.parse(base.evento(eid))
    except Exception:
        continue
    for i, r in enumerate(recs):
        if ops.get(r.instruction) != K.OP_DIALOGO or r.argument != 1:
            continue
        t = r.body.decode('cp932', 'replace')
        es = any('Ａ' <= ch <= 'ｚ' for ch in t)
        if b'%' in r.body:
            c[('es' if es else 'jp', 'con %')] += 1
            continue
        try:
            ok = M.respeta_motor(r.body)
        except Exception as e:
            c[('es' if es else 'jp', 'error')] += 1
            continue
        k = ('es' if es else 'jp', 'igual' if ok else 'REAJUSTA', 'piloto' if eid in (81000090, 92040100, 92010520, 92010550, 92010620, 92010640) else 'resto')
        c[k] += 1
        if not ok:
            ej.setdefault(k, []).append((eid, i))
for k, n in sorted(c.items()):
    print(k, n, ej.get(k, [])[:8])
