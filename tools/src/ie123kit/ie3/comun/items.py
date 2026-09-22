"""Tabla ``item.dat`` de IE3: nombres ofuscados de 44 bytes.

El consumidor 0x178284 indexa la tabla física. La correspondencia exige la
misma fila y una identidad única de metadatos; el módulo no escribe ``[28:44]``.
"""

import hashlib
import json

from ie123kit.ie3.comun.reinsert import _codificable
from ie123kit.ie3.comun.text import TextTable
from ie123kit.nucleo.registros.tabla_fija import RecordTable, TableSpec
from ie123kit.nucleo.texto.sjis_portador import GREEK, avance, es_encode

RECORD_SIZE = 44
NAME_SIZE = 28
RECORD_COUNT = 1024
IDENTITY_END = 42
ITEMS = TableSpec(size=RECORD_SIZE, fields={"name": (0, NAME_SIZE)})


def _ror2(value: int) -> int:
    return ((value >> 2) | ((value & 3) << 6)) & 0xFF


def _rol2(value: int) -> int:
    return ((value << 2) | (value >> 6)) & 0xFF


def _swap_extremes(data: bytearray, width: int) -> None:
    """Intercambia primero/último de cada grupo completo, sin tocar la cola."""
    for start in range(0, len(data) - width + 1, width):
        end = start + width - 1
        data[start], data[end] = data[end], data[start]


def desofuscar_record(record: bytes) -> bytes:
    """Transformación de 0x17DA4C, aplicada a una copia de 44 bytes."""
    if len(record) != RECORD_SIZE:
        raise ValueError("item.dat: registro distinto de 44 bytes")
    result = bytearray(_ror2(value ^ 0xAD) for value in record)
    for width in (3, 5, 7, 2):
        _swap_extremes(result, width)
    return bytes(result)


def ofuscar_record(record: bytes) -> bytes:
    """Inversa literal de :func:`desofuscar_record`."""
    if len(record) != RECORD_SIZE:
        raise ValueError("item.dat: registro distinto de 44 bytes")
    result = bytearray(record)
    for width in (2, 7, 5, 3):
        _swap_extremes(result, width)
    return bytes(_rol2(value) ^ 0xAD for value in result)


def _table(data: bytes) -> RecordTable:
    if len(data) != RECORD_COUNT * RECORD_SIZE:
        raise ValueError("item.dat: esperaba 1024 registros de 44 bytes")
    plain = b"".join(desofuscar_record(data[offset : offset + RECORD_SIZE]) for offset in range(0, len(data), RECORD_SIZE))
    return RecordTable(plain, ITEMS)


def _pool_names(table: RecordTable, text_table: TextTable) -> list[str]:
    names = []
    for index in range(table.count):
        field = table.get(index, "name")
        if b"\0" not in field:
            raise ValueError(f"item.dat: nombre {index} sin terminador NUL")
        names.append(text_table.decode(field.split(b"\0", 1)[0], errors="strict"))
    return names


def _metricas_pool(text: str) -> tuple[int, bool]:
    """Cota de tinta de FONT12: latín aprobado o 14 px conservadores."""
    known = all(char.isascii() or char.translate(GREEK) != char for char in text)
    ink = sum(avance(char) if char.isascii() or char.translate(GREEK) != char else 14 for char in text)
    return ink, known


def _unicos_por_identidad(table: RecordTable) -> dict[bytes, int]:
    """Índice de la identidad icono/tipo/efecto, sin el ID local final."""
    found = {}
    repeated = set()
    plain = table.to_bytes()
    for index in range(table.count):
        key = plain[index * RECORD_SIZE + NAME_SIZE : index * RECORD_SIZE + IDENTITY_END]
        if key in found:
            repeated.add(key)
        else:
            found[key] = index
    return {key: index for key, index in found.items() if key not in repeated}


