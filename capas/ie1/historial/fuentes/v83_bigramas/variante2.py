"""Variante «natural+»: espaciado proporcional, al menos 2 px entre tintas, y partición óptima
(programación dinámica): mínimo de casillas; a igualdad, pares con más aire."""
import sys
from functools import lru_cache
from previsualizar import glifo, tinta, CELDA, lienzo, dibujar_actual, dibujar_bigramas, particion_a
import previsualizar as P

def par2(a, b):
    da, _, adva, pa = glifo(a); db, _, _, pb = glifo(b)
    xa, xb = da, adva + db
    if pa and pb:
        a1 = tinta(pa)[1]; b0 = tinta(pb)[0]
        if xb + b0 < xa + a1 + 3:
            xb = xa + a1 + 3 - b0
    px = {}
    for (x, y), v in pa.items(): px[(x + xa, y)] = v
    for (x, y), v in pb.items(): px[(x + xb, y)] = max(v, px.get((x + xb, y), 0))
    if not px: return {}, 0, 0
    x0 = min(x for x, _ in px); ancho = max(x for x, _ in px) - x0 + 1
    px = {(x - x0, y): v for (x, y), v in px.items()}
    if b == ' ': return px, ancho, 1
    if a == ' ': return px, ancho, CELDA - ancho - 1
    return px, ancho, (CELDA - ancho) // 2

def particion_opt(t):
    @lru_cache(None)
    def f(i):
        if i >= len(t): return (0, 0, ())
        c, s, r = f(i + 1); mejor = (c + 1, s, (t[i],) + r)
        if i + 1 < len(t):
            ancho = par2(t[i], t[i+1])[1]
            if ancho <= CELDA - 1:
                c, s, r = f(i + 2)
                cand = (c + 1, s + (CELDA - 1 - ancho) ** 0.5 * -1, (t[i:i+2],) + r)
                if cand[:2] < mejor[:2]: mejor = cand
        return mejor
    return list(f(0)[2])

def celdas(t):
    out = []
    for p in particion_opt(t):
        if len(p) == 1:
            d, _, _, px = glifo(p); out.append({(x + d, y): v for (x, y), v in px.items()}); continue
        px, _, x0 = par2(*p); out.append({(x + x0, y): v for (x, y), v in px.items()})
    return out

for n, t in [('Aurelia', 'Aurelia'), ('Instituto_Wild', 'Instituto Wild'), ('H_de_negro', 'H. de negro'), ('Caseta_del_club', 'Caseta del club')]:
    a = dibujar_actual(t); b, _ = dibujar_bigramas(t, 'natural'); c = celdas(t)
    filas = [(f'actual ({len(a)})', a, len(a)), (f'natural ({len(b)})', b, len(a)), (f'natural+ ({len(c)}) {"|".join(particion_opt(t))}', c, len(a))]
    lienzo(filas, len(a)).save(str(__import__('pathlib').Path(__file__).parent / f'previews/v2_{n}.png'))
