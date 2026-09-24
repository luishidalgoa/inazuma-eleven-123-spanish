"""Compactación por streaming de un contenedor B123 (``archive.fa``).

Cada vez que se sustituye una entrada con ``reemplazar_entrada`` el contenido nuevo se ANEXA al
final y el FileEntry se reapunta; lo viejo se queda dentro sin que nada lo lea. Este módulo
reescribe el contenedor dejando solo los datos a los que apunta la tabla de ficheros.

A diferencia de ``FaArchive`` no carga el contenedor en memoria: lee cabecera y tablas con
lecturas parciales y copia los datos por bloques, así que sirve para ficheros de más de 2 GiB
(en Windows, ``read()`` de un fichero así falla con ``Errno 22``).

Decisiones:

* Los datos se copian en el orden de su desplazamiento original, alineados a 16. Así lo que no
  se tocó conserva su orden relativo (los parches binarios contra el original salen menores).
* Las entradas que comparten los mismos datos (mismo desplazamiento y tamaño) siguen
  compartiéndolos.
* Cabecera, tablas y nombres se copian tal cual; solo cambia el campo de desplazamiento de
  cada FileEntry.

API sin efectos de consola ni rutas fijas: devuelve un :class:`InformeCompactacion`.
"""

from __future__ import annotations

import hashlib
import os
import struct
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "EntradaFa",
    "InformeCompactacion",
    "compactar_fa",
    "huellas_entradas",
    "leer_entradas",
]

_BLOQUE = 4 * 1024 * 1024
_ALINEADO = 16
_DIR = 24
_FICHERO = 16
_MAGICS = (b"B123", b"ARC0", b"XFSA")


@dataclass(frozen=True)
class EntradaFa:
    """Un FileEntry: posición del registro en el fichero, desplazamiento relativo y tamaño."""

    registro: int
    offset: int
    tamano: int


@dataclass(frozen=True)
class InformeCompactacion:
    origen_bytes: int
    destino_bytes: int
    entradas: int
    bloques_unicos: int
    verificadas: int


def _cabecera(fh) -> tuple[int, int, int, int]:
    """(tabla de directorios, tabla de ficheros, inicio de datos, nº de directorios)."""
    fh.seek(0)
    cab = fh.read(32)
    if len(cab) < 32 or cab[:4] not in _MAGICS:
        raise ValueError(f"no es un contenedor B123: magic {cab[:4]!r}")
    de_off, _dh, fe_off, _names, data_off = struct.unpack_from("<5i", cab, 4)
    de_cnt = struct.unpack_from("<H", cab, 24)[0]
    return de_off, fe_off, data_off, de_cnt


def leer_entradas(ruta: str | os.PathLike[str]) -> tuple[int, list[EntradaFa]]:
    """Devuelve ``(data_off, entradas)`` en orden de tabla, sin cargar el contenedor entero."""
    with Path(ruta).open("rb") as fh:
        de_off, fe_off, data_off, de_cnt = _cabecera(fh)
        fh.seek(de_off)
        dirs = fh.read(de_cnt * _DIR)
        if len(dirs) != de_cnt * _DIR:
            raise ValueError("tabla de directorios truncada")
        salida: list[EntradaFa] = []
        for i in range(de_cnt):
            n = struct.unpack_from("<H", dirs, i * _DIR + 4)[0]
            primero = struct.unpack_from("<I", dirs, i * _DIR + 12)[0]
            if not n:
                continue
            fh.seek(fe_off + primero * _FICHERO)
            bloque = fh.read(n * _FICHERO)
            if len(bloque) != n * _FICHERO:
                raise ValueError("tabla de ficheros truncada")
            for j in range(n):
                off, tam = struct.unpack_from("<II", bloque, j * _FICHERO + 8)
                salida.append(EntradaFa(fe_off + (primero + j) * _FICHERO, off, tam))
    return data_off, salida


