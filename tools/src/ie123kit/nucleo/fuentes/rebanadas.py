"""Glifos de menú en rebanadas y reparto proporcional de etiquetas cortas (camino proporcional del motor).

Portado de ``work/ie2/shared/capas/menus_cro/menus`` (IE2 v23, issue #77) sin cambios de comportamiento
(F2.5, #51): ``modelo23.py`` entero y las partes genéricas de ``apply.py`` (reparto de bloques del CRO,
elección con presupuesto de códigos, escritura de glifos y rebanadas FONT8). Lo propio de cada juego
(direcciones de los bloques, códigos que se pueden reutilizar, parámetros por fuente) lo pasa el juego:
ver :mod:`ie123kit.ie2.comun.menus`.

Modelo medido contra una captura del menú de campo de IE2 (0xbd1e8 -> 0x121a78)::

    x_tinta = lápiz + trunc((CAJA - advance) / 2) + left + columna del mapa de bits
    lápiz += advance                                                (camino PROPORCIONAL)

CAJA = anchura FINF de la fuente (FONT12 15, FONT8 11). La etiqueta se dibuja una vez como TIRA con las
letras nativas de la fuente y se cubre con piezas: glifos EXISTENTES cuya tinta coincide píxel a píxel
con la tira (sin gastar códigos) o REBANADAS/TROZOS nuevos en códigos libres del registro de bigramas.

Portear este código no cambia ninguna fuente del proyecto: trabaja sobre la copia en memoria.
"""
from __future__ import annotations

import hashlib
import itertools
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from ie123kit.nucleo.fuentes import celdas

__all__ = [
    "CAJA",
    "INF",
    "ParametrosReparto",
    "Reparto",
    "columnas",
    "concretar",
    "elegir",
    "escribir_glifo",
    "escribir_rebanada",
    "existentes",
    "frente_bloque",
    "glifo",
    "huecos",
    "huella",
    "metricas_rebanada",
    "pintar",
    "pintar_fijo",
    "rebanar",
    "resolver",
    "tira",
    "tira_nucleo",
]

INF = float("inf")
#: Anchura FINF (la «caja» del camino proporcional) de cada fuente compartida de la recopilación.
CAJA = {"font/FONT12.bcfnt": 15, "font/FONT8.bcfnt": 11}


@dataclass(frozen=True)
class ParametrosReparto:
    """Parámetros del reparto en una fuente (los de IE2 v23 están en ``ie2.comun.menus``)."""

    nombre: str
    ancho: int                      # columnas máximas de un código nuevo
    umbral: int                     # alfa mínimo que cuenta como tinta al medir huecos
    permitidos: tuple[int, ...]     # huecos admitidos entre letras
    inicio: Mapping[int, float]     # columna de la primera tinta -> coste


def glifo(F: Any, gi: int, caja: int):
    """(desplazamiento de la primera columna con tinta respecto al lápiz, avance, columnas con tinta) o None."""
    left, _, adv = F.metrics[gi]
    bm = F.bitmap(gi)
    xs = [x for row in bm for x, v in enumerate(row) if v]
    if not xs:
        return None
    e0, e1 = min(xs), max(xs)
    cols = tuple(tuple(row[x] for row in bm) for x in range(e0, e1 + 1))
    return int((caja - adv) / 2) + left + e0, adv, cols


def pintar(F: Any, caja: int, gis: Sequence[int], x_origen: int = 0):
    """Dibujo del motor de una lista de glifos: ({(x, y): alfa}, [(x0 de la columna 0 del mapa, avance)])."""
    px: dict[tuple[int, int], int] = {}
    pen, pos = x_origen, []
    for gi in gis:
        left, _, adv = F.metrics[gi]
        x0 = pen + int((caja - adv) / 2) + left
        for y, row in enumerate(F.bitmap(gi)):
            for x, v in enumerate(row):
                if v:
                    px[(x0 + x, y)] = max(v, px.get((x0 + x, y), 0))
        pos.append((x0, adv))
        pen += adv
    return px, pos


