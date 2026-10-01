"""CIA descifrado de 3DS: contenido 0 (NCCH), su ExeFS y el ``.code`` plano. Solo lectura.

Estructura: cabecera ``<IHHIIIIQ>`` (tamaño de cabecera, tipo, versión, certificados, ticket, TMD, meta,
contenido), cada bloque alineado a 64 B. El contenido 0 es un NCCH: exheader en 0x200 (flag de
compresión del code en exheader+0xD, bit 0) y ExeFS en ``0x1A0``/``0x1A4`` (unidades de 0x200).
Sirve, p. ej., para leer el ``.code`` de una actualización oficial sin herramientas externas.
"""

from __future__ import annotations

import struct

from ie123kit.nucleo.compresion.blz import decompress
from ie123kit.nucleo.contenedores import exefs
from ie123kit.nucleo.errores import FormatoError

__all__ = ["code_plano", "exefs_de_ncch", "ncch_de_cia", "titulo_ncch"]

_MEDIA = 0x200


def _alinear(x: int) -> int:
    return (x + 63) // 64 * 64


def ncch_de_cia(datos: bytes) -> bytes:
    """Bytes del contenido 0 (NCCH) de un CIA descifrado."""
    if len(datos) < 0x20:
        raise FormatoError("cia_corto")
    cab, _tipo, _ver, cert, tik, tmd, _meta, contenido = struct.unpack_from("<IHHIIIIQ", datos, 0)
    inicio = _alinear(cab) + _alinear(cert) + _alinear(tik) + _alinear(tmd)
    ncch = datos[inicio:inicio + contenido]
    if ncch[0x100:0x104] != b"NCCH":
        raise FormatoError("cia_sin_ncch: el contenido 0 no es un NCCH (¿CIA cifrado?)")
    return ncch


def titulo_ncch(ncch: bytes) -> str:
    """ID de programa del NCCH en hexadecimal (16 dígitos)."""
    return f"{struct.unpack_from('<Q', ncch, 0x118)[0]:016X}"


def exefs_de_ncch(ncch: bytes) -> dict[str, bytes]:
    """Ficheros del ExeFS (``.code`` tal cual, comprimido o no) comprobando sus SHA-256."""
    off, tam = struct.unpack_from("<II", ncch, 0x1A0)
    datos = ncch[off * _MEDIA:(off + tam) * _MEDIA]
    if not exefs.comprobar_hashes(datos):
        raise FormatoError("exefs_hash")
    return {n: datos[0x200 + o:0x200 + o + t] for n, o, t in exefs.leer(datos)}


def code_plano(ncch: bytes) -> bytes:
    """``.code`` descomprimido (BLZ) si el exheader lo marca comprimido."""
    code = exefs_de_ncch(ncch)[".code"]
    comprimido = ncch[0x200 + 0xD] & 1
    return decompress(code) if comprimido else code
