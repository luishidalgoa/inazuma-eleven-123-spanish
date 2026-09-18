"""IE2 v09 · cofres: cierre neutro «¡Premio!» del mensaje de objeto obtenido.
Código común en work/ie1/capas/v93/cofres/cofres_comun.py (mismo patrón que IE1, offsets de IE2).
Base: work/ie2/shared/capas/v04/cro_restantes/romfs/cro/ina_main2.cro -> romfs/cro/ina_main2.cro
Uso: python -X utf8 work/ie2/shared/capas/v09/cofres/apply.py   (después validate.py)"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[5] / 'ie1/capas/v93/cofres'))
import cofres_comun  # noqa: E402
cofres_comun.aplicar('ie2')