def tira(F: Any, caja: int, texto: str, codepoint: Callable[[str], int]):
    """Dibujo de la etiqueta con las letras nativas (camino proporcional, lápiz desde 0)."""
    gis = []
    for ch in texto:
        gi = F.gi(codepoint(ch))
        if gi is None:
            raise KeyError(ch)
        gis.append(gi)
    return pintar(F, caja, gis)[0]


def columnas(px: Mapping[tuple[int, int], int], alto: int):
    if not px:
        return {}
    xs = [x for x, _ in px]
    return {x: tuple(px.get((x, y), 0) for y in range(alto)) for x in range(min(xs), max(xs) + 1)}


def huecos(px: Mapping[tuple[int, int], int]) -> list[int]:
    """Anchuras de las columnas vacías entre tramos de tinta (cualquier alfa)."""
    xs = sorted({x for x, _ in px})
    return [b - a - 1 for a, b in itertools.pairwise(xs) if b - a > 1]


def resolver(F: Any, caja: int, ancho_celda: int, texto: str, codepoint: Callable[[str], int],
             existentes: Sequence[tuple], max_piezas: int):
    """{n_piezas: (códigos nuevos, [pieza])} para cubrir la tira de `texto` (rebanado puro).
    existentes: [(codigo_bytes, gi, off, adv, cols)] glifos que se pueden reutilizar.
    pieza = dict(tipo='existente'|'rebanada', a, b, codigo?, gi?, lapiz)."""
    px = tira(F, caja, texto, codepoint)
    col = columnas(px, len(F.bitmap(0)))
    vacia = tuple(0 for _ in range(len(F.bitmap(0))))
    xs = sorted(col)
    x_ini, x_fin = xs[0], xs[-1]
    tinta = [x for x in xs if col[x] != vacia]
    por_primera: dict[Any, list] = {}
    for e in existentes:
        por_primera.setdefault(e[4][0], []).append(e)

    def siguiente(c):
        for x in tinta:
            if x >= c:
                return x
        return None

    @lru_cache(None)
    def f(c, lo, hi, k):
        """Mejor (códigos, piezas) con como mucho k piezas desde la columna c con el lápiz en [lo, hi]."""
        a = siguiente(c)
        if a is None:
            return (0, ())
        if k == 0:
            return (INF, ())
        best = (INF, ())
        for e in por_primera.get(col[a], ()):
            cod, gi, off, adv, cols = e
            req = a - off
            if not lo <= req <= hi:
                continue
            w = len(cols)
            if any(col.get(a + j, vacia) != cols[j] for j in range(w)):
                continue
            r = f(a + w, req + adv, req + adv, k - 1)
            if r[0] < best[0]:
                best = (r[0], ({"tipo": "existente", "a": a, "b": a + w - 1, "codigo": cod, "gi": gi, "lapiz": req, "adv": adv},)
                        + r[1])
        for b in range(a, min(a + ancho_celda, x_fin + 1)):
            if col[b] == vacia:
                continue
            r = f(b + 1, lo + 1, hi + caja, k - 1)
            if r[0] + 1 < best[0]:
                best = (r[0] + 1, ({"tipo": "rebanada", "a": a, "b": b},) + r[1])
        return best

    out = {}
    for k in range(1, max_piezas + 1):
        r = f(x_ini, 0, 0, k)
        if r[0] < INF and len(r[1]) == k and (not out or r[0] < min(v[0] for v in out.values())):
            out[k] = (r[0], concretar(list(r[1]), caja))
    return out, px


