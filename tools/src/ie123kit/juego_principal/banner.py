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

from ie123kit.nucleo.compresion import lz11
from ie123kit.nucleo.contenedores import cbmd
from ie123kit.nucleo.ejecutable import smdh
from ie123kit.nucleo.graficos import cgfx
from ie123kit.nucleo.media import bcwav

__all__ = ["TEXTURA_LOGO", "TITULO", "construir_banner", "construir_icono", "textura"]

#: Títulos del menú HOME en los 16 slots (misma forma que el original japonés: nombre + subtítulo).
TITULO = {
    "short": "Inazuma Eleven 1·2·3!!",
    "long": "Inazuma Eleven 1·2·3!!\nLa leyenda de Mark Evans",
    "publisher": "LEVEL-5",
}
#: Textura del CGFX común con el logo (256x256 RGBA4, delante del modelo 3D, que no se toca).
TEXTURA_LOGO = "COMMON1"


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
