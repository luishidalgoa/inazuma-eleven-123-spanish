"""Codificador DSP-ADPCM (GC/Wii/3DS) en Python puro y CWAV mono.

Porte del algoritmo de referencia de Nintendo tal como lo publica gc-dspadpcm-encode (jackoalan,
dominio público): cálculo de los 8 pares de coeficientes por correlación y codificación por tramas
de 14 muestras (1 byte de predictor/escala + 7 bytes de nibbles). ``decodificar`` es el decodificador
de referencia para comprobar la ida y vuelta.

Procede de ``work/ie2/shared/capas/media/voz_titulo/dsp_adpcm.py`` (IE2 v13) sin cambios de
comportamiento: la capa y este módulo dan los mismos bytes (test ``requiere_rom``).
:func:`cwav_mono` es el ``cwav`` de esa capa con la frecuencia como parámetro.
"""
from __future__ import annotations

import math
import struct

__all__ = ["codificar", "coeficientes", "cwav_mono", "decodificar"]

DBL_EPS = 2.220446049250313e-16


def _inner(vec, buf, o):
    for i in range(3):
        s = 0.0
        for x in range(14):
            s -= buf[o + x - i] * buf[o + x]
        vec[i] = s


def _outer(mtx, buf, o):
    for x in (1, 2):
        for y in (1, 2):
            s = 0.0
            for z in range(14):
                s += buf[o + z - x] * buf[o + z - y]
            mtx[x][y] = s


def _analyze(mtx, idx):
    recips = [0.0, 0.0, 0.0]
    for x in (1, 2):
        val = max(abs(mtx[x][1]), abs(mtx[x][2]))
        if val < DBL_EPS:
            return True
        recips[x] = 1.0 / val
    max_index = 0
    for i in (1, 2):
        for x in range(1, i):
            tmp = mtx[x][i]
            for y in range(1, x):
                tmp -= mtx[x][y] * mtx[y][i]
            mtx[x][i] = tmp
        val = 0.0
        for x in range(i, 3):
            tmp = mtx[x][i]
            for y in range(1, i):
                tmp -= mtx[x][y] * mtx[y][i]
            mtx[x][i] = tmp
            tmp = abs(tmp) * recips[x]
            if tmp >= val:
                val = tmp
                max_index = x
        if max_index != i:
            for y in (1, 2):
                mtx[max_index][y], mtx[i][y] = mtx[i][y], mtx[max_index][y]
            recips[max_index] = recips[i]
        idx[i] = max_index
        if mtx[i][i] == 0.0:
            return True
        if i != 2:
            tmp = 1.0 / mtx[i][i]
            for x in range(i + 1, 3):
                mtx[x][i] *= tmp
    mn, mx = 1.0e10, 0.0
    for i in (1, 2):
        tmp = abs(mtx[i][i])
        mn = min(mn, tmp)
        mx = max(mx, tmp)
    return mn / mx < 1.0e-10


def _bidir(mtx, idx, vec):
    x = 0
    for i in (1, 2):
        index = idx[i]
        tmp = vec[index]
        vec[index] = vec[i]
        if x != 0:
            for y in range(x, i):
                tmp -= vec[y] * mtx[i][y]
        elif tmp != 0.0:
            x = i
        vec[i] = tmp
    for i in (2, 1):
        tmp = vec[i]
        for y in range(i + 1, 3):
            tmp -= vec[y] * mtx[i][y]
        vec[i] = tmp / mtx[i][i]
    vec[0] = 1.0


def _quadratic(vec):
    v2 = vec[2]
    tmp = 1.0 - v2 * v2
    if tmp == 0.0:
        return True
    v0 = (vec[0] - v2 * v2) / tmp
    v1 = (vec[1] - vec[1] * v2) / tmp
    vec[0], vec[1] = v0, v1
    return abs(v1) > 1.0


def _finish(vin, out):
    for z in (1, 2):
        if vin[z] >= 1.0:
            vin[z] = 0.9999999999
        elif vin[z] <= -1.0:
            vin[z] = -0.9999999999
    out[0] = 1.0
    out[1] = vin[2] * vin[1] + vin[1]
    out[2] = vin[2]


def _matrix_filter(src, dst):
    mtx = [[0.0] * 3 for _ in range(3)]
    mtx[2][0] = 1.0
    for i in (1, 2):
        mtx[2][i] = -src[i]
    for i in (2, 1):
        val = 1.0 - mtx[i][i] * mtx[i][i]
        for y in range(1, i + 1):
            mtx[i - 1][y] = (mtx[i][i] * mtx[i][y] + mtx[i][y]) / val
    dst[0] = 1.0
    for i in (1, 2):
        dst[i] = 0.0
        for y in range(1, i + 1):
            dst[i] += mtx[i][y] * dst[i - y]


