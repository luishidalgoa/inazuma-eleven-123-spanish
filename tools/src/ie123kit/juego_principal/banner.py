"""Banner y títulos del menú HOME de la recopilación (``banner.bnr`` e ``icon.icn`` del ExeFS).

Orquestación de la capa ``work/shared/capas/graficos/banner_home`` sobre el paquete (F2.5, #51):
títulos SMDH (:mod:`ie123kit.nucleo.ejecutable.smdh`), CBMD (:mod:`ie123kit.nucleo.contenedores.cbmd`),
LZ11, texturas CGFX (:mod:`ie123kit.nucleo.graficos.cgfx`) y BCWAV
(:mod:`ie123kit.nucleo.media.bcwav`). Solo sirve para una .cia/.3ds reconstruida: LayeredFS de Luma no
sustituye estos ficheros. El logo compuesto y el audio los prepara la capa (recursos de ``work/``).
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np

from ie123kit.nucleo.compresion import lz11
from ie123kit.nucleo.contenedores import cbmd
from ie123kit.nucleo.ejecutable import smdh
from ie123kit.nucleo.graficos import cgfx
from ie123kit.nucleo.media import bcwav, voz

__all__ = ["RATE_BANNER", "TEXTURA_LOGO", "TITULO", "construir_banner", "construir_icono", "preparar_grito",
           "textura"]

#: Títulos del menú HOME en los 16 slots (misma forma que el original japonés: nombre + subtítulo).
TITULO = {
    "short": "Inazuma Eleven 1·2·3!!",
    "long": "Inazuma Eleven 1·2·3!!\nLa leyenda de Mark Evans",
    "publisher": "LEVEL-5",
}
#: Textura del CGFX común con el logo (256x256 RGBA4, delante del modelo 3D, que no se toca).
TEXTURA_LOGO = "COMMON1"
#: Frecuencia del BCWAV del banner HOME.
RATE_BANNER = 48000
#: Pico del grito del banner: -3 dBFS (deja la voz al mismo nivel RMS que el grito japonés).
PICO_BANNER = 32767 * 10 ** (-3.0 / 20)


def preparar_grito(pcm, rate: int, *, cola_s: float = 0.020) -> tuple[Any, dict[str, Any]]:
    """``(PCM int16 a 48000 Hz, informe)`` del grito del banner a partir de una grabación mono.

    Recorte al inicio y al final de la voz (umbral -50 dBFS, 10 ms de margen), fundido de entrada de
    3 ms y de salida de 40 ms, remuestreo polifásico a 48000 Hz, ganancia a -3 dBFS y ``cola_s`` de
    silencio final. Porteo de ``grito`` de ``work/shared/capas/graficos/banner_home/audio.py``.
    """
    x = np.asarray(pcm).astype(np.float64)
    y, (a, b) = voz.recortar_voz(x, rate)
    z = voz.remuestrear(y, rate, RATE_BANNER)
    gan = PICO_BANNER / np.abs(z).max()
    z = np.concatenate([z * gan, np.zeros(int(cola_s * RATE_BANNER))])
    out = np.clip(np.round(z), -32768, 32767).astype(np.int16)
    informe = {"rate_fuente": rate, "recorte_s": [round(a / rate, 4), round(b / rate, 4)],
               "duracion_fuente_s": round(len(x) / rate, 3), "duracion_s": round(len(out) / RATE_BANNER, 3),
               "ganancia_db": round(float(20 * np.log10(gan)), 2)}
    return out, informe


def construir_icono(icon: bytes, titulos: dict[str, str] | None = None) -> bytes:
    """``icon.icn`` (SMDH) con los títulos en español en todos los slots; el icono no cambia."""
    return smdh.escribir_titulos(icon, titulos or TITULO)


def textura(cgfx_datos: bytes, nombre: str = TEXTURA_LOGO) -> tuple[Any, tuple]:
    """``(imagen RGBA, fila de textures())`` de una textura del CGFX descomprimido."""
    fila = {t[0]: t for t in cgfx.textures(cgfx_datos)}[nombre]
    _n, _t, w, h, fmt, off, size = fila
    return cgfx.decode(cgfx_datos[off:off + size], w, h, fmt), fila


def construir_banner(bnr: bytes, logo: Any, pcm: Sequence[int] | None = None,
                     nombre: str = TEXTURA_LOGO) -> tuple[bytes, bytes, bytes]:
    """``(banner.bnr, CGFX descomprimido, BCWAV)`` con ``logo`` (imagen del tamaño de la textura) en
    ``nombre`` y, si se da, ``pcm`` mono como sonido del banner (con la cabecera del original)."""
    cgfx_lz, cwav_orig = cbmd.partes(bnr)
    c = bytearray(lz11.decompress(cgfx_lz))
    _img, (_n, _t, w, h, fmt, off, size) = textura(bytes(c), nombre)
    raw = cgfx.encode(logo, w, h, fmt)
    if len(raw) != size:
        raise ValueError(f"{nombre}: {len(raw)} B codificados, se esperaban {size}")
    c[off:off + size] = raw
    cwav = bcwav.codificar(cwav_orig, pcm) if pcm is not None else cwav_orig
    return cbmd.construir(lz11.compress(bytes(c)), cwav), bytes(c), cwav
