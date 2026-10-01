"""¿Se puede poner un .arc europeo entero en lugar del japonés? (maquetados QNA 051 equivalentes)

Criterio de las capas de gráficos del IE3 (``pendientes_92.compatible``, ``caja_partida_y_avisos``): el código del
juego solo conoce los grupos y las escenas del maquetado; las partes (cajas UV, posiciones, texturas) son datos del
propio .arc. Si cada QNA europeo tiene el mismo número de grupos y las mismas tablas de escenas (C y D) que el
japonés, el .arc europeo entero (texturas de otro tamaño incluidas) sirve en su sitio.

Cabecera QNA 051: ``+8`` cinco contadores (texturas, grupos, partes, C, D) y ``+36`` sus cinco desplazamientos;
C son registros de 32 B y D de 20 B.
"""
from __future__ import annotations

import struct

from ie123kit.nucleo.compresion.sszl import unwrap
from ie123kit.nucleo.contenedores.arcv import entries

__all__ = ["diferencias_maquetado", "escenas", "maquetados"]

_MAGIA = b" QNA 051"


def maquetados(arc: bytes) -> list[bytes]:
    """Blobs QNA del .arc (envuelto en SSZL o no), en orden."""
    crudo = unwrap(bytes(arc))
    salida = []
    for off, tam, _crc in entries(crudo):
        b = crudo[off:off + tam]
        b = unwrap(b) if b[:4] == b"SSZL" else b
        if b[:8] == _MAGIA:
            salida.append(bytes(b))
    return salida


def escenas(qna: bytes) -> tuple[int, bytes]:
    """``(grupos, tablas C + D)`` de un QNA 051."""
    _tex, grupos, _partes, nc, nd = struct.unpack_from("<5I", qna, 8)
    _on, _og, _op, oc, od = struct.unpack_from("<5I", qna, 36)
    if oc + 32 * nc > len(qna) or od + 20 * nd > len(qna):
        raise ValueError("tablas de escenas fuera del QNA")
    return grupos, qna[oc:oc + 32 * nc] + qna[od:od + 20 * nd]


def diferencias_maquetado(japones: bytes, europeo: bytes) -> list[str]:
    """Motivos por los que el .arc europeo NO puede ir entero; lista vacía si puede."""
    jq, eq = maquetados(japones), maquetados(europeo)
    if len(jq) != len(eq):
        return [f"número de maquetados {len(jq)} vs {len(eq)}"]
    motivos = []
    for k, (j, e) in enumerate(zip(jq, eq, strict=True)):
        (gj, sj), (ge, se) = escenas(j), escenas(e)
        if gj != ge:
            motivos.append(f"QNA {k}: grupos {gj} vs {ge}")
        elif sj != se:
            motivos.append(f"QNA {k}: tablas de escenas distintas")
    return motivos
