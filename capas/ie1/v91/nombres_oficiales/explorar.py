"""Busca un patrón en todos los registros de texto de los eventos IE1 de la candidata."""
import sys, re, collections
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'v82/saltos_dialogo'))
import comun82 as M
K = M.K
BASE = K.ROOT / 'work/shared/candidatas/probe_ie2_v05/archive.fa'
sys.stdout.reconfigure(encoding='utf-8')
pat = re.compile(sys.argv[1], re.I)
a = K.Archivo(BASE)
n = collections.Counter()
for eid in sorted(a.indice):
    try:
        end, ops, recs = K.S.parse(a.evento(eid))
    except ValueError:
        n['sinparse'] += 1; continue
    for i, r in enumerate(recs):
        try:
            t = K.a_espanol(r.body)
        except Exception:
            continue
        if pat.search(t):
            print(eid, i, hex(ops.get(r.instruction, 0)), r.argument, len(r.body), t)
print(n)
