"""Anclas estáticas: el cuerpo dibuja texto en coordenadas nativas, no DS×1,25.

No ejecuta el juego ni valida visualmente el resultado. Lee solo originales.
"""
import struct

import pytest

from ie123kit.nucleo.compresion.blz import decompress
from ie123kit.nucleo.config.raiz import find_root
from ie123kit.nucleo.ejecutable.cro import Cro

pytestmark = pytest.mark.requiere_rom


def test_body_coordinate_route_uses_unscaled_hint_and_native_offset():
    base = find_root() / "work/shared/base_3ds"
    paths = (base / "exefs.bin", base / "romfs/cro/ina_main3ogre.cro",
             base / "romfs/cro/static.crs")
    if not all(p.exists() for p in paths):
        pytest.skip("requiere ExeFS/CRO/CRS originales JP locales")
    exe, cro, crs = (p.read_bytes() for p in paths)
    assert exe[:8].rstrip(b"\0") == b".code"
    offset, size = struct.unpack_from("<II", exe, 8)
    code = decompress(exe[512 + offset:512 + offset + size])

    # r5=scene, sl=scene+EE4. Tanto SetPlanePosition como SetFlag usan ese grupo.
    cro_anchors = {
        0x3A764: "0150a0e10e8c81e203ab81e2b9af8ae2",
        # glifoX; group [r5+EE4]; SetPlanePosition; [sl]; r3=0; SetFlag.
        0x3AB98: ("f830d1e1e41e95e5000097e5ad1d05eb00109ae5000097e5"
                  "0030a0e3012086e22971ffeb"),
        # Stride 172 y escritura del flag en part+80.
        0x170C0: "ab00e0e3920c02e0020180e0010090e0803080151eff2fe1",
        # (part+1C + group+8)/4096 -> global+4; equivalente Y -> global+8.
        0x16420: ("1c0094e5081098e5010080e0100a00ee00011fe5c00ab8ee"
                  "080a20ee010a80ed0c1098e5202094e5021081e0101a00ee"
                  "c00ab8ee080a20ee020a80ed"),
        0x16330: "00008039",  # float 1/4096, no factor 1,25.
        # Bool(part+80) se escribe como cuarto argumento de pila, sp+C.
        0x196D00: ("801094e5c22abdee000050e3b0008d12000051e3881094e5"
                  "3cc096e50120a0130020a0030c208de5"),
        # X = trunc(global+4) + part+84; import1818 recibe coordenada entera.
        0x196D3C: ("012a96ed00009be5842094e5c22abdee181090e5100a12ee"
                  "023080e000009ae598208de2acaaf9eb"),
    }
    for address, expected_hex in cro_anchors.items():
        expected = bytes.fromhex(expected_hex)
        assert cro[address:address + len(expected)] == expected, hex(address)

    symbol = (b"_ZN2iz15cGameTextSystem30FindHintOnPlaneVramAndDrawTextEPKh"
              b"RNS_28cGamePrimitiveTextureManager19TEXTURE_INFO_HEADEREii6fvec_4Pfib")
    assert Cro(cro).imports()[0x1818].encode("ascii") == symbol
    name_offset, segment_offset = struct.unpack_from("<II", crs, 0x1114)
    assert crs[name_offset:name_offset + len(symbol) + 1] == symbol + b"\0"
    assert segment_offset == 0x650F00  # ExeFS .code+650F0, segmento 0.

    # Prologo: SP baja F0 bytes. X guardado C8, Y en F0, bool en FC.
    code_anchors = {
        0x650F0: "ff4f2de9f4c39fe5f8839fe5040b2ded0a8b2ded84d04de2",
        # Si bool==0 carga X/Y y salta el bloque de multiplicaciones completo.
        0x655A8: "fc009de5000050e3c8109d05f0209d050e00000a",
        0x655F8: "fc50d4e1",
    }
    for address, expected_hex in code_anchors.items():
        expected = bytes.fromhex(expected_hex)
        assert code[address:address + len(expected)] == expected, hex(address)
    branch = struct.unpack_from("<I", code, 0x655B8)[0]
    assert 0x655B8 + 8 + (branch & 0xFFFFFF) * 4 == 0x655F8
