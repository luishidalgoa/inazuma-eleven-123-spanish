"""IE2 v08 · modelo de casillas compactas para FONT8 a paso fijo de 10 px (pestaña del hablante y rótulo).

Colocación real (ina_main1/2.cro, gestor data+188, FONT_TYPE 1; v87):
    x = lápiz + trunc((11 - advance)/2) + left,  lápiz = 10 px por casilla.
Una casilla dibuja un TROZO de 1-4 caracteres (nombres: 1-3 letras; rótulos: también espacios) con su
núcleo (alfa >= 8) empezando en la columna `o` relativa al lápiz. Dentro del trozo las letras van a 1 px
(como los pares de v87) y un espacio interior vale ESP px. El núcleo cabe en 10 columnas y el mapa de bits
en 11 (se recorta el halo exterior si hace falta, como «ta» en v87).

Objetivo (la pestaña de «Silvia», Si|lv|ia: huecos 1 dentro de casilla y 2-3 entre casillas):
    dentro de palabra, hueco entre casillas 1-3 px (2 preferido); entre palabras 4-5 px.
Partición por programación dinámica sobre (posición, fin de la tinta anterior relativo al lápiz).
"""
from __future__ import annotations

from functools import lru_cache

PASO = 10
CAJA = 11          # FINF width de FONT8
COLS = 11          # columnas útiles del mapa de bits (celda 12 con borde)
SOLIDO = 8
G_IN = 1
ESP = 4
MAX_NUCLEO = 11     # núcleo de 11 columnas: sin halo exterior
G_MIN = 2          # hueco mínimo entre casillas (con paso 9 px de la pantalla inferior queda en 1)
INF = float('inf')


def coste_hueco(g, palabra):
    if palabra:
        if g < 3:
            return INF
        return {3: 1.0, 4: 0.0, 5: 0.0, 6: 0.5, 7: 1.2}.get(g, 1.2 + 0.8 * (g - 7))
    if g < G_MIN:
        return INF
    return {2: 0.0, 3: 0.5, 4: 2.5, 5: 5.0}.get(g, 5.0 + 3.0 * (g - 5))


class Letras8:
    def __init__(self, F8, codepoint):
        self.F = F8
        self.cp = codepoint

    @lru_cache(None)
    def letra(self, ch):
        """(px con el núcleo desde x=0, ancho del núcleo, núcleo nativo relativo al lápiz) o None."""
        gi = self.F.gi(self.cp(ch))
        if gi is None:
            return None
        left, _, adv = self.F.metrics[gi]
        px = {(x, y): v for y, row in enumerate(self.F.bitmap(gi)) for x, v in enumerate(row) if v}
        sol = [x for (x, _), v in px.items() if v >= SOLIDO]
        if not sol:
            return None
        c0, c1 = min(sol), max(sol)
        x0 = int((CAJA - adv) / 2) + left
        return {(x - c0, y): v for (x, y), v in px.items()}, c1 - c0 + 1, x0 + c0

    def nativa(self, ch):
        L = self.letra(ch)
        if L is None:
            return None
        return L[2], L[1]            # (o, w)

    @lru_cache(None)
    def trozo(self, t):
        """Trozo compuesto: dict(px, w, lead, trail, ventana) o None si no cabe."""
        if not t or t.strip(' ') == '' or '  ' in t:
            return None
        lead, trail = t[0] == ' ', t[-1] == ' '
        core = t.strip(' ')
        px, cur, fin = {}, 0, None
        for ch in core:
            if ch == ' ':
                cur += ESP - G_IN
                continue
            L = self.letra(ch)
            if L is None:
                return None
            p, w, _ = L
            for (x, y), v in p.items():
                q = (x + cur, y)
                px[q] = max(v, px.get(q, 0))
            fin = cur + w - 1
            cur = fin + 1 + G_IN
        w = fin + 1
        if w > MAX_NUCLEO:
            return None
        return dict(px=px, w=w, lead=lead, trail=trail)

    def dibujo(self, t, o, bmax):
        """Mapa de bits del trozo t con el núcleo en la columna o: columnas del lápiz en [0, bmax]
        (se recorta solo halo). Devuelve (px desde la columna del mapa, columna inicial, left, width, advance)."""
        m = self.trozo(t)
        assert 0 <= o and o + m['w'] - 1 <= bmax, (t, o)
        abs_px = {(x + o, y): v for (x, y), v in m['px'].items()}
        fuera = [v for (x, _), v in abs_px.items() if not 0 <= x <= bmax]
        assert all(v < SOLIDO for v in fuera), (t, o)
        abs_px = {k: v for k, v in abs_px.items() if 0 <= k[0] <= bmax}
        c0 = min(x for x, _ in abs_px)
        c1 = max(x for x, _ in abs_px)
        assert c1 - c0 + 1 <= COLS
        adv = m['w'] + (4 if ' ' in t else 0)
        left = c0 - int((CAJA - adv) / 2)
        assert -128 <= left <= 127
        px = {(x - c0, y): v for (x, y), v in abs_px.items()}
        return px, c0, left, c1 - c0 + 1, adv


