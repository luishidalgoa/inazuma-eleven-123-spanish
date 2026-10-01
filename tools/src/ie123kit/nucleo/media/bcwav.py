"""BCWAV (CWAV) DSP-ADPCM de varios canales: lectura, decodificación y escritura con plantilla.

Portado de ``work/shared/capas/graficos/banner_home/audio.py`` (``formato``, ``decodificar`` y
``codificar``) sin cambios de comportamiento (F2.5, #51). La escritura conserva la cabecera de la
plantilla (la del banner original) y reparte el mismo PCM mono en todos sus canales; el codificador es
:mod:`ie123kit.nucleo.media.dsp_adpcm`.
"""
from __future__ import annotations

import struct
from collections.abc import Sequence

from ie123kit.nucleo.media import dsp_adpcm as D

__all__ = ["canales", "codificar", "decodificar", "formato"]


def canales(w: bytes) -> list[tuple[int, int, int]]:
    """[(offset info canal, offset datos relativo al cuerpo DATA, offset info ADPCM)]"""
    n = struct.unpack_from("<I", w, 0x5C)[0]
    out = []
    for k in range(n):
        ci = 0x5C + struct.unpack_from("<I", w, 0x60 + 8 * k + 4)[0]
        out.append((ci, struct.unpack_from("<I", w, ci + 4)[0], ci + struct.unpack_from("<I", w, ci + 12)[0]))
    return out


def _data(w: bytes) -> int:
    """Offset del bloque DATA (cabecera: 0x20 tipo 0x7001, 0x24 offset, 0x28 tamaño)."""
    return struct.unpack_from("<I", w, 0x24)[0]


def formato(w: bytes) -> dict[str, int]:
    if not (w[:4] == b"CWAV" and w[0x40:0x44] == b"INFO" and w[_data(w):_data(w) + 4] == b"DATA"):
        raise ValueError("no es un CWAV con INFO y DATA")
    return {"codificacion": w[0x48], "bucle": w[0x49], "rate": struct.unpack_from("<I", w, 0x4C)[0],
                "muestras": struct.unpack_from("<I", w, 0x54)[0], "canales": len(canales(w))}


def decodificar(w: bytes) -> list[list[int]]:
    """PCM int16 por canal de un CWAV DSP-ADPCM (codificación 2)."""
    f = formato(w)
    if f["codificacion"] != 2:
        raise ValueError("solo DSP-ADPCM (codificación 2)")
    out = []
    for _ci, doff, ai in canales(w):
        coefs = [struct.unpack_from("<hh", w, ai + 4 * j) for j in range(8)]
        out.append(D.decodificar(w[_data(w) + 8 + doff:], coefs, f["muestras"]))
    return out


def codificar(plantilla: bytes, pcm: Sequence[int]) -> bytes:
    """CWAV con la cabecera de `plantilla` y `pcm` mono duplicado en todos sus canales."""
    muestras = [int(v) for v in pcm]
    datos, coefs, ps = D.codificar(muestras)
    dat = _data(plantilla)
    b = bytearray(plantilla[:dat + 8])
    lista = canales(b)
    if b[0x48] != 2 or b[0x49] != 0:
        raise ValueError("la plantilla no es DSP-ADPCM sin bucle")
    paso = len(datos) + (-len(datos) % 0x20)
    primero = lista[0][1]
    cuerpo = bytearray(primero)
    for k, (ci, _doff, ai) in enumerate(lista):
        struct.pack_into("<I", b, ci + 4, primero + k * paso)
        for j, (c1, c2) in enumerate(coefs):
            struct.pack_into("<hh", b, ai + 4 * j, c1, c2)
        struct.pack_into("<Hhh", b, ai + 0x20, ps, 0, 0)      # contexto inicial
        struct.pack_into("<Hhh", b, ai + 0x26, ps, 0, 0)      # contexto de bucle (sin bucle)
        cuerpo += datos + (bytes(paso - len(datos)) if k < len(lista) - 1 else b"")
    total = len(b) + len(cuerpo)
    struct.pack_into("<I", b, 0x0C, total)                  # tamaño del fichero
    struct.pack_into("<I", b, 0x28, total - dat)            # referencia al bloque DATA: tamaño
    struct.pack_into("<I", b, 0x54, len(muestras))          # fin (= número de muestras)
    struct.pack_into("<I", b, dat + 4, total - dat)         # cabecera del bloque DATA
    return bytes(b) + bytes(cuerpo)
