"""Rectángulo de selección de hints del menú principal, sin cambiar su buffer."""
from __future__ import annotations

import hashlib
import struct

from ie123kit.ie3.comun.ancho_ventana import direcciones_de_tablas
from ie123kit.ie3.comun.limite_nombre import _salto

HOOK = 0x10AFD8
RETORNO = HOOK + 4
STUB = 0x29BFCC
FIN = STUB + 40
FIN_ANTERIOR = 0x29BFC8
PRIMER_TEXTO = 0x165E8C
ANCHO = 144
ORIGINAL = 0xE6BF3070  # SXTH r3,r0, tras LDR r0,[sp,#14].


def instrucciones():
    return {
        STUB: 0xE595C108,       # LDR ip,[r5,#108]: array de textos del widget.
        STUB + 4: 0xE35C0000,
        STUB + 8: 0x159CC000,   # LDRNE ip,[ip]: primer literal, NULL no se lee.
        STUB + 12: 0xE04CC00F,  # SUB ip,ip,pc: independiente de ASLR.
        STUB + 16: 0xE59F300C,
        STUB + 20: 0xE15C0003,
        STUB + 24: 0x03A00090,  # MOVEQ r0,#144: resto conserva ancho original.
        STUB + 28: ORIGINAL,
        STUB + 32: _salto(STUB + 32, RETORNO),
        STUB + 36: (PRIMER_TEXTO - (STUB + 20)) & 0xFFFFFFFF,
    }


def parchear_rectangulo_menu(cro: bytes) -> tuple[bytes, dict]:
    """Componer después de colocacion_visible, antes de recalcular hashes CRO.

Exige su padding exacto, anclas del constructor y ninguna relocación afectada.
No acepta aplicación parcial, otro constructor ni un segmento ya extendido.
"""
    if len(cro) < 0x29C000 or cro[0x80:0x84] != b"CRO0":
        raise ValueError("CRO inválido para rectángulo del menú")
    table, count = struct.unpack_from("<II", cro, 0xC8)
    if count < 2:
        raise ValueError("segmentación CRO ausente")
    start, size, kind = struct.unpack_from("<III", cro, table)
    next_start = struct.unpack_from("<I", cro, table + 12)[0]
    if (start, start + size, kind, next_start) != (0x180, FIN_ANTERIOR, 0, 0x29C000):
        raise ValueError("requiere colocación terminada exactamente en 29BFC8")
    if any(cro[FIN_ANTERIOR:0x29C000]):
        raise ValueError("padding del rectángulo ocupado")
    anchors = {0x10AFD4: 0xE59D0014, HOOK: ORIGINAL,
               0x10AFDC: 0xE28D0004, 0x10AFE0: 0xE8900006,
               0x10AFE4: 0xE59B0000, 0x10AFE8: 0xEB01DC44,
               0x10B33C: 0xE5942108, 0x10B34C: 0xE7926100}
    for offset, word in anchors.items():
        if struct.unpack_from("<I", cro, offset)[0] != word:
            raise ValueError(f"ancla de rectángulo distinta en {offset:#x}")
    targets = direcciones_de_tablas(cro)
    touched = {HOOK, table + 4, *instrucciones()}
    if touched & targets or any(STUB <= target < 0x29C000 for target in targets):
        raise ValueError("rectángulo intersecta relocación")
    for offset in range(start, FIN_ANTERIOR, 4):
        word = struct.unpack_from("<I", cro, offset)[0]
        if word & 0x0E000000 == 0x0A000000:
            delta = word & 0xFFFFFF
            if delta & 0x800000:
                delta -= 1 << 24
            if STUB <= offset + 8 + delta * 4 < 0x29C000:
                raise ValueError("salto previo hacia el padding del rectángulo")
    output = bytearray(cro)
    struct.pack_into("<I", output, HOOK, _salto(HOOK, STUB))
    for offset, word in instrucciones().items():
        struct.pack_into("<I", output, offset, word)
    struct.pack_into("<I", output, table + 4, FIN - start)
    return bytes(output), {"before_sha256": hashlib.sha256(cro).hexdigest(),
                           "after_sha256": hashlib.sha256(output).hexdigest(),
                           "main_menu_selection_width": ANCHO,
                           "code_end_before": FIN_ANTERIOR, "code_end_after": FIN,
                           "other_lists_original_width": True,
                           "buffer_fonts_scales_buttons_unchanged": True,
                           "patch_offsets": sorted(touched), "runtime_verified": False}
