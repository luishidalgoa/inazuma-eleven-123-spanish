"""Parches de código en su sitio sobre una CRO (inmediatos ARM) con comprobación de relocalizaciones.

Porteo del motor de ``work/ie2/shared/capas/menus_cro/ancho_dialogo/apply.py`` (IE2 v15). Un parche
sustituye una palabra de 4 B por otra del mismo tamaño y exige:

- que la palabra de partida sea la esperada (y las palabras de contexto de alrededor);
- que ninguna entrada de las tablas de parches de la CRO (importación 0xF8, relocalización interna
  0x128 y la tabla 0x130; entradas de 12 B que escriben 4 B en su destino) se solape con los bytes
  parcheados: si el cargador reescribiera esa palabra, el parche se perdería;
- que el fichero solo cambie dentro de los parches declarados.

Las direcciones y palabras de cada juego no están aquí (IE2: ``ie123kit.ie2.comun.cro``). No se
reubica ni se recoloca nada: solo inmediatos en su sitio.
"""

from __future__ import annotations

import hashlib
import struct
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from ie123kit.nucleo.errores import ValidacionError

__all__ = ["TABLAS_PARCHES", "Contexto", "ParchePalabra", "aplicar", "comprobar_relocaciones", "tablas_parches"]

#: Tablas de parches de 12 B de la cabecera de una CRO: nombre -> offset de ``(offset, número)``.
TABLAS_PARCHES: Mapping[str, int] = {"importacion_0xF8": 0xF8, "relocacion_interna_0x128": 0x128,
                                     "tabla_0x130": 0x130}


@dataclass(frozen=True)
class ParchePalabra:
    """Sustituye la palabra de ``direccion`` (offset de fichero) ``antes`` -> ``despues``."""

    direccion: int
    antes: int
    despues: int
    texto: str = ""


@dataclass(frozen=True)
class Contexto:
    """Palabra que debe seguir intacta (``palabra=None``: solo se documenta, no se exige)."""

    direccion: int
    palabra: int | None
    texto: str = ""


def _u32(d, o: int) -> int:
    return struct.unpack_from("<I", d, o)[0]


def tablas_parches(d: bytes, tablas: Mapping[str, int] = TABLAS_PARCHES):
    """``({tabla: {offset, entradas, direcciones}}, segmentos)``: dirección de fichero de cada entrada."""
    segs = [struct.unpack_from("<III", d, _u32(d, 0xC8) + 12 * i) for i in range(_u32(d, 0xCC))]
    out = {}
    for nombre, cabecera in tablas.items():
        off, n = _u32(d, cabecera), _u32(d, cabecera + 4)
        dirs = []
        for i in range(n):
            so = _u32(d, off + 12 * i)
            seg = so & 0xF
            if seg >= len(segs):
                continue
            dirs.append(segs[seg][0] + (so >> 4))
        out[nombre] = {"offset": hex(off), "entradas": n, "direcciones": dirs}
    return out, segs


def comprobar_relocaciones(d: bytes, direcciones: Iterable[int], tablas: Mapping[str, int] = TABLAS_PARCHES):
    """``(por dirección {choques, entradas_a_0x80}, resumen de tablas, segmentos)``.

    Una entrada escribe 4 B en su destino ``x``: choca con un parche en ``a`` si ``x-3 <= a <= x+3``.
    """
    tabs, segs = tablas_parches(d, tablas)
    res = {}
    for a in direcciones:
        choques = {}
        for nombre, t in tabs.items():
            c = [hex(x) for x in t["direcciones"] if x - 3 <= a <= x + 3]
            if c:
                choques[nombre] = c
        cerca = sorted({x for t in tabs.values() for x in t["direcciones"] if abs(x - a) <= 0x80})
        res[hex(a)] = {"choques": choques, "entradas_a_0x80": [hex(x) for x in cerca]}
    resumen = {k: {"offset": v["offset"], "entradas": v["entradas"]} for k, v in tabs.items()}
    return res, resumen, [(hex(a), hex(b), c) for a, b, c in segs]


def _desensamblar(palabra: bytes, direccion: int) -> list[str]:
    try:
        from capstone import CS_ARCH_ARM, CS_MODE_ARM, Cs
    except ImportError:  # capstone es dependencia del paquete; sin él solo falta el texto informativo
        return []
    return [f"{i.mnemonic} {i.op_str}" for i in Cs(CS_ARCH_ARM, CS_MODE_ARM).disasm(palabra, direccion)]


def aplicar(cro: bytes, parches: Sequence[ParchePalabra], contexto: Sequence[Contexto] = (),
            tablas: Mapping[str, int] = TABLAS_PARCHES) -> tuple[bytes, dict]:
    """Aplica ``parches`` a ``cro`` y devuelve ``(cro parcheada, informe)``; lanza ValidacionError si algo no cuadra."""
    d = bytearray(cro)
    antes = bytes(d)
    for c in contexto:
        if c.palabra is not None and _u32(d, c.direccion) != c.palabra:
            raise ValidacionError("cro_contexto", detalle=f"{c.direccion:#x}: {_u32(d, c.direccion):#x} != {c.palabra:#x}")
    registro = []
    for p in parches:
        actual = _u32(d, p.direccion)
        if actual != p.antes:
            raise ValidacionError("cro_palabra_inesperada", detalle=f"{p.direccion:#x}: {actual:#x} != {p.antes:#x}")
        struct.pack_into("<I", d, p.direccion, p.despues)
        registro.append({"direccion": hex(p.direccion), "texto": p.texto,
                         "antes": struct.pack("<I", p.antes).hex(), "despues": struct.pack("<I", p.despues).hex(),
                         "desensamblado_despues": _desensamblar(bytes(d[p.direccion:p.direccion + 4]), p.direccion)})
    difs = [i for i in range(len(d)) if d[i] != antes[i]]
    if len(difs) > 4 * len(parches) or not all(any(p.direccion <= i < p.direccion + 4 for p in parches) for i in difs):
        raise ValidacionError("cro_cambios_fuera", detalle=str([hex(i) for i in difs][:12]))
    reloc, resumen, segs = comprobar_relocaciones(antes, [p.direccion for p in parches], tablas)
    choques = {k: v["choques"] for k, v in reloc.items() if v["choques"]}
    if choques:
        raise ValidacionError("cro_relocacion_solapada", detalle=str(choques))
    salida = bytes(d)
    return salida, {"base_sha256": hashlib.sha256(antes).hexdigest(),
                    "salida_sha256": hashlib.sha256(salida).hexdigest(),
                    "bytes_distintos": [hex(i) for i in difs], "parches": registro, "segmentos": segs,
                    "tablas_parches": resumen, "comprobacion_relocacion": reloc}
