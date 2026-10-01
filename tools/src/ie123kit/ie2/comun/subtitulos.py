"""Subtítulos incrustados de las cinemáticas de IE2 (capa ``media/subtitulos``, v11).

Estilo medido en los fotogramas japoneses (a2m03, a2m04): texto blanco (Y 235-242) sin contorno ni
sombra sobre la banda plana, una línea centrada en x = 160, tinta de kana en y = 214-228, ancho
máximo observado 299 px. Fuente: Yu Gothic UI Semibold 16 px (``YuGothB.ttc``, índice 2), línea
base en y = 226. Tiempos: ticks de 30 Hz del .dat de la NDS española sin retraso; el vídeo va a
24 fps (``tick = floor(floor(k*1000/24) * 30 / 1000)``, CRO 0xe84bc).
"""

from __future__ import annotations

import os
from pathlib import Path

from ie123kit.nucleo.media import subtitulos as S

__all__ = ["ESTILO_IE2", "FPS", "HZ", "estilo", "pistas"]

FPS = 24
HZ = 30

#: Fuente por defecto (Windows). Se puede cambiar con IE123_FUENTE_SUBTITULOS.
_FUENTE = Path("C:/Windows/Fonts/YuGothB.ttc")

ESTILO_IE2 = S.EstiloSubtitulo(fuente=_FUENTE, indice_fuente=2, tam=16, y0=208, alto=32, base_y=226,
                               blanco=235, ancho_max=300, centro=160)


def estilo() -> S.EstiloSubtitulo:
    """Estilo de IE2 con la ruta de la fuente resuelta (``IE123_FUENTE_SUBTITULOS`` manda)."""
    ruta = os.environ.get("IE123_FUENTE_SUBTITULOS")
    if not ruta:
        return ESTILO_IE2
    from dataclasses import replace

    return replace(ESTILO_IE2, fuente=Path(ruta))


def pistas(dat: bytes, est: S.EstiloSubtitulo | None = None) -> list[dict]:
    """Pista española de un .dat de la NDS ya partida y repartida en su intervalo."""
    est = est or estilo()
    return S.pistas(dat, lambda t: S.ancho_texto(t, est), est.ancho_max)
