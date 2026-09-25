"""LZ11 de Nintendo (cabecera 0x11): descompresión y compresión voraz.

Portado de ``work/shared/capas/graficos/banner_home/lz11.py`` sin cambios de comportamiento (F2.5, #51):
el CGFX del ``banner.bnr`` va en LZ11 y el test ``requiere_rom`` exige el mismo flujo comprimido que la
capa. La compresión busca coincidencias con un índice de 3 bytes (64 candidatas, ventana 0x1000).
"""
import struct

__all__ = ["compress", "decompress"]

def decompress(d):
    assert d[0] == 0x11
    size = d[1] | d[2] << 8 | d[3] << 16
    p = 4
    if size == 0:
        size = struct.unpack_from('<I', d, 4)[0]; p = 8
    out = bytearray()
    while len(out) < size:
        flags = d[p]; p += 1
        for b in range(8):
            if len(out) >= size: break
            if flags & (0x80 >> b):
                a = d[p]; ind = a >> 4
                if ind == 0:
                    ln = (((a & 0xF) << 4) | (d[p+1] >> 4)) + 0x11
                    disp = ((d[p+1] & 0xF) << 8 | d[p+2]) + 1; p += 3
                elif ind == 1:
                    ln = (((a & 0xF) << 12) | (d[p+1] << 4) | (d[p+2] >> 4)) + 0x111
                    disp = ((d[p+2] & 0xF) << 8 | d[p+3]) + 1; p += 4
                else:
                    ln = ind + 1
                    disp = ((a & 0xF) << 8 | d[p+1]) + 1; p += 2
                for _ in range(ln):
                    out.append(out[-disp])
            else:
                out.append(d[p]); p += 1
    return bytes(out)

def compress(src):
    n = len(src)
    out = bytearray([0x11, n & 0xFF, (n >> 8) & 0xFF, (n >> 16) & 0xFF])
    assert n < 1 << 24
    # indice hash de 3 bytes -> posiciones recientes
    table = {}
    i = 0
    while i < n:
        fpos = len(out); out.append(0); flags = 0
        for b in range(8):
            if i >= n: break
            best_len, best_d = 0, 0
            if i + 3 <= n:
                key = src[i:i+3]
                cands = table.get(key, [])
                for j in reversed(cands[-64:]):
                    d = i - j
                    if d > 0x1000: break
                    l = 3
                    m = min(0x10110, n - i)
                    while l < m and src[j+l] == src[i+l]: l += 1
                    if l > best_len:
                        best_len, best_d = l, d
                        if l == m: break
            if best_len >= 3:
                flags |= 0x80 >> b
                dd = best_d - 1; L = best_len
                if L <= 0x10:
                    out += bytes([((L-1) << 4) | (dd >> 8), dd & 0xFF])
                elif L <= 0x110:
                    l = L - 0x11
                    out += bytes([l >> 4, ((l & 0xF) << 4) | (dd >> 8), dd & 0xFF])
                else:
                    l = L - 0x111
                    out += bytes([0x10 | (l >> 12), (l >> 4) & 0xFF, ((l & 0xF) << 4) | (dd >> 8), dd & 0xFF])
                for k in range(best_len):
                    if i + k + 3 <= n:
                        table.setdefault(src[i+k:i+k+3], []).append(i+k)
                i += best_len
            else:
                if i + 3 <= n:
                    table.setdefault(src[i:i+3], []).append(i)
                out.append(src[i]); i += 1
        out[fpos] = flags
    while len(out) % 4: out.append(0)
    return bytes(out)
