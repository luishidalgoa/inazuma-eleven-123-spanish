"""Cargador de los ficheros congelados de tools/ (bloqueo tipográfico v20).

Los ficheros bloqueados (AGENTS.md, ``tools/dialogue_lock.py``) nunca se copian ni se
reformatean: se importan tal cual como módulos de NIVEL SUPERIOR para compartir
``sys.modules`` con las capas de ``work/`` y los scripts de ``tools/``.
``build_ui_revision`` no se importa como módulo (v55 hace ``exec`` de su texto).

Los congelados importan por su nombre plano de ``tools/`` módulos que ya viven en el paquete
(``from fa_unpack import FaArchive``, ``import reinsert as R``, ``from bcfnt import BCFNT``…). Hasta la
F2.7 esos nombres los resolvían shims en ``tools/``; ahora :func:`preparar` instala un resolutor en
``sys.meta_path`` que, al importarse uno de esos nombres (:data:`ALIAS_CONGELADOS`), devuelve su módulo
real con la misma identidad que daba el shim, y deja ``tools/`` en ``sys.path``. Es el único sitio donde sobreviven esos nombres planos:
el código nuevo importa siempre ``ie123kit.<...>``. No se puede editar los congelados (hashes del
bloqueo), así que quien importe uno debe llamar antes a :func:`preparar` (o usar :func:`cargar`).

Por lo mismo, los congelados con CLI ya no se lanzan con ``python tools/<nombre>.py`` sino con
``python -m ie123kit.nucleo.compat.congelados <nombre> [args...]``, que prepara los alias y ejecuta
el fichero intacto como ``__main__``.

Importar este módulo no produce efectos: la carga ocurre al llamar a :func:`preparar` o :func:`cargar`.
"""
from __future__ import annotations

import importlib
import importlib.abc
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

from ie123kit.nucleo.config.raiz import find_root

__all__ = ["ALIAS_CONGELADOS", "EJECUTABLES", "IMPORTABLES", "cargar", "preparar"]

IMPORTABLES = ("dialogue_typography", "font_patch", "dialogue_lock", "build_ie1_probe")
#: Congelados con bloque ``__main__`` (se lanzan con ``ie123kit.nucleo.compat.congelados``).
EJECUTABLES = ("build_ui_revision", "build_ie1_probe", "font_patch")

#: Nombres planos que importan los congelados -> módulo real. ``build_ie1_probe`` y
#: ``build_ui_revision`` usan los seis primeros; ``font_patch`` (y por él ``dialogue_typography``),
#: ``bcfnt``.
ALIAS_CONGELADOS: dict[str, str] = {
    "fa_unpack": "ie123kit._legado.fa_unpack",
    "fa_repack": "ie123kit._legado.fa_repack",
    "lz10": "ie123kit.nucleo.compresion.lz10",
    "pkb_unpack": "ie123kit._legado.pkb_unpack",
    "reinsert": "ie123kit._legado.reinsert",
    "ssd_records": "ie123kit.nucleo.eventos.ssd",
    "bcfnt": "ie123kit._legado.bcfnt",
}


class _AliasCongelados(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    """Resuelve los nombres planos de :data:`ALIAS_CONGELADOS` al módulo real, en el momento del import.

    Es perezoso a propósito: el módulo real se importa cuando un congelado hace ``import reinsert``,
    igual que hacía el shim, y no al llamar a :func:`preparar` (``_legado.reinsert`` carga
    ``font_patch`` al importarse, y una carga anticipada dejaría ciclos a medio inicializar).
    """

    def find_spec(self, nombre, ruta=None, objetivo=None):
        if ruta is None and nombre in ALIAS_CONGELADOS:
            return importlib.util.spec_from_loader(nombre, self)
        return None

    def create_module(self, spec):
        return importlib.import_module(ALIAS_CONGELADOS[spec.name])

    def exec_module(self, modulo):
        """El módulo real ya está inicializado (o inicializándose): no hay nada que ejecutar."""


_ALIAS = _AliasCongelados()


def preparar(raiz: Path | None = None) -> Path:
    """Deja importables los congelados de ``tools/`` y devuelve esa carpeta.

    Pone ``tools/`` al principio de ``sys.path`` (si no está) e instala en ``sys.meta_path`` el
    resolutor de los alias de :data:`ALIAS_CONGELADOS`: ``import lz10`` devuelve el mismo objeto
    que ``ie123kit.nucleo.compresion.lz10``. Es idempotente.
    """
    tools = Path(raiz if raiz is not None else find_root()) / "tools"
    if str(tools) not in sys.path:
        sys.path.insert(0, str(tools))
    if _ALIAS not in sys.meta_path:
        sys.meta_path.insert(0, _ALIAS)
    return tools


def cargar(nombre: str, raiz: Path | None = None) -> ModuleType:
    """Importa el fichero congelado ``tools/<nombre>.py`` y lo devuelve.

    Lanza ValueError si ``nombre`` no está en IMPORTABLES e ImportError si el módulo
    resuelto no es el de ``tools/`` de la raíz.
    """
    if nombre not in IMPORTABLES:
        raise ValueError(f"{nombre!r} no es un fichero congelado importable: {IMPORTABLES}")
    tools = preparar(raiz)
    mod = importlib.import_module(nombre)
    origen = getattr(mod, "__file__", None)
    if origen is None or Path(origen).resolve().parent != tools.resolve():
        raise ImportError(f"{nombre} se ha resuelto fuera de {tools}: {origen}")
    return mod
