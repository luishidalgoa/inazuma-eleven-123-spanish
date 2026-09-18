"""Imprime las cajas QNA completas: python qna.py <arc relativo a inazuma2/data_iz> <textura|*> ..."""
import sys

import comun as C

ruta = 'inazuma2/data_iz/' + sys.argv[1]
q = C.qna_cajas(ruta)
for t in sorted(q):
    if sys.argv[2] == '*' or any(a in t for a in sys.argv[2:]):
        print(t, sorted(q[t], key=lambda b: (b[1], b[0])))
