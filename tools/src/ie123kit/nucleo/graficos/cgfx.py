"""CGFX (texturas TXOB) y códec de texturas PICA200 para el banner del menú HOME.

Portado de ``work/shared/capas/graficos/banner_home/cgfx.py`` sin cambios de comportamiento (F2.5,
#51). ETC1/ETC1A4 necesitan ``texture2ddecoder`` (lectura) y ``etcpak`` (escritura), que se importan
solo al usarlos; el resto (RGBA8, RGB8, RGBA5551, RGB565, RGBA4, LA8) es Python + Pillow.
"""
import struct

from PIL import Image

__all__ = ["FMT", "decode", "encode", "textures"]

FMT = {0: "RGBA8", 1: "RGB8", 2: "RGBA5551", 3: "RGB565", 4: "RGBA4", 5: "LA8", 7: "L8",
       8: "A8", 9: "LA4", 10: "L4", 11: "A4", 12: "ETC1", 13: "ETC1A4"}


def _rel(c, o):
    return o + struct.unpack_from('<I', c, o)[0]


def _cstr(c, o):
    return c[o:c.index(b'\0', o)].decode()


def textures(c):
    """[(nombre, off_txob, w, h, fmt, off_datos, tam)]"""
    if c[:4] != b'CGFX' or c[0x14:0x18] != b'DATA':
        raise ValueError('no es CGFX')
    cnt = struct.unpack_from('<I', c, 0x1c + 8)[0]
    d = _rel(c, 0x1c + 8 + 4)
    assert c[d:d+4] == b'DICT'
    out = []
    for i in range(cnt):
        e = d + 0x1c + i * 16
        name, t = _cstr(c, _rel(c, e + 8)), _rel(c, e + 12)
        assert c[t+4:t+8] == b'TXOB'
        h, w = struct.unpack_from('<II', c, t + 0x18)
        fmt = struct.unpack_from('<I', c, t + 0x34)[0]
        size = struct.unpack_from('<I', c, t + 0x44)[0]
        data = _rel(c, t + 0x48)
        out.append((name, t, w, h, fmt, data, size))
    return out


def _pidx(x, y, w):
    m = 0
    for b in range(3):
        m |= ((x >> b) & 1) << (2 * b) | ((y >> b) & 1) << (2 * b + 1)
    return ((y // 8) * (w // 8) + x // 8) * 64 + m


def decode(raw, w, h, fmt):
    img = Image.new('RGBA', (w, h))
    if fmt in (12, 13):
        import texture2ddecoder
        pos, bs = 0, 16 if fmt == 13 else 8
        for y in range(0, h, 8):
            for x in range(0, w, 8):
                for dx, dy in ((0, 0), (4, 0), (0, 4), (4, 4)):
                    a = int.from_bytes(raw[pos:pos+8], 'little') if fmt == 13 else None
                    col = raw[pos+bs-8:pos+bs]
                    blk = Image.frombytes('RGBA', (4, 4), texture2ddecoder.decode_etc1(col[::-1], 4, 4), 'raw', 'BGRA')
                    if a is not None:
                        px = blk.load()
                        for yy in range(4):
                            for xx in range(4):
                                px[xx, yy] = px[xx, yy][:3] + (((a >> (4 * (xx * 4 + yy))) & 15) * 17,)
                    img.paste(blk, (x + dx, y + dy))
                    pos += bs
        return img
    px = img.load()
    for y in range(h):
        for x in range(w):
            i = _pidx(x, y, w)
            if fmt == 0:
                a, b, g, r = raw[4*i:4*i+4]
            elif fmt == 1:
                b, g, r = raw[3*i:3*i+3]; a = 255
            elif fmt in (2, 3, 4):
                v = struct.unpack_from('<H', raw, 2*i)[0]
                if fmt == 2:
                    r, g, b, a = ((v >> 11) & 31) * 255 // 31, ((v >> 6) & 31) * 255 // 31, ((v >> 1) & 31) * 255 // 31, (v & 1) * 255
                elif fmt == 3:
                    r, g, b, a = ((v >> 11) & 31) * 255 // 31, ((v >> 5) & 63) * 255 // 63, (v & 31) * 255 // 31, 255
                else:
                    r, g, b, a = ((v >> 12) & 15) * 17, ((v >> 8) & 15) * 17, ((v >> 4) & 15) * 17, (v & 15) * 17
            elif fmt == 5:
                a, r = raw[2*i:2*i+2]; g = b = r
            else:
                raise ValueError(f'formato no soportado {fmt}')
            px[x, y] = (r, g, b, a)
    return img


def encode(img, w, h, fmt, original_raw=None):
    """Codifica; en ETC1/ETC1A4 conserva los bloques originales no editados."""
    img = img.convert('RGBA')
    if fmt in (12, 13):
        import etcpak
        orig = decode(original_raw, w, h, fmt) if original_raw else None
        bs = 16 if fmt == 13 else 8
        out = bytearray(original_raw) if original_raw else bytearray(w * h // 16 * bs)
        pos = 0
        for y in range(0, h, 8):
            for x in range(0, w, 8):
                for dx, dy in ((0, 0), (4, 0), (0, 4), (4, 4)):
                    box = (x+dx, y+dy, x+dx+4, y+dy+4)
                    blk = img.crop(box)
                    if orig is None or blk.tobytes() != orig.crop(box).tobytes():
                        if fmt == 13:
                            a = sum(round(blk.getpixel((xx, yy))[3] / 17) << (4 * (xx * 4 + yy)) for yy in range(4) for xx in range(4))
                            out[pos:pos+8] = a.to_bytes(8, 'little')
                        out[pos+bs-8:pos+bs] = etcpak.compress_etc1_rgb(blk.tobytes(), 4, 4)[::-1]
                    pos += bs
        return bytes(out)
    bpp = {0: 4, 1: 3, 2: 2, 3: 2, 4: 2, 5: 2}[fmt]
    out = bytearray(w * h * bpp)
    px = img.load()
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]; i = _pidx(x, y, w)
            if fmt == 0:
                out[4*i:4*i+4] = bytes((a, b, g, r))
            elif fmt == 1:
                out[3*i:3*i+3] = bytes((b, g, r))
            elif fmt == 5:
                out[2*i:2*i+2] = bytes((a, r))
            else:
                if fmt == 2:
                    v = (round(r*31/255) << 11) | (round(g*31/255) << 6) | (round(b*31/255) << 1) | int(a >= 128)
                elif fmt == 3:
                    v = (round(r*31/255) << 11) | (round(g*63/255) << 5) | round(b*31/255)
                else:
                    v = (round(r/17) << 12) | (round(g/17) << 8) | (round(b/17) << 4) | round(a/17)
                struct.pack_into('<H', out, 2*i, v)
    return bytes(out)
