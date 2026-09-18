"""IE2 v09 · cofres: validación offline de romfs/cro/ina_main2.cro (código en work/ie1/capas/v93/cofres/cofres_comun.py)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[5] / 'ie1/capas/v93/cofres'))
import cofres_comun  # noqa: E402
cofres_comun.validar('ie2')
