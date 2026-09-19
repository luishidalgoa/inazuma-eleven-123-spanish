"""v22/ayuda (issue #77): utilidades comunes. Reutiliza el motor de v06/graficos (y por él el de v03).

Fuentes:
  JP   work/shared/base_3ds/romfs/archive.fa  (inazuma2/ japonés)
  NDS  work/ie2/tormenta_de_fuego/fuentes/nds_es/data_iz/pic3d/script/sp/{tt*,syup_bg*}.pac_
       (capturas de ayuda de la NDS española: LZ10 -> PAC de 3 partes: índices 8 bpp 256x192 lineales,
        paleta BGR555 de 256 colores, 16 B de cola)
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
V06 = HERE.parents[1] / 'historial' / 'graficos' / 'v06_graficos'
if str(V06) not in sys.path:
    sys.path.insert(0, str(V06))

import base as B6  # noqa: E402  (añade v03/graficos al path y fija C.IE1TR_FA)

C = B6.C
ROOT = C.ROOT
NDS_SP = ROOT / 'work/ie2/tormenta_de_fuego/fuentes/nds_es/data_iz/pic3d/script/sp'
EXTRA = HERE / 'extra'
PREVIEWS = HERE / 'previews'
CANDIDATA = ROOT / 'work/shared/candidatas/probe_ie2_v21/archive.fa'

AR = 'inazuma2/data_iz/a_data_replace/'
SYSTEM_B = 'inazuma2/data_iz/a_menu/system_b.arc'
MASTUTORIAL = 'inazuma2/data_iz/pic2d/menu/MASTutorial.SPF_'

# área de la captura dentro de la textura 512x256: NDS 256x192 ×1,25
W3, H3 = 320, 240


def capturas():
    """[(ruta_arc, nombre_nds)] de las capturas de ayuda de IE2 (help_b tt*, help_t y demo_bg syup_bg*)."""
    jp = C.jp()
    out = []
    for p in sorted(jp.rutas(AR)):
        if not p.endswith('.arc'):
            continue
        nombre = p.rsplit('/', 1)[1][len('ie02_'):-len('.arc')] if '/ie02_' in p else None
        if nombre is None:
            continue
        if ('/help_b/data/' in p and nombre.startswith('tt')) or \
                ('/help_t/data/' in p or '/demo_bg/data/' in p) and nombre.startswith('syup_bg'):
            out.append((p, nombre))
    return out


def nds_captura(nombre: str) -> Image.Image:
    raw = (NDS_SP / f'{nombre}.pac_').read_bytes()
    if raw[:1] == b'\x10':
        raw = C.lz10_decompress(raw)
    n = struct.unpack_from('<I', raw, 0)[0]
    (io, isz), (po, ps), _ = [struct.unpack_from('<2I', raw, 4 + 8 * i) for i in range(n)]
    assert isz == 256 * 192 and ps <= 512, (nombre, isz, ps)
    pal = np.zeros(256, np.int32)
    pal[:ps // 2] = struct.unpack_from('<%dH' % (ps // 2), raw, po)
    lut = np.stack([(pal & 31) * 255 // 31, ((pal >> 5) & 31) * 255 // 31, ((pal >> 10) & 31) * 255 // 31], -1)
    idx = np.frombuffer(raw, np.uint8, isz, io).reshape(192, 256)
    return Image.fromarray(lut[idx].astype(np.uint8), 'RGB')
