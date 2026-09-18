"""Capa v06/graficos (issue #73): reutiliza el motor de v03/graficos (solo lectura) y escribe aquí.

v03 NO se modifica. La salida (extra/) contiene solo los ficheros cuyo contenido difiere de v03
(o que v03 no tocaba); cada .arc parte del de v03 si existe, así el overlay v06 sobre v03 es seguro.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
V03 = HERE.parents[1] / 'v03' / 'graficos'
if str(V03) not in sys.path:
    sys.path.insert(0, str(V03))

import comun as C  # noqa: E402

# probe_ie1_v89 se borró; las texturas inazuma1/ de probe_ie2_v05 son idénticas byte a byte a las de v89
# (v90 solo cambió CRO y fuentes; comprobado contra las capas IE1 en extra/). v03/comun.py no se toca.
C.IE1TR_FA = C.ROOT / 'work/shared/candidatas/probe_ie2_v05/archive.fa'

EXTRA = HERE / 'extra'
PREVIEWS = HERE / 'previews'
V03_EXTRA = V03 / 'extra'
SCRATCH = HERE / '_hojas'


def base_arc(ruta):
    """Bytes del .arc de partida: el de v03 si lo escribió, si no el japonés."""
    f = V03_EXTRA / ruta
    return f.read_bytes() if f.exists() else C.jp().get(ruta)
