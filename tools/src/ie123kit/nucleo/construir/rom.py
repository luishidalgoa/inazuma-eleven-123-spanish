"""Reconstrucción local de la ROM .3ds con 3dstool (romfs -> cxi -> 3ds).

Traslado de ``work/ie1/capas/v33/_final/build_rom.py`` (hoy ``capas/historial/candidata/v33_final``) y de
``work/shared/releases/release_v35/build_base.py``. Diferencia importante: el RomFS de la base
NO se modifica ni se renombra nunca. Se hace una copia de trabajo en un directorio temporal, se
superponen ahí los ficheros de la candidata y se reconstruye desde esa copia, así que no hace
falta ningún «restaurar originales» en un ``finally``.

3dstool se invoca con ``subprocess`` y los argumentos como lista (nunca ``shell=True``); se
comprueba el código de retorno y la salida del proceso queda en el informe.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from ie123kit.nucleo import util
from ie123kit.nucleo.config import herramientas
from ie123kit.nucleo.config.raiz import find_root
from ie123kit.nucleo.errores import ValidacionError

__all__ = ["build_3ds"]

#: Piezas de la base extraída (``work/shared/base_3ds``) necesarias para recomponer la ROM.
_PIEZAS = ("exefs.bin", "ncch_header.bin", "exh.bin", "ncsd_header.bin")


def _ejecutar(argumentos: list[str]) -> dict:
    """Ejecuta 3dstool. Función aparte para poder monkeypatchearla en los tests."""
    proceso = subprocess.run(argumentos, capture_output=True, text=True, check=False)
    return {
        "argumentos": list(argumentos),
        "returncode": proceso.returncode,
        "stdout": (proceso.stdout or "")[-4000:],
        "stderr": (proceso.stderr or "")[-4000:],
    }


def _correr(argumentos: list[str], pasos: list[dict]) -> None:
    paso = _ejecutar([str(a) for a in argumentos])
    pasos.append(paso)
    if paso["returncode"] != 0:
        raise ValidacionError(
            "3DSTOOL_FALLO",
            detalle=f"código {paso['returncode']}: {(paso['stderr'] or paso['stdout']).strip()[-400:]}",
        )


def build_3ds(candidata, salida, *, base=None, herramienta=None, conservar_intermedios: bool = False) -> dict:
    """Construye la ROM ``salida`` con los ficheros de ``candidata`` sobre la base extraída.

    ``base`` es la carpeta de la base extraída (por defecto ``work/shared/base_3ds``), con
    ``romfs/`` y las piezas ``exefs.bin``/``ncch_header.bin``/``exh.bin``/``ncsd_header.bin``.
    Devuelve ``{path, size, sha256, pasos, ...}``.
    """
    candidata = Path(candidata).resolve()
    salida = Path(salida).resolve()
    if base is None:
        base = find_root() / "work" / "shared" / "base_3ds"
    base = Path(base).resolve()
    if not candidata.is_dir():
        raise FileNotFoundError(candidata)
    if not (base / "romfs").is_dir():
        raise FileNotFoundError(base / "romfs")
    for pieza in _PIEZAS:
        if not (base / pieza).is_file():
            raise FileNotFoundError(base / pieza)
    tool = Path(herramienta).resolve() if herramienta is not None else herramientas.exigir("3dstool")

    salida.parent.mkdir(parents=True, exist_ok=True)
    pasos: list[dict] = []
    sustituidos: list[str] = []
    temporal = Path(tempfile.mkdtemp(prefix="ie123_rom_"))
    try:
        romfs = temporal / "romfs"
        shutil.copytree(base / "romfs", romfs)
        archivo = candidata / "archive.fa"
        if archivo.is_file():
            shutil.copyfile(archivo, romfs / "archive.fa")
            sustituidos.append("archive.fa")
        candidata_romfs = candidata / "romfs"
        if candidata_romfs.is_dir():
            for src in sorted(candidata_romfs.rglob("*")):
                if not src.is_file():
                    continue
                rel = src.relative_to(candidata_romfs)
                destino = romfs / rel
                destino.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(src, destino)
                sustituidos.append(rel.as_posix())

        romfs_bin = temporal / "romfs_new.bin"
        cxi = temporal / "part0.cxi"
        _correr([tool, "-ctf", "romfs", romfs_bin, "--romfs-dir", romfs], pasos)
        opcional: list = []
        plain = base / "plain.bin"
        if plain.is_file() and plain.stat().st_size:
            opcional = ["--plain", plain]
        _correr([tool, "-ctf", "cxi", cxi, "--romfs", romfs_bin, "--exefs", base / "exefs.bin",
                 "--header", base / "ncch_header.bin", "--exh", base / "exh.bin",
                 "--not-encrypt", *opcional], pasos)
        _correr([tool, "-ctf", "3ds", salida, "-0", cxi, "--header", base / "ncsd_header.bin"], pasos)
        if conservar_intermedios:
            for pieza in (romfs_bin, cxi):
                if pieza.is_file():
                    shutil.copyfile(pieza, salida.parent / pieza.name)
        if not salida.is_file():
            raise ValidacionError("ROM_NO_GENERADA", ruta=salida, detalle="3dstool terminó sin crear la ROM")
        return {
            "path": str(salida),
            "size": salida.stat().st_size,
            "sha256": util.sha256_file(salida),
            "candidata": str(candidata),
            "base": str(base),
            "herramienta": str(tool),
            "sustituidos": sustituidos,
            "pasos": pasos,
            "runtime_verified": False,
        }
    finally:
        shutil.rmtree(temporal, ignore_errors=True)
