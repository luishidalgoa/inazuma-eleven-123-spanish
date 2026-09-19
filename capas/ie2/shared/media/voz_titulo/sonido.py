"""IE2 v13 · voz_titulo: lectura y montaje de sound.pb (3DS), sound.pkb (NDS), SWD y SED (Procyon).

Formatos (comprobados en esta capa):
- 3DS sound.ph: registros de 32 B = nombre 24 B + offset + tamaño en sound.pb.
- NDS sound.pkh: registros de 16 B (hash, offset, tamaño, 0); cada registro de sound.pkb es una tabla
  (offset, tamaño) de 1-2 ficheros; el nombre va en +0x20 de la cabecera sedl/swdl/smdl.
- SWD 3DS (0x480): tabla de chunks en 0x60 (etiqueta, 0, versión, offset, tamaño); wavi = tabla de
  punteros u16 (0x46 = número de huecos) + entradas de 0x40 B (+0x02 id, +0x24 posición en pcmd);
  cada muestra es un CWAV alineado a 32 B dentro de pcmd. Cabecera: 0x08 tamaño, 0x40 tamaño de pcmd.
- SWD NDS (0x415): chunks encadenados desde 0x50; entrada wavi +0x12 formato (0x200 = IMA 4 bits),
  +0x20 frecuencia, +0x24 posición, +0x28/+0x2c bucle (en palabras de 4 B); IMA con cabecera de 4 B
  (predictor s16, índice u8) y nibble bajo primero.
- SED: tabla de secuencias (u16) en 0x74a hasta un 0; cada secuencia = cabecera (u16 +2 = tamaño),
  chunk «trk » (u32 +12 = 4 + eventos; 4 B de preámbulo; relleno 0x98 hasta múltiplo de 4) y chunk
  «eoc » de 16 B. Cabecera del fichero: 0x08 tamaño.
- Eventos: nota = velocidad (<0x80) + byte de tecla (bits 7-6 = bytes de duración, 5-4 = cambio de
  octava + 2, 3-0 = tecla) + duración big-endian; 0x80-0x8f pausas fijas; 0x92 pausa de 1 B; 0x98 fin;
  0xa0 fija la octava.
"""
from __future__ import annotations

import struct

TABLA_SEQ = 0x74A


def leer_3ds(carpeta):
    ph = (carpeta / 'sound.ph').read_bytes()
    pb = (carpeta / 'sound.pb').read_bytes()
    out = []
    for i in range(0, len(ph), 32):
        nombre = ph[i:i + 24].split(b'\0')[0].decode()
        o, s = struct.unpack_from('<II', ph, i + 24)
        out.append((nombre, pb[o:o + s]))
    return ph, out


