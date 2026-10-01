"""CBMD (``banner.bnr`` del ExeFS): CGFX común en LZ11 + BCWAV del sonido del menú HOME.

Portado de ``work/shared/capas/graficos/banner_home/cgfx.py`` (``parse_cbmd``/``build_cbmd``) sin
cambios de comportamiento (F2.5, #51). Solo se admite el CBMD sin ranuras regionales, como el de la
recopilación: un CGFX común y el BCWAV al final.
"""
from __future__ import annotations

import struct

__all__ = ["REGIONES", "construir", "leer", "partes"]

REGIONES = ["EUR-EN", "EUR-FR", "EUR-DE", "EUR-IT", "EUR-ES", "EUR-NL", "EUR-PT", "EUR-RU",
            "JPN", "USA-EN", "USA-FR", "USA-ES", "USA-PT"]


def leer(b: bytes) -> tuple[int, list[int], int]:
    """``(offset del CGFX común, [13 offsets regionales], offset del BCWAV)``."""
    if b[:4] != b"CBMD":
        raise ValueError("no es CBMD")
    common = struct.unpack_from("<I", b, 8)[0]
    regional = list(struct.unpack_from("<13I", b, 0x0C))
    cwav = struct.unpack_from("<I", b, 0x84)[0]
    return common, regional, cwav


def partes(b: bytes) -> tuple[bytes, bytes]:
    """``(CGFX común comprimido en LZ11, BCWAV)``; falla si hay ranuras regionales."""
    common, regional, cwav = leer(b)
    if any(regional):
        raise ValueError("el CBMD trae ranuras regionales: no soportado")
    if b[cwav:cwav + 4] != b"CWAV":
        raise ValueError("BCWAV no encontrado")
    return b[common:cwav], b[cwav:]


def construir(cgfx_lz: bytes, cwav: bytes) -> bytes:
    """CBMD con el CGFX común (ya en LZ11) y el BCWAV alineado a 0x20."""
    head = bytearray(0x88)
    head[:4] = b"CBMD"
    struct.pack_into("<I", head, 8, 0x88)
    body = head + cgfx_lz
    while len(body) % 0x20:  # alineación (en el original el CWAV empieza alineado)
        body.append(0)
    struct.pack_into("<I", body, 0x84, len(body))
    return bytes(body) + cwav
