#!/usr/bin/env python3
"""Prepara una copia de un SMDH con el título del slot español cambiado.

No modifica el icono original. El SMDH conserva 12 slots de idioma de 0x200
bytes; el español ocupa el slot 5.
"""
import argparse
from pathlib import Path

from ie123kit.nucleo.ejecutable.smdh import *  # noqa: F401,F403


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("title")
    parser.add_argument("--slot", type=int, default=SPANISH_SLOT)
    args = parser.parse_args()
    patch_title(args.source, args.output, args.title, args.slot)
    print(f"SMDH preparado: {args.output} (slot {args.slot})")


if __name__ == "__main__":
    main()
