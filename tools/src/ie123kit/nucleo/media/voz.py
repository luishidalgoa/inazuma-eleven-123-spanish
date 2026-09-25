"""Preparación de grabaciones de voz para muestras del juego (recorte, huecos, fundidos, remuestreo).

Porteo de la parte pura de dos capas, sin cambios de comportamiento:

- ``work/shared/capas/media/voz_titulo_recopilatorio/apply.py`` (``tramos``/``montar``): reduce los
  silencios largos entre frases a un hueco fijo con fundidos en cada corte y conserva los cortos.
- ``work/shared/capas/graficos/banner_home/audio.py`` (recorte de ``grito``): recorta al inicio y al
  final de la voz con un margen y aplica fundidos de entrada y de salida.

Todas las funciones trabajan sobre ``numpy`` y no leen ni escriben ficheros. El umbral se compara
contra la ``escala`` del PCM (1.0 para flotante normalizado, 32768 para enteros de 16 bits).
"""
from __future__ import annotations

import numpy as np

__all__ = ["agrupar", "envolvente_rms", "montar_frases", "recortar_voz", "remuestrear", "tramos"]


def envolvente_rms(x: np.ndarray, sr: int, ventana_s: float = 0.010) -> np.ndarray:
    """Envolvente RMS de ``ventana_s`` (media móvil centrada del cuadrado)."""
    n = int(ventana_s * sr)
    return np.sqrt(np.convolve(x * x, np.ones(n) / n, "same"))


def tramos(x: np.ndarray, sr: int, umbral_db: float = -45.0, ventana_s: float = 0.010,
           minimo_s: float = 0.02, escala: float = 1.0) -> list[tuple[int, int]]:
    """``[(inicio, fin)]`` de voz: la envolvente RMS por encima de ``umbral_db``."""
    env = envolvente_rms(x, sr, ventana_s)
    on = env > escala * 10 ** (umbral_db / 20)
    bordes = list(np.flatnonzero(np.diff(on.astype(np.int8))) + 1)
    if on[0]:
        bordes.insert(0, 0)
    if on[-1]:
        bordes.append(len(x))
    return [(a, b) for a, b in zip(bordes[::2], bordes[1::2]) if b - a > int(minimo_s * sr)]


def agrupar(lista: list[tuple[int, int]], sr: int, gap_max_s: float,
            gap_s: float) -> tuple[list[list[int]], list[dict]]:
    """``(grupos, huecos)``: une los tramos separados por menos de ``gap_max_s`` (hueco conservado)."""
    grupos, huecos = [[lista[0][0], lista[0][1]]], []
    for a, b in lista[1:]:
        h = (a - grupos[-1][1]) / sr
        if h <= gap_max_s:
            grupos[-1][1] = b
            huecos.append({"s": round(float(h), 3), "accion": "se conserva"})
        else:
            grupos.append([a, b])
            huecos.append({"s": round(float(h), 3), "accion": f"-> {gap_s}"})
    return grupos, huecos


def montar_frases(x: np.ndarray, sr: int, *, umbral_db: float = -45.0, ventana_s: float = 0.010,
                  gap_max_s: float = 0.12, gap_s: float = 0.10, corte_fade_s: float = 0.008,
                  margen_s: float = 0.010, fade_in_s: float = 0.005,
                  fade_out_s: float = 0.030) -> tuple[np.ndarray, list[list[int]], list[dict]]:
    """``(señal, grupos, huecos)`` con los silencios largos reducidos a ``gap_s``.

    Cada grupo se extiende ``margen_s`` a cada lado; los cortes internos llevan fundidos de
    ``corte_fade_s`` y los extremos ``fade_in_s``/``fade_out_s``. El hueco total entre frases es
    ``gap_s`` (márgenes incluidos). Ni el tempo ni el tono cambian.
    """
    grupos, huecos = agrupar(tramos(x, sr, umbral_db, ventana_s), sr, gap_max_s, gap_s)
    m, fc = int(margen_s * sr), int(corte_fade_s * sr)
    piezas = []
    for k, (a, b) in enumerate(grupos):
        a, b = max(0, a - m), min(len(x), b + m)
        y = x[a:b].copy()
        fi = int(fade_in_s * sr) if k == 0 else fc
        fo = int(fade_out_s * sr) if k == len(grupos) - 1 else fc
        y[:fi] *= np.sin(np.linspace(0, np.pi / 2, fi)) ** 2
        y[-fo:] *= np.cos(np.linspace(0, np.pi / 2, fo)) ** 2
        piezas.append(y)
        if k < len(grupos) - 1:
            piezas.append(np.zeros(round(gap_s * sr) - 2 * m))
    return np.concatenate(piezas), grupos, huecos


def recortar_voz(x: np.ndarray, sr: int, *, umbral_db: float = -50.0, margen_s: float = 0.010,
                 fade_in_s: float = 0.003, fade_out_s: float = 0.040, ventana: int = 64,
                 escala: float = 32768.0) -> tuple[np.ndarray, tuple[int, int]]:
    """``(señal recortada con fundidos, (inicio, fin))`` de la única frase de ``x``."""
    env = np.convolve(np.abs(x), np.ones(ventana) / ventana, "same")
    voz = np.nonzero(env > escala * 10 ** (umbral_db / 20))[0]
    a = max(0, voz[0] - int(margen_s * sr))
    b = min(len(x), voz[-1] + int(margen_s * sr))
    y = x[a:b].copy()
    fi, fo = int(fade_in_s * sr), int(fade_out_s * sr)
    y[:fi] *= np.sin(np.linspace(0, np.pi / 2, fi)) ** 2
    y[-fo:] *= np.cos(np.linspace(0, np.pi / 2, fo)) ** 2
    return y, (int(a), int(b))


def remuestrear(x: np.ndarray, sr_in: int, sr_out: int) -> np.ndarray:
    """Remuestreo polifásico ``sr_in`` -> ``sr_out`` (misma duración, sin cambio de tono)."""
    from scipy.signal import resample_poly

    g = np.gcd(sr_in, sr_out)
    return resample_poly(x, sr_out // g, sr_in // g)
