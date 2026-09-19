"""Cinemáticas de IE1: catálogo de las 21 películas, volcado a MP4/SRT y reinserción.

El catálogo declarativo vive en ``cinematicas.toml`` (solo rutas y metadatos cortos) y
se lee con ``importlib.resources``, cacheado y sin ninguna E/S al importar.

Rotación OBLIGATORIA: los MOFLEX retail de IE1 usan layout ``0x16`` (Simple2D + giro 1).
El muxer de mobipeg emite ``0x06`` y Azahar muestra entonces el fotograma de lado, así
que tras codificar se restaura SIEMPRE con ``set_moflex_rotation`` y se verifica con
``disposicion_rotacion``.
"""

from __future__ import annotations

import subprocess
import tomllib
from functools import lru_cache
from importlib import resources
from pathlib import Path

from ie123kit.nucleo.config.herramientas import exigir
from ie123kit.nucleo.errores import ValidacionError
from ie123kit.nucleo.media.moflex import disposicion_rotacion, exportar_mp4, set_moflex_rotation
from ie123kit.nucleo.media.subtitulos_dat import SUBTITLE_TICK_RATE, read_subtitles

__all__ = ["CATALOGO", "LAYOUT_ESPERADO", "ROTACION", "exportar", "importar", "peliculas", "srt"]

CATALOGO = "cinematicas.toml"
ROTACION = 1
LAYOUT_ESPERADO = 0x16


@lru_cache(maxsize=1)
def _catalogo() -> tuple[dict, ...]:
    datos = resources.files(__package__).joinpath(CATALOGO).read_bytes()
    entradas = tomllib.loads(datos.decode("utf-8")).get("pelicula", [])
    return tuple(dict(entrada) for entrada in entradas)


def peliculas() -> list[dict]:
    """Catálogo de películas: ``id``, ``ruta_romfs``, ``subtitulos_dat`` (y ``fotogramas``)."""
    return [dict(entrada) for entrada in _catalogo()]


def _marca(ticks: int) -> str:
    total_ms = round(ticks * 1000 / SUBTITLE_TICK_RATE)
    horas, resto = divmod(total_ms, 3_600_000)
    minutos, resto = divmod(resto, 60_000)
    segundos, ms = divmod(resto, 1000)
    return f"{horas:02d}:{minutos:02d}:{segundos:02d},{ms:03d}"


def srt(subtitulos) -> str:
    """Convierte los ``Subtitle`` (ticks de 30 Hz) en un SRT UTF-8."""
    bloques = []
    for numero, item in enumerate(subtitulos, start=1):
        bloques.append(f"{numero}\n{_marca(item.start)} --> {_marca(item.end)}\n{item.text}\n")
    return "\n".join(bloques)


def exportar(origen_moflex: Path, destino_dir: Path, *, subtitulos: Path | None = None, ws=None) -> dict:
    """Escribe ``<id>.mp4`` y, si hay ``.dat``, ``<id>.srt`` en ``destino_dir``."""
    origen_moflex = Path(origen_moflex)
    destino_dir = Path(destino_dir)
    identificador = origen_moflex.stem.lower()
    destino_dir.mkdir(parents=True, exist_ok=True)
    mp4 = destino_dir / f"{identificador}.mp4"
    informe = dict(exportar_mp4(origen_moflex, mp4, ws=ws))
    informe["id"] = identificador
    informe["mp4"] = str(mp4)
    informe["srt"] = None
    informe["subtitulos"] = 0
    if subtitulos is not None:
        pistas = read_subtitles(Path(subtitulos))
        ruta_srt = destino_dir / f"{identificador}.srt"
        ruta_srt.write_text(srt(pistas), encoding="utf-8")
        informe["srt"] = str(ruta_srt)
        informe["subtitulos"] = len(pistas)
    return informe


def importar(mp4: Path, destino_moflex: Path, *, srt: Path | None = None,
             simular: bool = True, ws=None) -> dict:
    """Codifica el MP4 a MOFLEX con mobipeg x86 y deja el layout en ``0x16``.

    Con ``simular`` no se escribe el MOFLEX de destino, pero la herramienta se exige
    igual para que la incidencia ``HERRAMIENTA_AUSENTE`` salga antes de construir nada.
    """
    mp4 = Path(mp4)
    destino_moflex = Path(destino_moflex)
    herramienta = exigir("mobipeg", ws=ws)
    if not mp4.is_file():
        raise FileNotFoundError(str(mp4))
    informe = {
        "id": destino_moflex.stem.lower(),
        "entrada": str(mp4),
        "salida": str(destino_moflex),
        "herramienta": str(herramienta),
        "simulado": bool(simular),
        "layout": LAYOUT_ESPERADO,
        "descriptores": 0,
        "subtitulos": str(srt) if srt is not None else None,
    }
    if simular:
        return informe

    destino_moflex.parent.mkdir(parents=True, exist_ok=True)
    parcial = destino_moflex.with_suffix(destino_moflex.suffix + ".partial")
    orden = [str(herramienta), "-y", "-hide_banner", "-loglevel", "error", "-i", str(Path(mp4).resolve())]
    carpeta = None
    if srt is not None:
        # El filtro subtitles= toma los «:» de «C:/…» como separador de opciones: se ejecuta en la
        # carpeta del SRT y se le pasa solo el nombre, escapado para el analizador de filtros.
        srt = Path(srt).resolve()
        carpeta = srt.parent
        nombre = srt.name.replace("\\", r"\\").replace("'", r"\'").replace(":", r"\:")
        orden += ["-vf", f"subtitles='{nombre}'"]
    orden += ["-an", "-c:v", "mobiclip", "-mobiclip", "1", "-moflex", "1",
              "-pix_fmt", "yuv420p", "-threads", "1", "-f", "moflex", str(parcial.resolve())]
    proceso = subprocess.run(orden, check=False, capture_output=True, cwd=carpeta)
    if proceso.returncode or not parcial.is_file() or parcial.stat().st_size == 0:
        parcial.unlink(missing_ok=True)
        raise RuntimeError(f"mobipeg falló al codificar {mp4.name} (código={proceso.returncode})")
    informe["descriptores"] = set_moflex_rotation(parcial, ROTACION)
    disposiciones = disposicion_rotacion(parcial)
    if not disposiciones or set(disposiciones) != {LAYOUT_ESPERADO}:
        parcial.unlink(missing_ok=True)
        raise ValidacionError(
            "MOFLEX_LAYOUT_INVALIDO",
            ruta=destino_moflex,
            detalle=f"layout {sorted(set(disposiciones))} en lugar de 0x{LAYOUT_ESPERADO:02x}",
        )
    parcial.replace(destino_moflex)
    informe["bytes"] = destino_moflex.stat().st_size
    return informe
