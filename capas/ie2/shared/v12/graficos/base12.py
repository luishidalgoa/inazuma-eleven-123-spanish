"""Capa v12/graficos de IE2: logo del título, botón «Volver» del título y teclado de nombre.

Reutiliza el motor de v06/graficos (y, a través de él, el de v03) en solo lectura; escribe solo aquí.
Cada .arc parte del de v06 si v06 lo escribió, si no del de v03, si no del japonés: el overlay v12
se aplica DESPUÉS de v06 y lo sustituye entero en esas rutas.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
V06 = HERE.parents[1] / 'v06' / 'graficos'
if str(V06) not in sys.path:
    sys.path.insert(0, str(V06))

import base as B6  # noqa: E402  (módulo «base» = v06/graficos/base.py: añade v03 al path y fija C.IE1TR_FA)

C = B6.C
EXTRA = HERE / 'extra'
PREVIEWS = HERE / 'previews'
FUENTES = HERE / 'fuentes'          # logos oficiales copiados (no se lee nada de Descargas)
V06_EXTRA = B6.EXTRA
V03_EXTRA = B6.V03_EXTRA
#: IE1 traducida (teclado y fcode ya aprobados en IE1): la candidata instalada
IE1_FA = C.ROOT / 'work/shared/candidatas/probe_ie2_v10/archive.fa'


def origen_base(ruta):
    for nombre, d in (('v06', V06_EXTRA), ('v03', V03_EXTRA)):
        if (d / ruta).exists():
            return nombre
    return 'jp'


def base_arc(ruta):
    """Bytes del .arc de partida: v06 > v03 > japonés."""
    for d in (V06_EXTRA, V03_EXTRA):
        f = d / ruta
        if f.exists():
            return f.read_bytes()
    return C.jp().get(ruta)


def texturas_de(datos):
    return {n: b for n, _, _, b in C.texturas(C.U.unwrap(datos))}
