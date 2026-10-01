"""Inspección genérica de audio SADL (.SAD) de Level-5.

Solo lee la cabecera (canales, frecuencia, bucle, tamaños) y calcula el sha256, y
convierte SAD -> WAV con vgmstream. La dirección contraria (WAV -> SADL) NO está
soportada: las voces europeas se sobreponen completas por LayeredFS (docs/IE1_AUDIO_
CINEMATICAS_V34.md), nunca se recodifican.
"""

from __future__ import annotations

import hashlib
import struct
import subprocess
from dataclasses import dataclass
from pathlib import Path

from ie123kit.nucleo.config.herramientas import exigir
from ie123kit.nucleo.errores import FormatoError

__all__ = ["SadInfo", "inspect_sad", "sad_a_wav", "sha256", "validar_sad"]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class SadInfo:
    size: int
    channels: int
    sample_rate: int
    codec_flag: str
    loop: bool
    data_size: int
    start_offset: int
    sha256: str


def inspect_sad(path: Path) -> SadInfo:
    data = path.read_bytes()
    if len(data) < 0x58 or data[:4] != b"sadl":
        raise ValueError(f"{path}: no es un SADL válido")
    flags = data[0x33]
    rate_bits = flags & 0x06
    if rate_bits == 0x04:
        sample_rate = 32728
    elif rate_bits in (0x00, 0x02):
        sample_rate = 16364
    else:
        raise ValueError(f"{path}: frecuencia SADL desconocida (flags=0x{flags:02x})")
    return SadInfo(
        size=len(data),
        channels=data[0x32],
        sample_rate=sample_rate,
        codec_flag=f"0x{flags:02x}",
        loop=bool(data[0x31]),
        data_size=struct.unpack_from("<I", data, 0x40)[0],
        start_offset=struct.unpack_from("<I", data, 0x48)[0],
        sha256=sha256(path),
    )


def validar_sad(entrada: Path) -> SadInfo:
    """Como :func:`inspect_sad` pero lanza ``FormatoError`` si no es un SADL válido."""
    entrada = Path(entrada)
    if not entrada.is_file():
        raise FormatoError(f"{entrada}: no existe")
    try:
        return inspect_sad(entrada)
    except ValueError as exc:
        raise FormatoError(str(exc)) from exc


def sad_a_wav(entrada: Path, salida: Path, *, ws=None) -> dict:
    """Vuelca un SADL a WAV con vgmstream (``-o``), sin tocar el original.

    vgmstream se localiza con ``nucleo.config.herramientas.exigir``; si falta sube
    ``HerramientaAusente`` con el código ``HERRAMIENTA_AUSENTE``.
    """
    entrada = Path(entrada)
    salida = Path(salida)
    info = validar_sad(entrada)
    herramienta = exigir("vgmstream", ws=ws)
    salida.parent.mkdir(parents=True, exist_ok=True)
    orden = [str(herramienta), "-o", str(salida), str(entrada)]
    proceso = subprocess.run(orden, check=False, capture_output=True)
    if proceso.returncode or not salida.is_file() or salida.stat().st_size == 0:
        raise RuntimeError(f"vgmstream falló con {entrada.name} (código={proceso.returncode})")
    bytes_wav = max(salida.stat().st_size - 44, 0)
    muestras = bytes_wav // max(2 * info.channels, 1)
    return {
        "salida": str(salida),
        "sha256_origen": info.sha256,
        "muestras": muestras,
        "canales": info.channels,
        "frecuencia": info.sample_rate,
        "herramienta": str(herramienta),
    }
