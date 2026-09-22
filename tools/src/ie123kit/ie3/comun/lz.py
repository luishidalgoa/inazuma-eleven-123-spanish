"""Compresion Nintendo/Level-5 usada dentro de los PKB."""


class LZError(RuntimeError):
    pass


def is_lz10(data: bytes) -> bool:
    """LZ10 = byte 0x10 + tamano descomprimido de 24 bits."""
    if len(data) < 4 or data[0] != 0x10:
        return False
    return (data[1] | (data[2] << 8) | (data[3] << 16)) > 0


def lz10_decompress(data: bytes) -> bytes:
    if len(data) < 4 or data[0] != 0x10:
        raise LZError("no es un bloque LZ10")

    out_size = data[1] | (data[2] << 8) | (data[3] << 16)

    src = 4
    out = bytearray()
    limit = len(data)

    while len(out) < out_size:
        if src >= limit:
            raise LZError(
                f"LZ10 truncado leyendo flags "
                f"({len(out)}/{out_size} bytes producidos)"
            )

        flags = data[src]
        src += 1

        for bit in range(7, -1, -1):
            if len(out) >= out_size:
                break

            if not (flags & (1 << bit)):
                if src >= limit:
                    raise LZError("LZ10 truncado leyendo literal")
                out.append(data[src])
                src += 1
                continue

            if src + 1 >= limit:
                raise LZError("LZ10 truncado leyendo referencia")

            b1 = data[src]
            b2 = data[src + 1]
            src += 2

            length = (b1 >> 4) + 3
            back = (((b1 & 0x0F) << 8) | b2) + 1

            if back > len(out):
                raise LZError(
                    f"referencia LZ10 invalida (back={back}, "
                    f"producidos={len(out)})"
                )

            for _ in range(length):
                out.append(out[-back])
                if len(out) >= out_size:
                    break

    if len(out) != out_size:
        raise LZError(
            f"LZ10 produjo {len(out)} bytes y la cabecera declaraba {out_size}"
        )

    return bytes(out)


def maybe_decompress(data: bytes):
    """Devuelve (datos, comprimido?). Nunca lanza: si falla, deja el bloque tal cual."""
    if not is_lz10(data):
        return data, False
    try:
        return lz10_decompress(data), True
    except LZError:
        return data, False
