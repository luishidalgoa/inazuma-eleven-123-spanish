"""IE2 v08 · descripciones de la ficha (unitbase.STR) en FONT12 a paso fijo de 15 px.

Dibujo (ina_main1.cro 0x12929c -> 0x2ed24, gestor 0x1ff2c4 = FONT12; búfer 0xa5c38(obj, 14, 2), 112 x 16 u.),
alineación izquierda, 2 líneas. Límite por línea: 18 casillas, el máximo del japonés (sin furigana) en los
2.399 registros de IE1 y de IE2 (v89 se quedó en 14; IE2 v03 llegó a 21). Paso de 15 px:
x = lápiz + trunc((15 - advance)/2) + left.
Queja del usuario sobre v89 (Mark): «C apitán del Raim on,» / « de pasión sinigual.»: letras nativas
centradas junto a trozos centrados dan 4-5 px dentro de palabra (casi como los 6 px de «sin igual») y una
variante alineada a la derecha abre la 2.ª línea como si hubiera un espacio.

Modelo v08 (como los nombres de FONT8): casilla = trozo de 1-4 caracteres con la composición de v89
(ritmo.Maqueta.trozo: 2 px entre letras, 1 si no cabe; espacio interior 5 px) colocado con su tinta en
cualquier columna D con la tinta dentro de [0, 14]. Objetivo: 1-2 px dentro de palabra (3 tolerado), 5-8 px
entre palabras, la primera tinta de cada línea en las columnas 0-2, sin espacios al principio ni al final
de línea. Una casilla (texto, D) cuyo dibujo ya existe en el registro (mismo texto, misma tinta) reutiliza
su código; el resto necesita código nuevo.
"""
from __future__ import annotations

import collections
from functools import lru_cache

import comun08 as K
import modelo8 as M8

A88, A89, R = K.A88, K.A89, K.R
F12 = K.F12
PREF = ''
PASO = 15
MAX_CELDAS = 18    # el japonés nunca pasa de 18 caracteres por línea (sin furigana) en IE1, IE2 ni IE3
MAX_LINEAS = 2
INF = M8.INF


def coste_hueco(g, palabra):
    if palabra:
        if g < 5:
            return INF
        return {5: 0.2, 6: 0.0, 7: 0.0, 8: 0.2, 9: 0.8, 10: 1.8}.get(g, 1.8 + 1.5 * (g - 10))
    if g < 1:
        return INF
    return {1: 0.2, 2: 0.0, 3: 0.5, 4: 1.2}.get(g, INF)   # decisión del usuario: hasta 4 px dentro de palabra


def coste_relajado(g, palabra):
    """Respaldo cuando la línea no cabe con coste_hueco: separación de palabra de 4 px e interno de 5."""
    if palabra:
        return 3.0 if g == 4 else coste_hueco(g, True)
    return 6.0 if g == 5 else coste_hueco(g, False)


def clave(t, d, g=2):
    return f'{PREF}{d:+d}{PREF}{g}{PREF}{t}'


def de_clave(c):
    """(texto, D, g) de una clave v08 de descripción, o None."""
    if not c.startswith(PREF):
        return None
    _, d, g, t = c.split(PREF, 3)
    return t, int(d), int(g)


