import struct

from ie123kit.ie3.comun import ancho_ventana


def test_patch_width_keeps_three_lines_and_verifies_context():
    """El parche IE3 solo toca los tres inmediatos previamente comprobados."""
    data = bytearray(0x04F3D4)
    data[0x80:0x84] = b"CRO0"
    for offset, expected, _new, _label in ancho_ventana.PARCHES:
        struct.pack_into("<I", data, offset, expected)
    for offset, expected, _label in ancho_ventana.CONTEXTO:
        struct.pack_into("<I", data, offset, expected)

    patched, report = ancho_ventana.parchear(bytes(data))

    assert report["caracteres_por_linea"] == 51
    assert report["lineas_por_caja"] == 3
    for offset, _expected, replacement, _label in ancho_ventana.PARCHES:
        assert struct.unpack_from("<I", patched, offset)[0] == replacement
