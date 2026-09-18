"""IE2 v22 · modelo de casillas a paso fijo para los menús (FONT12, 15 px) y la caja Pasión/Amistad (FONT8, 10 px).

Colocación (la misma que usan v08/v20, ina_main2.cro 0x121a78 con anchura forzada):
    columna de un píxel = lápiz + trunc((CAJA - advance) / 2) + left + columna del mapa de bits
FONT12: paso 15, CAJA 15. FONT8: paso 10, CAJA 11.

Una palabra se reparte en casillas de 1-3 letras. Cada casilla es:
  - la letra nativa (ancho completo, 2 B),
  - un código del registro ya dibujado en esa fuente con ese texto (2 B, colocación fija medida en la fuente),
  - un carácter ASCII de 1 B (solo si se permite y solo al final de la palabra),
  - un código NUEVO (2 B) con la tinta dibujada por nosotros en la columna que se elija.
Huecos medidos en columnas de tinta (FONT12: alfa >= 1, es decir sin que se toquen ni con el antialias;
FONT8: núcleo alfa >= 8, el halo es de 1 px). Con paso fijo cada casilla (salvo la última) tiene que llenar
casi todo el paso con tinta para que el hueco siguiente sea pequeño, así que el hueco entre casillas puede
crecer: el coste es el de v89 (1-2 px gratis, 3 px 0.8, 4 px 3, 5 px 6...) y reparte la holgura, también
dentro de las casillas nuevas (hueco interno 1-3 px), para que la palabra quede pareja. Nunca 0 px.
La primera tinta de la palabra empieza en la columna 0-1 del lápiz (alineado a la izquierda).
"""
from __future__ import annotations

from functools import lru_cache

INF = float('inf')
IZQ_MAX = 4        # una casilla nueva puede empezar hasta 4 px antes de su lápiz (como «on»/«en» de v89)
DER_MAX = 2        # y acabar hasta 2 px después del final de su paso


class Modelo:
    def __init__(self, F, nombre, paso, caja, umbral, cols, huecos, coste_hueco, codepoint, internos):
        self.F, self.nombre, self.paso, self.caja = F, nombre, paso, caja
        self.umbral, self.cols = umbral, cols          # alfa mínimo que cuenta como tinta; columnas útiles
        self.huecos, self.coste_hueco = huecos, coste_hueco
        self.internos = internos                       # huecos internos con que se dibuja una casilla nueva
        self.cp = codepoint

    # ---------------------------------------------------------------- medidas
    def columnas(self, gi):
        """{columna relativa al lápiz: alfa máximo} del glifo gi tal como lo coloca el motor."""
        left, _, adv = self.F.metrics[gi]
        x0 = int((self.caja - adv) / 2) + left
        out = {}
        for row in self.F.bitmap(gi):
            for x, v in enumerate(row):
                if v:
                    out[x0 + x] = max(v, out.get(x0 + x, 0))
        return out

    def perfil(self, cols):
        """(S0, S1, [huecos internos]) con el umbral de tinta; None si no hay tinta."""
        xs = sorted(x for x, v in cols.items() if v >= self.umbral)
        if not xs:
            return None
        runs, ini = [], xs[0]
        for a, b in zip(xs, xs[1:]):
            if b != a + 1:
                runs.append((ini, a))
                ini = b
        runs.append((ini, xs[-1]))
        return xs[0], xs[-1], [runs[k + 1][0] - runs[k][1] - 1 for k in range(len(runs) - 1)]

    @lru_cache(None)
    def letra(self, ch):
        """(px {(x, y): v} con la tinta (umbral) desde x = 0, ancho de tinta) de la letra nativa."""
        gi = self.F.gi(self.cp(ch))
        if gi is None:
            return None
        px = {(x, y): v for y, row in enumerate(self.F.bitmap(gi)) for x, v in enumerate(row) if v}
        sol = [x for (x, _), v in px.items() if v >= self.umbral]
        if not sol:
            return None
        c0, c1 = min(sol), max(sol)
        return {(x - c0, y): v for (x, y), v in px.items()}, c1 - c0 + 1

    def fija(self, gi, n_letras):
        """Opción de colocación fija (código existente o letra nativa): (S0, S1) o None si no vale."""
        p = self.perfil(self.columnas(gi))
        if p is None:
            return None
        s0, s1, internos = p
        if len(internos) != n_letras - 1 or any(g not in self.huecos for g in internos):
            return None        # letras que se tocan (menos tramos que letras) o huecos fuera de rango
        return s0, s1, tuple(internos)

    @lru_cache(None)
    def nueva(self, t, g):
        """Dibujo de una casilla nueva con el texto t y hueco interno g: (px desde la tinta, ancho) o None."""
        px, cur = {}, 0
        for ch in t:
            L = self.letra(ch)
            if L is None:
                return None
            p, w = L
            for (x, y), v in p.items():
                q = (x + cur, y)
                px[q] = max(v, px.get(q, 0))
            cur += w + g
        w = cur - g
        xs = [x for x, _ in px]
        if w > self.cols or max(xs) - min(xs) + 1 > self.cols + 1:
            return None
        return px, w