class Desc:
    def __init__(self, reg, F12f, cp=None):
        self.F = F12f
        self.cp = cp or A88.codepoint
        self.mq = A89.Maqueta(F12f, self.cp)
        self.coste = {}
        self.coste_def = 1.5
        self._op = self.opciones()
        # dibujos existentes: (texto, D, sha de píxeles) -> sjis
        self.existentes = collections.defaultdict(list)     # texto -> [(S0, S1, D, ancho, clave_registro)]
        self.por_px = {}
        self._par = {}
        for e in reg['bigramas']:
            self._par[A89.clave_de(e)] = e['par']
            gi = F12f.gi(int(e['unicode'][2:], 16))
            m = A89.medir(F12f, gi)
            self.existentes[e['par']].append((m['S0'], m['S1'], m['D'], m['ancho'], A89.clave_de(e)))
            self.por_px[(e['par'], m['D'], _firma(m['px']))] = e

    @lru_cache(None)
    def trozo(self, t, g=2):
        """Composición de v89 con hueco interno g fijo (2 o 1) y espacio interior de 5 px; tinta <= 15."""
        core = t.strip(' ')
        if not core or '  ' in t:
            return None
        px, fin, esp = {}, None, False
        for ch in core:
            if ch == ' ':
                esp = True
                continue
            L = self.mq.letra(ch)
            if L is None:
                return None
            p, s0, s1, _, _, _ = L
            off = -s0 if fin is None else fin + 1 + (R.ESP if esp else g) - s0
            for (x, y), v in p.items():
                q = (x + off, y)
                px[q] = max(v, px.get(q, 0))
            fin = off + s1
            esp = False
        xs = [x for x, _ in px]
        f0, f1 = min(xs), max(xs)
        if f1 - f0 + 1 > PASO:
            return None
        if len(core) == 1 and g != 2:
            return None
        return dict(px={(x - f0, y): v for (x, y), v in px.items()}, s0r=-f0, s1r=fin - f0, ancho=f1 - f0 + 1, g=g)

    def reutilizable(self, t, d):
        t, d, g = de_clave(t) if isinstance(t, str) and t.startswith(PREF) else (t, d, 2)
        m = self.trozo(t, g)
        return self.por_px.get((t, d, _firma(m['px'])))

    def opciones(self, prohib=frozenset()):
        def op(t):
            fijas, libres = [], []
            lead, trail = t.startswith(' '), t.endswith(' ')
            if len(t) == 1 and t != ' ':
                nat = self.mq.nativa(t)
                if nat is not None:
                    fijas.append((nat[0], nat[1] - nat[0] + 1, False, False, 0.0, t))
            for s0, s1, d, ancho, c in self.existentes.get(t, ()):
                if c not in prohib and 0 <= d and d + ancho <= PASO:
                    fijas.append((s0, s1 - s0 + 1, lead, trail, 0.0, c))
            for g in (2, 1):
                m = self.trozo(t, g) if t.strip(' ') else None
                if m is None:
                    continue
                pen_g = 0.0 if g == 2 else 0.15
                libres.append((m['s0r'], m['s1r'] - m['s0r'] + 1, 0, PASO - m['ancho'], lead, trail,
                               lambda d, t=t, g=g, p=pen_g: self.coste.get(clave(t, d, g), self.coste_def) + p,
                               lambda d, t=t, g=g: clave(t, d, g)))
            return fijas, libres
        return op

    @staticmethod
    def huecos_ok(palabra):
        return (5, 6, 7, 8, 9, 10, 11, 12) if palabra else (2, 1, 3, 4)

    @staticmethod
    def margen_ini(o):
        return 0.0 if 0 <= o <= 2 else (1.5 if o == 3 else INF)

    def ancho_min(self, texto):
        """Cota inferior del ancho de la tinta sólida de una línea (1 px entre letras, 4 entre palabras)."""
        w, prev = 0, None
        for ch in texto:
            if ch == ' ':
                prev = ' '
                continue
            n = self.mq.nativa(ch)
            if n is None:
                return INF
            w += n[1] - n[0] + 1
            if prev is not None:
                w += 4 if prev == ' ' else 1
            prev = ch
        return w

    @lru_cache(None)
    def linea(self, texto):
        """(coste, [(clave, S0, w)]) de una línea sin espacios en los bordes, <= 14 casillas."""
        if texto != texto.strip(' ') or not texto:
            return INF, ()
        if self.ancho_min(texto) > PASO * MAX_CELDAS or len(texto) > 4 * MAX_CELDAS:
            return INF, ()
        cst, sel = M8.particion_libre(texto, self._op, 4, PASO, coste_hueco, self.huecos_ok, self.margen_ini,
                                      n_max=MAX_CELDAS)
        if cst == INF:
            cst, sel = M8.particion_libre(texto, self._op, 4, PASO, coste_relajado,
                                          lambda p: (5, 6, 7, 8, 4, 9, 10, 11, 12) if p else (2, 1, 3, 4, 5),
                                          self.margen_ini, n_max=MAX_CELDAS)
            cst += 20.0
        if cst == INF:
            return INF, ()
        return cst, tuple(sel)

    def texto_de(self, c):
        if c == ' ':
            return ' '
        d = de_clave(c)
        if d:
            return d[0]
        return R.texto(c) if len(c) <= 1 or R.variante(c) else self._par.get(c, c)

    def huecos(self, sel):
        out, prev, pal = [], None, False
        for c, o, w in sel:
            if c == ' ':
                prev = None if prev is None else prev - PASO
                pal = True
                continue
            t = self.texto_de(c)
            if prev is not None:
                out.append((o - prev - 1, pal or t.startswith(' ')))
            prev = o + w - 1 - PASO
            pal = t.endswith(' ')
        return out

    def envolver(self, texto, saltos_oficiales=True):
        """Mejor reparto en <= 2 líneas: primero los saltos oficiales; si no caben, por palabras.
        Devuelve (coste, [lineas], [sel por línea], modo) o None."""
        partes = [p.strip(' ') for p in texto.split('\n')]
        if saltos_oficiales and len(partes) <= MAX_LINEAS:
            res = [self.linea(p) for p in partes]
            if all(c < INF for c, _ in res):
                return sum(c for c, _ in res), partes, [s for _, s in res], 'saltos oficiales'
        palabras = ' '.join(partes).split()
        mejor = None
        for corte in range(1, len(palabras) + 1):
            l1 = ' '.join(palabras[:corte])
            l2 = ' '.join(palabras[corte:])
            c1, s1 = self.linea(l1)
            if c1 == INF:
                break
            if not l2:
                cand = (c1, [l1], [s1], 'una línea')
            else:
                c2, s2 = self.linea(l2)
                if c2 == INF:
                    continue
                cand = (c1 + c2 + 0.5, [l1, l2], [s1, s2], 'reajuste por palabras')
            if mejor is None or cand[0] < mejor[0]:
                mejor = cand
        return mejor


def _firma(px):
    return hash(tuple(sorted(px.items())))
