"""Lectura de un CIA descifrado (nucleo.contenedores.cia) y FaArchiveMapeado. Datos sintéticos."""

from __future__ import annotations

import struct
import sys
from pathlib import Path

import pytest

from ie123kit.nucleo.contenedores import exefs
from ie123kit.nucleo.contenedores.cia import code_plano, exefs_de_ncch, ncch_de_cia, titulo_ncch
from ie123kit.nucleo.contenedores.fa import FaArchive, FaArchiveMapeado
from ie123kit.nucleo.errores import FormatoError

CONTRATO = Path(__file__).resolve().parent.parent / "contrato"
if str(CONTRATO) not in sys.path:
    sys.path.insert(0, str(CONTRATO))

from fa_sintetico import escribir_fa

CODE = bytes(range(256)) * 4


def _al(x: int) -> int:
    return (x + 63) // 64 * 64


def cia_sintetico(titulo: int = 0x0004000E000BB800) -> bytes:
    ex = exefs.construir([(".code", CODE), ("icon", b"ICON")])
    ncch = bytearray(0x400)
    ncch[0x100:0x104] = b"NCCH"
    struct.pack_into("<Q", ncch, 0x118, titulo)
    struct.pack_into("<II", ncch, 0x1A0, 2, len(ex) // 0x200)
    ncch[0x200 + 0xD] = 0  # .code sin comprimir
    ncch += ex
    cab, cert, tik, tmd = 0x2020, 0x10, 0x20, 0x30
    datos = bytearray(_al(cab) + _al(cert) + _al(tik) + _al(tmd))
    struct.pack_into("<IHHIIIIQ", datos, 0, cab, 0, 0, cert, tik, tmd, 0, len(ncch))
    return bytes(datos + ncch)


def test_cia_ncch_exefs_y_code():
    ncch = ncch_de_cia(cia_sintetico())
    assert titulo_ncch(ncch) == "0004000E000BB800"
    assert exefs_de_ncch(ncch)["icon"] == b"ICON"
    assert code_plano(ncch) == CODE


def test_cia_invalido():
    with pytest.raises(FormatoError):
        ncch_de_cia(b"\0" * 0x3000)


def test_fa_mapeado_igual_que_fa(tmp_path):
    ficheros = {"inazuma3_ogre/data_iz/a/x.arc": b"uno", "inazuma1/data_iz/b/y.arc": b"dos"}
    ruta = escribir_fa(tmp_path / "archive.fa", ficheros)
    normal = FaArchive(str(ruta))
    with FaArchiveMapeado(ruta) as mapeado:
        assert mapeado.entries == normal.entries
        assert all(mapeado.read(r) == d for r, d in ficheros.items())
        assert mapeado.exists("inazuma1/data_iz/b/y.arc")
