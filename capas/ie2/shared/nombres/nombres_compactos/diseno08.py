"""IE2 v08 · diseño de casillas compactas (nombres +16 y rótulos) sobre las fuentes actuales.

Campos:
  nombre  unitbase +16 de IE1 e IE2 (pestaña del hablante, FONT8 a 10 px; listas FONT12; partido FONT12T).
          Casilla = 1-3 caracteres. FONT8: núcleo en las columnas [0, 10] del lápiz (la pestaña rasteriza cada
          glifo en su celda de VRAM de 8 u. DS x 1,5625 = 12,5 px: fuera de ella se recorta). FONT12: maqueta
          v89 (paso 15). FONT12T: relleno de FONT12 con contorno, <= 16 px (ver f12t).
  rotulo  eve 0x4037 arg 3 (FONT8 a 10 px, pantalla inferior: celda de 8 u. DS x 1,25 = 10 px): núcleo en
          [0, 10] como los 14 pares de rótulo de v88 ya publicados («ra», «ta»...; la columna 10 podría
          recortarse si la celda de VRAM mide 10 px: pendiente de ver en Azahar). Casilla = 1-4 caracteres (espacios incluidos). FONT12 (maqueta v89) por coherencia del registro.
Opciones de cada trozo: letra nativa (sin código), código del registro ya dibujado en FONT8 (sin coste) o
casilla nueva (texto, columna) con coste; varias rondas abaratan las casillas más repetidas para compartir
códigos.
"""
from __future__ import annotations

import collections
from functools import lru_cache

import comun08 as K
import modelo8 as M8

A88, A89, R = K.A88, K.A89, K.R
F12, F8, F12T = K.F12, K.F8, K.F12T
PREF = ''
RANGO = {'nombre': (0, 10), 'rotulo': (0, 10)}   # rótulo: como los pares de v88 ya publicados (núcleo hasta la columna 10)
BMAX = {'nombre': 10, 'rotulo': 10}
LARGO = {'nombre': 3, 'rotulo': 4}
PASO12 = 15
SOLIDO12 = 5


def clave_nueva(t, o):
    return f'{PREF}{o:+d}{PREF}{t}'


def de_clave(c):
    """(texto, columna) de una clave v08, o None."""
    if not c.startswith(PREF):
        return None
    _, o, t = c.split(PREF, 2)
    return t, int(o)


