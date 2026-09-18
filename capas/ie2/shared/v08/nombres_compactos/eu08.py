"""v08 · lectura del port europeo 3DS de IE1 (work/ie1/fuentes/3ds_eu, prefijo es/): unitbase alineado por
registro con el japonés (datos +64..+94 idénticos en los 2399). Nombre completo en +0, corto en +32;
descripción en unitbase.STR, huecos de 128 B, puntero u16 en +94 (x128). Texto: Shift-JIS con las letras
europeas en 0xA1..0xDF (tabla NDS) y 0x7E = º."""
import struct
import sys

import comun08 as K

sys.path.insert(0, str(K.ROOT / 'tools/src'))
from ie123kit.nucleo.texto.nds_latin import NDS_DEC  # noqa: E402

EU = K.ROOT / 'work/ie1/fuentes/3ds_eu/romfs/archive.fa'


def dec(b):
    out, i = [], 0
    while i < len(b):
        c = b[i]
        if 0x81 <= c <= 0x9F or 0xE0 <= c <= 0xFC:
            out.append(b[i:i + 2].decode('cp932', 'replace'))
            i += 2
            continue
        out.append(NDS_DEC.get(c, f'<{c:02X}>') if 0xA1 <= c <= 0xDF else ('º' if c == 0x7E else chr(c)))
        i += 1
    return ''.join(out)


class Eu:
    def __init__(self):
        g = K.comun88.abrir(EU)
        self.ub = g('es/inazuma1/data_iz/logic/unitbase.dat')
        self.st = g('es/inazuma1/data_iz/logic/unitbase.STR')

    def registro(self, i):
        r = self.ub[96 + i * 96:192 + i * 96]
        p = struct.unpack_from('<H', r, 94)[0]
        d = self.st[p * 128:self.st.index(b'\0', p * 128)] if p else b''
        return dict(nombre=dec(r[0:16].split(b'\0')[0]), corto=dec(r[32:64].split(b'\0')[0]),
                    descripcion=dec(d) if d else None)
