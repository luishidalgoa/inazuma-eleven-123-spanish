"""Desensamblado de solo lectura de ina_main1.cro BASE (work/shared/base_3ds)."""
import sys, importlib.util
from pathlib import Path
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
src = (ROOT/'work/ie1/capas/v82/saltos_dialogo/diagnostico/cro.py').read_text(encoding='utf-8')
src = src.replace("'work/shared/candidatas/probe_ie1_v81/romfs/cro/ina_main1.cro'", "'work/shared/base_3ds/romfs/cro/ina_main1.cro'")
src = src.replace("parents[6]", "parents[5]")
g = {'__file__': str(HERE/'desens.py'), '__name__': 'crob'}
exec(compile(src, 'cro', 'exec'), g)
if __name__ == '__main__':
    for a in sys.argv[1:]:
        s, e = (int(x, 16) for x in a.split(':'))
        print('\n'.join(g['dis'](s, e))); print('----')