def _merge_finish(src, dst):
    tmp = [0.0, 0.0, 0.0]
    val = src[0]
    dst[0] = 1.0
    for i in (1, 2):
        v2 = 0.0
        for y in range(1, i):
            v2 += dst[y] * src[i - y]
        dst[i] = -(v2 + src[i]) / val if val > 0.0 else 0.0
        tmp[i] = dst[i]
        for y in range(1, i):
            dst[y] += dst[i] * dst[i - y]
        val *= 1.0 - dst[i] * dst[i]
    _finish(tmp, dst)


def _contrast(s1, s2):
    val = (s2[2] * s2[1] + -s2[1]) / (1.0 - s2[2] * s2[2])
    val1 = s1[0] * s1[0] + s1[1] * s1[1] + s1[2] * s1[2]
    val2 = s1[0] * s1[1] + s1[1] * s1[2]
    val3 = s1[0] * s1[2]
    return val1 + 2.0 * val * val2 + 2.0 * (-s2[1] * val + -s2[2]) * val3


def _filter_records(best, exp, records):
    buf2 = [0.0, 0.0, 0.0]
    for _ in range(2):
        counts = [0] * exp
        acc = [[0.0, 0.0, 0.0] for _ in range(exp)]
        for rec in records:
            index, value = 0, 1.0e30
            for i in range(exp):
                t = _contrast(best[i], rec)
                if t < value:
                    value, index = t, i
            counts[index] += 1
            _matrix_filter(rec, buf2)
            for i in range(3):
                acc[index][i] += buf2[i]
        for i in range(exp):
            if counts[i] > 0:
                for y in range(3):
                    acc[i][y] /= counts[i]
        for i in range(exp):
            _merge_finish(acc[i], best[i])


def coeficientes(pcm):
    """8 pares (c1, c2) de coeficientes en Q11 para la lista de muestras int16."""
    n = len(pcm)
    frames = (n + 13) // 14
    hist = [0] * 28              # [0:14] trama anterior, [14:28] trama actual
    padded = list(pcm) + [0] * (frames * 14 - n)
    vec1, vec2 = [0.0] * 3, [0.0] * 3
    mtx = [[0.0] * 3 for _ in range(3)]
    idx = [0, 0, 0]
    records = []
    for f in range(frames):
        hist[0:14] = hist[14:28]
        hist[14:28] = padded[f * 14:f * 14 + 14]
        _inner(vec1, hist, 14)
        if abs(vec1[0]) > 10.0:
            _outer(mtx, hist, 14)
            if not _analyze(mtx, idx):
                _bidir(mtx, idx, vec1)
                if not _quadratic(vec1):
                    rec = [0.0, 0.0, 0.0]
                    _finish(vec1, rec)
                    records.append(rec)
    best = [[0.0, 0.0, 0.0] for _ in range(8)]
    vec1 = [1.0, 0.0, 0.0]
    for rec in records:
        _matrix_filter(rec, best[0])
        for y in (1, 2):
            vec1[y] += best[0][y]
    if records:
        for y in (1, 2):
            vec1[y] /= len(records)
    _merge_finish(vec1, best[0])
    exp = 1
    w = 0
    while w < 3:
        vec2 = [0.0, -1.0, 0.0]
        for i in range(exp):
            for y in range(3):
                best[exp + i][y] = 0.01 * vec2[y] + best[i][y]
        w += 1
        exp = 1 << w
        _filter_records(best, exp, records)
    out = []
    for z in range(8):
        par = []
        for k in (1, 2):
            d = -best[z][k] * 2048.0
            if d > 0.0:
                par.append(32767 if d > 32767.0 else math.floor(d + 0.5))
            else:
                par.append(-32768 if d < -32768.0 else -math.floor(-d + 0.5))
        out.append(tuple(par))
    return out


def _cdiv(a, b):
    """División entera de C (trunca hacia cero)."""
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b > 0) else -q


def _clamp16(v):
    return 32767 if v >= 32767 else (max(-32768, v))


