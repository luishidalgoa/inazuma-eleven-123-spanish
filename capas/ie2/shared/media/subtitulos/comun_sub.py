"""IE2 v11 · subtítulos incrustados en las cinemáticas (común a apply.py y validate.py).

Causa (ver informe.json, «diagnostico»): el 3DS no enseña movie/txt/*.dat encima del vídeo. El japonés 3DS
lleva el subtítulo INCRUSTADO en la banda negra; esta capa hace lo mismo en español sobre los vídeos
limpiados por v07 (se regeneran desde el MOFLEX japonés con el mismo proceso de v07/media/videos.py, sin
recodificar dos veces).

Estilo medido en los fotogramas japoneses (a2m03, a2m04): texto blanco (Y 235-242), sin contorno ni sombra,
sobre la banda plana (Y 25), una línea centrada en x = 160, tinta de kana en y = 214-228 (~15 px), ancho
máximo observado 299 px (x 11-309). Fuente: Yu Gothic UI Semibold 16 px (misma familia gótica que el kana),
línea base en y = 226, blanco Y = 235 (BT.601 limitado), crominancia neutra.
Tiempos: ticks de 30 Hz del .dat NDS español (sin retraso). El fotograma k se muestra en t = k/24 s, tick =
floor(floor(k*1000/24) * 30 / 1000), igual que el CRO (0xe84bc); máquina secuencial del CRO (por_fotograma).
"""
from __future__ import annotations

import sys
import unicodedata
from functools import lru_cache
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[5]
V07 = ROOT / 'work/ie2/shared/capas/media/media'
if str(V07) not in sys.path:
    sys.path.insert(0, str(V07))

import comun_media as C  # noqa: E402
import videos as V        # noqa: E402

SALIDA = HERE
SALIDA_FUEGO = ROOT / 'work/ie2/tormenta_de_fuego/capas/media/subtitulos'
RUTA_VIDEOS = Path('extra/inazuma2/data_iz/movie')

FUENTE = Path('C:/Windows/Fonts/YuGothB.ttc')
FUENTE_INDICE = 2          # Yu Gothic UI Semibold
TAM = 16
Y0 = 208                   # primera fila de pantalla de la banda (columna 31 del fotograma)
ALTO = 32
BASE_Y = 226               # línea base en pantalla
BLANCO = 235
ANCHO_MAX = 300
CENTRO = 160


def destino(n: str) -> Path:
    return (SALIDA_FUEGO if n == 'op00' else SALIDA) / RUTA_VIDEOS / f'{n}.moflex'


def dir_tiras(n: str) -> Path:
    return (SALIDA_FUEGO if n == 'op00' else SALIDA) / 'tiras'


@lru_cache(maxsize=1)
def fuente():
    from PIL import ImageFont
    return ImageFont.truetype(str(FUENTE), TAM, index=FUENTE_INDICE)


def texto_nds(cuerpo: bytes) -> str:
    """Texto oficial NDS tal cual; solo NFKC (paréntesis de ancho completo)."""
    return unicodedata.normalize('NFKC', C.es_nds(cuerpo)).strip()


def ancho(t: str) -> float:
    return fuente().getlength(t)


def partir(t: str):
    """Trozos de una línea <= ANCHO_MAX px, cortando por frase, coma o palabra (lo más equilibrado)."""
    if ancho(t) <= ANCHO_MAX:
        return [t]
    mejor = None
    for grupo in C.cortes(t):
        for a, b in grupo:
            i, d = t[:a].rstrip(), t[b:].lstrip()
            if not i or not d:
                continue
            clave = (max(ancho(i), ancho(d)) > ANCHO_MAX, abs(ancho(i) - ancho(d)))
            if mejor is None or clave < mejor[0]:
                mejor = (clave, i, d)
        if mejor is not None and not mejor[0][0]:
            break
    if mejor is None:
        raise ValueError(f'no se puede partir: {t!r}')
    return partir(mejor[1]) + partir(mejor[2])


def pistas(n: str):
    """[(inicio, fin, texto)] de la pista española, ya partida y repartida en su intervalo."""
    out = []
    for k, s in enumerate(C.leer_dat((C.TXT_ES / f'{n}.dat').read_bytes())):
        trozos = partir(texto_nds(s.cuerpo))
        for t, (a, b) in zip(trozos, C.repartir(s.inicio, s.fin, [(x, None) for x in trozos])):
            out.append(dict(registro_nds=k, inicio=a, fin=b, texto=t))
    return out


def tick(k: int) -> int:
    return (k * 1000 // 24) * 30 // 1000


def por_fotograma(subs, n_fotogramas):
    """Subtítulo visible en cada fotograma (-1 = ninguno), con la máquina secuencial del CRO (0xe84bc):
    un registro cada vez, en orden; se dibuja cuando tick >= inicio; con tick >= fin se pasa al siguiente, que se
    dibuja aunque su inicio ya pasara (en el mismo fotograma: sin parpadeo entre registros seguidos)."""
    idx = np.full(n_fotogramas, -1, int)
    cur, dibujado = 0, False
    for k in range(n_fotogramas):
        if cur >= len(subs):
            break
        t = tick(k)
        s = subs[cur]
        if dibujado:
            if t < s['fin']:
                idx[k] = cur
                continue
            cur, dibujado = cur + 1, False
            if cur < len(subs) and t >= subs[cur]['inicio']:   # sin fotograma vacío entre registros seguidos
                dibujado = True
                idx[k] = cur
        elif t >= s['inicio']:
            dibujado = True
            idx[k] = cur
    return idx


@lru_cache(maxsize=None)
def alfa(t: str) -> np.ndarray:
    """Banda de pantalla (ALTO x 320) con la cobertura 0..255 del texto."""
    from PIL import Image, ImageDraw
    im = Image.new('L', (320, ALTO), 0)
    d = ImageDraw.Draw(im)
    x = round(CENTRO - ancho(t) / 2)
    d.text((x, BASE_Y - Y0), t, font=fuente(), fill=255, anchor='ls')
    return np.array(im)


def a_columnas(banda: np.ndarray) -> np.ndarray:
    """Banda de pantalla (ALTO x 320) -> bloque del fotograma (320 filas x 32 columnas, col 31 = y 208)."""
    return banda[::-1, :].T


def quemar(Y, subs, idx):
    """Pinta el texto sobre la banda ya limpia (plano Y, en el sitio)."""
    for k in np.where(idx >= 0)[0]:
        a = a_columnas(alfa(subs[idx[k]]['texto'])).astype(np.float32) / 255
        base = Y[k, :, :ALTO].astype(np.float32)
        Y[k, :, :ALTO] = np.clip(base + a * (BLANCO - base), 0, 255).round().astype(np.uint8)
