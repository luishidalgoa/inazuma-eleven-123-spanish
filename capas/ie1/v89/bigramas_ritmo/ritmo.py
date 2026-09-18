"""v89 · ritmo uniforme a paso fijo de 15 px (FONT12): maquetación de «trozos» y partición por coste de huecos.

Problema de v88 (visto por el usuario): pares con >= 2 px entre letras y tinta <= 14 dejaban fuera casi todos
los pares de minúsculas anchas («cu», «en», «es»), así que muchas palabras llevaban letras sueltas centradas
en su casilla de 15 px (10 px de aire) -> «S u gran c u erpo».

Modelo v89:
- Cada casilla dibuja un TROZO del texto de 1 a 4 caracteres (letras/puntuación y, como mucho, un espacio en
  un borde o en medio). Dentro del trozo, 2 px sólidos entre letras (1 px si con 2 no cabe en 13), un espacio
  interior vale ESP px. Tinta total (con antialias) <= 15 columnas.
- Colocación fija por trozo (un código = una tinta): solo letras -> centrado; espacio delante -> la tinta
  acaba en la columna 13 (se pega a la casilla siguiente); espacio detrás -> empieza en la columna 1.
  Un trozo con espacio en el borde debe dejar sitio a la separación: tinta sólida <= 15 - PAL_MIN.
- Hueco entre casillas (sólido, alfa >= 5) = 15 + S0(sig) - S1(ant) - 1 (+15 por cada casilla de espacio
  nativa entre ambas). Dentro de palabra se busca 1-2 px (0 prohibido); entre palabras 4-8 px.
- Partición: programación dinámica sobre (posición, S1 anterior) minimizando el coste de los huecos.
"""
from __future__ import annotations

from functools import lru_cache

CELDA = 15
SOLIDO = 5
ESP = 5            # espacio interior de un trozo
PAL_MIN = 4        # hueco mínimo entre palabras
INF = float('inf')
IZQ, DER = '\ue000', '\ue001'   # prefijos de las variantes de un solo glifo (alineado a la izquierda/derecha)


def texto(c):
    """Texto real de una clave de casilla (sin marcas de variante)."""
    return c[1:] if c[:1] in (IZQ, DER) else c


def variante(c):
    return c[:1] in (IZQ, DER)


class Maqueta:
    def __init__(self, F12, cp):
        self.F = F12
        self.cp = cp

    @lru_cache(None)
    def letra(self, ch):
        """(px desde la columna 0 del bitmap, s0, s1, f0, f1, x0 nativo) o None."""
        gi = self.F.gi(self.cp(ch))
        if gi is None:
            return None
        left, _, adv = self.F.metrics[gi]
        px = {(x, y): v for y, row in enumerate(self.F.bitmap(gi)) for x, v in enumerate(row) if v}
        sol = [x for (x, _), v in px.items() if v >= SOLIDO]
        if not sol:
            return None
        xs = [x for x, _ in px]
        x0 = int((CELDA - adv) / 2) + left
        return px, min(sol), max(sol), min(xs), max(xs), x0

    @lru_cache(None)
    def nativa(self, ch):
        """(S0, S1) sólidos de la letra nativa en su casilla, o None si no tiene tinta (espacio)."""
        L = self.letra(ch)
        if L is None:
            return None
        _, s0, s1, _, _, x0 = L
        return x0 + s0, x0 + s1

    @lru_cache(None)
    def trozo(self, t):
        """Maqueta de un trozo de >= 2 caracteres: dict(px, S0, S1, D, ancho, g) o None si no vale."""
        if variante(t):
            L = self.letra(t[1])
            if L is None or len(t) != 2:
                return None
            p, s0, s1, f0, f1, _ = L
            w = s1 - s0 + 1
            shift = -s0 if t[0] == IZQ else (CELDA - 1) - s1
            shift = max(shift, -f0)
            shift = min(shift, CELDA - 1 - f1)
            return dict(px={(x - f0, y): v for (x, y), v in p.items()}, S0=shift + s0, S1=shift + s1,
                        D=shift + f0, ancho=f1 - f0 + 1, g=None)
        if len(t) < 2 or t.strip(' ') == '' or '  ' in t:
            return None
        lead, trail = t[0] == ' ', t[-1] == ' '
        core = t.strip(' ')
        if lead and trail and len(core) < 1:
            return None
        for g in (2, 1):
            px, fin, espacio = {}, None, False
            ok = True
            for ch in core:
                if ch == ' ':
                    espacio = True
                    continue
                L = self.letra(ch)
                if L is None:
                    ok = False
                    break
                p, s0, s1, _, _, _ = L
                off = -s0 if fin is None else fin + 1 + (ESP if espacio else g) - s0
                for (x, y), v in p.items():
                    q = (x + off, y)
                    px[q] = max(v, px.get(q, 0))
                fin = off + s1
                espacio = False
            if not ok:
                return None
            w = fin + 1
            xs = [x for x, _ in px]
            f0, f1 = min(xs), max(xs)
            if f1 - f0 + 1 > CELDA:
                continue
            limite = 13 if not (lead or trail) else CELDA - PAL_MIN
            if g == 2 and w > limite:
                continue
            if (lead or trail) and w > CELDA - PAL_MIN:
                return None
            if lead and not trail:
                shift = 13 - (w - 1)
            elif trail and not lead:
                shift = 1
            else:
                shift = (CELDA - w) // 2
            shift = max(shift, -f0)
            shift = min(shift, CELDA - 1 - f1)
            if shift + f0 < 0:
                return None
            D = shift + f0
            pix = {(x - f0, y): v for (x, y), v in px.items()}
            return dict(px=pix, S0=shift, S1=shift + w - 1, D=D, ancho=f1 - f0 + 1, g=g)
        return None

    def extremos(self, c):
        """(S0, S1) sólidos de la casilla c (trozo, variante o letra), None si no tiene tinta."""
        if len(c) == 1:
            return self.nativa(c)
        m = self.trozo(c)
        return (m['S0'], m['S1'])


