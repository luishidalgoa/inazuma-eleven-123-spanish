"""Entradas de fichero de los motores del juego principal que expone ``ie123 motor … --juego juego_principal``.

Cada función recibe rutas, escribe solo en ``salida`` (nunca en la entrada ni en capas de ``work/``),
se niega a sobrescribir y devuelve un dict serializable para el ``Resultado``. La lógica está en
``juego_principal.voz_titulo`` y en ``nucleo``; aquí solo hay lectura y escritura.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path
from typing import Any

__all__ = ["voz_recopilatorio"]


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _escribir(ruta: Path, datos: bytes) -> str:
    if ruta.exists():
        raise FileExistsError(f"ya existe: {ruta}")
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_bytes(datos)
    return str(ruta)


def _mono(fuente: Path, sr: int) -> Any:
    """PCM mono flotante de un audio cualquiera, remuestreado a ``sr`` con ffmpeg."""
    import numpy as np

    from ie123kit.nucleo.config.herramientas import exigir

    orden = [str(exigir("ffmpeg")), "-v", "error", "-i", str(fuente), "-ac", "1", "-ar", str(sr),
             "-f", "f32le", "-"]
    crudo = subprocess.run(orden, capture_output=True, check=True).stdout
    return np.frombuffer(crudo, "<f4").astype(np.float64)


def voz_recopilatorio(sonido: str | os.PathLike, fuente: str | os.PathLike,
                      salida: str | os.PathLike) -> dict:
    """``CM_000.SWD``/``.SED`` con la grabación ``fuente`` como grito del título del recopilatorio.

    ``sonido``: carpeta con el ``CM_000.SWD``/``.SED`` japoneses (``romfs/sound``); ``fuente``: audio
    de la voz española (cualquier formato que lea ffmpeg); ``salida``: carpeta donde se escriben los
    dos ficheros (no se sobrescriben).
    """
    from ie123kit.juego_principal import voz_titulo as VT

    carpeta = Path(sonido)
    swd = (carpeta / "CM_000.SWD").read_bytes()
    sed = (carpeta / "CM_000.SED").read_bytes()
    x = _mono(Path(fuente), VT.SR_FUENTE)
    nuevo_swd, nuevo_sed, informe = VT.construir(swd, sed, x)
    artefactos = [_escribir(Path(salida) / "CM_000.SWD", nuevo_swd),
                  _escribir(Path(salida) / "CM_000.SED", nuevo_sed)]
    return {
        **informe,
        "fuente": {"fichero": Path(fuente).name, "sha256": _sha(Path(fuente).read_bytes()),
                   "rate": VT.SR_FUENTE, "duracion_s": round(len(x) / VT.SR_FUENTE, 3)},
        "sha256": {"CM_000.SWD": _sha(nuevo_swd), "CM_000.SED": _sha(nuevo_sed)},
        "artefactos": artefactos,
    }
