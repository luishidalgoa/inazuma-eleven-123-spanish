"""Índices de bancos de sonido: ``sound.ph``/``sound.pb`` (3DS) y ``sound.pkh``/``sound.pkb`` (DS).

- 3DS ``sound.ph`` (y su copia ``sound.ph_``): registros de 32 B = nombre 24 B + offset + tamaño en
  ``sound.pb``. Los ficheros van contiguos y en el orden del índice.
- DS ``sound.pkh``: registros de 16 B (hash, offset, tamaño, 0); cada registro de ``sound.pkb`` es una
  tabla (offset, tamaño) de 1-2 ficheros; el nombre va en +0x20 de la cabecera ``sedl``/``swdl``/``smdl``.

Porteo de ``leer_3ds``/``leer_nds`` de ``work/ie2/shared/capas/media/voz_titulo/sonido.py`` y del
montaje de ``sound.pb`` de las capas de voces (IE2 v13/v20/v23), sobre bytes en vez de carpetas.
"""

from __future__ import annotations

import struct
from collections.abc import Iterable, Mapping

__all__ = ["leer_3ds", "leer_nds", "montar_3ds"]

_REG_3DS = 32
_NOMBRE_3DS = 24


def leer_3ds(ph: bytes, pb: bytes) -> list[tuple[str, bytes]]:
    """``[(nombre, bytes)]`` en el orden del índice."""
    out = []
    for i in range(0, len(ph), _REG_3DS):
        nombre = ph[i:i + _NOMBRE_3DS].split(b"\0")[0].decode()
        o, s = struct.unpack_from("<II", ph, i + _NOMBRE_3DS)
        out.append((nombre, pb[o:o + s]))
    return out


def leer_nds(pkh: bytes, pkb: bytes) -> dict[str, bytes]:
    """``{NOMBRE: bytes}`` (en mayúsculas; si se repite un nombre gana el primero)."""
    out: dict[str, bytes] = {}
    for i in range(0, len(pkh), 16):
        _h, o, s, _f = struct.unpack_from("<IIII", pkh, i)
        rec = pkb[o:o + s]
        for k in range(struct.unpack_from("<I", rec, 0)[0] // 8):
            so, ss = struct.unpack_from("<II", rec, 8 * k)
            blob = rec[so:so + ss]
            nombre = blob[0x20:0x30].split(b"\0")[0].split(b"\xff")[0].decode("ascii")
            out.setdefault(nombre.upper(), blob)
    return out


def montar_3ds(entradas: Iterable[tuple[str, bytes]], cambios: Mapping[str, bytes] | None = None) -> tuple[bytes, bytes]:
    """``(sound.pb, sound.ph)`` con las entradas en su orden y ``cambios`` sustituidos por nombre."""
    cambios = cambios or {}
    pb, ph = bytearray(), bytearray()
    for nombre, datos in entradas:
        datos = cambios.get(nombre, datos)
        codificado = nombre.encode("ascii")
        if len(codificado) > _NOMBRE_3DS:
            raise ValueError(f"nombre de más de {_NOMBRE_3DS} B: {nombre}")
        ph += codificado.ljust(_NOMBRE_3DS, b"\0") + struct.pack("<II", len(pb), len(datos))
        pb += datos
    return bytes(pb), bytes(ph)
