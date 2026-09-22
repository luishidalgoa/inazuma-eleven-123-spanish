"""Revisión de colocación tras capturas fase4, sin modificar ninguna fuente.

Dos trampolines dentro del padding anterior a datos; extensión declarativa del
segmento de código, sin mover secciones, referencias o aumentar el archivo.
"""
from __future__ import annotations

import hashlib
import struct

from ie123kit.ie3.comun.ancho_ventana import direcciones_de_tablas
from ie123kit.ie3.comun.limite_nombre import _salto

REFERENCIA = "29b48d42ddbdf0ac5b06f82b9c61de5804001a8ef7c7e9859ab5605d1df96c06"
ESPACIO = 3
INTERLINEADO = 1
FACTOR_Y = 100
FIN_CODIGO_ANTERIOR = 0x29BF48
# Control del CRO expone un rango semiabierto que TERMINA en29BF48. Conservar
# ese endpoint y sus primeros ocho bytes cero, sin incluirlo en los stubs.
STUB_ESPACIO = 0x29BF50
STUB_MENU = 0x29BF80
FIN = 0x29BFC8
RETORNO_CUERPO = 0x3A9A8
RETORNO_MENU = 0x10B3AC
PRIMER_LITERAL_MENU = 0x165E8C
LONGITUD_LITERALES = 56
LIMITE_MENU = 144


def _ldr_literal(reg, pc, literal):
    delta = literal - (pc + 8)
    if not 0 <= delta < 4096:
        raise ValueError("literal ARM fuera de alcance")
    return 0xE59F0000 | reg << 12 | delta


def instrucciones():
    """Palabras ARM32 y constantes PC-relativas; no direcciones absolutas nuevas."""
    s, m = STUB_ESPACIO, STUB_MENU
    return {
        s: 0xE59DC0BC,                    # ldr ip,[sp,#BC]: retorno guardado
        s+4: 0xE04FC00C,                  # sub ip,pc,ip (ASLR cancela)
        s+8: _ldr_literal(3, s+8, s+44),
        s+12: 0xE15C0003,                 # cmp ip,r3
        s+16: _salto(s+16, s+36, 1),
        s+20: 0xE5D4C000,                 # ldrb ip,[r4]: byte actual SJIS
        s+24: 0xE35C0020,                 # solo espacio ASCII explícito
        s+28: 0x03A03003,                 # moveq r3,#3: colocación, no CWDH
        s+32: 0x058D3048,                 # streq después de overrides de avance
        s+36: 0xE59D2028,                 # instrucción original desplazada
        s+40: _salto(s+40, 0x180E98),
        s+44: s+12-RETORNO_CUERPO,
        m: 0xE59D00C0,                    # texto inicial, no puntero móvil r4
        m+4: 0xE040000F,                  # sub r0,r0,pc
        m+8: _ldr_literal(12, m+8, m+68),
        m+12: 0xE040000C,
        m+16: 0xE3500038,                 # solo seis literales conocidos
        m+20: _salto(m+20, m+64, 2),
        m+24: 0xE59D00C4,
        m+28: 0xE0460000,                 # bytes de comandos ocupados
        m+32: 0xE59DC028,                 # ancho ORIGINAL, no comparando nuevo
        m+36: 0xE59D30CC,                 # altura ORIGINAL
        m+40: 0xE00C039C,                 # mul ip,ip,r3
        m+44: 0xE1A0C0AC,                 # lsr ip,ip,#1 -> capacidad bytes
        m+48: 0xE24CC020,                 # reserva terminador 32 bytes
        m+52: 0xE150000C,
        m+56: _salto(m+56, 0x1811A8, 2),  # fin antes de escribir si lleno
        m+60: 0xE3A02090,                 # solo comparando lógico
        m+64: _salto(m+64, 0x180AB8),      # CMP original y flags para BLE
        m+68: (PRIMER_LITERAL_MENU-(m+12)) & 0xFFFFFFFF,
    }


CAMBIOS = {0x180E94: (0xE59D2028, _salto(0x180E94, STUB_ESPACIO)),
           0x180944: (0x1A00005B, _salto(0x180944, STUB_MENU, 1)),
           0x3A8D4: (0xE3A02003, 0xE3A02001),
           0x3AB70: (0xE3A03073, 0xE3A03064)}


def parchear(cro):
    """Exige fase4 exacta; no reutiliza la salida ni tolera parches parciales."""
    if hashlib.sha256(cro).hexdigest() != REFERENCIA:
        raise ValueError("colocación exige CRO fase4 exacto")
    table, count = struct.unpack_from("<II", cro, 0xC8)
    segments = [struct.unpack_from("<III", cro, table+i*12) for i in range(count)]
    start, size, kind = segments[0]
    if (start, start+size, kind) != (0x180, FIN_CODIGO_ANTERIOR, 0) or segments[1][0] != 0x29C000:
        raise ValueError("segmentación no demuestra padding independiente")
    if any(cro[FIN_CODIGO_ANTERIOR:0x29C000]):
        raise ValueError("padding contiene datos")
    targets = direcciones_de_tablas(cro)
    touched = set(CAMBIOS) | set(instrucciones()) | {table+4}
    if touched & targets or any(STUB_ESPACIO <= x < 0x29C000 for x in targets):
        raise ValueError("destino de relocación intersecta parche")
    for offset in range(start, start+size, 4):
        word = struct.unpack_from("<I", cro, offset)[0]
        if word & 0x0E000000 == 0x0A000000:
            delta = word & 0xFFFFFF
            if delta & 0x800000:
                delta -= 1 << 24
            if STUB_ESPACIO <= offset+8+delta*4 < 0x29C000:
                raise ValueError("entrada previa al padding")
    for header in (0xF8, 0x128, 0x130):
        off, number = struct.unpack_from("<II", cro, header)
        for i in range(number):
            _src, info, target = struct.unpack_from("<III", cro, off+i*12)
            if (info >> 8) & 255 == 0 and STUB_ESPACIO <= start+target < 0x29C000:
                raise ValueError("referencia previa al padding")
    off, number = struct.unpack_from("<II", cro, 0xD0)
    for i in range(number):
        _name, target = struct.unpack_from("<II", cro, off+i*8)
        if target & 15 == 0 and STUB_ESPACIO <= start+(target >> 4) < 0x29C000:
            raise ValueError("exportación al padding")
    out = bytearray(cro)
    for off, (expected, value) in CAMBIOS.items():
        if struct.unpack_from("<I", cro, off)[0] != expected:
            raise ValueError(f"ancla distinta: {off:#x}")
        struct.pack_into("<I", out, off, value)
    for off, value in instrucciones().items():
        struct.pack_into("<I", out, off, value)
    struct.pack_into("<I", out, table+4, FIN-start)
    return bytes(out), {"before_sha256": REFERENCIA,
                        "after_sha256": hashlib.sha256(out).hexdigest(),
                        "word_spacing_body": ESPACIO, "extra_line_spacing": INTERLINEADO,
                        "vertical_factor": FACTOR_Y, "menu_logical_limit": LIMITE_MENU,
                        "menu_guard_actual_capacity": True,
                        "fonts_encoder_boxes_buffers_unchanged": True,
                        "code_segment_end_before": FIN_CODIGO_ANTERIOR, "code_segment_end_after": FIN,
                        "file_size_unchanged": len(out) == len(cro),
                        "patch_offsets": sorted(touched), "runtime_verified": False}