class Solucion:
    def __init__(self, coste, casillas):
        self.coste, self.casillas = coste, casillas     # casillas: [dict(t, tipo, s0, s1, bytes, ...)]

    @property
    def bytes(self):
        return sum(c['bytes'] for c in self.casillas)


def resolver(M, palabra, opciones_fijas, lam, ascii_final=None, izquierda=(0, 1), max_bytes=None, largo=3):
    """Mejor partición de `palabra` para cada tamaño en bytes: {bytes: Solucion}.
    opciones_fijas(t) -> [(clave, gi, sjis)] de códigos existentes con ese texto.
    ascii_final(ch) -> gi del glifo ASCII de 1 B (o None)."""
    n = len(palabra)

    @lru_cache(None)
    def opciones(i, L):
        t = palabra[i:i + L]
        out = []
        if L == 1:
            gi = M.F.gi(M.cp(t))
            if gi is not None:
                f = M.fija(gi, 1)
                if f:
                    out.append(dict(t=t, tipo='nativa', s0=f[0], s1=f[1], bytes=2, coste=0.0, internos=f[2]))
            if ascii_final and i + L == n:
                ga = ascii_final(t)
                if ga is not None:
                    f = M.fija(ga, 1)
                    if f:
                        out.append(dict(t=t, tipo='ascii', s0=f[0], s1=f[1], bytes=1, coste=0.0, internos=f[2]))
        for clave, gi, sjis in opciones_fijas(t):
            f = M.fija(gi, L)
            if f:
                c = sum(M.coste_hueco(g) for g in f[2])
                out.append(dict(t=t, tipo='registro', clave=clave, sjis=sjis, s0=f[0], s1=f[1], bytes=2,
                                coste=c, internos=f[2]))
        for g in sorted(M.internos):
            d = M.nueva(t, g)
            if d is None:
                continue
            px, w = d
            for D in range(-IZQ_MAX, M.cols - w + 1 + DER_MAX):
                out.append(dict(t=t, tipo='nueva', g=g, D=D, s0=D, s1=D + w - 1, bytes=2,
                                coste=lam + (L - 1) * M.coste_hueco(g), internos=(g,) * (L - 1)))
        return out

    @lru_cache(None)
    def f(i, s1):
        """{bytes: (coste, casillas)} desde la letra i con la tinta anterior acabando en s1 (rel. al lápiz)."""
        if i >= n:
            return {0: (0.0, ())}
        res = {}
        for L in range(1, largo + 1):
            if i + L > n:
                break
            for o in opciones(i, L):
                if s1 is None:
                    if o['s0'] not in izquierda:
                        continue
                    cst = 0.0
                else:
                    g = M.paso + o['s0'] - s1 - 1
                    if g not in M.huecos:
                        continue
                    cst = M.coste_hueco(g)
                for b, (c, cel) in f(i + L, o['s1']).items():
                    bb = b + o['bytes']
                    if max_bytes is not None and bb > max_bytes:
                        continue
                    tot = cst + o['coste'] + c
                    if bb not in res or tot < res[bb][0]:
                        res[bb] = (tot, (o,) + cel)
        return res

    return {b: Solucion(c, list(cel)) for b, (c, cel) in f(0, None).items()}


def huecos_de(M, casillas):
    """Todos los huecos (internos y entre casillas) de una solución, en orden."""
    out, prev = [], None
    for c in casillas:
        if prev is not None:
            out.append(M.paso + c['s0'] - prev - 1)
        out.extend(c['internos'])
        prev = c['s1']
    return out
