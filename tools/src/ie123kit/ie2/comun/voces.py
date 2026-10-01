"""Voces de IE2: bancos Procyon de la 3DS rehechos con las muestras españolas de la NDS.

Porteo de las capas ``media/voz_titulo`` (v13, grito del título 3D_901), ``historial/media/v20_voces``
(3D_003_*: gol y gol encajado) y ``media/voces`` (v23, 2D_020_*: anuncio del capítulo).

El SWD de la 3DS (0x480) guarda cada muestra como CWAV DSP-ADPCM; el de la NDS (0x415) en IMA de
4 bits. Un SWD de DS no sirve tal cual: se conserva el SWD 3DS (``wavi``/``prgi`` intactos) y solo se
cambian los CWAV de las muestras con voz española (``nucleo.media.dsp_adpcm``). El SED es el de la NDS
con la versión y fecha de la cabecera japonesa (0x0c-0x1f).

La frecuencia de la 3DS (32728 Hz) es un parámetro; si la muestra NDS va a otra frecuencia se
remuestrea con ``scipy.signal.resample_poly`` (dependencia opcional, solo para ese caso).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from math import gcd

from ie123kit.nucleo.media import procyon as PR
from ie123kit.nucleo.media.dsp_adpcm import cwav_mono

__all__ = ["FORMATO_IMA", "FRECUENCIA_3DS", "banco_desde_nds", "cwavs_desde_nds", "pcm_nds", "remuestrear"]

#: Frecuencia de las muestras de voz de los SWD de la 3DS (IE2).
FRECUENCIA_3DS = 32728
#: Formato IMA 4 bits de la entrada ``wavi`` de un SWD de DS (+0x12).
FORMATO_IMA = 0x200


def remuestrear(pcm: Iterable[int], origen: int, destino: int) -> list[int]:
    """PCM int16 de ``origen`` Hz a ``destino`` Hz (``resample_poly``, redondeo y saturación)."""
    pcm = list(pcm)
    if origen == destino:
        return pcm
    import numpy as np
    from scipy.signal import resample_poly

    g = gcd(origen, destino)
    up = resample_poly(np.array(pcm, dtype=np.float64), destino // g, origen // g)
    return [int(v) for v in np.clip(np.round(up), -32768, 32767).astype(np.int16)]


def pcm_nds(swd_nds: bytes, id_muestra: int, alinear: int = 16) -> tuple[list[int], int]:
    """``(PCM int16, frecuencia)`` de una muestra IMA de un SWD de DS."""
    _, ents = PR.muestras_nds(swd_nds, alinear)
    e = next(x for x in ents if x["id"] == id_muestra)
    if e["fmt"] != FORMATO_IMA:
        raise ValueError(f"muestra {id_muestra}: formato {e['fmt']:#x} != IMA")
    return PR.ima_nds(e["data"]), e["rate"]


def cwavs_desde_nds(swd_3ds: bytes, swd_nds: bytes, voces: Mapping[int, int], *,
                    frecuencia: int = FRECUENCIA_3DS, alinear: int = 16,
                    silencios: Iterable[int] = (), n_silencio: int = 700) -> dict[int, bytes]:
    """``{id 3DS: CWAV}`` con la voz NDS ``voces[id]`` (remuestreada si hace falta) y silencios cortos.

    Cada CWAV usa como plantilla la cabecera del CWAV original de esa muestra.
    """
    _, ents = PR.muestras_3ds(swd_3ds)
    por_id = {e["id"]: e for e in ents}
    out = {}
    for id_3ds, id_nds in voces.items():
        pcm, rate = pcm_nds(swd_nds, id_nds, alinear)
        out[id_3ds] = cwav_mono(por_id[id_3ds]["cwav"], remuestrear(pcm, rate, frecuencia), frecuencia)
    for id_3ds in silencios:
        out[id_3ds] = cwav_mono(por_id[id_3ds]["cwav"], [0] * n_silencio, frecuencia)
    return out


def banco_desde_nds(swd_3ds: bytes, sed_3ds: bytes, swd_nds: bytes, sed_nds: bytes, *,
                    frecuencia: int = FRECUENCIA_3DS, alinear: int = 16) -> tuple[bytes, bytes, dict]:
    """``(SED, SWD, informe)`` de un banco cuyas muestras NDS son un prefijo de las de la 3DS.

    Exige el mismo mapa tecla -> muestra en las teclas de la NDS y los mismos ids. Las muestras
    japonesas que la NDS no tiene se conservan (el SED español no toca su tecla).
    """
    _, e3 = PR.muestras_3ds(swd_3ds)
    _, en = PR.muestras_nds(swd_nds, alinear)
    t3, tn = PR.prgi_teclas(swd_3ds), PR.prgi_teclas(swd_nds, nds=True, alinear=alinear)
    if any(t3.get(k) != v for k, v in tn.items()):
        raise ValueError(f"mapa tecla -> muestra distinto: {t3} / {tn}")
    ids_3ds = [x["id"] for x in e3]
    if [x["id"] for x in en] != ids_3ds[:len(en)]:
        raise ValueError("las muestras de la NDS no son un prefijo de las de la 3DS")
    if sed_3ds[:4] != b"sedl" or sed_nds[:4] != b"sedl":
        raise ValueError("SED sin firma sedl")
    voces = {x["id"]: x["id"] for x in en}
    cw = cwavs_desde_nds(swd_3ds, swd_nds, voces, frecuencia=frecuencia, alinear=alinear)
    swd = PR.swd_con_cwavs(swd_3ds, cw)
    sed = bytearray(sed_nds)
    sed[0x0C:0x20] = sed_3ds[0x0C:0x20]
    sed[0x08:0x0C] = len(sed).to_bytes(4, "little")
    informe = {"muestras_es": sorted(cw), "japonesas_sin_uso": [i for i in ids_3ds if i not in cw],
               "sed_jp": len(sed_3ds), "sed": len(sed), "swd_jp": len(swd_3ds), "swd": len(swd)}
    return bytes(sed), swd, informe
