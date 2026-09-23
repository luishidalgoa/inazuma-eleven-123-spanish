"""PackNum tipo 0 IE3: conservar compresión por entrada y cabecera opaca."""

import struct

from ie123kit.ie3.comun.ssd import parse_flat_text, parse_ssd
from ie123kit.ie3.comun.text import TextTable
from ie123kit.nucleo.compresion import lz10
from ie123kit.nucleo.eventos import packnum


def leer_paquete(pkh: bytes, pkb: bytes, kind: str):
    if len(pkh) < 48 or pkh[:7] != b"PackNum":
        raise ValueError("PackNum: cabecera/índice inválido")
    if struct.unpack_from("<H", pkh, 0x12)[0] != 0:
        raise ValueError("PackNum: solo tabla tipo 0 auditada")
    if struct.unpack_from("<H", pkh, 0x10)[0] != len(pkh):
        raise ValueError("PackNum: longitud del índice no coincide")
    alignment = struct.unpack_from("<I", pkh, 0x18)[0]
    if alignment != 16:
        raise ValueError("PackNum: alineamiento distinto de la variante auditada")
    count = struct.unpack_from("<H", pkh, 0x16)[0]
    end = 48 + count * 12
    tail = pkh[end:]
    if end > len(pkh) or len(tail) not in (0, 4, 8, 12) or tail != b"\xff" * len(tail):
        raise ValueError("PackNum: cola/centinela no canónico")
    entries = packnum.parse_index(pkh[:end])
    blocks, metadata = {}, {}
    previous_end = 0
    previous_id = -1
    for eid, offset, size in entries:
        if (
            eid == 0xFFFFFFFF
            or eid in blocks
            or offset % alignment
            or offset < previous_end
            or (size == 0 and kind != "evet")
            or offset + size > len(pkb)
        ):
            raise ValueError(f"PackNum: entrada inválida {eid}")
        if eid <= previous_id:
            raise ValueError("PackNum: IDs no ordenados para búsqueda binaria")
        stored = pkb[offset : offset + size]
        candidates = []
        for compressed in (False, True):
            if compressed and not stored.startswith(b"\x10"):
                continue
            try:
                body = lz10.decompress(stored) if compressed else stored
                if kind == "eve":
                    parse_ssd(body, TextTable.identity())
                elif kind == "evet":
                    records = parse_flat_text(body, TextTable.identity())
                    if any(
                        r.size < 8 or r.size % 4 or b"\0" not in body[r.offset + 4 : r.offset + r.size] for r in records
                    ):
                        raise ValueError("registro evet inválido")
                else:
                    raise ValueError("tipo de recurso no soportado")
                candidates.append((body, compressed))
            except (ValueError, RuntimeError, IndexError, struct.error, AssertionError):
                continue
        if len(candidates) != 1:
            raise ValueError(f"PackNum: compresión/formato ambiguo o inválido en {eid}")
        blocks[eid], compressed = candidates[0]
        metadata[eid] = {"offset": offset, "size": size, "compressed": compressed}
        previous_end = offset + size
        previous_id = eid
    return blocks, metadata


def reconstruir_paquete(pkh, pkb, kind, replacements):
    blocks, metadata = leer_paquete(pkh, pkb, kind)
    if set(replacements) - set(blocks):
        raise ValueError("PackNum: evento desconocido")
    changed = {eid: body for eid, body in replacements.items() if body != blocks[eid]}
    if not changed:
        return pkh, pkb, []  # Round-trip literal, incluido padding residual.
    encoded = {eid: lz10.compress(body) if metadata[eid]["compressed"] else body for eid, body in changed.items()}
    for eid, body in changed.items():
        if metadata[eid]["compressed"] and lz10.decompress(encoded[eid]) != body:
            raise ValueError("LZ10: round-trip fallido")
    end = 48 + 12 * len(blocks)
    new_h, new_b, report = packnum.rebuild(pkh[:end], pkb, encoded, comprimir=False, align=16, keep_header_size=False)
    new_h += pkh[end:]
    header = bytearray(new_h)
    maximum = max(size for eid, _, size in packnum.parse_index(new_h) if eid != 0xFFFFFFFF)
    struct.pack_into("<I", header, 0x1C, (maximum + 15) & ~15)
    new_h = bytes(header)
    actual, newmeta = leer_paquete(new_h, new_b, kind)
    for eid, body in blocks.items():
        if actual[eid] != replacements.get(eid, body):
            raise ValueError(f"PackNum: reextracción difiere {eid}")
        if newmeta[eid]["compressed"] != metadata[eid]["compressed"]:
            raise ValueError("PackNum: compresión modificada")
        if eid not in changed:
            old, new = metadata[eid], newmeta[eid]
            if pkb[old["offset"] : old["offset"] + old["size"]] != new_b[new["offset"] : new["offset"] + new["size"]]:
                raise ValueError("PackNum: bloque almacenado ajeno modificado")
    if new_h[:0x1C] + new_h[0x20:0x30] != pkh[:0x1C] + pkh[0x20:0x30] or new_h[end:] != pkh[end:]:
        raise ValueError("PackNum: cabecera opaca/centinela modificado")
    return new_h, new_b, report
