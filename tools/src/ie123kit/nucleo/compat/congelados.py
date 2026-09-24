"""Lanza como script un fichero congelado de tools/ (F2.7).

Uso: python -m ie123kit.nucleo.compat.congelados {build_ui_revision,build_ie1_probe,font_patch} [args...]

Sustituye a ``python tools/<nombre>.py``: sin shims en tools/, los congelados solo encuentran los
nombres planos que importan (``fa_unpack``, ``lz10``, ``reinsert``…) tras
:func:`ie123kit.nucleo.config.congelados.preparar`. El fichero se ejecuta intacto con ``runpy``.
"""
from __future__ import annotations

import runpy
import sys
from pathlib import Path

from ie123kit.nucleo.config.congelados import EJECUTABLES, preparar

__all__ = ["ejecutar", "main"]


def ejecutar(nombre: str, argv: list[str] | None = None, raiz: Path | None = None) -> int:
    """Ejecuta ``tools/<nombre>.py`` como ``__main__`` con los alias preparados; devuelve el código de salida."""
    if nombre not in EJECUTABLES:
        raise ValueError(f"{nombre!r} no es un congelado ejecutable: {EJECUTABLES}")
    ruta = preparar(raiz) / f"{nombre}.py"
    antes = sys.argv
    sys.argv = [str(ruta), *(argv or [])]
    try:
        runpy.run_path(str(ruta), run_name="__main__")
    except SystemExit as exc:
        if exc.code is None or isinstance(exc.code, int):
            return exc.code or 0
        print(exc.code, file=sys.stderr)
        return 1
    finally:
        sys.argv = antes
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] not in EJECUTABLES:
        ayuda = bool(args) and args[0] in ("-h", "--help")
        print(
            "uso: python -m ie123kit.nucleo.compat.congelados {" + ",".join(EJECUTABLES) + "} [args del script...]",
            file=sys.stdout if ayuda else sys.stderr,
        )
        return 0 if ayuda else 2
    return ejecutar(args[0], args[1:])


if __name__ == "__main__":
    sys.exit(main())