def concretar(piezas: list[dict], caja: int) -> list[dict]:
    """Lápiz de cada pieza y avance de cada rebanada (el lápiz empieza en 0)."""
    n = len(piezas)
    iv: list[Any] = [None] * (n + 1)
    iv[0] = (0, 0)
    for i, p in enumerate(piezas):
        lo, hi = iv[i]
        if p["tipo"] == "existente":
            if not lo <= p["lapiz"] <= hi:
                raise AssertionError((i, lo, hi, p["lapiz"]))
            iv[i] = (p["lapiz"], p["lapiz"])
            iv[i + 1] = (p["lapiz"] + p["adv"],) * 2
        else:
            iv[i + 1] = (lo + 1, hi + caja)
    pen: list[Any] = [None] * (n + 1)
    pen[n] = iv[n][0]
    for i in range(n - 1, -1, -1):
        p = piezas[i]
        lo, hi = iv[i]
        if p["tipo"] == "existente":
            pen[i] = p["lapiz"]
        else:
            cand = max(lo, pen[i + 1] - caja)
            if cand > min(hi, pen[i + 1] - 1):
                raise AssertionError((i, lo, hi, pen[i + 1]))
            pen[i] = cand
            p["adv"] = pen[i + 1] - pen[i]
        p["lapiz"] = pen[i]
    return piezas


def metricas_rebanada(p: Mapping[str, int], caja: int) -> tuple[int, int, int]:
    """(left, width, advance) de una rebanada con la columna 0 de su mapa en la columna p['a'] de la tira."""
    adv = p["adv"]
    if not 1 <= adv <= caja:
        raise ValueError(adv)
    left = p["a"] - p["lapiz"] - int((caja - adv) / 2)
    if not -128 <= left <= 127:
        raise ValueError(left)
    return left, p["b"] - p["a"] + 1, adv


