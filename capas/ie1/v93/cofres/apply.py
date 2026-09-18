"""IE1 v93 · cofres: cierre neutro «¡Premio!» del mensaje de objeto obtenido (ver cofres_comun.py).
Base: work/ie1/capas/v90/cro_restantes/romfs/cro/ina_main1.cro -> romfs/cro/ina_main1.cro
Uso: python -X utf8 work/ie1/capas/v93/cofres/apply.py   (después validate.py)"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import cofres_comun  # noqa: E402
cofres_comun.aplicar('ie1')
