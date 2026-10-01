#!/usr/bin/env python3
"""Convierte vídeo MobiClip de Nintendo DS (.mods) a 3DS (.moflex).

El MODS de DS almacena los planos cromáticos como YCgCo. FFmpeg los etiqueta
correctamente, pero su conversor de color no admite todavía esa transformación.
Este puente descodifica a Y/Cg/Co, convierte cada fotograma a RGB, incrusta si
existe la pista de subtítulos europea, lo gira al formato 240x320 usado por IE1
en 3DS y lo entrega al codificador MobiClip. Finalmente restaura en todos los
descriptores MOFLEX la marca de rotación que usa el juego original.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ie123kit.nucleo.config.raiz import find_root
from ie123kit.nucleo.media import moflex as _moflex
from ie123kit.nucleo.media.moflex import probe, rgb_to_yuv420, set_moflex_rotation, ycgco420_to_rgb
from ie123kit.nucleo.media.subtitulos_dat import (
    SUBTITLE_TICK_RATE,
    Subtitle,
    add_caption,
    fit_caption,
    read_subtitles,
)
from ie123kit.nucleo.texto.nds_latin import DS_TABLE, decode_ds

REPO = find_root()
# La compilación x64 v2.1 se bloquea al codificar imágenes complejas en Windows
# (0xc0000005). La compilación x86 del mismo lanzamiento supera ese caso.
DEFAULT_MOBIPEG = REPO / "work" / "shared" / "herramientas" / "media_tools" / "mobipeg-v2.1-x86"
DEFAULT_FONT = Path("C:/Windows/Fonts/arialbd.ttf")


def convert(source: Path, target: Path, mobipeg_dir: Path, qp: int,
            subtitles_path: Path | None = None, font_path: Path = DEFAULT_FONT,
            rotation: int = 1) -> tuple[int, int, int]:
    """Envoltorio heredado de ie123kit.nucleo.media.moflex.convert con la fuente arialbd por defecto."""
    return _moflex.convert(source, target, mobipeg_dir, qp, subtitles_path, font_path, rotation)


def _main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("target", type=Path)
    parser.add_argument("--mobipeg", type=Path, default=DEFAULT_MOBIPEG)
    parser.add_argument("--qp", type=int, default=28)
    parser.add_argument("--subtitles", type=Path,
                        help="pista movie/txt/sp/*.dat que se incrustará en el vídeo")
    parser.add_argument("--font", type=Path, default=DEFAULT_FONT)
    parser.add_argument("--rotation", type=int, default=1,
                        help="ImageRotation del MOFLEX (IE1 retail usa 1)")
    args = parser.parse_args()

    frames, subtitles, descriptors = convert(
        args.source.resolve(), args.target.resolve(), args.mobipeg.resolve(), args.qp,
        args.subtitles.resolve() if args.subtitles else None, args.font.resolve(), args.rotation,
    )
    print(f"OK: {frames} fotogramas, {subtitles} subtítulos, "
          f"{descriptors} descriptores de giro -> {args.target}")



def main() -> int:
    try:
        _main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
