"""v08 · calibración del dibujo de la ficha (descripción FONT12) con la captura del usuario de Mark (v05):
«C apitán del Raim on,» / « de pasión sinigual.». Prueba hipótesis de paso/colocación."""
import sys, struct
sys.path.insert(0, '.')
import comun08 as K
A88, A89, R = K.A88, K.A89, K.R
reg, F, antes, tmp = K.cargar_fuentes()
# la candidata v05 lleva la FONT12 de v90 (sin los subtítulos v07: no afecta a estos códigos)
import tempfile, pathlib
t = pathlib.Path(tempfile.mkdtemp())
(t / 'f.bcfnt').write_bytes((K.W / 'ie1/capas/v90/cro_restantes/extra/font/FONT12.bcfnt').read_bytes())
F12 = A88.cargar(t / 'f.bcfnt')
codec = A89.Codec(reg['bigramas'])
get = K.comun88.abrir(K.CAND)
ub = get(K.UNIT['ie1']); st = get('inazuma1/data_iz/logic/unitbase.STR')


def glifo(tok, t):
    if tok in codec.por_codigo:
        cp = int(next(e for e in reg['bigramas'] if e['sjis'] == tok.hex().upper())['unicode'][2:], 16)
    else:
        cp = A88.codepoint(t)
    gi = F12.gi(cp)
    left, width, adv = F12.metrics[gi]
    px = {(x, y): v for y, row in enumerate(F12.bitmap(gi)) for x, v in enumerate(row) if v}
    return left, width, adv, px


def simular(body, modo):
    lineas, pen, cur = [], 0, []
    for tok, t in codec.tokens(body):
        if tok == b'\n':
            lineas.append(cur); cur = []; pen = 0; continue
        left, width, adv, px = glifo(tok, t)
        if modo == 'fijo15':
            x = pen + int((15 - adv) / 2) + left; paso = 15
        elif modo == 'prop':
            x = pen + left; paso = adv
        elif modo == 'prop_w':
            x = pen + left; paso = left + width + 1
        elif modo == 'fijo15_izq':
            x = pen + left; paso = 15
        sol = [a + x for (a, _), v in px.items() if v >= 5]
        cur.append((t if len(tok) == 2 and tok not in codec.por_codigo else codec.por_codigo.get(tok, t), min(sol) if sol else None, max(sol) if sol else None))
        pen += paso
    lineas.append(cur)
    return lineas


def huecos(linea):
    out, prev = [], None
    for t, a, b in linea:
        if a is None:
            continue
        if prev is not None:
            out.append((prev[0] + '|' + t, a - prev[1] - 1))
        prev = (t, b)
    return out


r = ub[96:192]
off = struct.unpack_from('<H', r, 94)[0] * 32
body = st[off:st.index(b'\0', off)]
print(codec.texto(body))
for modo in ('fijo15', 'prop', 'prop_w', 'fijo15_izq'):
    print(modo)
    for l in simular(body, modo):
        print('   ', [(p, g) for p, g in huecos(l)], 'inicio', l[0][1])