def _copiar(src, dst, tamano: int, h=None) -> None:
    restante = tamano
    while restante:
        trozo = src.read(min(_BLOQUE, restante))
        if not trozo:
            raise ValueError("el contenedor acaba antes que una de sus entradas")
        if h is not None:
            h.update(trozo)
        dst.write(trozo)
        restante -= len(trozo)


def _hash_rango(fh, inicio: int, tamano: int) -> str:
    h = hashlib.sha256()
    fh.seek(inicio)
    restante = tamano
    while restante:
        trozo = fh.read(min(_BLOQUE, restante))
        if not trozo:
            raise ValueError("el contenedor acaba antes que una de sus entradas")
        h.update(trozo)
        restante -= len(trozo)
    return h.hexdigest()


def huellas_entradas(ruta: str | os.PathLike[str]) -> dict[int, str]:
    """sha256 de los datos de cada entrada, indexado por la posición de su FileEntry."""
    data_off, entradas = leer_entradas(ruta)
    cache: dict[tuple[int, int], str] = {}
    with Path(ruta).open("rb") as fh:
        for e in entradas:
            clave = (e.offset, e.tamano)
            if clave not in cache:
                cache[clave] = _hash_rango(fh, data_off + e.offset, e.tamano)
    return {e.registro: cache[(e.offset, e.tamano)] for e in entradas}


def compactar_fa(
    origen: str | os.PathLike[str],
    destino: str | os.PathLike[str],
    *,
    verificar: bool = True,
    progreso: Callable[[int, int], None] | None = None,
) -> InformeCompactacion:
    """Escribe en ``destino`` el contenedor ``origen`` sin datos huérfanos.

    Con ``verificar`` vuelve a leer ``destino`` y exige que cada entrada devuelva el mismo
    sha256 que en ``origen``; si no, borra ``destino`` y lanza ``ValueError``.
    ``progreso(hechos, total)`` se llama tras copiar cada bloque de datos.
    """
    origen, destino = Path(origen), Path(destino)
    if origen.resolve() == destino.resolve():
        raise ValueError("origen y destino no pueden ser el mismo fichero")
    data_off, entradas = leer_entradas(origen)
    unicos = sorted({(e.offset, e.tamano) for e in entradas})
    antes: dict[tuple[int, int], str] = {}
    nuevo: dict[tuple[int, int], int] = {}

    destino.parent.mkdir(parents=True, exist_ok=True)
    try:
        with origen.open("rb") as src, destino.open("wb") as dst:
            src.seek(0)
            _copiar(src, dst, data_off)
            for i, (off, tam) in enumerate(unicos, 1):
                dst.write(bytes((-dst.tell()) % _ALINEADO))
                rel = dst.tell() - data_off
                if rel > 0xFFFFFFFF:
                    raise ValueError("el contenedor compactado no cabe en desplazamientos de 32 bits")
                nuevo[(off, tam)] = rel
                src.seek(data_off + off)
                h = hashlib.sha256()
                _copiar(src, dst, tam, h)
                antes[(off, tam)] = h.hexdigest()
                if progreso is not None:
                    progreso(i, len(unicos))
            dst.flush()
            for e in entradas:
                dst.seek(e.registro + 8)
                dst.write(struct.pack("<II", nuevo[(e.offset, e.tamano)], e.tamano))

        verificadas = 0
        if verificar:
            esperado = {e.registro: antes[(e.offset, e.tamano)] for e in entradas}
            obtenido = huellas_entradas(destino)
            if obtenido != esperado:
                malas = [hex(r) for r in esperado if obtenido.get(r) != esperado[r]]
                raise ValueError(f"{len(malas)} entradas no coinciden tras compactar: {malas[:5]}")
            verificadas = len(obtenido)
    except BaseException:
        destino.unlink(missing_ok=True)
        raise

    return InformeCompactacion(
        origen_bytes=origen.stat().st_size,
        destino_bytes=destino.stat().st_size,
        entradas=len(entradas),
        bloques_unicos=len(unicos),
        verificadas=verificadas,
    )
