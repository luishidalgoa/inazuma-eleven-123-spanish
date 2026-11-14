"""Instalación de una candidata como mod LayeredFS de Azahar.

Traslado de ``work/ie1/legacy/vs_revision/install.py``: se niega a instalar con Azahar abierto
(solo LISTA procesos, nunca mata ninguno), copia ``archive.fa`` y todo lo que haya bajo
``<candidata>/romfs``, vuelve a calcular el sha256 de cada copia instalada y lanza si alguna no
coincide, y deja ``installation.json`` junto a la candidata.

Antes de copiar nada comprueba que ``usearch.dat`` corresponde al ``unitbase.dat`` de la candidata (hook de nombres,
``servicio.sincronia_usearch``): una candidata desincronizada, o que no se puede comprobar, no se instala. El único
opt-out es el argumento nombrado ``comprobar_sincronia_usearch=False``.

Nunca toca la ROM original ni envía entradas al emulador: la QA la hace una persona
(docs/PROTOCOLO_QA_IE1.md), por eso ``runtime_verified`` siempre sale ``false``.
"""

from __future__ import annotations

import importlib
import os
import shutil
import subprocess
from pathlib import Path

from ie123kit.nucleo import util
from ie123kit.nucleo.errores import ValidacionError

__all__ = ["TITLE_ID", "azahar", "raiz_mods_por_defecto"]

#: Título de la recopilación Inazuma Eleven 1·2·3 (EUR).
TITLE_ID = "00040000000BB800"

_PROCESO = "azahar.exe"
#: se carga POR NOMBRE al instalar: ``nucleo`` no importa ``servicio`` (misma razón que en ``construir.candidata``)
_MODULO_SINCRONIA_USEARCH = "ie123kit.servicio.sincronia_usearch"


def raiz_mods_por_defecto(entorno: dict[str, str] | None = None) -> Path:
    """``%APPDATA%/Azahar/load/mods`` (o ``~/.local/share`` fuera de Windows)."""
    entorno = dict(os.environ if entorno is None else entorno)
    base = entorno.get("APPDATA") or entorno.get("XDG_DATA_HOME")
    raiz = Path(base) if base else Path.home() / ".local" / "share"
    return raiz / "Azahar" / "load" / "mods"


def _azahar_en_ejecucion() -> bool:
    """Lista procesos para saber si Azahar está abierto. No mata nada. Monkeypatcheable."""
    try:
        salida = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {_PROCESO}"],
            capture_output=True, text=True, check=False,
        ).stdout or ""
    except (OSError, subprocess.SubprocessError):
        return False
    return _PROCESO in salida.lower()


def _pares(candidata: Path, destino: Path) -> list[tuple[Path, Path]]:
    pares = [(candidata / "archive.fa", destino / "archive.fa")]
    romfs = candidata / "romfs"
    if romfs.is_dir():
        pares += [(src, destino / src.relative_to(romfs)) for src in sorted(romfs.rglob("*")) if src.is_file()]
    return pares


def _exigir_sincronia_usearch(archive: Path) -> None:
    """Falla (``ValidacionError``) si ``usearch.dat`` de ``archive`` no corresponde a su ``unitbase.dat``."""
    verificar_archive = importlib.import_module(_MODULO_SINCRONIA_USEARCH).verificar_archive
    try:
        informe = verificar_archive(archive)
    except Exception as exc:  # un archive ilegible no se da por sincronizado
        raise ValidacionError(
            "USEARCH_DESINCRONIZADO", ruta=archive,
            detalle=f"no se pudo comprobar la sincronía de usearch.dat: {exc}",
        ) from exc
    if not informe["ok"]:
        raise ValidacionError(
            informe.get("codigo") or "USEARCH_DESINCRONIZADO", ruta=archive,
            detalle="; ".join(informe["errores"][:5]) + " (python -m ie123kit.servicio.sincronia_usearch cerrar <copia>)",
        )


def azahar(
    candidata,
    *,
    title_id: str = TITLE_ID,
    raiz_mods=None,
    rehusar_si_ejecuta: bool = True,
    limpiar_obsoletos: bool = False,
    comprobar_sincronia_usearch: bool = True,
) -> dict:
    """Instala ``candidata`` en ``<raiz_mods>/<title_id>/romfs`` y devuelve el informe."""
    candidata = Path(candidata).resolve()
    if not candidata.is_dir():
        raise FileNotFoundError(candidata)
    if comprobar_sincronia_usearch:
        _exigir_sincronia_usearch(candidata / "archive.fa")
    if rehusar_si_ejecuta and _azahar_en_ejecucion():
        raise ValidacionError(
            "AZAHAR_EN_EJECUCION",
            ruta=candidata,
            detalle="Azahar está abierto: ciérralo antes de instalar la candidata.",
        )
    raiz = Path(raiz_mods).resolve() if raiz_mods is not None else raiz_mods_por_defecto()
    destino = raiz / title_id / "romfs"

    pares = _pares(candidata, destino)
    for src, _ in pares:
        if not src.is_file():
            raise FileNotFoundError(src)

    if limpiar_obsoletos and destino.is_dir():
        esperados = {dst.resolve() for _, dst in pares}
        for viejo in sorted(destino.rglob("*"), reverse=True):
            if viejo.is_file() and viejo.resolve() not in esperados:
                viejo.unlink()

    ficheros = []
    for src, dst in pares:
        esperado = util.sha256_file(src)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        instalado = util.sha256_file(dst)
        if instalado != esperado:
            raise ValidacionError(
                "HASH_TRAS_COPIA",
                ruta=dst,
                detalle=f"sha256 {instalado} != {esperado} (origen {src})",
            )
        ficheros.append({
            "rel": src.relative_to(candidata).as_posix(),
            "destino": str(dst),
            "sha256": instalado,
            "bytes": dst.stat().st_size,
        })

    informe = {
        "candidata": str(candidata),
        "title_id": title_id,
        "destino": str(destino),
        "fecha": util.ahora_iso(),
        "ficheros": ficheros,
        "runtime_verified": False,
        "nota": "Instalada para la QA manual en Azahar; no se ha enviado ninguna entrada al emulador.",
    }
    util.escribir_json(candidata / "installation.json", informe)
    return informe
