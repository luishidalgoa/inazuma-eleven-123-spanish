import sys, json, collections
sys.path.insert(0, '.')
import comun08 as K
A88, A89, R = K.A88, K.A89, K.R
reg, F, antes, tmp = K.cargar_fuentes()
codec = A89.Codec(reg['bigramas'])
get = K.comun88.abrir(K.CAND)
F8 = F[K.F8]

def celda8(c):
    """px relativos al lápiz en FONT8 de una clave (letra o código)."""
    if len(c) == 1:
        gi = F8.gi(A88.codepoint(c))
    else:
        gi = F8.gi(int(codec_e[c]['unicode'][2:], 16))
    if gi is None:
        return None
    left, _, adv = F8.metrics[gi]
    x0 = int((11 - adv) / 2) + left
    return {(x + x0, y): v for y, row in enumerate(F8.bitmap(gi)) for x, v in enumerate(row) if v}

codec_e = {A89.clave_de(e): e for e in reg['bigramas']}

def huecos8(cel):
    out, prev = [], None
    for k, c in enumerate(cel):
        px = celda8(c)
        sol = [x + 10 * k for (x, _), v in (px or {}).items() if v >= 8]
        if not sol:
            prev = None if c != ' ' else prev
            continue
        if prev is not None:
            out.append(min(sol) - prev - 1)
        prev = max(sol)
    return out

if __name__ == '__main__':
    for juego in ('ie1', 'ie2'):
        ub = get(K.UNIT[juego])
        n = (len(ub) - 96) // 96
        stats = collections.Counter()
        ejemplos = {}
        for i in range(n):
            r = ub[96 + i * 96:192 + i * 96]
            for off in (0, 16):
                body = r[off:off + 16].split(b'\0')[0]
                if not body:
                    continue
                cl = codec.claves(body)
                if None in cl:
                    stats['opaco'] += 1
                    continue
                t = ''.join(R.texto(c) for c in cl)
                if t in ('Silvia', 'Axel', 'Mark', 'Nathan', 'Celia', 'Jude', 'Shawn', 'Jack', 'Aurelia') and off == 16:
                    ejemplos.setdefault(t, []).append((i, '|'.join(cl), huecos8(cl), len(body)))
        for t, v in ejemplos.items():
            print(juego, t, v[:3])
