"""IE2 v19 · modelo del motor del diálogo con los límites de la v15/v17, para TODO el diálogo.

Reutiliza sin copiar el modelo ya validado en emulador de la capa v17
(`work/ie2/shared/capas/v17/paginas/comun17.py`):

- reajuste 0x48398 con [ventana+0x131e] = 0x1A0 -> 448 px / 37 caracteres por línea;
- dibujo 0x121a78 con el ancho global 0x1C0 -> también 37;
- 3 líneas por página y búfer de página de 131 B (`2 × caracteres + (líneas − 1)`);
- 247 B por registro (`comun_ie2.MAX_BYTES`).

Lo único que añade la v19 es el envoltorio `reparte` (repartir + transporte + todas las
comprobaciones del registro) para poder aplicarlo a los ~60 000 registros de eve y mch, no solo
a la sonda 22500101/22500102.
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[5]
V17 = ROOT / 'work/ie2/shared/capas/v17/paginas'


def _modulo(nombre: str, ruta: Path):
    spec = importlib.util.spec_from_file_location(nombre, ruta)
    m = importlib.util.module_from_spec(spec)
    sys.modules[nombre] = m
    spec.loader.exec_module(m)
    return m


C = _modulo('comun17_v19', V17 / 'comun17.py')   # modelo del motor (v17, validado en Azahar)
M = C.M                                          # comun_ie2 (transporte, Archivo, dialogos…)

MAX_CAR, LINEAS, PAGINA_MAX = C.MAX_CAR, C.LINEAS, C.PAGINA_MAX
MAX_BYTES = M.MAX_BYTES
SALTO, PAGINA = C.SALTO, C.PAGINA
PROTEGIDOS = M.PROTEGIDOS

paginas = C.paginas
problemas = C.problemas
reajusta = C.reajusta
repartir = C.repartir
partir_paginas = C.partir_paginas

JAPONES = re.compile(r'[぀-ヿ一-鿿]')


def espanol(b: bytes) -> str:
    return M.normalizar(M.K.a_espanol(b).replace('－', '−').replace('～', '〜'))


def es_espanol(b: bytes) -> bool:
    t = espanol(b)
    return bool(re.search(r'[A-Za-zÁÉÍÓÚáéíóúñÑ]', t)) and not JAPONES.search(t)


def palabras(t: str):
    return t.replace(SALTO, ' ').replace(PAGINA, ' ').split()


def ida_y_vuelta(b: bytes) -> bool:
    """True si `espanol`/`transportar` reproducen el registro byte a byte.

    Es la red que protege lo que no es texto español corriente (bigramas de la pestaña del nombre,
    portadores de acentos raros, tablas): si el viaje de ida y vuelta no es exacto, el registro NO
    se rehace."""
    try:
        return M.transportar(espanol(b)) == b
    except Exception:
        return False


def reparte(b: bytes):
    """Registro -> (nuevo cuerpo, texto español) con el reparto a 37 × 3 y <= 131 B.

    Devuelve (None, motivo) si no se puede rehacer con garantías. El texto NO se toca nunca:
    solo cambian los saltos de línea y de página."""
    if not es_espanol(b):
        return None, 'no es texto español'
    if not ida_y_vuelta(b):
        return None, 'ida y vuelta no exacta'
    antes = espanol(b)
    try:
        texto = repartir(antes)
    except ValueError as e:
        return None, str(e)[:120]
    nuevo = M.transportar(texto)
    if palabras(espanol(nuevo)) != palabras(antes):
        return None, 'palabras distintas'
    if M.pct(nuevo.decode('cp932')) != M.pct(b.decode('cp932')):
        return None, '%s/%d distintos'
    if M.sin_glifo(nuevo):
        return None, 'sin glifo: ' + ''.join(M.sin_glifo(nuevo))
    if reajusta(nuevo):
        return None, 'el motor reajusta'
    p = problemas(nuevo)
    if p:
        return None, '; '.join(p)
    return nuevo, texto
