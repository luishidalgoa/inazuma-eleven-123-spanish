"""Compresor SSZL (LZSS con anillo de 4096 B que empieza en 0xFEE), inverso de ui_archive.unwrap.

Los .lzs/.arc del juego se cargan en búferes del tamaño aproximado del original comprimido: envolver
los datos solo con literales (12,5 % más grande que sin comprimir) hace que la textura no cargue.
"""
import struct
from collections import defaultdict

from ie123kit.nucleo.errores import ValidacionError


def unwrap(data):
    if data[:4] != b'SSZL':
        return data
    packed, expected = struct.unpack_from('<II', data, 8)
    if packed + 16 != len(data):
        raise ValueError('SSZL size mismatch')
    ring = bytearray(4096)
    cursor, pos, out = 0xfee, 16, bytearray()
    while len(out) < expected:
        flags = data[pos]
        pos += 1
        for bit in range(8):
            if len(out) == expected:
                break
            if flags & (1 << bit):
                values = [data[pos]]
                pos += 1
                for value in values:
                    out.append(value);ring[cursor] = value;cursor = (cursor+1)&4095
            else:
                lo, hi = data[pos:pos+2]
                pos += 2
                offset = lo | ((hi & 0xf0) << 4)
                length = (hi & 15)+3
                for k in range(length):
                    if len(out) >= expected:
                        raise ValueError('SSZL output overflow')
                    value = ring[(offset+k)&4095]
                    out.append(value);ring[cursor] = value;cursor = (cursor+1)&4095
    return bytes(out)


def compress(raw: bytes) -> bytes:
    n = len(raw)
    out = bytearray()
    cadenas = defaultdict(list)
    i = 0
    while i < n:
        flag_pos = len(out)
        out.append(0)
        flags = 0
        for bit in range(8):
            if i >= n:
                break
            mejor_len, mejor_j = 0, 0
            if i + 3 <= n:
                clave = raw[i:i + 3]
                lista = cadenas[clave]
                for j in reversed(lista[-64:]):
                    if i - j > 4078:
                        break
                    k = 3
                    while k < 18 and i + k < n and raw[j + k] == raw[i + k]:
                        k += 1
                    if k > mejor_len:
                        mejor_len, mejor_j = k, j
                        if k == 18:
                            break
            if mejor_len >= 3:
                off = (0xFEE + mejor_j) & 0xFFF
                out += bytes((off & 0xFF, ((off >> 4) & 0xF0) | (mejor_len - 3)))
                paso = mejor_len
            else:
                flags |= 1 << bit
                out.append(raw[i])
                paso = 1
            for p in range(i, min(i + paso, n - 2)):
                cadenas[raw[p:p + 3]].append(p)
            i += paso
        out[flag_pos] = flags
    data = b'SSZL' + bytes(4) + struct.pack('<II', len(out), n) + bytes(out)
    assert unwrap(data) == raw
    return data


#: Bytes virtuales a cero que preceden a los datos: el anillo del lector arranca a cero en 0..0xFED, de modo que un
#: bloque de ceros al principio puede copiarse de ahi. Los SSZL originales de IE2 lo usan (comprobado en 8 .arc).
_PREFIJO_CEROS = 4078
_VENTANA = 4078