class Diseno:
    def __init__(self, reg, F):
        self.reg = reg
        self.F = F
        self.L8 = M8.Letras8(F[F8], K.cp)
        self.mq = A89.Maqueta(F[F12], K.cp)
        self.coste = {}                    # clave nueva -> coste
        self.coste_def = 1.2
        self.prohibidos = collections.defaultdict(set)   # texto completo -> trozos prohibidos
        self.por_clave = {A89.clave_de(e): e for e in reg['bigramas']}
        self.fijos = collections.defaultdict(list)       # trozo -> [(o, w, clave, tiene_f12t)]
        for c, e in self.por_clave.items():
            if F8 not in e['fuentes']:
                continue
            o, w = self.medir8(e)
            self.fijos[e['par']].append((o, w, c, F12T in e['fuentes']))

    # ------------------------------------------------------------------ medidas
    def medir8(self, e):
        Fu = self.F[F8]
        gi = Fu.gi(int(e['unicode'][2:], 16))
        left, _, adv = Fu.metrics[gi]
        x0 = int((11 - adv) / 2) + left
        sol = [x for row in Fu.bitmap(gi) for x, v in enumerate(row) if v >= M8.SOLIDO]
        return x0 + min(sol), max(sol) - min(sol) + 1

    @lru_cache(None)
    def f12t(self, t):
        """Trozo en estilo FONT12T: relleno de las letras de FONT12 (alfa >= 6) bajado 1 fila, contorno de
        1 px, 2 px entre rellenos (1 si no cabe), espacio = 4 px entre rellenos. Ancho con contorno <= 16.
        Columna D: centrado en 15 (<= 15 px) o 0 (16 px); «x » D = 0; « x» D = 15 - W (>= 0).
        Devuelve (px, W, D) o None. Con paso 15 y D >= 0, dos casillas vecinas solo pueden compartir una
        columna de contorno (rellenos separados >= 1 px), como el contorno compartido dentro de un par."""
        partes = []
        for ch in t.strip(' '):
            if ch == ' ':
                partes.append(None)
                continue
            L = self.mq.letra(ch)
            if L is None:
                return None
            fill = {(x, y) for (x, y), v in L[0].items() if v >= 6}
            if not fill:
                return None
            partes.append(fill)
        for sep in (2, 1):
            fill, x, esp = set(), 1, False
            for pt in partes:
                if pt is None:
                    esp = True
                    continue
                if esp:
                    x += 4 - sep
                    esp = False
                x0 = min(a for a, _ in pt)
                x1 = max(a for a, _ in pt)
                fill |= {(a - x0 + x, b + 1) for a, b in pt}
                x += (x1 - x0 + 1) + sep
            borde = {(a + da, b + db) for (a, b) in fill for da in (-1, 0, 1) for db in (-1, 0, 1)} - fill
            todo = fill | borde
            x0 = min(a for a, _ in todo)
            W = max(a for a, _ in todo) - x0 + 1
            if W > 16:
                continue
            if t.endswith(' ') and not t.startswith(' '):
                D = 0
            elif t.startswith(' ') and not t.endswith(' '):
                D = max(0, 15 - W)
            else:
                D = max(0, (15 - W) // 2)
            px = {}
            for (a, b) in borde:
                if 0 <= b <= 16:
                    px[(a - x0, b)] = 0x0F
            for (a, b) in fill:
                if 0 <= b <= 16:
                    px[(a - x0, b)] = 0xFF
            return px, W, D
        return None

    @lru_cache(None)
    def f12(self, t):
        """Maqueta FONT12 de un trozo nuevo: letra suelta = copia de la nativa; si no, trozo de v89."""
        if len(t) == 1:
            if t == K.APOSTROFO:
                return self._letra12(t)
            return 'nativa' if self.mq.nativa(t) is not None else None
        if '  ' in t:
            return None
        return R.Maqueta.trozo(self.mq, t)

    def _letra12(self, t):
        """Maqueta FONT12 de una letra sin glifo nativo (apóstrofo): centrada en la casilla de 15."""
        p, s0, s1, f0, f1, _ = self.mq.letra(t)
        ancho = f1 - f0 + 1
        D = (15 - ancho) // 2
        return dict(px={(x - f0, y): v for (x, y), v in p.items()}, S0=D + s0 - f0, S1=D + s1 - f0, D=D,
                    ancho=ancho, g=None)

    @lru_cache(None)
    def valido(self, t, campo):
        if t == ' ' or self.L8.trozo(t) is None or self.f12(t) is None:
            return False
        if campo == 'nombre' and self.f12t(t) is None:
            return False
        if campo == 'nombre' and len(t) > 1 and t.count(' ') > 0 and len(t.strip(' ')) == 0:
            return False
        return True

    # ------------------------------------------------------------------ opciones y partición
    def opciones(self, campo, texto):
        omin, omax = RANGO[campo]
        prohib = self.prohibidos.get((campo, texto), set())

        def op(t):
            out = []
            lead, trail = t.startswith(' '), t.endswith(' ')
            if len(t) == 1 and t not in (' ', K.APOSTROFO):
                nat = self.L8.nativa(t)
                if nat is not None and t not in prohib:
                    out.append((nat[0], nat[1], False, False, 0.0, t))
            for o, w, c, t3 in self.fijos.get(t, ()):
                if c in prohib or (campo == 'nombre' and not t3 and self.f12t(t) is None):
                    continue
                if campo == 'rotulo' and not (0 <= o and o + w - 1 <= 10):
                    continue
                out.append((o, w, lead, trail, 0.0, c))
            if self.valido(t, campo):
                w = self.L8.trozo(t)['w']
                for o in range(omin, omax - w + 2):
                    c = clave_nueva(t, o)
                    if c in prohib:
                        continue
                    out.append((o, w, lead, trail, self.coste.get(c, self.coste_def), c))
            return out
        return op

    @staticmethod
    def margen_nombre(o, prev, k):
        if o is not None:
            return 0.3 * abs(o - 2)
        r = -prev - 1
        return 0.0 if 0 <= r <= 3 else (0.8 * (r - 3) if r > 3 else 0.8 * -r)

    @staticmethod
    def margen_rotulo(o, prev, k):
        return 0.0

    def partir(self, campo, texto, n_max):
        margen = self.margen_nombre if campo == 'nombre' else self.margen_rotulo
        coste, sel = M8.particion(texto, self.opciones(campo, texto), LARGO[campo], margen, n_max)
        return coste, list(sel)

    # ------------------------------------------------------------------ comprobaciones de solape
    def texto_de(self, c):
        if c == ' ':
            return ' '
        d = de_clave(c)
        if d:
            return d[0]
        if c in self.por_clave:
            return self.por_clave[c]['par']
        return c

    @lru_cache(None)
    def ext12(self, c):
        """(S0, S1) sólidos en FONT12 a paso 15 (None si no hay tinta)."""
        if c == ' ':
            return None
        if c in self.por_clave:
            e = self.por_clave[c]
            m = A89.medir(self.F[F12], self.F[F12].gi(int(e['unicode'][2:], 16)))
            return m['S0'], m['S1']
        t = self.texto_de(c)
        m = self.f12(t)
        if m == 'nativa':
            return self.mq.nativa(t)
        return m['S0'], m['S1']

    @lru_cache(None)
    def ext12t(self, c):
        """(x0, x1) de toda la tinta (contorno incluido) en FONT12T a paso 15."""
        if c == ' ':
            return None
        Fu = self.F[F12T]
        if len(c) == 1 or (c in self.por_clave and F12T in self.por_clave[c]['fuentes']):
            cp = A88.codepoint(c) if len(c) == 1 else int(self.por_clave[c]['unicode'][2:], 16)
            gi = Fu.gi(cp)
            left, _, adv = Fu.metrics[gi]
            x0 = int((16 - adv) / 2) + left
            xs = [x for row in Fu.bitmap(gi) for x, v in enumerate(row) if v]
            return (x0 + min(xs), x0 + max(xs)) if xs else None
        px, W, D = self.f12t(self.texto_de(c))
        return D, D + W - 1

    def fallos(self, sel, campo):
        """Trozos a prohibir por solape: FONT8 a 10 y 9 px (hueco >= 1), FONT12 a 15 (>= 1),
        FONT12T a 15 (tinta con contorno >= -1: como mucho una columna de contorno compartida)."""
        malos = set()
        claves = [c for c, _, _ in sel]
        if campo != 'nombre':
            return malos          # el rótulo usa siempre paso 10 (0x2ed24); solo los nombres pasan por 0xe6214
        # FONT8 a 9 px (pantalla inferior): los huecos de 10 px bajan 1 por casilla
        prev = None
        for c, o, w in sel:
            if c == ' ':
                prev = None if prev is None else prev - 9
                continue
            if prev is not None and o - prev - 1 < 1:
                malos.add(c)
            prev = o + w - 1 - 9
        for ext, minimo in ((self.ext12, 1), (self.ext12t, -1)):
            prev, pc = None, None
            for c in claves:
                e = ext(c)
                if e is None:
                    if prev is not None:
                        prev -= PASO12
                    continue
                if prev is not None and e[0] - prev - 1 < minimo:
                    malos |= {x for x in (c, pc) if len(x) > 1 or x.startswith(PREF)}
                prev, pc = e[1] - PASO12, c
        return malos

    def huecos8(self, sel):
        """[(hueco, es_palabra)] en FONT8 a 10 px."""
        out, prev, pal = [], None, False
        for c, o, w in sel:
            if c == ' ':
                prev = None if prev is None else prev - 10
                pal = True
                continue
            t = self.texto_de(c)
            if prev is not None:
                out.append((o - prev - 1, pal or t.startswith(' ')))
            prev = o + w - 1 - 10
            pal = t.endswith(' ')
        return out
