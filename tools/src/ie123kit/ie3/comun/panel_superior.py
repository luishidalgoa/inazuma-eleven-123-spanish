"""Presentación localizada del panel superior; fuentes y métricas inmutables."""
from __future__ import annotations

import hashlib
import struct

from ie123kit.ie3.comun.ancho_ventana import direcciones_de_tablas

TITULO = 0x1F9D94
ANCLAS_TITULO = {
    0x1F9D8C: 0xE3A02001, TITULO: 0xE3A01003,
    0x1F9D98: 0xE1A00004, 0x1F9D9C: 0xEBFDA57C,
    0x1F9DEC: 0xE1D400BC, 0x1F9DF0: 0xE1D410BE,
    0x1F9DF4: 0xE0010190, 0x1F9DFC: 0xE1A01281,
    0x1F9914: 0xE1D410BC, 0x1F9918: 0xE1D420BE,
    0x1F991C: 0xE0010291, 0x1F9920: 0xE1A02281,
    0x1F992C: 0xE1D400BC, 0x1F9930: 0xE1D410BE,
    0x1F9934: 0xE0000190, 0x1F9938: 0xE0866280,
    0x19F70: 0xE0010791, 0x19F80: 0xE08210C1,
    0x1A608: 0xE59D0068, 0x1A60C: 0xE2871020,
    0x1A610: 0xE1510000, 0x1A614: 0x8A000097,
    0x1A80C: 0xE2877020,
}


def parchear_reserva_titulo(cro: bytes) -> tuple[bytes, dict]:
    """Recupera la reserva europea 6×1, no declara resuelto el recorte visual.

    EU Spark/Ogre 20831C reserva seis tiles; JP 1F9D94 reserva tres. Cada tile
    alberga un comando de 32 B, no un carácter de ancho ocho. La asignación,
    copia y avance del siguiente bloque usan dimensiones dinámicas. El límite
    antes de escribir permanece intacto. La selección UV se audita aparte.
    """
    if len(cro) <= max(ANCLAS_TITULO) + 4 or cro[0x80:0x84] != b"CRO0":
        raise ValueError("CRO inválido para reserva de Título")
    for offset, word in ANCLAS_TITULO.items():
        if struct.unpack_from("<I", cro, offset)[0] != word:
            raise ValueError(f"ancla de reserva Título distinta en {offset:#x}")
    if TITULO in direcciones_de_tablas(cro):
        raise ValueError("la reserva Título intersecta relocación")
    result = bytearray(cro)
    struct.pack_into("<I", result, TITULO, 0xE3A01006)
    output = bytes(result)
    return output, {
        "before_sha256": hashlib.sha256(cro).hexdigest(),
        "after_sha256": hashlib.sha256(output).hexdigest(),
        "patch_offsets": [TITULO], "tiles_before": [3, 1], "tiles_after": [6, 1],
        "command_bytes_before": 96, "command_bytes_after": 192,
        "glyph_capacity_before": 3, "glyph_capacity_after": 6,
        "bounds_check_unchanged": True, "copy_size_dynamic": True,
        "official_eu_instruction": "20831C MOV r1,#6",
        "fonts_metrics_encoder_unchanged": True,
        "visual_rectangle_verified": False, "runtime_verified": False,
    }
