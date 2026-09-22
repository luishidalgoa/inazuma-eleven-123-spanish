"""
De ROM/CIA a RomFS, usando 3dstool y ctrtool.

Acepta .3ds / .trim.3ds / .cci (NCSD), .cxi / .app (NCCH), .cia, o una
carpeta de RomFS ya extraida (en cuyo caso no hace nada).
"""

import shutil
import struct
import subprocess
from pathlib import Path


class RomError(RuntimeError):
    pass


NCSD_SUFFIXES = (".3ds", ".cci", ".ncsd")
NCCH_SUFFIXES = (".cxi", ".app", ".ncch")


def run(cmd, log, allow_failure=False):
    cmd = [str(x) for x in cmd]
    log(f"$ {subprocess.list2cmdline(cmd)}")

    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        errors="replace",
    )

    if result.returncode != 0 and not allow_failure:
        tail = "\n".join((result.stdout or "").strip().splitlines()[-15:])
        raise RomError(
            f"el comando fallo con codigo {result.returncode}:\n"
            f"{subprocess.list2cmdline(cmd)}\n{tail}"
        )

    return result.returncode, result.stdout or ""


def read_magic(path, offset, length=4):
    try:
        with open(path, "rb") as f:
            f.seek(offset)
            return f.read(length)
    except OSError:
        return b""


def is_ncch(path):
    return read_magic(path, 0x100) == b"NCCH"


def is_ncsd(path):
    return read_magic(path, 0x100) == b"NCSD"


def product_code(cxi):
    with open(cxi, "rb") as f:
        f.seek(0x150)
        return f.read(16).split(b"\x00")[0].decode("ascii", "replace")


def title_id(path):
    if is_ncsd(path):
        with open(path, "rb") as f:
            f.seek(0x108)
            return f"{struct.unpack('<Q', f.read(8))[0]:016X}"
    return None


def detect_kind(path):
    path = Path(path)

    if path.is_dir():
        return "romfs-dir"

    suffix = path.suffix.lower()

    if suffix == ".cia":
        return "cia"
    if is_ncsd(path) or suffix in NCSD_SUFFIXES:
        return "ncsd"
    if is_ncch(path) or suffix in NCCH_SUFFIXES:
        return "ncch"
    if suffix == ".bin" or suffix == ".romfs":
        return "romfs-bin"

    raise RomError(
        f"No se reconoce el formato de {path}. Se admite .3ds, .trim.3ds, "
        f".cci, .cxi, .app, .cia, romfs.bin o una carpeta de RomFS."
    )


def cia_to_cxi(cia, work, ctrtool, log):
    prefix = work / "cia_contents"

    for stale in work.glob("cia_contents.*"):
        stale.unlink()

    # ctrtool devuelve un codigo distinto de cero al verificar algunas firmas
    # aunque haya extraido el contenido correctamente, asi que comprobamos el
    # resultado en disco en vez de fiarnos del codigo de salida.
    code, _ = run(
        [ctrtool, f"--contents={prefix}", cia], log, allow_failure=True
    )

    produced = sorted(work.glob("cia_contents.*"))

    if not produced:
        raise RomError(
            f"ctrtool no genero ningun contenido a partir de {cia} "
            f"(codigo {code})"
        )

    ncch = [p for p in produced if is_ncch(p)]

    if not ncch:
        raise RomError(
            f"ctrtool extrajo {len(produced)} contenidos de {cia} pero "
            f"ninguno es un NCCH/CXI"
        )

    ncch.sort(key=lambda p: p.stat().st_size, reverse=True)

    if code != 0:
        log(
            f"  aviso: ctrtool termino con codigo {code} (normalmente es la "
            f"verificacion de firmas); el contenido se extrajo bien"
        )

    return ncch[0]


def ncsd_to_cxi(rom, work, dstool, log):
    cxi = work / "partition0.cxi"

    run(
        [
            dstool, "-x", "-t", "3ds", "-f", rom,
            "--header", work / "ncsd_header.bin",
            "-0", cxi,
        ],
        log,
    )

    if not cxi.exists():
        raise RomError(f"3dstool no genero {cxi}")

    return cxi


def cxi_to_romfs_bin(cxi, work, dstool, log):
    romfs_bin = work / "romfs.bin"

    run(
        [
            dstool, "-x", "-t", "cxi", "-f", cxi,
            "--header", work / "ncch_header.bin",
            "--exefs", work / "exefs.bin",
            "--romfs", romfs_bin,
        ],
        log,
    )

    if not romfs_bin.exists():
        raise RomError(f"3dstool no genero {romfs_bin}")

    return romfs_bin


def romfs_bin_to_dir(romfs_bin, work, dstool, log, force=False):
    romfs_dir = work / "romfs"

    if romfs_dir.exists() and any(romfs_dir.iterdir()) and not force:
        log(f"  RomFS ya extraido en {romfs_dir}, se reutiliza")
        return romfs_dir

    if romfs_dir.exists():
        shutil.rmtree(romfs_dir)

    run(
        [dstool, "-x", "-t", "romfs", "-f", romfs_bin, "--romfs-dir", romfs_dir],
        log,
    )

    return romfs_dir


def prepare_romfs(source, work, dstool, ctrtool, log, force=False):
    """Deja el RomFS en disco y devuelve su carpeta."""
    source = Path(source).resolve()
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)

    kind = detect_kind(source)
    log(f"Entrada: {source.name}  ({kind})")

    if kind == "romfs-dir":
        return source

    romfs_dir = work / "romfs"
    if romfs_dir.exists() and any(romfs_dir.iterdir()) and not force:
        log(f"  RomFS ya extraido en {romfs_dir}, se reutiliza (--force para rehacerlo)")
        return romfs_dir

    if kind == "romfs-bin":
        return romfs_bin_to_dir(source, work, dstool, log, force)

    if kind == "cia":
        cxi = cia_to_cxi(source, work, ctrtool, log)
    elif kind == "ncsd":
        cxi = ncsd_to_cxi(source, work, dstool, log)
    else:
        cxi = source

    log(f"  CXI: {cxi.name}  ({product_code(cxi)})")

    romfs_bin = cxi_to_romfs_bin(cxi, work, dstool, log)

    return romfs_bin_to_dir(romfs_bin, work, dstool, log, force)
