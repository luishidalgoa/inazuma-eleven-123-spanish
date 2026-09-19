"""v08 · exploración: huecos actuales de +16 en v05 y viabilidad del modelo compacto (estricto / relajado)."""
import collections
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import comun08 as K  # noqa: E402
import modelo8 as M8  # noqa: E402

A88, A89, R = K.A88, K.A89, K.R
reg, F, antes, tmp = K.cargar_fuentes()
codec = A89.Codec(reg['bigramas'])
get = K.comun88.abrir(K.CAND)
L8 = M8.Letras8(F[K.F8], A88.codepoint)
pares = A88.Pares(F)
mq = A89.Maqueta(F[K.F12], A88.codepoint)
DUMMY = 'ダミー'.encode('cp932')


def f8_existente(e):
    Fu = F[K.F8]
    gi = Fu.gi(int(e['unicode'][2:], 16))
    left, _, adv = Fu.metrics[gi]
    x0 = int((11 - adv) / 2) + left
    sol = [x for y, row in enumerate(Fu.bitmap(gi)) for x, v in enumerate(row) if v >= 8]
    return x0 + min(sol), max(sol) - min(sol) + 1


fijos = collections.defaultdict(list)
for e in reg['bigramas']:
    if K.F8 in e['fuentes'] and K.F12T in e['fuentes'] and not R.variante(A89.clave_de(e)) and len(A89.clave_de(e)) == len(e['par']):
        o, w = f8_existente(e)
        fijos[e['par']].append((o, w, A89.clave_de(e)))


def textos16():
    out = collections.Counter()
    actuales = {}
    for juego in ('ie1', 'ie2'):
        ub = get(K.UNIT[juego])
        for i in range((len(ub) - 96) // 96):
            r = ub[96 + i * 96:192 + i * 96]
            if i == 0 or DUMMY in r[:32]:
                continue
            body = r[16:32].split(b'\0')[0]
            if not body:
                continue
            cl = codec.claves(body)
            if None in cl:
                continue
            t = ''.join(R.texto(c) for c in cl)
            out[t] += 1
            actuales[t] = cl
    return out, actuales


@__import__('functools').lru_cache(None)
def valido_nombre(t):
    if len(t) == 1:
        return True
    if L8.trozo(t) is None or ' ' in t:
        return False
    if len(t) == 2:
        if pares.f12t(t) is None:
            return False
    elif pares.f12t(t) is None:
        return False
    return R.Maqueta.trozo(mq, t) is not None


def opciones_factory(omin, omax_fin, coste_nuevo):
    def opciones(t):
        out = []
        if len(t) == 1:
            nat = L8.nativa(t)
            if nat is None:
                return out
            out.append((nat[0], nat[1], False, False, 0.0, t))
        for o, w, clave in fijos.get(t, []):
            out.append((o, w, False, False, 0.0, clave))
        if valido_nombre(t):
            w = L8.trozo(t)['w']
            for o in range(omin, omax_fin - w + 2):
                out.append((o, w, False, False, coste_nuevo, ('N', t, o)))
        return out
    return opciones


def margen(o, prev, k):
    if o is not None:
        return 0.3 * abs(o - 2)
    r = -prev - 1
    return 0.0 if 0 <= r <= 3 else (0.8 * (r - 3) if r > 3 else 0.8 * -r)


def huecos(sel):
    out, prev = [], None
    for clave, o, w in sel:
        if clave == ' ':
            prev = None if prev is None else prev - 10
            continue
        if prev is not None:
            out.append(o - prev - 1)
        prev = o + w - 1 - 10
    return out


if __name__ == '__main__':
    ts, act = textos16()
    print('textos +16 distintos', len(ts))
    # huecos actuales
    hist = collections.Counter()
    malos = 0
    for t, cl in act.items():
        sel = []
        for c in cl:
            if c == ' ':
                sel.append((' ', None, 0))
                continue
            if len(c) == 1 and not R.variante(c):
                o, w = L8.nativa(c)
            else:
                e = next(x for x in reg['bigramas'] if A89.clave_de(x) == c)
                o, w = f8_existente(e)
            sel.append((c, o, w))
        h = huecos(sel)
        hist.update(h)
        if any(g > 3 for g in h):
            malos += 1
    print('actual: huecos', dict(sorted(hist.items())), 'nombres con hueco > 3:', malos)
    for nombre, (omin, omaxf) in {'estricto': (0, 9), 'relajado': (-3, 12), 'medio': (-1, 10)}.items():
        op = opciones_factory(omin, omaxf, 0.8)
        hist = collections.Counter()
        codigos = collections.Counter()
        malos, sin = 0, []
        for t in ts:
            c, sel = M8.particion(t, op, 3, margen, 7)
            if c == M8.INF:
                sin.append(t)
                continue
            h = huecos(sel)
            hist.update(h)
            if any(g > 3 for g in h):
                malos += 1
            codigos.update(s[0] for s in sel if isinstance(s[0], tuple))
        print(nombre, dict(sorted(hist.items())), 'malos', malos, 'sin', len(sin), sin[:5], 'códigos nuevos', len(codigos))
