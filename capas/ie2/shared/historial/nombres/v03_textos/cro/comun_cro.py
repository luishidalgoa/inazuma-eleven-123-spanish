"""IE2 v03 · literales de ina_main2.cro: rutas, codificación y comprobaciones comunes (apply/validate)."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from functools import lru_cache
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[7]
for p in (HERE, HERE.parent, ROOT / 'tools'):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from dialogue_typography import ACCENTS, encode_fullwidth  # noqa: E402
from crorefs2 import Refs  # noqa: E402

REL = 'romfs/cro/ina_main2.cro'
BASE = ROOT / 'work/shared/base_3ds' / REL
IE1_ORIG = ROOT / 'work/shared/base_3ds/romfs/cro/ina_main1.cro'
IE1_V89 = ROOT / 'work/shared/candidatas/probe_ie1_v89/romfs/cro/ina_main1.cro'
OUT = HERE / REL
TABLA = HERE / 'literales.json'
INFORME = HERE / 'informe.json'
NFTR = 'inazuma2/data_iz/font/FONT12.NFTR'

INV = {v: k for k, v in ACCENTS.items()}
FMT = re.compile(r'%[0-9]*[sd]')
MARCA = re.compile(r'%[0-9]+F')
RUBI = re.compile(r'\[([^/\]]*)/[^\]]*\]')
PROHIBIDOS = set('\'"-‐‒–—―‘’“”´`«»')


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def tabla():
    return json.loads(TABLA.read_text(encoding='utf-8'))


def a_espanol(body: bytes) -> str:
    s = body.decode('cp932')
    return ''.join(INV.get(c, ' ' if c == '　' else (chr(ord(c) - 0xFEE0) if 0xFF01 <= ord(c) <= 0xFF5E else c))
                   for c in s)


def cuerpo(d: bytes, o: int) -> bytes:
    return d[o:d.index(b'\0', o)]


def jp_bytes(e) -> bytes:
    return e['japones'].encode('cp932')


def capacidad(e) -> int:
    """Bytes del hueco incluido el NUL final."""
    return e.get('capacidad', len(jp_bytes(e)) + 1)


def limite(e) -> int:
    """Bytes máximos del texto: la longitud japonesa (búfer del juego) o el hueco acotado si es menor."""
    lim = min(len(jp_bytes(e)), capacidad(e) - 1)
    if e.get('clase') == 'formato':  # formato ASCII compartido (no se copia a un búfer de texto)
        lim = capacidad(e) - 1
    return lim


def codificar(e) -> bytes:
    """Ancho completo; los formatos ASCII compartidos (clase «formato») van tal cual, como en IE1 v89
    (el espacio ASCII es el único glifo de 1 byte con métrica)."""
    if e.get('clase') == 'formato':
        return e['espanol'].encode('ascii')
    return encode_fullwidth(e['espanol'])


def lineas_jp(t: str):
    return [len(x) for x in RUBI.sub(lambda m: m.group(1), MARCA.sub('', t)).split('\n')]


@lru_cache(maxsize=1)
def glifos() -> set[int]:
    """Códigos Shift-JIS con glifo en FONT12.NFTR de inazuma2 (probe_ie2_v02, solo lectura)."""
    import comun_v03 as C
    from ie123kit.nucleo.fuentes.nftr import read_metrics
    return set(read_metrics(C.base()(NFTR)))


def sin_glifo(b: bytes) -> list[str]:
    g = glifos()
    malos, i = [], 0
    while i < len(b):
        c = b[i]
        if c < 0x80:  # salto o especificador printf (se comprueban aparte)
            i += 1
            continue
        ch = b[i:i + 2].decode('cp932')
        # Los portadores de acento (letras griegas) los pinta la BCFNT parcheada, como en IE1 v89.
        if ((c << 8) | b[i + 1]) not in g and ch not in INV:
            malos.append(ch)
        i += 2
    return malos


def ascii_sueltos(b: bytes) -> list[str]:
    """Bytes ASCII que no son salto ni especificador printf (las fuentes no tienen métricas ASCII)."""
    s = b.decode('cp932')
    resto = FMT.sub('', s).replace('\n', '')
    return sorted({ch for ch in resto if ord(ch) < 0x80})
