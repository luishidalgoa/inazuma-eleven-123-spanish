"""Consumidores IE3 0x301D: referencias @offset,longitud a evet.

Los operandos tipo3 se enlazan por (ID instrucción, slot físico) de la tabla
SSD, no por buscar enteros que parezcan offsets. Evidencia: CRO JP 4F05C,
164814 y 161B24; véase docs/IE3_FASE2_REFERENCIAS.md.
"""

import re
import struct
from dataclasses import dataclass
from itertools import pairwise

from ie123kit.ie3.comun.ssd import parse_flat_text, parse_ssd
from ie123kit.ie3.comun.text import TextTable

REFERENCIA = re.compile(rb"@([0-9]+),([0-9]+)\Z")


@dataclass(frozen=True)
class Instruccion:
    ident: int
    opcode: int
    offset: int
    tipos: tuple[int, ...]
    valores: tuple[int, ...]
    slots: tuple[int, ...]


@dataclass(frozen=True)
class Referencia:
    instruccion: Instruccion
    texto_ssd: int
    inicio: int
    longitud: int
    registros: tuple[int, ...]


def instrucciones(data):
    """Instrucciones con slots físicos que realmente enlaza el cargador v3."""
    count, texts = struct.unpack_from("<hh", data, 12)
    if count < 0 or texts < 0:
        raise ValueError("SSD: contador signed16 negativo")
    end = 32 + struct.unpack_from("<I", data, 16)[0]
    pos, result, seen = 32, [], set()
    while pos < end:
        ident, size, opcode, argc, _flags = struct.unpack_from("<HHHBB", data, pos)
        words = (argc + 7) // 8
        if argc > 32 or size != 8 + 4 * words + 4 * argc or pos + size > end:
            raise ValueError(f"instrucción {ident}: tamaño/argc no soportado")
        if ident in seen:
            raise ValueError(f"ID instrucción duplicado: {ident}")
        seen.add(ident)
        types = tuple((data[pos + 8 + i // 2] >> (4 * (i % 2))) & 15 for i in range(argc))
        values = struct.unpack_from(f"<{argc}I", data, pos + 8 + 4 * words)
        result.append(Instruccion(ident, opcode, pos, types, values, tuple(words + i for i in range(argc))))
        pos += size
    if pos != end or len(result) != count:
        raise ValueError("SSD: cuenta de instrucciones incoherente")
    return result


def leer_referencias(ssd: bytes, evet: bytes | None):
    info, texts = parse_ssd(ssd, TextTable.identity())
    if info["version"] != 0x30001:
        raise ValueError("SSD: versión diferente del consumidor auditado")
    if len(texts) != struct.unpack_from("<H", ssd, 14)[0]:
        raise ValueError("SSD: cuenta de textos incoherente")
    instructions = instrucciones(ssd)
    owners = {}
    for index, text in enumerate(texts):
        if text.size < 8 or text.size % 4:
            raise ValueError("SSD: registro no alineado")
        if text.key in owners:
            raise ValueError(f"SSD: propietario de texto duplicado: {text.key}")
        owners[text.key] = index
    records = [] if evet is None else parse_flat_text(evet, TextTable.identity())
    boundaries = {r.offset: i for i, r in enumerate(records)}
    if evet is not None:
        boundaries[len(evet)] = len(records)
    for r in records:
        if r.size < 8 or r.size % 4 or b"\0" not in evet[r.offset + 4 : r.offset + r.size]:
            raise ValueError(f"evet: registro no alineado/sin NUL en {r.offset}")
    refs, inline = [], []
    handled = set()
    for ins in instructions:
        if ins.opcode != 0x301D:
            continue
        if not ins.tipos or ins.tipos[0] != 3:
            raise ValueError(f"301D {ins.ident}: primer operando no es texto")
        indices = []
        for kind, slot in zip(ins.tipos, ins.slots):
            if kind == 3:
                key = (ins.ident, slot)
                if key not in owners:
                    raise ValueError(f"SSD: falta enlace {key}")
                indices.append(owners[key])
        idx = indices[0]
        raw = texts[idx].raw
        if not raw.startswith(b"@"):
            inline.append({"instruction": ins.ident, "ssd_index": idx, "text": texts[idx].text})
            continue
        match = REFERENCIA.fullmatch(raw)
        if not match:
            raise ValueError(f"301D {ins.ident}: sintaxis @ no soportada")
        text = texts[idx]
        end = text.offset + text.size
        # El compilador oficial permite @ sin NUL cuando ocupa exactamente el
        # registro. El parser decimal acaba en el primer no-dígito; el loader
        # enlaza un puntero directo, sin añadir un terminador implícito.
        if b"\0" not in ssd[text.offset + 4 : end] and (end >= len(ssd) or 0x30 <= ssd[end] <= 0x39):
            raise ValueError(f"301D {ins.ident}: referencia sin terminador decimal seguro")
        start, length = map(int, match.groups())
        if max(start, length, start + length) > 0x7FFFFFFF or length > 1024 or length == 0:
            raise ValueError(f"301D {ins.ident}: lectura fuera de límites del consumidor")
        if start not in boundaries or start + length not in boundaries:
            raise ValueError(f"301D {ins.ident}: @ fuera de límites de registro/recurso ausente")
        first, last = boundaries[start], boundaries[start + length]
        if last - first != len(indices):
            raise ValueError(f"301D {ins.ident}: registros != operandos tipo3")
        refs.append(Referencia(ins, idx, start, length, tuple(range(first, last))))
        handled.add(idx)
    # No mover texto que pudiera tener un consumidor @ todavía desconocido.
    unknown = [i for i, t in enumerate(texts) if REFERENCIA.fullmatch(t.raw) and i not in handled]
    if unknown:
        raise ValueError(f"referencias @ con consumidor no auditado: {unknown[:5]}")
    ordered = sorted(refs, key=lambda r: r.inicio)
    for a, b in pairwise(ordered):
        if b.inicio < a.inicio + a.longitud and (a.inicio, a.longitud) != (b.inicio, b.longitud):
            raise ValueError("tramos de consumidores parcialmente solapados")
    return refs, inline, records, texts, info


def sustituir_tabla(ssd: bytes, changes: dict[int, bytes]) -> bytes:
    """Misma sección de código, mismo orden/identidad, padding no tocado literal."""
    info, records = parse_ssd(ssd, TextTable.identity())
    if set(changes) - set(range(len(records))):
        raise ValueError("índice SSD desconocido")
    table = bytearray()
    for index, r in enumerate(records):
        body = changes.get(index, r.raw)
        if body == r.raw:
            table.extend(ssd[r.offset : r.offset + r.size])
            continue
        size = (len(body) + 8) & ~3
        if b"\0" in body or size > 252:
            raise ValueError("cuerpo SSD no representable")
        table.extend(struct.pack("<HBB", r.instruction, r.argument, size) + body + bytes(size - 4 - len(body)))
    result = bytearray(ssd[: 32 + info["code_len"]]) + table
    struct.pack_into("<I", result, 8, len(result))
    struct.pack_into("<I", result, 20, len(table))
    return bytes(result)


def reconstruir_evento(ssd: bytes, evet: bytes, replacements: dict[int, bytes]):
    """Crece solo cuerpos principales explícitos; conserva los secundarios.

    Claves: offsets originales de cabecera del mensaje, no índices físicos nuevos.
    Retorna SSD, evet y mapa completo de cada registro original a reconstruido.
    Los cuerpos llegan codificados y validados por la capa de contenido.
    """
    refs, _, records, _, info = leer_referencias(ssd, evet)
    heads = {r.inicio for r in refs}
    if set(replacements) - heads:
        raise ValueError("reemplazo no corresponde a una cabeza referenciada")
    result = bytearray()
    mapping = {}
    trace = []
    for r in records:
        mapping[r.offset] = len(result)
        body = replacements.get(r.offset, r.raw)
        if body == r.raw:
            output = evet[r.offset : r.offset + r.size]
        else:
            size = max(r.size, (len(body) + 8) & ~3)
            if b"\0" in body or size > 252:
                raise ValueError("registro principal supera u8 o contiene NUL")
            output = struct.pack("<HBB", r.instruction, r.argument, size) + body + bytes(size - 4 - len(body))
        result.extend(output)
        trace.append(
            {
                "old_offset": r.offset,
                "new_offset": mapping[r.offset],
                "old_size": r.size,
                "new_size": len(output),
                "changed": body != r.raw,
            }
        )
    mapping[len(evet)] = len(result)
    changes = {}
    for ref in refs:
        start = mapping[ref.inicio]
        length = mapping[ref.inicio + ref.longitud] - start
        if length > 1024:
            raise ValueError("grupo reconstruido supera buffer de 1024 bytes")
        if (start, length) != (ref.inicio, ref.longitud):
            changes[ref.texto_ssd] = f"@{start},{length}".encode("ascii")
    rebuilt = sustituir_tabla(ssd, changes)
    if rebuilt[32 : 32 + info["code_len"]] != ssd[32 : 32 + info["code_len"]]:
        raise ValueError("código SSD modificado")
    check, _, out_records, _, _ = leer_referencias(rebuilt, bytes(result))
    if len(check) != len(refs) or len(out_records) != len(records):
        raise ValueError("identidad de referencias/registros modificada")
    return rebuilt, bytes(result), {"records": trace, "references_changed": len(changes)}
