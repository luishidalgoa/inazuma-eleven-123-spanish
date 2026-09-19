"""IE2 v04 · literales visibles de ina_main2.cro que quedaban en japonés (issue de la tanda CRO restante).

Tabla: literales.json de esta carpeta. La pasada es común con IE1 v90 porque los códigos de bigrama y las
fuentes font/*.bcfnt son compartidos por la recopilación: este script ejecuta
work/ie1/capas/historial/menus_cro/v90_cro_restantes/apply.py, que escribe aquí romfs/cro/ina_main2.cro, extra/font/*.bcfnt
(idénticas a las de IE1 v90), informe.json y previews/. Registro: work/ie1/capas/historial/menus_cro/v90_cro_restantes/registro.json.
Uso: python -X utf8 apply.py   (después validate.py)
"""
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[6]
runpy.run_path(str(ROOT / 'work/ie1/capas/historial/menus_cro/v90_cro_restantes/apply.py'), run_name='__main__')