class Reparto:
    """Reparto por trozos de texto cuando no hay códigos para rebanar toda la tira.

    Cada casilla es un trozo de 1-3 letras: un glifo EXISTENTE con ese texto (letra nativa o código del
    registro, métricas fijas) o un código NUEVO con el trozo dibujado con las letras nativas y su espaciado
    natural (métricas libres). Todo se coloca con el modelo proporcional. Los huecos entre letras se miden
    en la tinta (alfa >= umbral) y se comparan con los de la tira nativa: |hueco - natural| cuesta, fuera de
    `permitidos` no vale. El primer píxel de tinta cae en `inicio`.
    """

    def __init__(self, F, caja, ancho_celda, codepoint, umbral, permitidos, existentes, inicio=(1,), largo=3):
        self.F, self.caja, self.ancho, self.cp = F, caja, ancho_celda, codepoint
        self.umbral, self.permitidos, self.largo = umbral, set(permitidos), largo
        self.inicio = dict(inicio) if isinstance(inicio, dict) else {c: 0.0 for c in inicio}   # columna: coste
        self.existentes = existentes          # texto -> [(codigo, gi)]
        self.alto = len(F.bitmap(0))

    @classmethod
    def con(cls, F: Any, caja: int, codepoint: Callable[[str], int], p: ParametrosReparto,
            existentes: Mapping[str, list]) -> Reparto:
        return cls(F, caja, p.ancho, codepoint, p.umbral, p.permitidos, existentes, dict(p.inicio))

    def _tinta(self, px):
        return sorted({x for (x, _), v in px.items() if v >= self.umbral})

    def _tramos(self, xs):
        runs, ini = [], xs[0]
        for a, b in itertools.pairwise(xs):
            if b != a + 1:
                runs.append((ini, a))
                ini = b
        runs.append((ini, xs[-1]))
        return runs

    @lru_cache(None)  # noqa: B019 - la caché vive lo que el reparto, como en la capa
    def natural(self, a, b):
        """Hueco natural (tinta) entre las letras a y b escritas seguidas con la fuente."""
        px = tira(self.F, self.caja, a + b, self.cp)
        pa = tira(self.F, self.caja, a, self.cp)
        xa = self._tinta(pa)
        xs = self._tinta(px)
        fin_a = xa[-1]
        ini_b = min(x for x in xs if x > fin_a) if any(x > fin_a for x in xs) else fin_a + 1
        return ini_b - fin_a - 1

    def coste_hueco(self, g, a, b):
        if g not in self.permitidos:
            return INF
        return abs(g - self.natural(a, b))

    @lru_cache(None)  # noqa: B019
    def opciones(self, t):
        """[(tipo, codigo, gi, off_tinta, adv, ancho_tinta, coste_interno, px_rel)]; off_tinta None = libre."""
        out = []
        for cod, gi in self.existentes.get(t, ()):
            left, _, adv = self.F.metrics[gi]
            px = {(x, y): v for y, row in enumerate(self.F.bitmap(gi)) for x, v in enumerate(row) if v}
            xs = self._tinta(px)
            if not xs:
                continue
            runs = self._tramos(xs)
            if len(runs) != len(t):
                continue
            c = 0.0
            for k in range(len(t) - 1):
                c += self.coste_hueco(runs[k + 1][0] - runs[k][1] - 1, t[k], t[k + 1])
            if c == INF:
                continue
            x0 = xs[0]
            off = int((self.caja - adv) / 2) + left + x0
            rel = {(x - x0, y): v for (x, y), v in px.items()}
            out.append(("existente", cod, gi, off, adv, xs[-1] - x0 + 1, c, rel))
        px = tira(self.F, self.caja, t, self.cp)
        xs = self._tinta(px)
        todos = sorted({x for x, _ in px})
        x0 = xs[0]
        if todos[-1] - todos[0] + 1 <= self.ancho:
            rel = {(x - x0, y): v for (x, y), v in px.items()}
            out.append(("nueva", None, None, None, None, xs[-1] - x0 + 1, 0.0, rel))
        return tuple(out)

    def resolver(self, texto, max_piezas, lam=100.0):
        """{(piezas, códigos): (coste, [casilla])} frente de Pareto."""
        n = len(texto)
        caja = self.caja

        @lru_cache(None)
        def f(i, s1, lo, hi):
            if i >= n:
                return {(0, 0): (0.0, ())}
            res = {}
            for L in range(1, self.largo + 1):
                if i + L > n:
                    break
                t = texto[i:i + L]
                for tipo, cod, gi, off, adv, w, cin, rel in self.opciones(t):
                    if s1 is None:
                        inicios = sorted(self.inicio)
                    else:
                        inicios = [s1 + 1 + g for g in sorted(self.permitidos)]
                    for x in inicios:
                        cg = self.inicio[x] if s1 is None else self.coste_hueco(x - s1 - 1, texto[i - 1], t[0])
                        if cg == INF:
                            continue
                        if tipo == "existente":
                            req = x - off
                            if not lo <= req <= hi:
                                continue
                            nlo = nhi = req + adv
                            nuevos = 0
                        else:
                            nlo, nhi = lo + 1, hi + caja
                            nuevos = 1
                        for (k, c), (cst, cel) in f(i + L, x + w - 1, nlo, nhi).items():
                            key = (k + 1, c + nuevos)
                            tot = cst + cg + cin
                            if key[0] > max_piezas:
                                continue
                            if key not in res or tot < res[key][0]:
                                cas = {"t": t, "tipo": tipo, "codigo": cod, "gi": gi, "x": x, "w": w, "off": off, "adv": adv, "rel": rel}
                                res[key] = (tot, (cas,) + cel)
            return res

        out = f(0, None, 0, 0)
        return {k: (v[0], self.concretar([dict(c) for c in v[1]])) for k, v in out.items()}

    def concretar(self, cas):
        """Lápiz de cada casilla y métricas de las nuevas."""
        caja, n = self.caja, len(cas)
        iv: list[Any] = [None] * (n + 1)
        iv[0] = (0, 0)
        for i, c in enumerate(cas):
            lo, hi = iv[i]
            if c["tipo"] == "existente":
                req = c["x"] - c["off"]
                if not lo <= req <= hi:
                    raise AssertionError((i, lo, hi, req))
                iv[i] = (req, req)
                iv[i + 1] = (req + c["adv"],) * 2
            else:
                iv[i + 1] = (lo + 1, hi + caja)
        pen: list[Any] = [None] * (n + 1)
        pen[n] = iv[n][0]
        for i in range(n - 1, -1, -1):
            c = cas[i]
            lo, hi = iv[i]
            if c["tipo"] == "existente":
                pen[i] = iv[i][0]
            else:
                cand = max(lo, pen[i + 1] - caja)
                if cand > min(hi, pen[i + 1] - 1):
                    raise AssertionError((i, lo, hi, pen[i + 1]))
                pen[i] = cand
                c["adv"] = pen[i + 1] - pen[i]
            c["lapiz"] = pen[i]
        return cas


