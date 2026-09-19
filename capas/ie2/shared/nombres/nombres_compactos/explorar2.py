import collections, sys, time
sys.path.insert(0, '.')
import explorar as X, modelo8 as M8
ts, act = X.textos16()
for rng in [(0, 9), (0, 10)]:
    t0 = time.time()
    extra = {}
    for ronda in range(3):
        def op(t, _base=X.opciones_factory(*rng, 0.8)):
            out = []
            for o, w, l, tr, c, clave in _base(t):
                if isinstance(clave, tuple):
                    c = extra.get(clave, 1.2)
                out.append((o, w, l, tr, c, clave))
            return out
        uso = collections.Counter(); malos = 0; hist = collections.Counter()
        for t, n in ts.items():
            c, sel = M8.particion(t, op, 3, X.margen, 7)
            h = X.huecos(sel); hist.update(h)
            malos += any(g > 3 for g in h) and ' ' not in t
            uso.update(s[0] for s in sel if isinstance(s[0], tuple))
        print(rng, ronda, 'códigos', len(uso), 'malos', malos, dict(sorted(hist.items())), round(time.time()-t0))
        extra = {k: (0.1 if v >= 3 else 0.6) for k, v in uso.items()}
