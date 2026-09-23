#!/usr/bin/env python3
"""BLZ (backward-LZSS de Nintendo) — descompresor/compresor del `.code` (ejecutable
ARM11) del 3DS. El `.code` va comprimido (flag bit0 del exheader) y se procesa HACIA
ATRAS: los flags y los datos se leen desde el final, y la salida se escribe desde el
final. Necesario para parchear las funciones de texto que crashean (PC en code.bin).

Para reinsertar SIN recomprimir: descomprimir -> parchear -> dejar el .code PLANO y
poner el flag compress-code del exheader a 0 (el loader lo carga tal cual)."""
import struct


def decompress(data):
    """Descomprime un `.code` BLZ. Si no esta comprimido (inc_len=0) lo devuelve igual."""
    data = bytes(data)
    n = len(data)
    inc_len = struct.unpack_from("<I", data, n - 4)[0]
    if inc_len == 0:
        return data
    hdr_len = data[n - 5]                              # bytes de footer al final
    enc_len = struct.unpack_from("<I", data, n - 8)[0] & 0xFFFFFF
    dec_len = n - enc_len                              # cabecera RAW al inicio (tal cual)
    out = bytearray(n + inc_len)                       # tamano total descomprimido
    out[:dec_len] = data[:dec_len]

    pak = n - hdr_len                                  # leer comprimido hacia atras
    raw = len(out)                                     # escribir salida hacia atras
    mask = 0
    flags = 0
    while raw > dec_len:
        mask >>= 1
        if mask == 0:
            pak -= 1
            flags = data[pak]
            mask = 0x80
        if flags & mask:                               # match (comprimido)
            pak -= 2
            pos = (data[pak + 1] << 8) | data[pak]
            length = (pos >> 12) + 3
            disp = (pos & 0xFFF) + 3
            for _ in range(length):
                raw -= 1
                out[raw] = out[raw + disp]
        else:                                          # literal
            pak -= 1
            raw -= 1
            out[raw] = data[pak]
    return bytes(out)
