import sys, struct, itertools
sys.path.insert(0, '.')
from calibrar import *
toks = [(tok, t) for tok, t in codec.tokens(body)]
obs_big = {'C|ap', 'm|on'}
obs_small = {'ap|it', 'it|án', 'R|ai', 'ai|m', 'in |ig', 'ig|ua', 'pa|si', 'si|ón', ' d|el '}
obs_word = {'án| d', 'el |R', 'e |pa', 'ón| s'}
pasos = {f'c{s}': (lambda l, w, a, s=s: s) for s in (10, 11, 12, 13, 14, 15, 16)}
pasos.update({'adv': lambda l, w, a: a, 'wid': lambda l, w, a: w, 'lw': lambda l, w, a: l + w,
              'adv125': lambda l, w, a: a * 1.25, 'wid125': lambda l, w, a: w * 1.25})
xs = {'cent15': lambda pen, l, w, a: pen + int((15 - a) / 2) + l,
      'cent12': lambda pen, l, w, a: pen + int((12 - a) / 2) + l,
      'left': lambda pen, l, w, a: pen + l, 'orig': lambda pen, l, w, a: pen,
      'centw': lambda pen, l, w, a: pen + int((15 - w) / 2)}
res = []
for (pn, pf), (xn, xf) in itertools.product(pasos.items(), xs.items()):
    lineas, pen, cur = [], 0, []
    for tok, t in toks:
        if tok == b'\n':
            lineas.append(cur); cur = []; pen = 0; continue
        l, w, a, px = glifo(tok, t)
        x = int(xf(pen, l, w, a))
        sol = [p + x for (p, _), v in px.items() if v >= 5]
        name = codec.por_codigo.get(tok, t)
        cur.append((name, min(sol), max(sol)))
        pen += pf(l, w, a)
    lineas.append(cur)
    g = dict(p for l in lineas for p in huecos(l))
    score = sum(g[k] >= 5 for k in obs_big) * 2 + sum(g[k] <= 2 for k in obs_small) + sum(g[k] >= 4 for k in obs_word)
    score += 2 * (g['in |ig'] <= 1) + 2 * (lineas[1][0][1] - lineas[0][0][1] >= 4)
    res.append((score, pn, xn, g, lineas[0][0][1], lineas[1][0][1]))
res.sort(key=lambda r: -r[0])
for r in res[:8]:
    print(r[0], r[1], r[2], r[4], r[5], r[3])
