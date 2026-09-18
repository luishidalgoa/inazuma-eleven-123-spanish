import sys
sys.path.insert(0,'.')
import comun90 as C
T=C.Tipografia()
def minimo(t,campo):
    for n in range(1,len(t)+1):
        try: return n, T.celdas(t,campo,n)
        except ValueError: pass
for arg in sys.argv[1:]:
    campo,t=arg.split(':',1)
    n,cel=minimo(t,campo)
    print(f'{campo:7s} {t!r:22s} {n:2d} {cel}')