def tira_nucleo(F, texto, codepoint, umbral=8, hueco=2, inicio=1):
    """Tira con las letras nativas separadas por `hueco` columnas de núcleo (alfa >= umbral), con la primera
    columna de núcleo en `inicio`. Se usa en FONT8, cuyo avance nativo junta las letras."""
    px: dict[tuple[int, int], int] = {}
    fin = None
    for ch in texto:
        gi = F.gi(codepoint(ch))
        bm = F.bitmap(gi)
        nucleo = [x for row in bm for x, v in enumerate(row) if v >= umbral]
        x0 = (inicio if fin is None else fin + 1 + hueco) - min(nucleo)
        for y, row in enumerate(bm):
            for x, v in enumerate(row):
                if v:
                    px[(x0 + x, y)] = max(v, px.get((x0 + x, y), 0))
        fin = x0 + max(nucleo)
    return px


def rebanar(px, paso):
    """Rebanadas de `paso` columnas desde la columna 0: [(k, {(x, y): v} con x relativo a paso*k)]."""
    xs = [x for x, _ in px]
    if min(xs) < 0:
        raise ValueError("tinta a la izquierda de la columna 0")
    n = max(xs) // paso + 1
    out = []
    for k in range(n):
        out.append((k, {(x - paso * k, y): v for (x, y), v in px.items() if paso * k <= x < paso * (k + 1)}))
    return out


# ------------------------------------------------------------------------------------------------ reparto de bloques
def existentes(F: Any, fuente: str, registro: Sequence[Mapping[str, Any]], letras: str,
               codepoint: Callable[[str], int], excluir: Sequence[str] = ()) -> dict[str, list]:
    """Glifos reutilizables: letras nativas de ``letras`` y códigos del registro dibujados en ``fuente``."""
    out: dict[str, list] = {}
    fuera = set(excluir)
    for ch in letras:
        cp = codepoint(ch)
        gi = F.gi(cp)
        if gi is not None:
            out.setdefault(ch, []).append((chr(cp).encode("cp932"), gi))
    for e in registro:
        if fuente in e["fuentes"] and e["sjis"] not in fuera:
            gi = F.gi(ord(bytes.fromhex(e["sjis"]).decode("cp932")))
            if gi is not None:
                out.setdefault(e["par"], []).append((bytes.fromhex(e["sjis"]), gi))
    return out


