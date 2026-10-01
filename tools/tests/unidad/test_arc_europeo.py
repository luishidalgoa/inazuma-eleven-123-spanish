"""arc_europeo: el .arc europeo entero solo si sus QNA tienen los mismos grupos y escenas."""
from __future__ import annotations

import struct

from ie123kit.nucleo.contenedores.arcv import rearmar
from ie123kit.nucleo.graficos.arc_europeo import diferencias_maquetado, maquetados


def _qna(grupos: int, escena: bytes, partes: int = 1) -> bytes:
    cab = bytearray(b" QNA 051" + bytes(56))
    oc, od = 64, 96
    struct.pack_into("<5I", cab, 8, 0, grupos, partes, 1, 1)
    struct.pack_into("<5I", cab, 36, 0, 0, 128, oc, od)
    cuerpo = bytearray(128 + 128 * partes)
    cuerpo[oc:oc + 32] = escena.ljust(32, b"\0")
    cuerpo[od:od + 20] = bytes(20)
    return bytes(cab) + bytes(cuerpo[len(cab):])


def _arc(*blobs: bytes) -> bytes:
    return rearmar([(i, b) for i, b in enumerate(blobs)], alinea=16)


def test_mismas_escenas_con_otras_partes_es_compatible():
    jp = _arc(b"CTPKxx", _qna(3, b"escena", partes=1))
    eu = _arc(b"CTPKyyyy", _qna(3, b"escena", partes=2))
    assert len(maquetados(eu)) == 1
    assert diferencias_maquetado(jp, eu) == []


def test_grupos_o_escenas_distintos_no():
    jp = _arc(_qna(3, b"escena"))
    assert diferencias_maquetado(jp, _arc(_qna(4, b"escena")))
    assert diferencias_maquetado(jp, _arc(_qna(3, b"otra")))
    assert diferencias_maquetado(jp, _arc(_qna(3, b"escena"), _qna(3, b"escena")))
