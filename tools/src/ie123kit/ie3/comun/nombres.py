"""Localización conservadora de nombres cortos de hablante de IE3.

La tabla JP y la oficial ES conservan el orden físico, pero el identificador
interno de cada ficha puede variar. Por eso se exige igualdad de todos los
campos no textuales antes de copiar un nombre; jamás se empareja solo por ID.
"""
from __future__ import annotations

from ie123kit.ie3.comun.text import TextTable
from ie123kit.nucleo.texto import sjis_portador

HEADER = 0x60
RECORD_SIZE = 0x68
SHORT_OFFSET = 0x24
SHORT_SIZE = 16

def _field(record: bytes, offset: int, size: int) -> bytes:
    return record[offset:offset + size].split(b"\0", 1)[0]


def _compatible(japanese: bytes, european: bytes) -> bool:
    """Los únicos cambios permitidos son id local, nombre largo y corto."""
    return japanese[:6] == european[:6] and japanese[0x34:] == european[0x34:]


def _encode_target(text: str) -> bytes | None:
    """Codifica sin fallback: un '?' solo se admite si ya era literal."""
    carrier = text.translate(sjis_portador.GREEK)
    try:
        carrier.encode("shift-jis")
    except UnicodeEncodeError:
        return None
    return sjis_portador.es_encode(text, 1 << 20)


def caracteres_cortos(japanese: bytes, european: bytes,
                      european_table: TextTable) -> set[str]:
    """Caracteres visibles de nombres oficiales compatibles y codificables."""
    if len(japanese) != len(european) or len(japanese) < HEADER:
        raise ValueError("unitbase IE3 no tiene el tamaño esperado frente a la referencia ES")
    count = (len(japanese) - HEADER) // RECORD_SIZE
    caracteres: set[str] = set()
    for index in range(count):
        offset = HEADER + index * RECORD_SIZE
        jp = japanese[offset:offset + RECORD_SIZE]
        es = european[offset:offset + RECORD_SIZE]
        if not _compatible(jp, es):
            continue
        target_raw = _field(es, SHORT_OFFSET, SHORT_SIZE)
        if not target_raw:
            continue
        target = european_table.decode(target_raw)
        encoded = _encode_target(target)
        if encoded is not None and len(encoded) < SHORT_SIZE:
            caracteres.update(
                ch for ch in target
                if ch.isascii() or ch.translate(sjis_portador.GREEK) != ch
            )
    return caracteres


def localizar_cortos(japanese: bytes, european: bytes,
                     european_table: TextTable) -> tuple[bytes, dict]:
    """Devuelve la tabla JP con nombres cortos oficiales que caben.

    ``european_table`` decodifica los slots de `CodeTable.bin` de la versión ES.
    El informe enumera tanto omisiones seguras como entradas aplicadas.
    """
    if len(japanese) != len(european) or len(japanese) < HEADER:
        raise ValueError("unitbase IE3 no tiene el tamaño esperado frente a la referencia ES")
    count = (len(japanese) - HEADER) // RECORD_SIZE
    out = bytearray(japanese)
    applied = skipped_structure = skipped_empty = skipped_encoding = skipped_size = 0
    entries = []
    for index in range(count):
        offset = HEADER + index * RECORD_SIZE
        jp = japanese[offset:offset + RECORD_SIZE]
        es = european[offset:offset + RECORD_SIZE]
        if not _compatible(jp, es):
            skipped_structure += 1
            continue
        source = _field(jp, SHORT_OFFSET, SHORT_SIZE)
        target_raw = _field(es, SHORT_OFFSET, SHORT_SIZE)
        if not source or not target_raw:
            skipped_empty += 1
            continue
        target = european_table.decode(target_raw)
        encoded = _encode_target(target)
        if encoded is None:
            skipped_encoding += 1
            continue
        if len(encoded) >= SHORT_SIZE:
            skipped_size += 1
            continue
        if source == encoded:
            continue
        out[offset + SHORT_OFFSET:offset + SHORT_OFFSET + SHORT_SIZE] = encoded.ljust(SHORT_SIZE, b"\0")
        applied += 1
        entries.append({"record": index, "speaker_id": int.from_bytes(jp[0x56:0x58], "little"), "name": target})
    return bytes(out), {
        "records_examined": count,
        "applied": applied,
        "skipped_structure": skipped_structure,
        "skipped_empty": skipped_empty,
        "skipped_encoding": skipped_encoding,
        "skipped_size": skipped_size,
        "characters": len(caracteres_cortos(japanese, european, european_table)),
        "entries": entries,
    }