def _trama(pcm16, count, coefs):
    """pcm16: [yn2, yn1, s0..s13]. Devuelve (8 bytes, pcm16 con las muestras reconstruidas)."""
    ins = [[0] * 16 for _ in range(8)]
    outs = [[0] * 14 for _ in range(8)]
    scale = [0] * 8
    dist_acc = [0.0] * 8
    for i in range(8):
        c1, c2 = coefs[i]
        ins[i][0], ins[i][1] = pcm16[0], pcm16[1]
        distance = 0
        for s in range(count):
            v1 = _cdiv(pcm16[s] * c2 + pcm16[s + 1] * c1, 2048)
            ins[i][s + 2] = v1
            v3 = _clamp16(pcm16[s + 2] - v1)
            if abs(v3) > abs(distance):
                distance = v3
        sc = 0
        while sc <= 12 and (distance > 7 or distance < -8):
            sc += 1
            distance = _cdiv(distance, 2)
        sc = -1 if sc <= 1 else sc - 2
        while True:
            sc += 1
            dist_acc[i] = 0.0
            index = 0
            for s in range(count):
                v1 = ins[i][s] * c2 + ins[i][s + 1] * c1
                v2 = (pcm16[s + 2] << 11) - v1
                q = v2 / (1 << sc) / 2048
                v3 = int(q + 0.4999999) if v2 > 0 else int(q - 0.4999999)
                if v3 < -8:
                    index = max(index, -8 - v3)
                    v3 = -8
                elif v3 > 7:
                    index = max(index, v3 - 7)
                    v3 = 7
                outs[i][s] = v3
                v1 = (v1 + ((v3 * (1 << sc)) << 11) + 1024) >> 11
                v2 = _clamp16(v1)
                ins[i][s + 2] = v2
                d = pcm16[s + 2] - v2
                dist_acc[i] += d * float(d)
            x = index + 8
            while x > 256:
                sc += 1
                if sc >= 12:
                    sc = 11
                x >>= 1
            if not (sc < 12 and index > 1):
                break
        scale[i] = sc
    best = min(range(8), key=lambda k: (dist_acc[k], k))
    res = list(pcm16)
    for s in range(count):
        res[s + 2] = ins[best][s + 2]
    o = outs[best]
    for s in range(count, 14):
        o[s] = 0
    b = bytearray([(best << 4) | (scale[best] & 0xF)])
    for y in range(7):
        b.append(((o[2 * y] << 4) & 0xF0) | (o[2 * y + 1] & 0xF))
    return bytes(b), res


def codificar(pcm, coefs=None):
    """(bytes ADPCM, coefs, predictor/escala inicial). Sin bucle; historia inicial 0."""
    if coefs is None:
        coefs = coeficientes(pcm)
    out = bytearray()
    hist = [0, 0]
    for f in range(0, len(pcm), 14):
        blk = list(pcm[f:f + 14])
        cnt = len(blk)
        blk += [0] * (14 - cnt)
        b, res = _trama(hist + blk, cnt, coefs)
        out += b
        hist = [res[14], res[15]] if cnt == 14 else [res[cnt], res[cnt + 1]]
    nbytes = (len(pcm) + 13) // 14 * 8
    return bytes(out[:nbytes]), coefs, out[0] if out else 0


def decodificar(data, coefs, n):
    """Decodificador de referencia (historia inicial 0)."""
    out = []
    h1 = h2 = 0
    for f in range(0, len(data), 8):
        ps = data[f]
        c1, c2 = coefs[ps >> 4]
        sc = 1 << (ps & 0xF)
        for k in range(14):
            if len(out) >= n:
                return out
            byte = data[f + 1 + k // 2]
            nib = (byte >> 4) if k % 2 == 0 else (byte & 0xF)
            if nib >= 8:
                nib -= 16
            v = ((nib * sc) << 11) + 1024 + c1 * h1 + c2 * h2
            v = _clamp16(v >> 11)
            out.append(v)
            h2, h1 = h1, v
    return out


def cwav_mono(plantilla: bytes, pcm, frecuencia: int) -> bytes:
    """CWAV mono DSP-ADPCM sin bucle con la cabecera de ``plantilla`` (la original de la muestra).

    Cambia solo tamaños, frecuencia, número de muestras, coeficientes y contextos; el resto de la
    cabecera (0xE0 B) es la de la plantilla.
    """
    muestras = [int(v) for v in pcm]
    datos, coefs, ps = codificar(muestras)
    cuerpo = datos + b"\0" * (-len(datos) % 4)
    total = 0xE0 + len(cuerpo)
    b = bytearray(plantilla[:0xE0])
    if b[:4] != b"CWAV" or b[0x40:0x44] != b"INFO" or b[0xC0:0xC4] != b"DATA":
        raise ValueError("la plantilla no es un CWAV con INFO en 0x40 y DATA en 0xC0")
    if b[0x48] != 2 or b[0x49] != 0:
        raise ValueError("la plantilla no es DSP-ADPCM mono")
    struct.pack_into("<I", b, 0x0C, total)
    struct.pack_into("<I", b, 0x28, total - 0xC0)            # referencia al bloque DATA
    struct.pack_into("<IIII", b, 0x4C, frecuencia, 0, len(muestras), 0)
    for k, (c1, c2) in enumerate(coefs):
        struct.pack_into("<hh", b, 0x7C + 4 * k, c1, c2)
    struct.pack_into("<Hhh", b, 0x9C, ps, 0, 0)              # contexto inicial
    struct.pack_into("<Hhh", b, 0xA2, ps, 0, 0)              # contexto de bucle (sin bucle: igual)
    struct.pack_into("<I", b, 0xC4, total - 0xC0)
    return bytes(b) + cuerpo
