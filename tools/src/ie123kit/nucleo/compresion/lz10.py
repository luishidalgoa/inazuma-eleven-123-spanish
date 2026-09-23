#!/usr/bin/env python3
"""Compresor/descompresor LZ10 de Nintendo (cabecera 0x10 + tamaño 24-bit LE).

Es el formato de cada entrada de los .pkb (scripts de evento) de Inazuma Eleven.
`compress` produce un stream que `decompress` (y el juego) entienden. Greedy.
"""
import struct


def compress_store(data):
    """LZ10 valido con TODO literales (sin matching): O(n), casi instantaneo.
    Salida ~12% mayor que el dato. Para builds de longitud VARIABLE donde el ratio
    no importa y la velocidad si. El juego lo descomprime igual (es LZ10 estandar)."""
    n = len(data)
    out = bytearray(b"\x10")
    out += struct.pack("<I", n)[:3]
    i = 0
    while i < n:
        out.append(0x00)                 # flag: los 8 siguientes son literales
        out += data[i:i + 8]
        i += 8
    return bytes(out)


def decompress(data):
    if not data or data[0] != 0x10:
        return data
    size = data[1] | (data[2] << 8) | (data[3] << 16)
    out = bytearray()
    p = 4
    while len(out) < size and p < len(data):
        flags = data[p]; p += 1
        for bit in range(8):
            if len(out) >= size or p >= len(data):
                break
            if flags & (0x80 >> bit):
                b1, b2 = data[p], data[p + 1]; p += 2
                length = (b1 >> 4) + 3
                disp = ((b1 & 0xF) << 8 | b2) + 1
                for _ in range(length):
                    out.append(out[-disp])
            else:
                out.append(data[p]); p += 1
    return bytes(out)


# candidatos por posicion (mas = mejor ratio, mas lento). Global ajustable: para
# builds de longitud variable basta un valor bajo (el evento crece igual, da igual
# que comprima un poco peor; gana mucha velocidad).
MAX_CAND = 256


def compress_optimal(data):
    """Minimum-byte LZ10 stream, including the one flag byte per eight tokens.

    Intended for small sprites that must fit an existing allocation. Keeps the
    normal compressor unchanged for larger packages.
    """
    data=bytes(data);n=len(data)
    if n>=1<<24:raise ValueError('LZ10 input exceeds 24-bit size')
    latest=[{} for _ in range(19)];matches=[]
    for i in range(n):
        row=[]
        for length in range(3,min(18,n-i)+1):
            key=data[i:i+length];previous=latest[length].get(key)
            if previous is not None and i-previous<=4096:row.append((length,i-previous))
            latest[length][key]=i
        matches.append(row)
    costs=[[0]*8 for _ in range(n+1)]
    choices=[[None]*8 for _ in range(n)]
    for i in range(n-1,-1,-1):
        for slot in range(8):
            nxt=(slot+1)%8;flag=int(slot==0)
            best=flag+1+costs[i+1][nxt];choice=(1,0)
            for length,distance in matches[i]:
                cost=flag+2+costs[i+length][nxt]
                if cost<=best:best=cost;choice=(length,distance)
            costs[i][slot]=best;choices[i][slot]=choice
    out=bytearray(b'\x10'+n.to_bytes(3,'little'));i=0;slot=0
    while i<n:
        if slot==0:flag_at=len(out);out.append(0)
        length,distance=choices[i][slot]
        if distance:
            out[flag_at]|=0x80>>slot
            value=((length-3)<<12)|(distance-1)
            out.extend(value.to_bytes(2,'big'))
        else:out.append(data[i])
        i+=length;slot=(slot+1)%8
    return bytes(out)


def compress(data):
    """LZ10 con lazy matching. Ventana 4096, longitud 3..18."""
    from collections import defaultdict
    n = len(data)
    out = bytearray(b"\x10")
    out += struct.pack("<I", n)[:3]
    pos = defaultdict(list)
    mv = memoryview(data)

    MAX_CAND = globals()["MAX_CAND"]   # leer el global (override-able)

    def best(i):
        if i + 3 > n:
            return 0, 0
        bl, bd = 0, 0
        maxlen = min(18, n - i)
        cand = pos.get(bytes(mv[i:i + 3]))
        if not cand:
            return 0, 0
        checked = 0
        for j in reversed(cand):
            disp = i - j
            if disp > 4096:
                break
            length = 3
            while length < maxlen and data[j + length] == data[i + length]:
                length += 1
            if length > bl:
                bl, bd = length, disp
                if length == maxlen:
                    break
            # No se cambia por enumerate: el contador solo avanza en los candidatos que
            # llegan hasta aquí, y alterar el corte por MAX_CAND cambiaría los bytes
            # comprimidos (y con ellos el sha de las candidatas golden).
            checked += 1  # noqa: SIM113
            if checked >= MAX_CAND:
                break
        return bl, bd

    def addpos(i):
        if i + 3 <= n:
            lst = pos[bytes(mv[i:i + 3])]
            lst.append(i)
            if len(lst) > 1024:       # acota listas de prefijos muy comunes
                del lst[:512]

    tokens = []
    i = 0
    while i < n:
        bl, bd = best(i)
        if bl >= 3:
            addpos(i)
            nl, _ = best(i + 1) if i + 1 < n else (0, 0)
            if nl > bl:                       # lazy: mejor empezar match en i+1
                tokens.append((False, data[i], 1))
                i += 1
                continue
            for k in range(i + 1, i + bl):
                addpos(k)
            tokens.append((True, bd, bl))
            i += bl
        else:
            tokens.append((False, data[i], 1))
            addpos(i)
            i += 1

    k = 0
    while k < len(tokens):
        grp = tokens[k:k + 8]
        flag = 0
        for bit, (is_match, a, b) in enumerate(grp):
            if is_match:
                flag |= 0x80 >> bit
        out.append(flag)
        for is_match, a, b in grp:
            if is_match:
                disp, length = a - 1, b - 3
                out.append((length << 4) | (disp >> 8))
                out.append(disp & 0xFF)
            else:
                out.append(a)
        k += 8
    return bytes(out)


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    # auto-test
    samples = [b"", b"A", b"ABABABABABAB", b"hola mundo " * 20,
               bytes(range(256)) * 4]
    ok = all(decompress(compress(s)) == s for s in samples)
    print("roundtrip auto-test:", "OK" if ok else "FALLO")
