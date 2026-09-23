"""Límite de presentación del hablante, sin ampliar su buffer ni tipografía.

Separa el umbral de salto (134) de la capacidad real (512 bytes). El hook solo
reconoce el retorno exacto del llamador de nombres, mediante diferencia de PC,
válida tras reubicar el CRO. Reutiliza código muerto FONT8 de fase 3 y parejas
NOP cuyo flujo normal se desvía al mismo destino original. Ver documentación.
"""

from __future__ import annotations

import hashlib
import struct

from ie123kit.ie3.comun.ancho_ventana import direcciones_de_tablas

CRO_FASE3_SHA256 = "763e5246edece475c23ba27eb1fe35db2861618903a80213b8d470c640cb1c77"
HOOK = 0x180E9C
RETORNO_NOMBRE = 0x160FB8
LIMITE_LOGICO = 134  # 15 glifos lógicos: 14 * (8 + tracking1) + 8
CAPACIDAD_REAL = 512
BYTES_COMANDO = 32
MAX_COMANDOS = 15

ANTES = {
    0x180930: 0xE59D3034, 0x180934: 0xE3530000,
    0x180938: 0x05981000, 0x18093C: 0x0A00000B,
    0x180940: 0xE3530001, 0x180944: 0x05981004,
    0x180948: 0xEA000008, HOOK: 0xE1510002,
    0x180A54: 0xE320F000, 0x180A58: 0xE320F000, 0x180A5C: 0xEA000029,
    0x180A6C: 0xE320F000, 0x180A70: 0xE320F000, 0x180A74: 0xEA000023,
    0x180A84: 0xE320F000, 0x180A88: 0xE320F000, 0x180A8C: 0xEA00001D,
    0x180A9C: 0xE320F000, 0x180AA0: 0xE320F000, 0x180AA4: 0xEA000017,
    0x180AB4: 0xE320F000, 0x180AB8: 0xE320F000, 0x180ABC: 0xEA000011,
}