def construir_items(japanese: bytes, european: bytes, european_table: TextTable) -> tuple[bytes, dict]:
    """Inserta solo nombres ES que mantienen identidad física y metadatos.

    Devuelve bytes ofuscados JP y un informe. Los nombres se vuelven a extraer
    tras ofuscar; una diferencia, incluido cualquier byte de cola, aborta.
    """
    jp = _table(japanese)
    es = _table(european)
    jp_names = _pool_names(jp, TextTable.identity())
    es_names = _pool_names(es, european_table)
    es_by_identity = _unicos_por_identidad(es)
    jp_by_identity = _unicos_por_identidad(jp)
    shared_identities = set(jp_by_identity) & set(es_by_identity)
    out = RecordTable(jp.to_bytes(), ITEMS)
    applied = []
    pending = []
    visible = list(jp_names)
    skipped = {"empty": 0, "identity": 0, "encoding": 0, "size": 0, "already": 0}
    for index, source in enumerate(jp_names):
        jp_record = jp.to_bytes()[index * RECORD_SIZE : (index + 1) * RECORD_SIZE]
        identity = jp_record[NAME_SIZE:IDENTITY_END]
        european_index = es_by_identity.get(identity)
        if jp_by_identity.get(identity) != index or european_index != index:
            skipped["identity"] += 1
            pending.append({"record": index, "reason": "identity", "japanese": source})
            continue
        target = es_names[european_index]
        if not source or not target:
            skipped["empty"] += 1
            pending.append({"record": index, "reason": "empty"})
            continue
        if not _codificable(target):
            skipped["encoding"] += 1
            pending.append({"record": index, "source_record": european_index, "reason": "encoding",
                            "official": target, "unsupported": sorted({c for c in target if not _codificable(c)})})
            continue
        encoded = es_encode(target, 1 << 30)
        if len(encoded) >= NAME_SIZE:
            skipped["size"] += 1
            pending.append({"record": index, "source_record": european_index, "reason": "size",
                            "official": target, "bytes": len(encoded), "capacity": NAME_SIZE - 1})
            continue
        if encoded == jp.get(index, "name").split(b"\0", 1)[0]:
            skipped["already"] += 1
            continue
        out.set_text(index, "name", target, encoder=lambda _text, payload=encoded: payload)
        applied.append({"record": index, "source_record": european_index, "name": target})
        # El payload lleva portadores del FONT v7; para la cota visible se
        # conserva el Unicode oficial que originó esos bytes.
        visible[index] = target

    plain = out.to_bytes()
    payload = b"".join(ofuscar_record(plain[offset : offset + RECORD_SIZE]) for offset in range(0, len(plain), RECORD_SIZE))
    checked = _table(payload)
    for index in range(RECORD_COUNT):
        original = jp.to_bytes()[index * RECORD_SIZE : (index + 1) * RECORD_SIZE]
        before = plain[index * RECORD_SIZE : (index + 1) * RECORD_SIZE]
        after = checked.to_bytes()[index * RECORD_SIZE : (index + 1) * RECORD_SIZE]
        if before != after:
            raise ValueError(f"item.dat: reextracción distinta en registro {index}")
        if after[NAME_SIZE:] != original[NAME_SIZE:]:
            raise ValueError(f"item.dat: cola no textual modificada en registro {index}")
        if index not in {entry["record"] for entry in applied}:
            original_obfuscated = japanese[index * RECORD_SIZE : (index + 1) * RECORD_SIZE]
            if payload[index * RECORD_SIZE : (index + 1) * RECORD_SIZE] != original_obfuscated:
                raise ValueError(f"item.dat: registro no parcheado modificado en {index}")
    pool = []
    for index, text in enumerate(visible):
        raw = checked.get(index, "name").split(b"\0", 1)[0]
        if len(raw) > NAME_SIZE - 1:
            raise ValueError(f"item.dat: nombre {index} supera la cota de 27 bytes")
        ink, known = _metricas_pool(text)
        pool.append({"text": text, "bytes": len(raw), "glyphlen": len(text), "ink": ink, "unicode_known": known})
    pool_blob = json.dumps(pool, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return payload, {
        "records": RECORD_COUNT,
        "applied": applied,
        "skipped": skipped,
        "pending": pending,
        "pool": pool,
        "pool_sha256": hashlib.sha256(pool_blob).hexdigest(),
        "payload_sha256": hashlib.sha256(payload).hexdigest(),
        "pool_max_bytes": max(item["bytes"] for item in pool),
        "pool_max_glyphlen": max(item["glyphlen"] for item in pool),
        "pool_max_ink": max(item["ink"] for item in pool),
        "proof_nontext": {
            "field": "name[0:28]",
            "tail": "[28:44]",
            "identity": "same physical row + metadata[28:42] unique in JP and ES; bytes[42:44] retained from JP",
            "unique_identity_records": len(shared_identities),
            "jp_tail_preserved_records": RECORD_COUNT,
            "unpatched_obfuscated_literal": True,
            "roundtrip_exact": True,
        },
    }