def frente_bloque(R: Reparto, bloque: tuple, forzados: Mapping[str, Sequence[str]] | None = None):
    """{códigos: (clave, [(jp, texto, casillas)])} con clave = (alternativas, coste); DP sobre las entradas.

    ``bloque`` = (inicio, fin, máx. bytes por entrada, fuente, [(clave, [alternativas])]); ``forzados``
    sustituye las alternativas de una entrada (decisión del usuario).
    """
    ini, fin, max_e, _f, entradas = bloque
    total = fin - ini + 1
    estados: dict[tuple[int, int], Any] = {(0, 0): ((0, 0.0), [])}
    for jp, alternativas in entradas:
        tope = max_e
        if forzados and jp in forzados:
            alternativas = list(forzados[jp])
        opciones = []
        for ia, alt in enumerate(alternativas):
            for (k, c), (coste, cas) in R.resolver(alt, tope // 2).items():
                opciones.append((ia, 2 * k, c, coste, alt, cas))
        nuevos: dict[tuple[int, int], Any] = {}
        for (b, c), (clave, el) in estados.items():
            for ia, nb, nc, coste, alt, cas in opciones:
                kb, kc = b + nb + 1, c + nc
                if kb > total:
                    continue
                cl = (clave[0] + ia, round(clave[1] + coste, 6))
                if (kb, kc) not in nuevos or cl < nuevos[(kb, kc)][0]:
                    nuevos[(kb, kc)] = (cl, el + [(jp, alt, cas)])
        estados = nuevos
    frente: dict[int, Any] = {}
    for (_b, c), (cl, el) in estados.items():
        if c not in frente or cl < frente[c][0]:
            frente[c] = (cl, el)
    return frente


def elegir(frentes: Mapping[str, Mapping[int, Any]], presupuesto: int):
    """Mejor combinación de los bloques con como mucho `presupuesto` códigos nuevos."""
    mejor: dict[int, Any] = {0: ((0, 0.0), {})}
    for nombre, fr in frentes.items():
        nuevo: dict[int, Any] = {}
        for c0, (cl0, el0) in mejor.items():
            for c1, (cl1, el1) in fr.items():
                c = c0 + c1
                if c > presupuesto:
                    continue
                cl = (cl0[0] + cl1[0], round(cl0[1] + cl1[1], 6))
                if c not in nuevo or cl < nuevo[c][0]:
                    nuevo[c] = (cl, {**el0, nombre: el1})
        mejor = nuevo
    c = min(mejor, key=lambda k: (mejor[k][0], k))
    return c, mejor[c]


def escribir_glifo(Fu: celdas.FuenteBCFNT, gi: int, rel: Mapping[tuple[int, int], int], x: int, lapiz: int,
                   adv: int, ancho: int, caja: int) -> tuple[list[int], list[int]]:
    """Dibuja la tinta rel (x = 0 en la primera columna con tinta) con esa columna en ``x`` de la tira."""
    esc = celdas.EscritorA4(Fu)
    xs = [a for a, _ in rel]
    xm = min(xs)
    for y in range(Fu.sy):
        for c in range(Fu.sx):
            esc.escribir(gi, c, y, 0)
    for (a, y), v in rel.items():
        bx = a - xm
        if not (0 <= bx < ancho and 0 <= y <= Fu.sy - 2):
            raise ValueError((gi, a, y))
        esc.escribir(gi, 1 + bx, 1 + y, v)
    viejo = list(Fu.metrics[gi])
    left = (x + xm) - lapiz - int((caja - adv) / 2)
    if not (1 <= adv <= caja and -128 <= left <= 127):
        raise ValueError((gi, left, adv))
    Fu.set_metrics(gi, left, max(xs) - xm + 1, adv)
    return viejo, [left, max(xs) - xm + 1, adv]


def escribir_rebanada(Fu: celdas.FuenteBCFNT, gi: int, rel: Mapping[tuple[int, int], int],
                      paso: int) -> tuple[list[int], list[int]]:
    """Rebanada a paso fijo: columna 0 del mapa = columna 0 de la rebanada; left 0, ancho y avance ``paso``."""
    esc = celdas.EscritorA4(Fu)
    for y in range(Fu.sy):
        for c in range(Fu.sx):
            esc.escribir(gi, c, y, 0)
    for (a, y), v in rel.items():
        if not (0 <= a < paso and 0 <= y <= Fu.sy - 2):
            raise ValueError((gi, a, y))
        esc.escribir(gi, 1 + a, 1 + y, v)
    viejo = list(Fu.metrics[gi])
    Fu.set_metrics(gi, 0, paso, paso)
    return viejo, [0, paso, paso]


def pintar_fijo(F: Any, caja: int, gis: Sequence[int], paso: int):
    """Modelo de paso fijo: x = paso * k + trunc((CAJA - adv)/2) + left."""
    px: dict[tuple[int, int], int] = {}
    for k, gi in enumerate(gis):
        left, _, adv = F.metrics[gi]
        x0 = paso * k + int((caja - adv) / 2) + left
        for y, row in enumerate(F.bitmap(gi)):
            for x, v in enumerate(row):
                if v:
                    px[(x0 + x, y)] = max(v, px.get((x0 + x, y), 0))
    return px


def huella(rel: Mapping[tuple[int, int], int]) -> str:
    return hashlib.sha1(json.dumps(sorted(rel.items())).encode()).hexdigest()
