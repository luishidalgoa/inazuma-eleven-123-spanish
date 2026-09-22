"""Literales UI comunes, identidad por GetString EU y consumidores JP auditados.

No escribe ficheros, no amplía ranuras ni modifica instrucciones/punteros.
Las fuentes Spark/Ogre EU se auditan por separado; destino CRO IE3 compartido.
"""
from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass

from ie123kit.ie3.comun.ancho_ventana import direcciones_de_tablas
from ie123kit.ie3.comun.text import TextTable
from ie123kit.nucleo.compresion.blz import decompress
from ie123kit.nucleo.contenedores.exefs import comprobar_hashes, leer
from ie123kit.nucleo.texto.sjis_portador import es_encode

FUENTES_SHA256 = {
    "codigo": "7f9fc4b95464a71ce037dad245df822e79625522d4c4bef27a0f8110177e1311",
    "crs": "744547cda9a631f3d23b512670c5bb7954bd5eb8f1d24b6476e197af3e36f3dc",
    "cro": "8de193fdbd3eeef82a486fbe145186c7b8b5c7c6ed97fda28fc0a314d1551e5c",
    "codetable": "01002d10db8907d29ccfd0f21e5fd138d5498142ff386db579b97ba2d07e8875",
}
FUENTES_OGRE_SHA256 = {
    **FUENTES_SHA256,
    "codigo": "6a2f8b407f4db73bd4c16cb5539e3a889e0de885e9e8f4a770af4812235bd828",
    "crs": "101e0cf3d52eb1cbb17423c148f2d0c880d8e5c572c8e2ce6a3737c9f11cca87",
}
SIMBOLO = b"_ZN2iz8localize9GetStringEi\0"
ANCLAS_JP = {
    0x165D78: "011c8fe2213e00eb",
    0x165D94: "f0108fe2e53d00eb",
    0x1755E8: "0500a0e1632cfaeb050080e0015080e2",
    0x175608: "0f20a0e3f00080e27a2bfaea",
    0x1F9B54: "ba1f8fe2",
    0x1F9B90: "af1f8fe2",
    0x1F9DC8: "b4108fe2",
    0x5EB4C: "102094e5001097e50b60a0e3e33f8fe20400a0e199fd03eb",
    0x5EC08: "142094e5001097e50c60a0e32e3e8fe20400a0e16afd03eb",
    0x165EC4: "ff7f0000",
}
ANCLAS_ES = {
    0x1734DC: "870081e2d436faeb",  # r1=0x12C +0x87 => ID435
    0x1734FC: "6d0fa0e300f020e3cb36faeb",  # ID436
    0x208198: "5d00a0e3a5e3f7eb",
    0x2083BC: "5e00a0e31ce3f7eb",
    0x208344: "6000a0e300f020e339e3f7eb",
    0x627B0: "3a00a0e300f020e31e7afeeb",
    0x62858: "3b00a0e3f579feeb",
}


@dataclass(frozen=True)
class Literal:
    nombre: str
    offset: int
    capacidad: int
    japones: tuple[str, ...]
    fuente_id: int


LITERALES = (
    Literal("menu_titulo", 0x165E80, 12, ("コマンド",), 435),
    Literal("menu_seis_entradas", 0x165E8C, 56,
            ("なかま", "もちもの", "せんじゅつ", "じょうほう", "システム", "セーブ"), 436),
    Literal("nivel_maestro", 0x1F9E44, 12, ("マスター",), 93),
    Literal("nivel_equipo", 0x1F9E54, 16, ("チームレベル",), 94),
    Literal("titulo_equipo", 0x1F9E84, 8, ("称号",), 96),
    Literal("pasion", 0x5EEEC, 12, ("ねっけつ",), 58),
    Literal("amistad", 0x5EEFC, 12, ("ゆうじょう",), 59),
)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def _anclas(data: bytes, anchors: dict[int, str], nombre: str) -> None:
    for offset, value in anchors.items():
        expected = bytes.fromhex(value)
        if data[offset:offset + len(expected)] != expected:
            raise ValueError(f"{nombre}: ancla inesperada {offset:#x}")


def codigo_desde_exefs(exefs: bytes) -> bytes:
    """Lee y descomprime el miembro .code; no parchea ni reconstruye ExeFS."""
    if not comprobar_hashes(exefs):
        raise ValueError("ExeFS: hashes internos incorrectos")
    members = [entry for entry in leer(exefs) if entry[0] == ".code"]
    if len(members) != 1:
        raise ValueError("ExeFS debe contener exactamente un .code")
    _, offset, size = members[0]
    return decompress(exefs[0x200 + offset:0x200 + offset + size])


def _leer_id(codigo: bytes, table: TextTable, ident: int, count: int = 1) -> tuple[str, ...]:
    if not 0 <= ident < 864:
        raise ValueError("GetString: ID fuera de rango")
    table_offset = _u32(codigo, 0x7AFE0) - 0x100000
    pointer = _u32(codigo, table_offset + ident * 4) - 0x100000
    result = []
    for _ in range(count):
        if not 0 <= pointer < len(codigo):
            raise ValueError("GetString: puntero fuera de .code")
        end = codigo.find(b"\0", pointer, pointer + 4096)
        if end < 0:
            raise ValueError("GetString: literal sin NUL")
        result.append(table.decode(codigo[pointer:end], errors="strict"))
        pointer = end + 1
    return tuple(result)


