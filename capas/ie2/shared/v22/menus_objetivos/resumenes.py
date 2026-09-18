"""IE2 v22 · objetivos que no caben en 40 B (20 casillas): candidatos resumidos, en orden de preferencia.

Excepción pedida por el usuario SOLO para los objetivos (issue #77). La tabla contiene texto del juego, así
que NO se versiona: vive en work/ie2/shared/capas/v22/menus_objetivos/resumenes.json con el formato
{"objetivo oficial íntegro": ["candidato 1", "candidato 2", ...]}. Sin ese fichero la tabla queda vacía y
apply.py solo acepta objetivos que quepan íntegros.
"""
import json
from pathlib import Path

_RAIZ = next(p for p in Path(__file__).resolve().parents if (p / 'tools/src').is_dir())
_DATOS = _RAIZ / 'work/ie2/shared/capas/v22/menus_objetivos/resumenes.json'
RESUMEN = json.loads(_DATOS.read_text('utf-8')) if _DATOS.exists() else {}