def _salto(desde: int, hasta: int, condicion: int = 14) -> int:
    delta = hasta - desde - 8
    if delta % 4 or not -(1 << 25) <= delta < (1 << 25):
        raise ValueError("salto ARM fuera de alcance/alineación")
    return (condicion << 28) | 0x0A000000 | ((delta // 4) & 0xFFFFFF)


DESPUES = {
    HOOK: _salto(HOOK, 0x180930),
    0x180930: 0xE59D00BC,  # ldr r0,[sp,#BC]: retorno guardado, no LR transitorio
    0x180934: 0xE04F0000,  # sub r0,pc,r0: la base de relocación se cancela
    0x180938: 0xE2400B7E,  # sub r0,r0,#1F800
    0x18093C: 0xE3500F61,  # cmp r0,#184: PC18093C - retorno160FB8
    0x180940: 0x02822046,  # addeq r2,r2,#70: solo comparando temporal, no sp28
    0x180944: _salto(0x180944, 0x180AB8, 1),  # otros llamadores: CMP original
    0x180948: _salto(0x180948, 0x180A58),
    0x180A54: _salto(0x180A54, 0x180B08),  # color: mismo destino que antes
    0x180A58: 0xE59D00C4,  # base real de comandos
    0x180A5C: _salto(0x180A5C, 0x180A70),
    0x180A6C: _salto(0x180A6C, 0x180B08),
    0x180A70: 0xE0460000,  # sub r0,r6,r0: bytes ocupados reales
    0x180A74: _salto(0x180A74, 0x180A88),
    0x180A84: _salto(0x180A84, 0x180B08),
    0x180A88: 0xE3500E1E,  # cmp r0,#480; reserva un comando para terminador
    0x180A8C: _salto(0x180A8C, 0x180AA0),
    0x180A9C: _salto(0x180A9C, 0x180B08),
    0x180AA0: _salto(0x180AA0, 0x1811A8, 2),  # bhs fin ANTES del dibujo
    0x180AA4: _salto(0x180AA4, 0x180AB8),
    0x180AB4: _salto(0x180AB4, 0x180B08),
    0x180AB8: 0xE1510002,  # cmp r1,r2: flags exactos para BLE original
    0x180ABC: _salto(0x180ABC, 0x180EA0),
}

# Además del fingerprint completo, evidencias locales legibles y fail-closed.
ANCLAS = {
    0x160F80: 0xE3A02040,  # argumento64 y capacidad siguen intactos
    0x160F88: 0xE58D2008,
    0x160FB4: 0xEB007E31,
    0x180880: 0xE92D4FFF, 0x18088C: 0xED2D8B02, 0x180890: 0xE24DD084,
    0x180918: 0x0A000014,  # el antiguo bloque FONT8 ya NO tiene entrada
    0x18092C: 0xEA00000F,
    0x180E94: 0xE59D2028, 0x180E98: 0xE088100B,
    0x180EA0: 0xDA00002C,
    0x181168: 0xE2866020,
    0x1811B4: 0xE0000190,  # MUL capacidad original, no se falsea
    0x1811CC: 0x25860000,
}


def _u32(data, offset):
    return struct.unpack_from("<I", data, offset)[0]


def _validar_sin_entradas(data: bytes) -> dict:
    """Descarta entradas por salto directo, exportación o relocación al stub.

Los únicos flujos normales hacia las parejas NOP son el retorno de la llamada
de color inmediatamente anterior; ahora su primer NOP salta al destino original.
Las tablas de salto mantienen sus entradas al principio de cada caso de color.
"""
    privados = set(range(0x180930, 0x18094C, 4))
    privados.update(x for a in (0x180A54, 0x180A6C, 0x180A84, 0x180A9C, 0x180AB4)
                    for x in (a, a + 4, a + 8))
    segment_offset, count = struct.unpack_from("<II", data, 0xC8)
    segments = [struct.unpack_from("<III", data, segment_offset + 12 * i) for i in range(count)]
    code, size, kind = segments[0]
    if code != 0x180 or kind != 0 or not all(code <= x < code + size for x in privados):
        raise ValueError("stub no está dentro del segmento de código existente")
    for offset in range(code, code + size, 4):
        word = _u32(data, offset)
        if word & 0x0E000000 == 0x0A000000:
            imm = word & 0xFFFFFF
            if imm & 0x800000:
                imm -= 1 << 24
            if offset + 8 + imm * 4 in privados:
                raise ValueError(f"salto preexistente al stub desde {offset:#x}")
    for table in (0xF8, 0x128, 0x130):
        offset, count = struct.unpack_from("<II", data, table)
        for i in range(count):
            _source, info, target = struct.unpack_from("<III", data, offset + 12 * i)
            if (info >> 8) & 255 == 0 and code + target in privados:
                raise ValueError("referencia reubicable preexistente al stub")
    offset, count = struct.unpack_from("<II", data, 0xD0)
    for i in range(count):
        _name, target = struct.unpack_from("<II", data, offset + 8 * i)
        if target & 15 == 0 and code + (target >> 4) in privados:
            raise ValueError("exportación preexistente al stub")
    return {"segment_file_offset": code, "segment_size_unchanged": size,
            "preexisting_direct_relocation_export_entries": 0}


def parchear_limite_nombre(cro: bytes) -> tuple[bytes, dict]:
    """Parche puro e idempotente; requiere fase3 exacta o su propia salida."""
    if len(cro) < 0x181200 or cro[0x80:0x84] != b"CRO0":
        raise ValueError("CRO inválido para límite del nombre")
    original = bytearray(cro)
    for offset, before in ANTES.items():
        actual = _u32(cro, offset)
        if actual not in (before, DESPUES[offset]):
            raise ValueError(f"instrucción del nombre inesperada en {offset:#x}")
        struct.pack_into("<I", original, offset, before)
    if hashlib.sha256(original).hexdigest() != CRO_FASE3_SHA256:
        raise ValueError("CRO no coincide con fase3 exacta")
    is_before = all(_u32(cro, o) == w for o, w in ANTES.items())
    is_after = all(_u32(cro, o) == w for o, w in DESPUES.items())
    if not (is_before or is_after):
        raise ValueError("parche del nombre parcialmente aplicado")
    for offset, word in ANCLAS.items():
        if _u32(cro, offset) != word:
            raise ValueError(f"ancla del nombre distinta en {offset:#x}")
    relocations = direcciones_de_tablas(original)
    if set(ANTES) & relocations:
        raise ValueError("parche del nombre sobre un destino de relocación")
    audit = _validar_sin_entradas(bytes(original))
    output = bytearray(cro)
    for offset, word in DESPUES.items():
        struct.pack_into("<I", output, offset, word)
    result = bytes(output)
    return result, {
        "sha256_before": hashlib.sha256(cro).hexdigest(),
        "sha256_after": hashlib.sha256(result).hexdigest(),
        "reference_sha256": CRO_FASE3_SHA256,
        "patch_words": len(DESPUES), "patch_offsets": sorted(DESPUES),
        "logical_line_limit": LIMITE_LOGICO, "stored_width_unchanged": 64,
        "allocated_command_bytes_unchanged": CAPACIDAD_REAL,
        "max_commands_before_terminator": MAX_COMANDOS,
        "runtime_guard_before_drawing": True,
        "fonts_metrics_tracking_buffers_unchanged": True,
        "caller_return_file_offset": RETORNO_NOMBRE,
        "other_callers_comparison_unchanged": True,
        "color_paths_destination_unchanged": 0x180B08,
        "relocation_targets_checked": len(relocations),
        "dead_code_audit": audit, "already_applied": is_after,
        "runtime_verified": False,
    }