def extraer_fuente_programa(codigo: bytes, crs: bytes, cro: bytes,
                           codetable: bytes) -> tuple[dict[int, tuple[str, ...]], dict]:
    """Fuente certificada por hash, símbolo import/export y consumidores concretos."""
    sources = {"codigo": codigo, "crs": crs, "cro": cro, "codetable": codetable}
    hashes = {name: _sha(data) for name, data in sources.items()}
    profile = "ogre" if hashes["codigo"] == FUENTES_OGRE_SHA256["codigo"] else "spark"
    expected_hashes = FUENTES_OGRE_SHA256 if profile == "ogre" else FUENTES_SHA256
    for name, digest in hashes.items():
        if digest != expected_hashes[name]:
            raise ValueError(f"fuente oficial {profile} EU inesperada: {name}")
    _anclas(cro, ANCLAS_ES, "CRO EU")
    if (struct.unpack_from("<II", cro, 0x2ECA70) != (0x2F1EA8, 0x2E653C)
            or cro[0x2F1EA8:0x2F1EA8 + len(SIMBOLO)] != SIMBOLO
            or cro[0x1038:0x1040] != bytes.fromhex("04f01fe500000000")
            or cro[0x2E653C:0x2E6548] != bytes.fromhex("c0eb00000201000000000000")
            or struct.unpack_from("<II", crs, 0x16EC) != (0xACB1, 0x7AF840)
            or crs[0xACB1:0xACB1 + len(SIMBOLO)] != SIMBOLO
            or _u32(codigo, 0x7AFE0) != 0x2B4A18
            or codigo[0x7AFCC:0x7AFD0] != bytes.fromhex("040192e7")):
        raise ValueError("cadena import/export/GetString no coincide")
    table = TextTable.from_codetable(codetable)
    result = {lit.fuente_id: _leer_id(codigo, table, lit.fuente_id, len(lit.japones))
              for lit in LITERALES}
    result[60] = _leer_id(codigo, table, 60)
    return result, {"profile": profile + "_eu_common_ui", "sha256": hashes,
                    "getstring_code_offset": 0x7AF84, "table_code_offset": 0x1B4A18,
                    "identity": "equivalent consumer + GetString ID + import/export chain"}


def _contenido(texts: tuple[str, ...], capacidad: int) -> bytes:
    # Encode without budget first: never ask the legacy encoder to truncate.
    payload = b"".join(es_encode(text, 1 << 30) + b"\0" for text in texts)
    if len(payload) > capacidad:
        raise ValueError(f"literal completo no cabe: {len(payload)} > {capacidad}")
    return payload.ljust(capacidad, b"\0")


def _aplicar(cro: bytes, fuente: dict[int, tuple[str, ...]]) -> tuple[bytes, dict]:
    if cro[0x80:0x84] != b"CRO0":
        raise ValueError("destino no es CRO0")
    _anclas(cro, ANCLAS_JP, "CRO JP")
    relocations = direcciones_de_tablas(cro)
    pending = []
    for lit in LITERALES:
        start, end = lit.offset, lit.offset + lit.capacidad
        if any(start < location + 4 and location < end for location in relocations):
            raise ValueError(f"{lit.nombre}: rango intersecta relocación")
        original = b"".join(text.encode("shift_jis") + b"\0" for text in lit.japones)
        original = original.ljust(lit.capacidad, b"\0")
        texts = fuente[lit.fuente_id]
        if len(texts) != len(lit.japones) or any(not text or "\0" in text for text in texts):
            raise ValueError(f"{lit.nombre}: número/contenido de cadenas inesperado")
        desired = _contenido(texts, lit.capacidad)
        if cro[start:end] not in (original, desired):
            raise ValueError(f"{lit.nombre}: literal JP/padding inesperado")
        pending.append((lit, desired, cro[start:end] == desired))
    output = bytearray(cro)
    records = []
    for lit, payload, already in pending:
        output[lit.offset:lit.offset + lit.capacidad] = payload
        if output[lit.offset:lit.offset + lit.capacidad] != payload:
            raise AssertionError("roundtrip literal distinto")
        records.append({"field": lit.nombre, "offset": lit.offset,
                        "capacity": lit.capacidad, "source_id": lit.fuente_id,
                        "labels": len(lit.japones), "already_applied": already,
                        "source_texts": list(fuente[lit.fuente_id])})
    if len(output) != len(cro):
        raise AssertionError("CRO cambió de tamaño")
    return bytes(output), {"status": "pending_visual_validation", "blocks": records,
                           "labels": sum(len(lit.japones) for lit in LITERALES),
                           "modified_blocks": sum(not row[2] for row in pending),
                           "size_preserved": True, "roundtrip_official_exact": True,
                           "pending": [{"field": "contador_jugadores", "source_id": 60,
                                        "source_texts": list(fuente[60]), "offset": 0x1F9E70,
                                        "capacity": 8, "reason": "official_text_does_not_fit"}]}


def parchear_literales_ie3(cro_actual: bytes, codigo_es: bytes, crs_es: bytes,
                          cro_es: bytes, codetable_es: bytes) -> tuple[bytes, dict]:
    """Compone 7 bloques (12 etiquetas) sin exigir hash global del CRO actual."""
    source, proof = extraer_fuente_programa(codigo_es, crs_es, cro_es, codetable_es)
    output, report = _aplicar(cro_actual, source)
    report["source_proof"] = proof
    report["before_sha256"] = _sha(cro_actual)
    report["after_sha256"] = _sha(output)
    return output, report
