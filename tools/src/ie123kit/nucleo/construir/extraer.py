"""Extracción de las ROM a ``work/``: RomFS/ExeFS de la 3DS (3dstool) y sistema de archivos NDS.

Sustituye a ``tools/extract_romfs.ps1`` (mismos pasos de 3dstool y misma disposición de salida en
``work/shared/base_3ds``) y a ``tools/extract_nds.ps1``/``tools/nds_unpack.py`` (extractor NDS en
Python puro, sin ndstool; misma salida que ``nds_unpack``: ``salida/data_iz/...``).

El contenido extraído tiene copyright: solo se escribe bajo ``work/`` (ignorado por git, Norma 2).
3dstool se invoca con los argumentos como lista, nunca con ``shell=True``.
"""

from __future__ import annotations

import os
import struct
from pathlib import Path

from ie123kit.nucleo.config import herramientas
from ie123kit.nucleo.construir import rom as _rom
from ie123kit.nucleo.contenedores import nds_rom
from ie123kit.nucleo.errores import ValidacionError

__all__ = ["nds", "romfs_3ds"]


def romfs_3ds(rom: str | os.PathLike, salida: str | os.PathLike, *, herramienta=None, ws=None) -> dict:
    """ROM 3DS descifrada -> ``salida/{romfs,exefs}`` con las cabeceras y los .bin intermedios."""
    rom, salida = Path(rom), Path(salida)
    if not rom.is_file():
        raise ValidacionError("ROM_AUSENTE", rom)
    tool = Path(herramienta) if herramienta else herramientas.exigir("3dstool", ws=ws)
    salida.mkdir(parents=True, exist_ok=True)
    cxi, romfs, exefs = salida / "partition0.cxi", salida / "romfs.bin", salida / "exefs.bin"
    pasos: list[dict] = []
    _rom._correr([tool, "-xtf", "3ds", rom, "--header", salida / "ncsd_header.bin", "-0", cxi], pasos)
    _rom._correr([tool, "-xtf", "cxi", cxi, "--header", salida / "ncch_header.bin", "--exefs", exefs,
                  "--romfs", romfs], pasos)
    _rom._correr([tool, "-xtf", "romfs", romfs, "--romfs-dir", salida / "romfs"], pasos)
    _rom._correr([tool, "-xtf", "exefs", exefs, "--exefs-dir", salida / "exefs"], pasos)
    return {"rom": str(rom), "salida": str(salida), "romfs": str(salida / "romfs"),
            "exefs": str(salida / "exefs"), "pasos": len(pasos)}


def nds(rom: str | os.PathLike, salida: str | os.PathLike | None) -> dict:
    """ROM NDS -> ``salida/<árbol de la ROM>`` (como nds_unpack; ``salida=None``: solo lista)."""
    rom = Path(rom)
    if not rom.is_file():
        raise ValidacionError("ROM_AUSENTE", rom)
    data = rom.read_bytes()
    if len(data) < 0x50:
        raise ValidacionError("ROM_NDS_CORTA", rom)
    fnt_off, fat_off, fat_size = nds_rom.u32(data, 0x40), nds_rom.u32(data, 0x48), nds_rom.u32(data, 0x4C)
    fat = [struct.unpack_from("<II", data, fat_off + 8 * i) for i in range(fat_size // 8)]
    destino = None
    if salida is not None:
        destino = Path(salida)
        destino.mkdir(parents=True, exist_ok=True)
    ficheros: list = []
    nds_rom.read_dir(data, fnt_off, 0xF000, fat, names_only=destino is None,
                     out_dir=str(destino) if destino else None, files_log=ficheros)
    return {"rom": str(rom), "titulo": data[0:12].decode("ascii", "replace").rstrip("\0"),
            "codigo": data[12:16].decode("ascii", "replace"), "ficheros": len(ficheros),
            "bytes": sum(t for _, t in ficheros), "salida": str(destino) if destino else None}