def leer_nds(carpeta):
    pkh = (carpeta / 'sound.pkh').read_bytes()
    pkb = (carpeta / 'sound.pkb').read_bytes()
    out = {}
    for i in range(0, len(pkh), 16):
        _h, o, s, _f = struct.unpack_from('<IIII', pkh, i)
        rec = pkb[o:o + s]
        for k in range(struct.unpack_from('<I', rec, 0)[0] // 8):
            so, ss = struct.unpack_from('<II', rec, 8 * k)
            blob = rec[so:so + ss]
            nombre = blob[0x20:0x30].split(b'\0')[0].split(b'\xff')[0].decode('ascii')
            out.setdefault(nombre.upper(), blob)
    return out


# ------------------------------------------------------------------ SWD

def chunks_3ds(d):
    out, p = {}, 0x60
    while True:
        tag = d[p:p + 4]
        off, ln = struct.unpack_from('<II', d, p + 8)
        out[tag.decode('latin1')] = (off, ln)
        if tag == b'eod ':
            return out
        p += 16


def fila_chunk(d, tag):
    p = 0x60
    while d[p:p + 4] != tag:
        assert d[p:p + 4] != b'eod ', tag
        p += 16
    return p


def muestras_3ds(d):
    ch = chunks_3ds(d)
    wo, _ = ch['wavi']
    po, _ = ch['pcmd']
    out = []
    for k in range(struct.unpack_from('<H', d, 0x46)[0]):
        ptr = struct.unpack_from('<H', d, wo + 2 * k)[0]
        if not ptr:
            continue
        e = d[wo + ptr:wo + ptr + 0x40]
        pos = struct.unpack_from('<I', e, 0x24)[0]
        assert d[po + pos:po + pos + 4] == b'CWAV', (k, pos)
        size = struct.unpack_from('<I', d, po + pos + 12)[0]
        cw = d[po + pos:po + pos + size]
        out.append(dict(hueco=k, ptr=ptr, id=struct.unpack_from('<H', e, 2)[0], pos=pos, entrada=e, cwav=cw,
                        muestras=struct.unpack_from('<I', cw, 0x54)[0],
                        rate=struct.unpack_from('<I', cw, 0x4C)[0]))
    return ch, out


def chunks_nds(d):
    out, p = {}, 0x50
    while p + 16 <= len(d):
        tag = d[p:p + 4]
        ln = struct.unpack_from('<I', d, p + 12)[0]
        out[tag.decode('latin1')] = (p + 16, ln)
        if tag not in (b'wavi', b'prgi', b'kgrp', b'pcmd'):
            break
        p += 16 + ln
    return out


def muestras_nds(d):
    ch = chunks_nds(d)
    wo, _ = ch['wavi']
    po, _ = ch['pcmd']
    out = []
    for k in range(struct.unpack_from('<H', d, 0x46)[0]):
        ptr = struct.unpack_from('<H', d, wo + 2 * k)[0]
        if not ptr:
            continue
        e = d[wo + ptr:wo + ptr + 0x40]
        rate, pos, lb, ll = struct.unpack_from('<IIII', e, 0x20)
        n = (lb + ll) * 4
        out.append(dict(hueco=k, id=struct.unpack_from('<H', e, 2)[0], fmt=struct.unpack_from('<H', e, 0x12)[0],
                        rate=rate, pos=pos, data=d[po + pos:po + pos + n]))
    return ch, out


def prgi_teclas(d, nds=False):
    """{tecla: muestra} de los splits de prgi (un solo programa)."""
    ch = chunks_nds(d) if nds else chunks_3ds(d)
    o, ln = ch['prgi']
    blob = d[o:o + ln]
    out = {}
    # splits de 0x30 B: +0x01 índice, +0x04..+0x07 rango de teclas, +0x12 muestra, final 00 7f 28 ff
    for q in range(0, len(blob) - 0x2F):
        if blob[q] == 0 and blob[q + 2] == 2 and blob[q + 0x2C:q + 0x30] == bytes.fromhex('007f28ff') \
                and blob[q + 4] == blob[q + 5] == blob[q + 6] == blob[q + 7]:
            out.setdefault(blob[q + 4], struct.unpack_from('<H', blob, q + 0x12)[0])
    return out


_IDX = [-1, -1, -1, -1, 2, 4, 6, 8]
_STEP = [7, 8, 9, 10, 11, 12, 13, 14, 16, 17, 19, 21, 23, 25, 28, 31, 34, 37, 41, 45, 50, 55, 60, 66, 73, 80,
         88, 97, 107, 118, 130, 143, 157, 173, 190, 209, 230, 253, 279, 307, 337, 371, 408, 449, 494, 544, 598,
         658, 724, 796, 876, 963, 1060, 1166, 1282, 1411, 1552, 1707, 1878, 2066, 2272, 2499, 2749, 3024, 3327,
         3660, 4026, 4428, 4871, 5358, 5894, 6484, 7132, 7845, 8630, 9493, 10442, 11487, 12635, 13899, 15289,
         16818, 18500, 20350, 22385, 24623, 27086, 29794, 32767]


def ima_nds(data):
    pred, idx = struct.unpack_from('<hB', data, 0)
    pcm = []
    for b in data[4:]:
        for nib in (b & 15, b >> 4):
            st = _STEP[idx]
            diff = st >> 3
            if nib & 1:
                diff += st >> 2
            if nib & 2:
                diff += st >> 1
            if nib & 4:
                diff += st
            pred = max(-32768, min(32767, pred - diff if nib & 8 else pred + diff))
            idx = max(0, min(88, idx + _IDX[nib & 7]))
            pcm.append(pred)
    return pcm


# ------------------------------------------------------------------ SED

def secuencias(d):
    ptrs = []
    p = TABLA_SEQ
    while True:
        v = struct.unpack_from('<H', d, p)[0]
        if not v:
            break
        ptrs.append(v)
        p += 2
    out = []
    for s in ptrs:
        hl = struct.unpack_from('<H', d, s + 2)[0]
        trk = s + hl
        assert d[trk:trk + 4] == b'trk ', hex(trk)
        ln = struct.unpack_from('<I', d, trk + 12)[0]
        fin = trk + 16 + ln
        eoc = fin + (-fin % 4)
        assert d[eoc:eoc + 4] == b'eoc ', hex(eoc)
        assert set(d[fin:eoc]) <= {0x98}
        out.append(dict(ptr=s, cabecera=d[s:trk], trk=d[trk:trk + 16], preambulo=d[trk + 16:trk + 20],
                        eventos=d[trk + 20:fin], eoc=d[eoc:eoc + 16], fin=eoc + 16))
    return out


def montar_sed(d, seqs, pistas):
    primero = seqs[0]['ptr']
    out = bytearray(d[:primero])
    for k in range(len(seqs)):
        struct.pack_into('<H', out, TABLA_SEQ + 2 * k, 0)
    for k, (s, ev) in enumerate(zip(seqs, pistas)):
        struct.pack_into('<H', out, TABLA_SEQ + 2 * k, len(out))
        out += s['cabecera']
        trk = bytearray(s['trk'])
        struct.pack_into('<I', trk, 12, 4 + len(ev))
        out += trk + s['preambulo'] + ev
        out += b'\x98' * (-len(out) % 4)
        out += s['eoc']
    struct.pack_into('<I', out, 0x08, len(out))
    return bytes(out)


_PAUSA = {0x80: 1, 0x81: 2, 0x82: 3, 0x83: 4, 0x84: 6, 0x85: 8, 0x86: 9, 0x87: 12, 0x88: 16, 0x89: 18,
          0x8a: 24, 0x8b: 32, 0x8c: 36, 0x8d: 48, 0x8e: 64, 0x8f: 72}
_PARAMS = {0x90: 0, 0x91: 1, 0x92: 1, 0x93: 2, 0x94: 3, 0x95: 1, 0x98: 0, 0xa0: 1, 0xa4: 1, 0xa8: 2, 0xac: 1,
           0xe0: 1, 0xe3: 1, 0xe8: 1}


def notas(ev):
    """[[tick, tecla, velocidad, duración], ...] + ['fin', tick]. Falla con eventos desconocidos."""
    i, octava, t, ultima, out = 0, 0, 0, 0, []
    while i < len(ev):
        b = ev[i]
        i += 1
        if b < 0x80:
            kd = ev[i]
            i += 1
            n = (kd >> 6) & 3
            octava += ((kd >> 4) & 3) - 2
            dur = int.from_bytes(ev[i:i + n], 'big') if n else None
            i += n
            out.append([t, octava * 12 + (kd & 15), b, dur])
        elif b in _PAUSA:
            ultima = _PAUSA[b]
            t += ultima
        elif b == 0x98:
            out.append(['fin', t])
            assert i == len(ev), 'eventos tras el fin'
            return out
        else:
            if b not in _PARAMS:
                raise ValueError(f'evento desconocido {b:#x}')
            prm = ev[i:i + _PARAMS[b]]
            i += _PARAMS[b]
            if b == 0xa0:
                octava = prm[0]
            elif b == 0x92:
                ultima = prm[0]
                t += ultima
            elif b == 0x90:
                t += ultima
    raise ValueError('pista sin fin')
