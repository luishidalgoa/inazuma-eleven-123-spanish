"""Lectura y escritura por flujo de un ``archive.fa`` (B123) sin cargarlo entero en memoria.

``FaArchive`` (fa.py) lee el fichero completo (1,6 GB el instalado, 2,9 GB la candidata). Este módulo solo lee las
tablas (unos MB) y accede a cada entrada con ``seek``; la escritura sigue el modelo de ``reemplazar_entrada``: la
carga nueva se ANEXA al final alineada a 16 B y se reapunta el FileEntry (``offset`` relativo a los datos y
``tamaño``). No toca nada más del contenedor, de modo que solo cambian esos 8 B por entrada y el final del fichero.

Las rutas son las de ``FaArchive.index`` (``inazuma1/data_iz/logic/usearch.dat``).
"""
from __future__ import annotations

import struct
from pathlib import Path
from typing import Self

__all__ = ["FaFlujo", "comparar_archives", "reemplazar_en_disco"]

MAGICOS = (b"B123", b"ARC0", b"XFSA")


class FaFlujo:
    """Índice de un archive.fa y lectura por entrada; usar como gestor de contexto."""

    def __init__(self, ruta):
        self.ruta = Path(ruta)
        self._fh = self.ruta.open("rb")
        cabecera = self._fh.read(0x40)
        if cabecera[:4] not in MAGICOS:
            self._fh.close()
            raise ValueError(f"Magic no soportado: {cabecera[:4]!r}")
        self.off_dirs, _, self.off_ficheros, self.off_nombres, self.off_datos = struct.unpack_from("<5i", cabecera, 4)
        n_dirs = struct.unpack_from("<H", cabecera, 24)[0]
        n_ficheros = struct.unpack_from("<I", cabecera, 28)[0]
        self._fh.seek(self.off_dirs)
        dirs = self._fh.read(n_dirs * 24)
        self._fh.seek(self.off_ficheros)
        ficheros = self._fh.read(n_ficheros * 16)
        self._fh.seek(self.off_nombres)
        nombres = self._fh.read(self.off_datos - self.off_nombres)

        def nombre(base: int) -> str:
            return nombres[base:nombres.index(b"\0", base)].decode("shift-jis", "replace")

        #: ruta -> (índice de FileEntry, offset relativo a los datos, tamaño)
        self.entradas: dict[str, tuple[int, int, int]] = {}
        for i in range(n_dirs):
            o = i * 24
            cuantos = struct.unpack_from("<H", dirs, o + 4)[0]
            base_nombres, primero = struct.unpack_from("<II", dirs, o + 8)
            nombre_dir = struct.unpack_from("<I", dirs, o + 20)[0]
            carpeta = nombre(nombre_dir)
            for j in range(cuantos):
                indice = primero + j
                _, rel_nombre, rel_datos, tamano = struct.unpack_from("<IIII", ficheros, indice * 16)
                self.entradas[carpeta + nombre(base_nombres + rel_nombre)] = (indice, rel_datos, tamano)

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc) -> None:
        self.cerrar()

    def cerrar(self) -> None:
        if not self._fh.closed:
            self._fh.close()

    def existe(self, ruta: str) -> bool:
        return ruta in self.entradas

    def leer(self, ruta: str) -> bytes:
        try:
            _, rel, tamano = self.entradas[ruta]
        except KeyError:
            raise KeyError(f"entrada ausente en el contenedor: {ruta}") from None
        self._fh.seek(self.off_datos + rel)
        datos = self._fh.read(tamano)
        if len(datos) != tamano:
            raise ValueError(f"lectura incompleta de {ruta}")
        return datos


def reemplazar_en_disco(destino, cambios: dict[str, bytes]) -> None:
    """Anexa cada carga al final de ``destino`` (alineada a 16 B) y reapunta su FileEntry, escribiendo en sitio."""
    with FaFlujo(destino) as fa:
        puntos = {ruta: fa.entradas[ruta][0] for ruta in cambios}
        off_ficheros, off_datos = fa.off_ficheros, fa.off_datos
    with Path(destino).open("r+b") as fh:
        for ruta, datos in cambios.items():
            fh.seek(0, 2)
            fh.write(bytes((-fh.tell()) % 16))
            off = fh.tell()
            fh.write(datos)
            fh.seek(off_ficheros + puntos[ruta] * 16 + 8)
            fh.write(struct.pack("<II", off - off_datos, len(datos)))


def comparar_archives(origen, destino, *, bloque: int = 1 << 24) -> dict:
    """Qué ha cambiado entre dos archive.fa si ``destino`` salió de ``origen`` solo con :func:`reemplazar_en_disco`.

    Devuelve las entradas cuyo (offset, tamaño) difiere, los bytes distintos de la región original que NO son
    FileEntry de esas entradas (deben ser 0), los bytes anexados y si las tablas coinciden. Lee ambos ficheros
    de forma secuencial, sin cargarlos en memoria.
    """
    with FaFlujo(origen) as a, FaFlujo(destino) as b:
        if set(a.entradas) != set(b.entradas):
            return {"mismas_rutas": False}
        distintas = sorted(r for r in a.entradas if a.entradas[r] != b.entradas[r])
        permitidos = [(a.off_ficheros + a.entradas[r][0] * 16 + 8, a.off_ficheros + a.entradas[r][0] * 16 + 16)
                      for r in distintas]
        if any(a.entradas[r][0] != b.entradas[r][0] for r in distintas):
            return {"mismas_rutas": True, "entradas_distintas": distintas, "indices_distintos": True}
    tam_a, tam_b = Path(origen).stat().st_size, Path(destino).stat().st_size
    fuera = 0
    with Path(origen).open("rb") as fa_, Path(destino).open("rb") as fb_:
        pos = 0
        while pos < tam_a:
            x, y = fa_.read(min(bloque, tam_a - pos)), fb_.read(min(bloque, tam_a - pos))
            if x != y:
                for i in range(len(x)):
                    if x[i] != y[i] and not any(ini <= pos + i < fin for ini, fin in permitidos):
                        fuera += 1
            pos += len(x)
    return {
        "mismas_rutas": True,
        "entradas_distintas": distintas,
        "bytes_distintos_fuera_de_filentry": fuera,
        "bytes_anexados": tam_b - tam_a,
        "tamano_origen": tam_a,
        "tamano_destino": tam_b,
    }
