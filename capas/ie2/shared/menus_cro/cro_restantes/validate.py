"""IE2 v04 · validación de romfs/cro/ina_main2.cro y de las BCFNT de extra/ (lógica común en
work/ie1/capas/historial/menus_cro/v90_cro_restantes/validar90.py)."""
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[6]
sys.argv = [sys.argv[0], 'ie2']
runpy.run_path(str(ROOT / 'work/ie1/capas/historial/menus_cro/v90_cro_restantes/validar90.py'), run_name='__main__')
