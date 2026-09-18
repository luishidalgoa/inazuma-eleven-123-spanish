"""IE2 v08 · nombres compactos: utilidades comunes (fuentes, registro, módulos previos)."""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[5]
W = ROOT / 'work'
V88DIR = W / 'ie1/capas/v88/bigramas_total'
for p in (V88DIR, W / 'ie1/capas/v89/bigramas_ritmo'):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import comun88  # noqa: E402

A89 = comun88.modulo('v89_bigramas_ritmo', W / 'ie1/capas/v89/bigramas_ritmo/apply.py')
A88 = A89.A88
R = A89.R
F12, F8, F12T = A88.F12, A88.F8, A88.F12T
FUENTES = (F12, F8, F12T)
CAND = W / 'shared/candidatas/probe_ie2_v05/archive.fa'
BASE_JP = W / 'shared/base_3ds/romfs/archive.fa'
REG07 = W / 'ie2/shared/capas/v07/media/registro.json'
FUENTE_ORIGEN = {F12: W / 'ie2/shared/capas/v07/media/extra' / F12,
                 F8: W / 'ie1/capas/v90/cro_restantes/extra' / F8,
                 F12T: W / 'ie1/capas/v90/cro_restantes/extra' / F12T}
UNIT = {'ie1': 'inazuma1/data_iz/logic/unitbase.dat', 'ie2': 'inazuma2/data_iz/logic/unitbase.dat'}


APOSTROFO = "'"


def cp(ch):
    """Codepoint de dibujo de un carácter: como codepoint() del transporte, salvo el apóstrofo, que no tiene
    glifo de ancho completo (U+FF07) y se toma del glifo ASCII 0x27 de cada fuente (solo dentro de casillas)."""
    return 0x27 if ch == APOSTROFO else A88.codepoint(ch)


def sha(b):
    return hashlib.sha256(b).hexdigest()


def cargar_fuentes():
    reg = json.loads(REG07.read_text(encoding='utf-8'))
    tmp = Path(tempfile.mkdtemp(prefix='ie2_v08_'))
    F, antes = {}, {}
    for f in FUENTES:
        d = FUENTE_ORIGEN[f].read_bytes()
        assert sha(d) == reg['fuentes_dibujadas'][f], f
        antes[f] = d
        (tmp / Path(f).name).write_bytes(d)
        F[f] = A88.cargar(tmp / Path(f).name)
    return reg, F, antes, tmp


def inversos(F):
    out = {}
    for f, Fu in F.items():
        d = {}
        for cp, gi in Fu.cmap.items():
            d.setdefault(gi, []).append(cp)
        out[f] = d
    return out
