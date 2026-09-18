"""IE1 v93 · cofres: validación offline de romfs/cro/ina_main1.cro (ver cofres_comun.py)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import cofres_comun  # noqa: E402
cofres_comun.validar('ie1')