def compress_optimo(raw: bytes, profundidad: int = 4096) -> bytes:
    """Como :func:`compress`, pero con análisis óptimo (programación dinámica) en vez de voraz.

    Mismo formato y mismo lector (``unwrap``): solo cambia qué copias se eligen, así que el resultado nunca
    es más grande que el de :func:`compress` y suele ser un 1-4 % menor. Cada token cuesta 9 bits (literal) o
    17 bits (copia de 3..18 B); en cada posición se toma la copia más larga disponible y la programación
    dinámica decide la longitud usada. No excede la distancia 4078 que respetan los .arc originales y puede
    copiar ceros del prefijo virtual (anillo inicial a cero). Comprueba ``unwrap(resultado) == raw``.

    ``profundidad`` acota los candidatos probados por posición (4096 = toda la ventana).
    """
    n = len(raw)
    pad = _PREFIJO_CEROS
    datos = bytes(pad) + raw
    cadenas: dict[bytes, list[int]] = defaultdict(list)
    cadenas[b'\0\0\0'] = list(range(pad - 2))
    mejor_len = [0] * n
    mejor_j = [0] * n
    for i in range(n - 2):
        ii = i + pad
        lista = cadenas[datos[ii:ii + 3]]
        tope = min(18, n - i)
        mejor, mj, probados = 0, 0, 0
        for idx in range(len(lista) - 1, -1, -1):
            j = lista[idx]
            if ii - j > _VENTANA:
                break
            probados += 1
            if probados > profundidad or mejor >= tope:
                break
            if mejor and datos[j + mejor] != datos[ii + mejor]:
                continue
            k = 3
            while k < tope and datos[j + k] == datos[ii + k]:
                k += 1
            if k > mejor:
                mejor, mj = k, j
        mejor_len[i] = mejor
        mejor_j[i] = mj - pad
        lista.append(ii)
    coste = [0] * (n + 1)
    elegido = [1] * n
    for i in range(n - 1, -1, -1):
        c, e = coste[i + 1] + 9, 1
        for k in range(3, mejor_len[i] + 1):
            cc = coste[i + k] + 17
            if cc < c:
                c, e = cc, k
        coste[i], elegido[i] = c, e
    out = bytearray()
    i = 0
    while i < n:
        flag_pos = len(out)
        out.append(0)
        flags = 0
        for bit in range(8):
            if i >= n:
                break
            k = elegido[i]
            if k >= 3:
                off = (0xFEE + mejor_j[i]) & 0xFFF
                out += bytes((off & 0xFF, ((off >> 4) & 0xF0) | (k - 3)))
                i += k
            else:
                flags |= 1 << bit
                out.append(raw[i])
                i += 1
        out[flag_pos] = flags
    data = b'SSZL' + bytes(4) + struct.pack('<II', len(out), n) + bytes(out)
    if unwrap(data) != raw:
        raise ValidacionError('sszl_ida_vuelta', None, 'unwrap(compress_optimo(datos)) != datos')
    return data


#: Políticas admitidas por :func:`reenvolver_como`.
POLITICAS = ('keep', 'raw', 'sszl', 'keep_optimo', 'sszl_optimo')


def reenvolver_como(original: bytes, nuevo_raw: bytes, politica: str = 'keep',
                    crecimiento_max: float | None = None) -> bytes:
    """Devuelve `nuevo_raw` envuelto según `politica`, imitando lo que hacen las capas de work/.

    - 'raw': lo devuelve tal cual, sin envolver (lo que hace V37 al escribir extra/*.arc).
    - 'sszl': comprime siempre con :func:`compress`.
    - 'keep': comprime solo si `original` venía envuelto en SSZL (v64 y v65).
    - 'sszl_optimo' / 'keep_optimo': igual que 'sszl' / 'keep' pero con :func:`compress_optimo` (mismo formato,
      salida menor o igual; sirve para que el envoltorio no crezca respecto al original).

    Cuando comprime, exige que ``unwrap(resultado) == nuevo_raw``. No se expone el modo de
    solo literales: tools/sszl.py documenta que hace que la textura no cargue, porque los
    búferes del juego se dimensionan según el original comprimido.
    """
    if politica not in POLITICAS:
        raise ValueError(f'política de reenvoltura desconocida: {politica!r}; se admiten {POLITICAS}')
    if politica == 'raw' or (politica.startswith('keep') and original[:4] != b'SSZL'):
        resultado = bytes(nuevo_raw)
    else:
        comprimir = compress_optimo if politica.endswith('_optimo') else compress
        resultado = comprimir(bytes(nuevo_raw))
        if unwrap(resultado) != nuevo_raw:
            raise ValidacionError('sszl_ida_vuelta', None, 'unwrap(compress(datos)) != datos')
    if crecimiento_max is not None and len(resultado) > len(original) * crecimiento_max:
        raise ValidacionError(
            'sszl_crecimiento',
            None,
            f'{len(resultado)} B > {len(original)} B x {crecimiento_max}',
        )
    return resultado
