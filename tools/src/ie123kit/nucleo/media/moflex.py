"""Vídeo MOFLEX de 3DS: conversión desde MODS de DS y marca de rotación.

Layout 0x16 OBLIGATORIO: los MOFLEX retail de IE1 usan Simple2D + giro 1 en el
byte de layout de cada descriptor de vídeo (type 3, tamaño 13). El muxer de
mobipeg emite 0x06 y Azahar muestra entonces el fotograma 240x320 de lado, así
que tras codificar siempre se restaura la rotación (set_moflex_rotation) y se
verifica con disposicion_rotacion.

El MODS de DS almacena los planos cromáticos como YCgCo; aquí se descodifican a
RGB, se incrustan los subtítulos (ticks de 30 Hz) y se giran a 240x320.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

from ie123kit.nucleo.config.herramientas import exigir
from ie123kit.nucleo.media.subtitulos_dat import SUBTITLE_TICK_RATE, Subtitle, add_caption, read_subtitles

__all__ = [
    "SUBTITLE_TICK_RATE",
    "Subtitle",
    "convert",
    "disposicion_rotacion",
    "exportar_mp4",
    "probe",
    "rgb_to_yuv420",
    "set_moflex_rotation",
    "ycgco420_to_rgb",
]


def set_moflex_rotation(path: Path, rotation: int) -> int:
    """Copia ImageRotation al nibble alto de cada descriptor type-3.

    Los MOFLEX retail de IE1 usan layout 0x16: Simple2D + giro 1. El muxer de
    mobipeg emite 0x06 y Azahar muestra entonces el fotograma 240x320 de lado.
    """
    if not 0 <= rotation <= 15:
        raise ValueError("la rotación MOFLEX debe estar entre 0 y 15")
    data = bytearray(path.read_bytes())
    changed = 0
    pos = 0
    while True:
        pos = data.find(b"\x4c\x32", pos)
        if pos < 0:
            break
        # Cabecera de sincronía (14 bytes), descriptor type 3, tamaño 13;
        # el byte de layout es el último byte del payload.
        if pos + 29 <= len(data) and data[pos + 14] == 3 and data[pos + 15] == 13:
            layout_pos = pos + 28
            data[layout_pos] = (rotation << 4) | (data[layout_pos] & 0x0F)
            changed += 1
        pos += 2
    if not changed:
        raise ValueError(f"{path}: no se encontró ningún descriptor de vídeo MOFLEX")
    path.write_bytes(data)
    return changed


def probe(ffprobe: Path, source: Path) -> tuple[int, int, str]:
    proc = subprocess.run(
        [
            str(ffprobe), "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height,r_frame_rate", "-of", "json",
            str(source),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    stream = json.loads(proc.stdout)["streams"][0]
    return int(stream["width"]), int(stream["height"]), stream["r_frame_rate"]


def ycgco420_to_rgb(frame: bytes, width: int, height: int) -> np.ndarray:
    y_size = width * height
    c_width, c_height = width // 2, height // 2
    c_size = c_width * c_height
    if len(frame) != y_size + c_size * 2:
        raise ValueError("fotograma YUV420 incompleto")

    y = np.frombuffer(frame, np.uint8, y_size, 0).reshape(height, width).astype(np.int16)
    cg = np.frombuffer(frame, np.uint8, c_size, y_size).reshape(c_height, c_width)
    co = np.frombuffer(frame, np.uint8, c_size, y_size + c_size).reshape(c_height, c_width)
    cg = np.repeat(np.repeat(cg, 2, axis=0), 2, axis=1).astype(np.int16) - 128
    co = np.repeat(np.repeat(co, 2, axis=0), 2, axis=1).astype(np.int16) - 128

    temporary = y - cg
    rgb = np.stack((temporary + co, y + cg, temporary - co), axis=2)
    return np.clip(rgb, 0, 255).astype(np.uint8)


def rgb_to_yuv420(image: Image.Image) -> bytes:
    y, cb, cr = image.convert("YCbCr").split()
    half = (image.width // 2, image.height // 2)
    cb = cb.resize(half, Image.Resampling.BOX)
    cr = cr.resize(half, Image.Resampling.BOX)
    return y.tobytes() + cb.tobytes() + cr.tobytes()


def convert(source: Path, target: Path, mobipeg_dir: Path, qp: int,
            subtitles_path: Path | None = None, font_path: Path | None = None,
            rotation: int = 1) -> tuple[int, int, int]:
    ffmpeg = mobipeg_dir / "ffmpeg.exe"
    ffprobe = mobipeg_dir / "ffprobe.exe"
    if not ffmpeg.is_file() or not ffprobe.is_file():
        raise FileNotFoundError(f"Falta mobipeg portátil en {mobipeg_dir}")

    width, height, fps = probe(ffprobe, source)
    num, _, den = fps.partition("/")
    fps_value = float(num) / float(den or 1)
    if width % 2 or height % 2:
        raise ValueError("MODS no usa dimensiones pares")
    frame_size = width * height * 3 // 2
    subtitles = read_subtitles(subtitles_path)
    if subtitles and font_path is None:
        raise ValueError('falta font_path para incrustar subtítulos')
    if subtitles and subtitles[-1].end >= 10_000_000:
        raise ValueError(f"{subtitles_path}: tiempos de subtítulo inverosímiles")
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(target.suffix + ".partial")

    decoder = subprocess.Popen(
        [
            str(ffmpeg), "-hide_banner", "-loglevel", "error", "-i", str(source),
            "-map", "0:v:0", "-an", "-c:v", "rawvideo", "-pix_fmt", "yuv420p",
            "-f", "rawvideo", "pipe:1",
        ],
        stdout=subprocess.PIPE,
    )
    frames = 0
    raw_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix="mods_to_moflex_", suffix=".yuv", dir=target.parent, delete=False
        ) as raw_file:
            raw_path = Path(raw_file.name)
            assert decoder.stdout is not None
            while True:
                raw = decoder.stdout.read(frame_size)
                if not raw:
                    break
                if len(raw) != frame_size:
                    raise RuntimeError("el descodificador entregó un fotograma truncado")
                rgb = ycgco420_to_rgb(raw, width, height)
                image = Image.fromarray(rgb, "RGB")
                # Los .dat de movie/txt cuentan en ticks de 30 Hz, no en fotogramas del vídeo
                # (op00: 1763 fotogramas a 20 fps y último subtítulo en 2675 = 1763 * 30/20).
                tick = frames * SUBTITLE_TICK_RATE / fps_value
                active = next((item.text for item in subtitles if item.start <= tick <= item.end), "")
                add_caption(image, active, font_path)
                image = image.transpose(Image.Transpose.ROTATE_270)
                image = image.resize((240, 320), Image.Resampling.LANCZOS)
                raw_file.write(rgb_to_yuv420(image))
                frames += 1
    finally:
        if decoder.stdout:
            decoder.stdout.close()

    decoder_code = decoder.wait()
    if decoder_code:
        if raw_path:
            raw_path.unlink(missing_ok=True)
        raise RuntimeError(f"falló la descodificación (código={decoder_code})")

    try:
        encoder = subprocess.run(
            [
                str(ffmpeg), "-y", "-hide_banner", "-loglevel", "error",
                "-f", "rawvideo", "-pix_fmt", "yuv420p", "-s:v", "240x320", "-r", fps,
                "-i", str(raw_path), "-an", "-c:v", "mobiclip", "-mobiclip", "1",
                "-moflex", "1", "-qp", str(qp), "-pix_fmt", "yuv420p",
                "-threads", "1", "-x264opts", "mvrange=32",
                "-f", "moflex", str(partial),
            ],
            check=False,
        )
        if encoder.returncode or not partial.is_file() or partial.stat().st_size == 0:
            partial.unlink(missing_ok=True)
            raise RuntimeError(f"falló la codificación (código={encoder.returncode})")
        descriptors = set_moflex_rotation(partial, rotation)
        partial.replace(target)
        return frames, len(subtitles), descriptors
    finally:
        if raw_path:
            raw_path.unlink(missing_ok=True)


def disposicion_rotacion(path: Path) -> list[int]:
    """Devuelve el byte de layout de cada descriptor de vídeo MOFLEX (type 3, tamaño 13)."""
    data = path.read_bytes()
    values = []
    pos = 0
    while True:
        pos = data.find(b"\x4c\x32", pos)
        if pos < 0:
            return values
        if pos + 29 <= len(data) and data[pos + 14:pos + 16] == b"\x03\x0d":
            values.append(data[pos + 28])
        pos += 2


def exportar_mp4(entrada: Path, salida: Path, *, ws=None) -> dict:
    """Descodifica un MOFLEX a MP4 con ffmpeg (H.264 + yuv420p).

    ffmpeg se localiza con ``nucleo.config.herramientas.exigir``; si falta, la
    excepción ``HerramientaAusente`` sube con el código ``HERRAMIENTA_AUSENTE``.
    """
    entrada = Path(entrada)
    salida = Path(salida)
    if not entrada.is_file():
        raise FileNotFoundError(str(entrada))
    ffmpeg = exigir("ffmpeg", ws=ws)
    salida.parent.mkdir(parents=True, exist_ok=True)
    orden = [
        str(ffmpeg), "-y", "-hide_banner", "-loglevel", "error", "-i", str(entrada),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(salida),
    ]
    proceso = subprocess.run(orden, check=False, capture_output=True)
    if proceso.returncode or not salida.is_file() or salida.stat().st_size == 0:
        raise RuntimeError(f"ffmpeg falló al exportar {entrada.name} (código={proceso.returncode})")
    return {
        "entrada": str(entrada),
        "salida": str(salida),
        "herramienta": str(ffmpeg),
        "bytes": salida.stat().st_size,
    }
