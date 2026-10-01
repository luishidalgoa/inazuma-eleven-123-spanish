"""Paquetes ``*.SPF_`` (firma ``SFP\\0``, casi siempre comprimidos en LZ10).

Formato leído del cargador de IE2 (ina_main2.cro ``0xfacfc -> 0x2020c4``): el juego comprueba la
firma, quita directorios del nombre pedido, lo pasa a mayúsculas y lo busca en la tabla de nombres.

- ``0x0c``: tamaño de bloque (u32) · ``0x10``: base de los datos (u32);
- ``0x20..``: entradas de 16 B ``{offset del nombre, tamaño, bloque, 0}`` hasta el offset del
  primer nombre (la tabla termina donde empiezan las cadenas);
- datos de una entrada = ``base + bloque * tamaño_de_bloque``.

Lo usan los menús de IE2 (``MMName.SPF_``, ``MMProfd.SPF_``: tablas FCODE del teclado). Solo se
admite sustituir una entrada por otra del MISMO tamaño: la tabla de nombres no cambia nunca.
"""

from __future__ import annotations

import struct
from collections.abc import Mapping
from dataclasses import dataclass

from ie123kit.nucleo.compresion import lz10
from ie123kit.nucleo.errores import ValidacionError

__all__ = ["FIRMA", "EntradaSpf", "descomprimir", "empaquetar", "entradas", "leer", "sustituir"]

FIRMA = b"SFP\0"


@dataclass(frozen=True)
class EntradaSpf:
    nombre: str
    offset: int
    tamano: int


def descomprimir(datos: bytes) -> bytes:
    """Contenido SFP de un ``.SPF_`` (LZ10 si empieza por 0x10; si no, tal cual)."""
    plano = lz10.decompress(datos) if datos[:1] == b"\x10" else bytes(datos)
    if plano[:4] != FIRMA:
        raise ValidacionError("spf_sin_firma", detalle=plano[:4].hex())
    return plano


def entradas(plano: bytes) -> dict[str, EntradaSpf]:
    """``{NOMBRE: EntradaSpf}`` de un paquete SFP ya descomprimido."""
    if plano[:4] != FIRMA:
        raise ValidacionError("spf_sin_firma", detalle=plano[:4].hex())
    tam_bloque, base = struct.unpack_from("<II", plano, 0x0C)
    fin = struct.unpack_from("<I", plano, 0x20)[0]
    if fin > len(plano) or fin < 0x20 or (fin - 0x20) % 16:
        raise ValidacionError("spf_tabla_invalida", detalle=hex(fin))
    out: dict[str, EntradaSpf] = {}
    for i in range(0x20, fin, 16):
        n_off, tam, bloque, _ = struct.unpack_from("<4I", plano, i)
        nombre = plano[n_off:plano.index(b"\0", n_off)].decode("ascii")
        offset = base + bloque * tam_bloque
        if offset + tam > len(plano):
            raise ValidacionError("spf_entrada_fuera", detalle=nombre)
        out[nombre] = EntradaSpf(nombre, offset, tam)
    return out


def leer(plano: bytes, nombre: str) -> bytes:
    """Bytes de la entrada ``nombre`` (sin directorios, sin distinguir mayúsculas)."""
    e = entradas(plano)[nombre.replace("\\", "/").rsplit("/", 1)[-1].upper()]
    return bytes(plano[e.offset:e.offset + e.tamano])


def sustituir(plano: bytes, cambios: Mapping[str, bytes]) -> bytes:
    """Copia de ``plano`` con las entradas de ``cambios`` sustituidas (mismo tamaño obligatorio)."""
    tabla = entradas(plano)
    out = bytearray(plano)
    for nombre, datos in cambios.items():
        if nombre not in tabla:
            raise ValidacionError("spf_entrada_ausente", detalle=nombre)
        e = tabla[nombre]
        if len(datos) != e.tamano:
            raise ValidacionError("spf_tamano_distinto", detalle=f"{nombre}: {len(datos)} != {e.tamano}")
        out[e.offset:e.offset + e.tamano] = datos
    return bytes(out)


def empaquetar(plano: bytes) -> bytes:
    """Comprime en LZ10 y comprueba la ida y vuelta."""
    comp = lz10.compress(bytes(plano))
    if lz10.decompress(comp) != bytes(plano):
        raise ValidacionError("spf_lz10_ida_vuelta")
    return comp
