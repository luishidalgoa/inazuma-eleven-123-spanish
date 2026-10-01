"""Puerta del bloqueo tipográfico v20 sobre una candidata ya construida.

Extrae en crudo, a un temporal que siempre se borra, las cinco fuentes que fija
``tools/dialogue_lock.py`` (FONT_HASHES) desde el ``archive.fa`` de la candidata y
delega en ``dialogue_lock.validate``, que además comprueba los hashes de
``tools/dialogue_typography.py``, ``tools/font_patch.py`` y del ajuste de líneas
bloqueado de ``tools/build_ie1_probe.py``. No se modifica ningún fichero bloqueado.

Uso: ``python -m ie123kit.nucleo.validar.bloqueo --candidata <archive.fa|carpeta>``.
Importar este módulo no produce I/O: los módulos de tools/ se cargan al llamar.
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

from ie123kit.nucleo.config.congelados import preparar
from ie123kit.nucleo.config.raiz import find_root
from ie123kit.nucleo.errores import BloqueoTipograficoError

__all__ = ["comprobar"]


def comprobar(candidata: str | os.PathLike, raiz: Path | None = None) -> None:
    """Lanza BloqueoTipograficoError si la candidata no respeta el bloqueo v20.

    ``candidata`` es el ``archive.fa`` o la carpeta que lo contiene. Códigos:
    ``candidata_ausente``, ``fuente_ausente`` y ``bloqueo_v20``.
    """
    archive = Path(candidata)
    if archive.is_dir():
        archive = archive / "archive.fa"
    if not archive.is_file():
        raise BloqueoTipograficoError("candidata_ausente", archive)

    raiz = Path(raiz) if raiz is not None else find_root()
    preparar(raiz)

    # Por nombre de tools/: dialogue_lock y el layout bloqueado son los ficheros intactos.
    import dialogue_lock
    from build_ie1_probe import layout
    from ie123kit.nucleo.contenedores.fa import FaArchive

    arc = FaArchive(archive)
    entradas: dict[str, tuple[int, int]] = {}
    for ruta, abs_off, size in arc.entries:
        entradas.setdefault(ruta, (abs_off, size))
    tmp = Path(tempfile.mkdtemp(prefix="ie123_bloqueo_"))
    try:
        for rel in dialogue_lock.FONT_HASHES:
            if rel not in entradas:
                raise BloqueoTipograficoError("fuente_ausente", rel)
            abs_off, size = entradas[rel]
            destino = tmp / rel
            destino.parent.mkdir(parents=True, exist_ok=True)
            # En crudo, sin descomprimir: así las escriben build_ie1_probe y build_ui_revision.
            destino.write_bytes(arc.file_bytes(abs_off, size))
        try:
            dialogue_lock.validate(True, tmp, layout)
        except ValueError as exc:
            raise BloqueoTipograficoError("bloqueo_v20", archive, str(exc)) from exc
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    import argparse

    _ap = argparse.ArgumentParser(
        prog="python -m ie123kit.nucleo.validar.bloqueo",
        description="Comprueba que una candidata respeta el bloqueo tipográfico v20.",
    )
    _ap.add_argument("--candidata", required=True, type=Path, help="archive.fa o carpeta de la candidata")
    _ap.add_argument("--raiz", type=Path, help="raíz del repositorio (por defecto, find_root)")
    _args = _ap.parse_args()
    try:
        comprobar(_args.candidata, _args.raiz)
    except BloqueoTipograficoError as _exc:
        print(f"ERROR: {_exc}", file=sys.stderr)
        raise SystemExit(1)
    print(f"bloqueo v20 OK: {_args.candidata}")
    raise SystemExit(0)