def particion(texto, opciones, largo_max, margen=None, n_max=None, paso=PASO, coste=None):
    """opciones(t) -> [(o, w, lead, trail, coste, clave)] para el trozo t (t de 1 carácter sin espacios
    incluye la letra nativa). Casilla de espacio nativa: clave ' '.
    margen(S0 primera, S1 última, n) -> coste de los bordes. Devuelve (coste, [(clave, o, w)])."""
    n = len(texto)
    coste = coste or coste_hueco

    @lru_cache(None)
    def f(i, prev, pal, k):
        # prev: fin de la tinta anterior relativo al lápiz actual (None al principio); pal: hay límite de
        # palabra pendiente; k: casillas usadas
        if i >= n:
            return (0.0, ()) if margen is None else (margen(None, prev, k), ())
        if n_max is not None and k >= n_max:
            return INF, ()
        mejor = (INF, ())
        if texto[i] == ' ':
            r = f(i + 1, None if prev is None else prev - paso, True, k + 1)
            if r[0] < mejor[0]:
                mejor = (r[0], ((' ', None, 0),) + r[1])
        for L in range(1, largo_max + 1):
            if i + L > n:
                break
            t = texto[i:i + L]
            for o, w, lead, trail, c, clave in opciones(t):
                palabra = pal or lead or (i > 0 and texto[i - 1] == ' ')
                if prev is None:
                    cst = 0.0 if margen is None else margen(o, None, None)
                else:
                    cst = coste(o - prev - 1, palabra)
                if cst == INF:
                    continue
                r = f(i + L, o + w - 1 - paso, trail, k + 1)
                tot = cst + c + r[0]
                if tot < mejor[0]:
                    mejor = (tot, ((clave, o, w),) + r[1])
        return mejor

    return f(0, None, False, 0)


def particion_libre(texto, opciones, largo_max, paso, coste, huecos_ok, margen_ini, lam=0.05, n_max=None,
                    margen_fin=None):
    """Como particion, pero las casillas libres se generan solo con las columnas que dan un hueco admisible.
    opciones(t) -> (fijas, libres): fijas = [(o, w, lead, trail, coste, clave)];
    libres = [(s0r, w, dmin, dmax, lead, trail, coste(d), clave(d))] (o = d + s0r).
    huecos_ok(palabra) -> huecos a probar; margen_ini(o) -> coste de la primera tinta (INF si no vale).
    Cada casilla suma `lam`; si el resultado pasa de n_max casillas se repite con lam mayor."""
    n = len(texto)
    for lam_i in (lam, 0.6, 2.5, 10.0):
        @lru_cache(None)
        def f(i, prev, pal):
            if i >= n:
                return (0.0 if margen_fin is None else margen_fin(prev)), ()
            mejor = (INF, ())
            if texto[i] == ' ':
                r = f(i + 1, None if prev is None else prev - paso, True)
                if r[0] + lam_i < mejor[0]:
                    mejor = (r[0] + lam_i, ((' ', None, 0),) + r[1])
            for L in range(1, largo_max + 1):
                if i + L > n:
                    break
                t = texto[i:i + L]
                fijas, libres = opciones(t)
                palabra = pal or t.startswith(' ') or (i > 0 and texto[i - 1] == ' ')
                cands = list(fijas)
                for s0r, w, dmin, dmax, lead, trail, cf, kf in libres:
                    if prev is None:
                        ds = range(dmin, dmax + 1)
                    else:
                        ds = [prev + 1 + g - s0r for g in huecos_ok(palabra)]
                    for d in ds:
                        if dmin <= d <= dmax:
                            cands.append((d + s0r, w, lead, trail, cf(d), kf(d)))
                for o, w, lead, trail, c, clave in cands:
                    if prev is None:
                        cst = margen_ini(o)
                    else:
                        cst = coste(o - prev - 1, palabra)
                    if cst == INF:
                        continue
                    r = f(i + L, o + w - 1 - paso, t.endswith(' '))
                    tot = cst + c + lam_i + r[0]
                    if tot < mejor[0]:
                        mejor = (tot, ((clave, o, w),) + r[1])
            return mejor
        res = f(0, None, False)
        if res[0] == INF or n_max is None or len(res[1]) <= n_max:
            return res
    return INF, ()
