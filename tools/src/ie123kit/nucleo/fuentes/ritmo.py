"""Ritmo uniforme a paso fijo: maquetación de «trozos» y partición por coste de huecos (DP).

Portado de ``work/ie1/capas/fuentes/bigramas_ritmo/ritmo.py`` (IE1 v89) sin cambios de comportamiento
(F2.5, #51). Las constantes de la capa son ahora :class:`ParametrosRitmo`, con los valores de IE1
(FONT12, casilla de 15 px) por defecto; cada juego pasa los suyos.

Modelo:

- Cada casilla dibuja un TROZO del texto de 1 a 4 caracteres (letras/puntuación y, como mucho, un
  espacio en un borde o en medio). Dentro del trozo, 2 px sólidos entre letras (1 px si con 2 no cabe en
  ``celda - 2``), un espacio interior vale ``esp`` px. Tinta total (con antialias) <= ``celda`` columnas.
- Colocación fija por trozo (un código = una tinta): solo letras -> centrado; espacio delante -> la tinta
  acaba en la columna ``celda - 2``; espacio detrás -> empieza en la columna 1. Un trozo con espacio en
  el borde deja sitio a la separación: tinta sólida <= ``celda - pal_min``.
- Hueco entre casillas (sólido, alfa >= ``solido``) = ``celda + S0(sig) - S1(ant) - 1`` (+``celda`` por
  cada casilla de espacio nativa entre ambas). Dentro de palabra se busca 1-2 px (0 prohibido); entre
  palabras 4-8 px.
- Partición: programación dinámica sobre (posición, S1 anterior) minimizando el coste de los huecos.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

__all__ = [
    "DER",
    "IE1_FONT12",
    "INF",
    "IZQ",
    "Maqueta",
    "ParametrosRitmo",
    "coste_hueco",
    "huecos",
    "medir",
    "metricas",
    "particion",
    "texto",
    "variante",
]

INF = float("inf")
IZQ, DER = "", ""   # prefijos de las variantes de un solo glifo (alineado a izquierda/derecha)


@dataclass(frozen=True)
class ParametrosRitmo:
    """Medidas del ritmo de una fuente (las de IE1 v89 por defecto)."""

    celda: int = 15      # paso fijo de la casilla (FINF width de FONT12)
    solido: int = 5      # alfa mínimo que cuenta como tinta sólida al medir huecos
    esp: int = 5         # espacio interior de un trozo
    pal_min: int = 4     # hueco mínimo entre palabras
    fin_trozo: int = 13  # última columna de tinta sólida de un trozo con espacio delante


#: FONT12 de la recopilación, paso fijo de 15 px (IE1 v89: descripciones, objetivos y nombres).
IE1_FONT12 = ParametrosRitmo()


def texto(c: str) -> str:
    """Texto real de una clave de casilla (sin marcas de variante)."""
    return c[1:] if c[:1] in (IZQ, DER) else c


def variante(c: str) -> bool:
    return c[:1] in (IZQ, DER)


class Maqueta:
    """Maqueta de letras nativas, trozos y variantes de una fuente a paso fijo."""

    def __init__(self, F12: Any, cp: Callable[[str], int], parametros: ParametrosRitmo = IE1_FONT12):
        self.F = F12
        self.cp = cp
        self.p = parametros
        self.fijos: dict[str, dict] = {}

    @lru_cache(None)  # noqa: B019 - la caché vive lo que la maqueta, como en la capa
    def letra(self, ch: str):
        """(px desde la columna 0 del bitmap, s0, s1, f0, f1, x0 nativo) o None."""
        gi = self.F.gi(self.cp(ch))
        if gi is None:
            return None
        left, _, adv = self.F.metrics[gi]
        px = {(x, y): v for y, row in enumerate(self.F.bitmap(gi)) for x, v in enumerate(row) if v}
        sol = [x for (x, _), v in px.items() if v >= self.p.solido]
        if not sol:
            return None
        xs = [x for x, _ in px]
        x0 = int((self.p.celda - adv) / 2) + left
        return px, min(sol), max(sol), min(xs), max(xs), x0

    @lru_cache(None)  # noqa: B019
    def nativa(self, ch: str):
        """(S0, S1) sólidos de la letra nativa en su casilla, o None si no tiene tinta (espacio)."""
        L = self.letra(ch)
        if L is None:
            return None
        _, s0, s1, _, _, x0 = L
        return x0 + s0, x0 + s1

    def trozo(self, t: str):
        """Maqueta de un trozo: la fija (dibujo ya existente) si la hay; si no, la calculada."""
        if t in self.fijos:
            return self.fijos[t]
        return self.trozo_nuevo(t)

    @lru_cache(None)  # noqa: B019
    def trozo_nuevo(self, t: str):
        """Maqueta de un trozo de >= 2 caracteres: dict(px, S0, S1, D, ancho, g) o None si no vale."""
        CELDA, ESP, PAL_MIN, FIN = self.p.celda, self.p.esp, self.p.pal_min, self.p.fin_trozo
        if variante(t):
            L = self.letra(t[1])
            if L is None or len(t) != 2:
                return None
            p, s0, s1, f0, f1, _ = L
            shift = -s0 if t[0] == IZQ else (CELDA - 1) - s1
            shift = max(shift, -f0)
            shift = min(shift, CELDA - 1 - f1)
            return {"px": {(x - f0, y): v for (x, y), v in p.items()}, "S0": shift + s0, "S1": shift + s1,
                        "D": shift + f0, "ancho": f1 - f0 + 1, "g": None}
        if len(t) < 2 or t.strip(" ") == "" or "  " in t:
            return None
        lead, trail = t[0] == " ", t[-1] == " "
        core = t.strip(" ")
        if lead and trail and len(core) < 1:
            return None
        for g in (2, 1):
            px: dict[tuple[int, int], int] = {}
            fin, espacio = None, False
            ok = True
            for ch in core:
                if ch == " ":
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
            limite = FIN if not (lead or trail) else CELDA - PAL_MIN
            if g == 2 and w > limite:
                continue
            if (lead or trail) and w > CELDA - PAL_MIN:
                return None
            if lead and not trail:
                shift = FIN - (w - 1)
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
            return {"px": pix, "S0": shift, "S1": shift + w - 1, "D": D, "ancho": f1 - f0 + 1, "g": g}
        return None

    def extremos(self, c: str):
        """(S0, S1) sólidos de la casilla c (trozo, variante o letra), None si no tiene tinta."""
        if len(c) == 1:
            return self.nativa(c)
        m = self.trozo(c)
        return (m["S0"], m["S1"])


def coste_hueco(g: int, palabra: bool, parametros: ParametrosRitmo = IE1_FONT12) -> float:
    if palabra:
        if g < parametros.pal_min:
            return INF
        return 1.0 * max(0, 5 - g) + 0.15 * max(0, g - 8) ** 2
    if g < 1:
        return INF
    return (0.0, 0.0, 0.8, 3.0, 6.0)[g - 1] if g <= 5 else 6.0 + 2.5 * (g - 5)


def particion(t: str, mq: Maqueta, admitido: Callable[[str], bool], largo_max: int = 4):
    """Partición de t (sin opacos) en casillas. admitido(c) -> bool para trozos de >= 2 caracteres.
    Devuelve (coste, (casillas...))."""
    n = len(t)
    CELDA = mq.p.celda

    def es_palabra(i: int) -> bool:
        return t[i - 1] == " " or t[i] == " "

    @lru_cache(None)
    def f(i: int, s1):
        if i >= n:
            return 0.0, ()
        mejor = (INF, ())
        opciones = []
        for k in range(1, largo_max + 1):
            if i + k > n:
                break
            opciones.append((k, t[i:i + k]))
            if k == 1 and t[i] != " ":
                opciones += [(1, IZQ + t[i]), (1, DER + t[i])]
        for k, c in opciones:
            if k == 1 and not variante(c):
                ext = mq.nativa(c) if c != " " else None
                if c != " " and ext is None:
                    continue
            else:
                if not admitido(c) or mq.trozo(c) is None:
                    continue
                ext = mq.extremos(c)
            if ext is None:            # casilla de espacio nativa: arrastra el S1 anterior
                nuevo = None if s1 is None else s1 - CELDA
                cst = 0.0
            else:
                cst = 0.0 if s1 is None else coste_hueco(CELDA + ext[0] - s1 - 1, es_palabra(i), mq.p)
                nuevo = ext[1]
            if cst == INF:
                continue
            resto, cel = f(i + k, nuevo)
            total = cst + resto + (0.05 if variante(c) else 0.0)   # variantes solo si mejoran
            if total < mejor[0]:
                mejor = (total, (c,) + cel)
        return mejor

    return f(0, None)


def huecos(cel, mq: Maqueta) -> list[tuple[int, bool]]:
    """[(hueco, es_palabra)] de una lista de casillas (None = opaco, corta)."""
    CELDA = mq.p.celda
    out, s1, pal = [], None, False
    for c in cel:
        if c is None:
            s1 = None
            continue
        ext = mq.extremos(c) if c != " " else None
        palabra = texto(c)[0] == " " or pal
        if ext is None:
            if s1 is not None:
                s1 -= CELDA
            pal = True
            continue
        if s1 is not None:
            out.append((CELDA + ext[0] - s1 - 1, palabra))
        s1 = ext[1]
        pal = c[-1] == " "
    return out


def medir(F: Any, gi: int, parametros: ParametrosRitmo = IE1_FONT12) -> dict:
    """Maqueta equivalente del dibujo que ya tiene un código (para fijarlo sin redibujarlo)."""
    left, _width, adv = F.metrics[gi]
    x0 = int((parametros.celda - adv) / 2) + left
    px = {(x, y): v for y, row in enumerate(F.bitmap(gi)) for x, v in enumerate(row) if v}
    sol = [x for (x, _), v in px.items() if v >= parametros.solido]
    xs = [x for x, _ in px]
    return {"px": {(x - min(xs), y): v for (x, y), v in px.items()}, "S0": x0 + min(sol), "S1": x0 + max(sol),
                "D": x0 + min(xs), "ancho": max(xs) - min(xs) + 1, "g": None, "medido": True}


def metricas(m: dict, par: str, parametros: ParametrosRitmo = IE1_FONT12) -> tuple[int, int, int]:
    """CWDH ``(left, width, advance)`` de una maqueta: ``x = lápiz + trunc((celda - adv)/2) + left = D``;
    ``advance = D + ancho + R`` (R = 1, o ``esp`` si la casilla acaba en espacio)."""
    ancho, D = m["ancho"], m["D"]
    R = parametros.esp if par.endswith(" ") else 1
    adv = D + ancho + R
    left = D - int((parametros.celda - adv) / 2)
    if not (-128 <= left <= 127 and 0 < adv <= 255):
        raise ValueError(f"métricas fuera de rango para {par!r}: left {left}, advance {adv}")
    return left, ancho, adv