def coste_hueco(g, palabra):
    if palabra:
        if g < PAL_MIN:
            return INF
        return 1.0 * max(0, 5 - g) + 0.15 * max(0, g - 8) ** 2
    if g < 1:
        return INF
    return (0.0, 0.0, 0.8, 3.0, 6.0)[g - 1] if g <= 5 else 6.0 + 2.5 * (g - 5)


def particion(t, mq, admitido, largo_max=4):
    """Partición de t (sin opacos) en casillas. admitido(c) -> bool para trozos de >= 2 caracteres.
    Devuelve (coste, [casillas])."""
    n = len(t)

    def es_palabra(i):
        return t[i - 1] == ' ' or t[i] == ' '

    @lru_cache(None)
    def f(i, s1):
        if i >= n:
            return 0.0, ()
        mejor = (INF, ())
        opciones = []
        for k in range(1, largo_max + 1):
            if i + k > n:
                break
            opciones.append((k, t[i:i + k]))
            if k == 1 and t[i] != ' ':
                opciones += [(1, IZQ + t[i]), (1, DER + t[i])]
        for k, c in opciones:
            if k == 1 and not variante(c):
                ext = mq.nativa(c) if c != ' ' else None
                if c != ' ' and ext is None:
                    continue
            else:
                if not admitido(c) or mq.trozo(c) is None:
                    continue
                ext = mq.extremos(c)
            if ext is None:            # casilla de espacio nativa: arrastra el S1 anterior
                nuevo = None if s1 is None else s1 - CELDA
                cst = 0.0
            else:
                cst = 0.0 if s1 is None else coste_hueco(CELDA + ext[0] - s1 - 1, es_palabra(i))
                nuevo = ext[1]
            if cst == INF:
                continue
            resto, cel = f(i + k, nuevo)
            total = cst + resto + (0.05 if variante(c) else 0.0)   # variantes solo si mejoran
            if total < mejor[0]:
                mejor = (total, (c,) + cel)
        return mejor

    return f(0, None)


def huecos(cel, mq):
    """[(hueco, es_palabra)] de una lista de casillas (None = opaco, corta)."""
    out, s1, pal = [], None, False
    for c in cel:
        if c is None:
            s1 = None
            continue
        ext = mq.extremos(c) if c != ' ' else None
        palabra = texto(c)[0] == ' ' or pal
        if ext is None:
            if s1 is not None:
                s1 -= CELDA
            pal = True
            continue
        if s1 is not None:
            out.append((CELDA + ext[0] - s1 - 1, palabra))
        s1 = ext[1]
        pal = c[-1] == ' '
    return out
