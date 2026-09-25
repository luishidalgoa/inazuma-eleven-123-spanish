"""Bancos de sonido Procyon (SWD de muestras y SED de secuencias) de 3DS y de DS.

Porteo de ``work/ie2/shared/capas/media/voz_titulo/sonido.py`` (IE2 v13) con la corrección de la
v20 (los chunks del SWD de DS van alineados a 16 B) como parámetro ``alinear``, más ``swd_nuevo`` de
la misma capa (:func:`swd_con_cwavs`). Formatos:

- SWD 3DS (0x480): tabla de chunks en 0x60 (etiqueta, 0, versión, offset, tamaño); ``wavi`` = tabla
  de punteros u16 (0x46 = número de huecos) + entradas de 0x40 B (+0x02 id, +0x24 posición en
  ``pcmd``); cada muestra es un CWAV alineado a 32 B dentro de ``pcmd``. Cabecera: 0x08 tamaño del
  fichero, 0x40 tamaño de ``pcmd``.
- SWD DS (0x415): chunks encadenados desde 0x50; entrada ``wavi`` +0x12 formato (0x200 = IMA 4 bits),
  +0x20 frecuencia, +0x24 posición, +0x28/+0x2c bucle (palabras de 4 B); IMA con cabecera de 4 B
  (predictor s16, índice u8) y nibble bajo primero.
- SED: tabla de secuencias (u16) en 0x74a hasta un 0; cada secuencia = cabecera (u16 +2 = tamaño),
  chunk ``trk `` (u32 +12 = 4 + eventos; 4 B de preámbulo; relleno 0x98 hasta múltiplo de 4) y
  chunk ``eoc `` de 16 B. Cabecera del fichero: 0x08 tamaño.
- Eventos: nota = velocidad (<0x80) + byte de tecla (bits 7-6 = bytes de duración, 5-4 = cambio de
  octava + 2, 3-0 = tecla) + duración big-endian; 0x80-0x8f pausas fijas; 0x92 pausa de 1 B;
  0x98 fin; 0xa0 fija la octava.
"""
from __future__ import annotations

import struct

__all__ = ["TABLA_SEQ", "chunks_3ds", "chunks_nds", "fila_chunk", "ima_nds", "montar_sed", "muestras_3ds",
           "muestras_nds", "nota_con_ticks", "notas", "prgi_teclas", "secuencias", "sed_con_ticks",
           "swd_con_cwavs"]

TABLA_SEQ = 0x74A

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
        out.append({"hueco": k, "ptr": ptr, "id": struct.unpack_from('<H', e, 2)[0], "pos": pos, "entrada": e, "cwav": cw,
                        "muestras": struct.unpack_from('<I', cw, 0x54)[0],
                        "rate": struct.unpack_from('<I', cw, 0x4C)[0]})
    return ch, out


def chunks_nds(d, alinear=16):
    """{etiqueta: (offset de datos, longitud)} de un SWD de DS (0x415), chunks encadenados desde 0x50.

    Los chunks van alineados a 16 B (corrección de la v20); ``alinear=1`` reproduce la lectura
    de la v13, que no alineaba y que solo es correcta en los SWD cuyos chunks ya caen alineados.
    """
    out, p = {}, 0x50
    while p + 16 <= len(d):
        tag = d[p:p + 4]
        ln = struct.unpack_from('<I', d, p + 12)[0]
        out[tag.decode('latin1')] = (p + 16, ln)
        if tag not in (b'wavi', b'prgi', b'kgrp', b'pcmd'):
            break
        p += 16 + ln
        p += -p % alinear
    return out


def muestras_nds(d, alinear=16):
    ch = chunks_nds(d, alinear)
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
        out.append({"hueco": k, "id": struct.unpack_from('<H', e, 2)[0], "fmt": struct.unpack_from('<H', e, 0x12)[0],
                        "rate": rate, "pos": pos, "data": d[po + pos:po + pos + n]})
    return ch, out


