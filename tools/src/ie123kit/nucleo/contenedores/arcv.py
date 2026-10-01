"""Read SSZL-wrapped ARCV UI resources from the IE123 original archive."""
import struct


def entries(data):
    if data[:4] != b'ARCV':
        raise ValueError('not ARCV')
    count, size = struct.unpack_from('<II', data, 4)
    if size != len(data) or 12+12*count > len(data):
        raise ValueError('invalid ARCV size')
    result = []
    for i in range(count):
        off, size, crc = struct.unpack_from('<III', data, 12+12*i)
        if off < 12+12*count or off+size > len(data):
            raise ValueError('ARCV entry out of range')
        result.append((off,size,crc))
    return result


def rearmar(lista, alinea=128, relleno=0xAC):
    """ARCV con las entradas ``[(hash, blob)]`` en orden, alineadas a ``alinea`` y rellenas con ``relleno``
    (el formato de los .arc de UI de la recopilación: tabla de 12 B por entrada tras la cabecera)."""
    n = len(lista)
    pos = 12 + 12 * n
    pos += (-pos) % alinea
    cuerpo, tabla = bytearray(), []
    for h, blob in lista:
        tabla.append((pos, len(blob), h))
        pad = (-(pos + len(blob))) % alinea
        cuerpo += blob + bytes([relleno]) * pad
        pos += len(blob) + pad
    salida = bytearray(b'ARCV' + struct.pack('<II', n, pos))
    for t in tabla:
        salida += struct.pack('<III', *t)
    salida += bytes([relleno]) * ((-len(salida)) % alinea)
    salida += cuerpo
    if len(salida) != pos:
        raise ValueError('ARCV mal rearmado')
    return bytes(salida)
