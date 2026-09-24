"""Rótulos PAC (sprites DS de 4 bpp, 32 px de alto) de la CIA europea -> forma que espera el ejecutable japonés.

Caso: los nombres de supertécnica de pic3d/script/mbv_c (índice .pkh de 16 B: crc32, desplazamiento, tamaño,
cabecera LZ10 | tamaño descomprimido << 8). El europeo guarda el mapa de bits a otra anchura (128 o 256 px) que la
japonesa y declara en los metadatos un ancho de pantalla distinto del de los datos (su motor escala); a veces con
paleta corta y fondo opaco. El japonés declara siempre ancho = ancho de los datos (meta+2 = log2(ancho/8)) y en
meta+12 el ancho útil, múltiplo de 8 (≈ tinta + 3).

Conversión: ancho de los datos = tamaño·2/alto; meta+2 según ese ancho; paleta de 16 con el fondo en el índice 0;
ancho útil = múltiplo de 8 de (última columna con tinta + 3). Cabecera PAC: 7 u32
(n=3, píxeles, tamaño, paleta, tamaño de paleta, meta, tamaño de meta).
"""
from __future__ import annotations

import struct

from ie123kit.nucleo.compresion import lz10

ALTO_META = 3          # meta+3
ANCHO_META = 2         # meta+2
UTIL_META = 12         # u16


def cabecera(d: bytes) -> dict:
    n, pix, size, pal, ps, meta, ms = struct.unpack_from("<7I", d)
    if n != 3:
        raise ValueError("PAC no soportado")
    return {"pix": pix, "size": size, "pal": pal, "ps": ps, "meta": meta, "ms": ms, "alto": 8 << d[meta + ALTO_META]}


def indices(d: bytes) -> list[int]:
    c = cabecera(d)
    return [(d[c["pix"] + q // 2] >> (4 * (q % 2))) & 15 for q in range(c["size"] * 2)]


def a_forma_japonesa(eu: bytes) -> bytes:
    """PAC europeo (descomprimido) -> PAC japonés (descomprimido)."""
    c = cabecera(eu)
    alto = c["alto"]
    ancho = c["size"] * 2 // alto
    if ancho * alto != c["size"] * 2 or ancho & (ancho - 1) or ancho < 8:
        raise ValueError(f"ancho de datos no válido: {ancho}")
    pal = list(struct.unpack_from(f"<{c['ps'] // 2}H", eu, c["pal"]))
    idx = indices(eu)
    if c["ps"] >= 32:
        fondo, orden = 0, list(range(16))
    else:
        fondo = idx[-1]                       # paleta corta: el fondo es la esquina inferior derecha
        usados = sorted(set(idx) - {fondo})
        if any(u >= len(pal) for u in usados + [fondo]):
            raise ValueError("índice fuera de la paleta")
        orden = [fondo] + usados
    mapa = {v: k for k, v in enumerate(orden)}
    npal = [pal[v] if v < len(pal) else 0 for v in orden] + [0] * (16 - len(orden))
    pix = bytearray(c["size"])
    tinta = 0
    for q, v in enumerate(idx):
        m = mapa.get(v, 0)
        pix[q // 2] |= m << (4 * (q % 2))
        if m:
            tinta = max(tinta, q % ancho + 1)
    util = min(ancho, (tinta + 3 + 7) // 8 * 8)
    meta = bytearray(eu[c["meta"]:c["meta"] + c["ms"]])
    meta[ANCHO_META] = (ancho // 8).bit_length() - 1
    struct.pack_into("<H", meta, UTIL_META, util)
    pal_off = 0x20 + len(pix)
    cab = struct.pack("<8I", 3, 0x20, len(pix), pal_off, 32, pal_off + 32, len(meta), pal_off + 0x10)
    return cab + bytes(pix) + struct.pack("<16H", *npal) + bytes(meta)


def leer_16(pkh: bytes, pkb: bytes) -> list[tuple[int, bytes, int]]:
    """``[(crc, datos guardados, palabra z)]`` de un índice de 16 B."""
    return [(k, pkb[o:o + s], z) for k, o, s, z in (struct.unpack_from("<4I", pkh, i)
                                                    for i in range(0, len(pkh) - 15, 16))]


def reempaquetar_16(pkh: bytes, pkb: bytes, cambios: dict[int, bytes]) -> tuple[bytes, bytes]:
    """Sustituye entradas (``crc -> PAC descomprimido``, se guarda en LZ10) y reconstruye .pkh/.pkb."""
    ent = leer_16(pkh, pkb)
    alin = 4 if all(o % 4 == 0 for _, o, _, _ in (struct.unpack_from("<4I", pkh, i)
                                                   for i in range(0, len(pkh) - 15, 16))) else 1
    nh, nb = bytearray(), bytearray()
    for k, datos, z in ent:
        if k in cambios:
            crudo = cambios[k]
            datos = lz10.compress(crudo)
            if lz10.decompress(datos) != crudo:
                raise ValueError("LZ10: ida y vuelta fallida")
            z = 0x10 | (len(crudo) << 8)
        nb.extend(bytes((-len(nb)) % alin))
        nh += struct.pack("<4I", k, len(nb), len(datos), z)
        nb.extend(datos)
    nb.extend(bytes((-len(nb)) % alin))
    nh += pkh[len(nh):]
    return bytes(nh), bytes(nb)
