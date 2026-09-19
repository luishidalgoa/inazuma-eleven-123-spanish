"""IE1 v90 · validación de romfs/cro/ina_main1.cro y de las BCFNT de extra/ (ver validar90.py)."""
import runpy
import sys
from pathlib import Path

sys.argv = [sys.argv[0], 'ie1']
runpy.run_path(str(Path(__file__).resolve().parent / 'validar90.py'), run_name='__main__')