def prgi_teclas(d, nds=False, alinear=16):
    """{tecla: muestra} de los splits de prgi (un solo programa)."""
    ch = chunks_nds(d, alinear) if nds else chunks_3ds(d)
    o, ln = ch['prgi']
    blob = d[o:o + ln]
    out = {}
    # splits de 0x30 B: +0x01 índice, +0x04..+0x07 rango de teclas, +0x12 muestra, final 00 7f 28 ff
    for q in range(len(blob) - 0x2F):
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
        out.append({"ptr": s, "cabecera": d[s:trk], "trk": d[trk:trk + 16], "preambulo": d[trk + 16:trk + 20],
                        "eventos": d[trk + 20:fin], "eoc": d[eoc:eoc + 16], "fin": eoc + 16})
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


def swd_con_cwavs(swd_3ds: bytes, cwavs: dict) -> bytes:
    """SWD 3DS con los CWAV de ``cwavs`` ({id de muestra: CWAV}); ``wavi``/``prgi`` intactos.

    Se recoloca ``pcmd`` (alineado a 32 B, en el orden de las posiciones originales) y se ajustan
    las posiciones (+0x24 de cada entrada de ``wavi``), la longitud de ``pcmd`` y el tamaño.
    """
    ch, ents = muestras_3ds(swd_3ds)
    po, _pl = ch['pcmd']
    wo, _ = ch['wavi']
    pcmd = bytearray()
    out = bytearray(swd_3ds[:po])
    for e in sorted(ents, key=lambda x: x['pos']):
        blob = cwavs.get(e['id'], e['cwav'])
        pos = len(pcmd)
        pcmd += blob + b'\0' * (-len(blob) % 32)
        struct.pack_into('<I', out, wo + e['ptr'] + 0x24, pos)
    struct.pack_into('<I', out, 0x08, po + len(pcmd))
    struct.pack_into('<I', out, 0x40, len(pcmd))
    fila = fila_chunk(swd_3ds, b'pcmd')
    struct.pack_into('<I', out, fila + 12, len(pcmd))
    return bytes(out) + bytes(pcmd)


# ------------------------------------------------------------------ retoque de una nota del SED

def nota_con_ticks(patron: bytes, ticks: int) -> bytes:
    """El mismo evento que ``patron`` con otra duración, sin cambiar de tamaño (4 B distintos).

    ``patron`` es la secuencia ``a0 <octava> <velocidad> <tecla> <dur BE 2 B> 93 <pausa LE 2 B> 98``
    (una nota suelta con su pausa y el fin de pista, como el grito del título del recopilatorio). La
    nota y la pausa pasan a durar ``ticks``; la codificación de 2 B se mantiene, así que el SED que la
    contiene conserva su longitud (porteo de ``nota_nueva`` de
    ``work/shared/capas/media/voz_titulo_recopilatorio/apply.py``).
    """
    if len(patron) != 10 or patron[0] != 0xA0 or patron[6] != 0x93 or patron[9] != 0x98:
        raise ValueError("patrón inesperado: 0xa0 octava, nota, pausa 0x93 de 2 B y fin 0x98")
    if (patron[3] >> 6) & 3 != 2:
        raise ValueError("la nota del patrón no lleva una duración de 2 B")
    if not 0 <= ticks <= 0xFFFF:
        raise ValueError(f"ticks fuera de 2 B: {ticks}")
    return patron[:4] + ticks.to_bytes(2, "big") + b"\x93" + ticks.to_bytes(2, "little") + b"\x98"


def sed_con_ticks(sed: bytes, patron: bytes, ticks: int) -> bytes:
    """SED con la única aparición de ``patron`` cambiada a ``ticks``; el resto y el tamaño intactos."""
    if sed.count(patron) != 1:
        raise ValueError(f"el patrón aparece {sed.count(patron)} veces en el SED (se esperaba 1)")
    nuevo = sed.replace(patron, nota_con_ticks(patron, ticks))
    if len(nuevo) != len(sed):
        raise AssertionError("el SED ha cambiado de tamaño")
    return nuevo
