"""Grito del título de la recopilación: muestra 162 de ``romfs/sound/CM_000.SWD`` y su nota en el SED.

Orquestación de la capa ``work/shared/capas/media/voz_titulo_recopilatorio`` sobre el paquete: banco
Procyon (:mod:`ie123kit.nucleo.media.procyon`), CWAV DSP-ADPCM
(:mod:`ie123kit.nucleo.media.bcwav`) y preparación de la voz (:mod:`ie123kit.nucleo.media.voz`).

Qué sonido es (comprobado en la capa, evidencia en su ``informe.json``):

- ``ina_menu.cro`` (menú del recopilatorio) carga de ``/sound/`` los bancos ``CM_000``, ``3D_900``,
  ``3D_901`` y ``2D_000``-``2D_002``. En el romfs raíz solo existe ``CM_000.SED``/``.SWD``; los
  ``3D_90x`` son los de cada juego (``inazuma1|2/data_iz/sound``) y no se tocan.
- ``CM_000.SWD``, muestra 162: CWAV mono DSP-ADPCM a 32728 Hz, 97503 muestras (2,979 s); correlación
  0,9999 con el audio del banner HOME japonés (el grito «1·2·3 円堂守伝説»).
- ``prgi``, programa 146: la tecla 84 toca la muestra 162 y la única secuencia con ese programa
  (``trk`` en 0xfcc de ``CM_000.SED``) la suena 300 ticks con una pausa de 300.
- La base de tiempo es <= 100,5 ticks/s, así que la nota nueva dura ``ceil(duración * 100,5) + 8``
  ticks con la misma codificación de 2 B: el SED no cambia de tamaño.

Reglas de capas: solo importa ``ie123kit.nucleo``; no lee ni escribe ficheros.
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np

from ie123kit.nucleo.media import bcwav, procyon, voz

__all__ = ["ID", "NOTA_JP", "PICO_REL", "RATE", "SR_FUENTE", "TICKS_MARGEN", "TICKS_S", "construir",
           "cwav_muestra", "preparar", "ticks_para"]

#: Muestra del SWD con el grito del título del recopilatorio.
ID = 162
#: Frecuencia de la muestra 162 (la del banco; no se cambia).
RATE = 32728
#: Frecuencia de la grabación del usuario.
SR_FUENTE = 44100
#: Pico máximo respecto al del grito japonés (margen para el rebase del DSP-ADPCM).
PICO_REL = 0.97
#: Base de tiempo de la secuencia y ticks de margen de la nota.
TICKS_S, TICKS_MARGEN = 100.5, 8
#: Nota japonesa del grito en ``CM_000.SED``: octava 7, tecla 84, 300 ticks, pausa 300 y fin.
NOTA_JP = bytes.fromhex("a0077fa0012c932c0198")
#: Formato exigido a la muestra 162 del banco japonés.
FORMATO_JP: dict[str, int] = {"codificacion": 2, "bucle": 0, "rate": RATE, "muestras": 97503, "canales": 1}


def cwav_muestra(swd: bytes, ident: int = ID) -> bytes:
    """CWAV de la muestra ``ident`` de un SWD 3DS."""
    _ch, ents = procyon.muestras_3ds(swd)
    for e in ents:
        if e["id"] == ident:
            return e["cwav"]
    raise KeyError(f"el SWD no tiene la muestra {ident}")


def ticks_para(duracion_s: float) -> int:
    """Ticks de la nota para una muestra de ``duracion_s`` (con el margen de la capa)."""
    return math.ceil(duracion_s * TICKS_S) + TICKS_MARGEN


def preparar(x: np.ndarray, pico_jp: float, sr: int = SR_FUENTE) -> tuple[np.ndarray, dict[str, Any]]:
    """``(PCM int16 a 32728 Hz, informe)`` de la grabación ``x`` (mono flotante normalizado).

    Los silencios de más de 0,12 s entre frases bajan a 0,10 s con fundidos de 8 ms en cada corte; los
    huecos internos más cortos se conservan. Remuestreo polifásico (misma duración y tono) y ganancia
    al 97 % de ``pico_jp`` (el pico del grito japonés).
    """
    y, grupos, huecos = voz.montar_frases(x, sr)
    z = voz.remuestrear(y, sr, RATE)
    gan = PICO_REL * pico_jp / (np.abs(z).max() * 32768)
    pcm = np.clip(np.round(z * 32768 * gan), -32768, 32767).astype(np.int16)
    informe = {
        "frases_s": [[round(float(a) / sr, 3), round(float(b) / sr, 3)] for a, b in grupos],
        "huecos": huecos,
        "ganancia_db": round(20 * math.log10(float(gan)), 2),
        "pico_jp": int(pico_jp),
        "muestras": len(pcm),
        "duracion_s": round(len(pcm) / RATE, 3),
    }
    return pcm, informe


def construir(swd: bytes, sed: bytes, x: np.ndarray,
              sr: int = SR_FUENTE) -> tuple[bytes, bytes, dict[str, Any]]:
    """``(CM_000.SWD, CM_000.SED, informe)`` con la grabación ``x`` como muestra 162.

    Del SWD solo cambia el CWAV 162 (misma cabecera DSP-ADPCM); los demás van byte a byte y se
    recolocan ``pcmd``, las posiciones de ``wavi`` y los tamaños. Del SED solo la duración de la nota
    del grito y su pausa (4 bytes, sin cambiar de tamaño).
    """
    cw_jp = cwav_muestra(swd)
    fmt = bcwav.formato(cw_jp)
    if fmt != FORMATO_JP:
        raise ValueError(f"la muestra {ID} no es la esperada: {fmt}")
    pcm_jp = np.asarray(bcwav.decodificar(cw_jp)[0], dtype=np.int16)
    pico_jp = float(np.abs(pcm_jp.astype(np.int32)).max())

    pcm, informe = preparar(x, pico_jp, sr)
    cw = bcwav.codificar(cw_jp, pcm)
    if bcwav.formato(cw) != {**fmt, "muestras": len(pcm)}:
        raise AssertionError(f"el CWAV nuevo no conserva el formato: {bcwav.formato(cw)}")
    nuevo_swd = procyon.swd_con_cwavs(swd, {ID: cw})

    ticks = ticks_para(len(pcm) / RATE)
    nuevo_sed = procyon.sed_con_ticks(sed, NOTA_JP, ticks)
    informe = {
        **informe,
        "ticks": ticks,
        "ticks_cubren_s": round(ticks / TICKS_S, 3),
        "antes": {"muestras": fmt["muestras"], "duracion_s": round(fmt["muestras"] / RATE, 3), "ticks": 300},
        "tamanos": {"swd_jp": len(swd), "swd": len(nuevo_swd), "sed": len(nuevo_sed)},
    }
    return nuevo_swd, nuevo_sed, informe
