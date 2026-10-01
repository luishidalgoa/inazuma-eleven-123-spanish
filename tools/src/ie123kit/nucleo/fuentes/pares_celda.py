"""Pares de letras en una casilla (bigramas) para textos con un límite de casillas.

Algunos pintores del juego dibujan un texto a paso fijo, una casilla por carácter (1 byte latino o
2 bytes Shift-JIS), y admiten un número máximo de casillas: en el IE3 el nombre corto del unitbase se
sale de las placas y cuelga el partido con 7 o más (#87). La solución, como en los rótulos y nombres del
IE1/IE2, es juntar dos letras en un solo código kanji sin uso redibujado como el par.

Este módulo es puro (sin E/S ni fuentes concretas):

- :func:`casillas` parte un texto codificado en casillas;
- :func:`elegir_pares` busca un conjunto pequeño de pares con el que todos los textos quepan
  (heurística voraz de cobertura: cada paso añade el par que más textos acerca a su límite; a igualdad,
  el más barato de dibujar);
- :func:`particion` elige, para un texto, qué pares juntar (exactamente los necesarios, los más baratos);
- :func:`codificar` y :func:`decodificar` pasan de casillas a bytes con la tabla par -> código;
- :func:`componer` y :func:`componer_la4` dibujan un par a partir de los mapas de bits de sus dos letras,
  estrechándolas en horizontal solo si no caben en el ancho pedido.

La primera casilla nunca se junta (``desde=1``): el Registro del IE3 calcula la pestaña con el primer
carácter del nombre corto.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass

__all__ = [
    "Dibujo",
    "Par",
    "casillas",
    "codificar",
    "componer",
    "componer_la4",
    "decodificar",
    "elegir_pares",
    "es_doble",
    "maximo_juntable",
    "metricas_centradas",
    "particion",
]

#: un par es la tupla de las dos casillas (bytes) que se juntan
Par = tuple[bytes, bytes]


def es_doble(b: int) -> bool:
    """Primer byte de un carácter Shift-JIS de 2 bytes."""
    return 0x81 <= b <= 0x9F or 0xE0 <= b <= 0xFC


def casillas(datos: bytes) -> tuple[bytes, ...]:
    """Casillas de un texto: cada carácter de 1 byte o de 2 bytes Shift-JIS es una casilla."""
    salida: list[bytes] = []
    i = 0
    while i < len(datos):
        n = 2 if es_doble(datos[i]) and i + 1 < len(datos) else 1
        salida.append(datos[i:i + n])
        i += n
    return tuple(salida)


def maximo_juntable(texto: Sequence[bytes], pares: Iterable[Par] | set[Par], desde: int = 1) -> int:
    """Máximo de pares disjuntos de ``pares`` que se pueden juntar en ``texto`` (desde la casilla ``desde``)."""
    conjunto = pares if isinstance(pares, (set, frozenset)) else set(pares)
    n = len(texto)
    f = [0] * (n + 2)
    for i in range(n - 2, desde - 1, -1):
        f[i] = f[i + 1]
        if (texto[i], texto[i + 1]) in conjunto:
            f[i] = max(f[i], 1 + f[i + 2])
    return f[desde] if n - desde >= 2 else 0


def elegir_pares(textos: Iterable[Sequence[bytes]], limite: int,
                 coste: Callable[[Par], float] | None = None, desde: int = 1,
                 admitido: Callable[[Par], bool] | None = None) -> list[Par]:
    """Conjunto pequeño de pares con el que cada texto queda en ``limite`` casillas o menos.

    ``coste(par)`` (>= 0, por defecto 0) penaliza los pares que hay que estrechar para dibujarlos;
    ``admitido(par)`` descarta pares que no se pueden dibujar. Devuelve los pares en el orden en que se
    eligieron. Lanza ``ValueError`` si algún texto no puede quedar en el límite con pares admitidos.
    """
    coste = coste or (lambda _p: 0.0)
    admitido = admitido or (lambda _p: True)
    lista = {tuple(t) for t in textos if len(t) > limite}
    necesidad = {t: len(t) - limite for t in lista}
    for t in lista:
        todos = {(t[i], t[i + 1]) for i in range(desde, len(t) - 1) if admitido((t[i], t[i + 1]))}
        if maximo_juntable(t, todos, desde) < necesidad[t]:
            raise ValueError(f"no cabe en {limite} casillas ni juntando pares: {b''.join(t)!r}")
    elegidos: list[Par] = []
    conjunto: set[Par] = set()
    pendientes = set(lista)
    while pendientes:
        ganancia: Counter[Par] = Counter()
        for t in pendientes:
            base = min(necesidad[t], maximo_juntable(t, conjunto, desde))
            for i in range(desde, len(t) - 1):
                p = (t[i], t[i + 1])
                if p in conjunto or not admitido(p):
                    continue
                if min(necesidad[t], maximo_juntable(t, conjunto | {p}, desde)) > base:
                    ganancia[p] += 1
        mejor = max(ganancia, key=lambda p: (ganancia[p] / (1.0 + coste(p)), -coste(p), p))
        elegidos.append(mejor)
        conjunto.add(mejor)
        pendientes = {t for t in pendientes if maximo_juntable(t, conjunto, desde) < necesidad[t]}
    return elegidos


def particion(texto: Sequence[bytes], pares: Iterable[Par], limite: int,
              coste: Callable[[Par], float] | None = None, desde: int = 1) -> tuple[bytes | Par, ...]:
    """Casillas de ``texto`` juntando exactamente los pares necesarios para no pasar de ``limite``.

    Entre las formas posibles, la de menor coste total (y, a igualdad, la que junta más a la derecha).
    Un texto que ya cabe se devuelve tal cual. ``ValueError`` si no hay forma.
    """
    coste = coste or (lambda _p: 0.0)
    conjunto = set(pares)
    t = tuple(texto)
    k = len(t) - limite
    if k <= 0:
        return t
    n = len(t)
    inf = float("inf")
    # g[i][r] = (coste, casillas) desde i con r pares aún por juntar
    memo: dict[tuple[int, int], tuple[float, tuple]] = {}

    def g(i: int, r: int) -> tuple[float, tuple]:
        if (i, r) in memo:
            return memo[(i, r)]
        if i >= n:
            res = (0.0, ()) if r == 0 else (inf, ())
        else:
            c1, s1 = g(i + 1, r)
            res = (c1, (t[i],) + s1)
            if r > 0 and i >= desde and i + 1 < n and (t[i], t[i + 1]) in conjunto:
                c2, s2 = g(i + 2, r - 1)
                c2 += coste((t[i], t[i + 1]))
                if c2 <= res[0]:
                    res = (c2, ((t[i], t[i + 1]),) + s2)
        memo[(i, r)] = res
        return res

    c, s = g(0, k)
    if c == inf:
        raise ValueError(f"no cabe en {limite} casillas con los pares dados: {b''.join(t)!r}")
    return s


def codificar(partes: Iterable[bytes | Par], codigos: Mapping[Par, bytes]) -> bytes:
    """Bytes de una partición: cada par se sustituye por su código de 2 bytes."""
    return b"".join(codigos[p] if isinstance(p, tuple) else p for p in partes)


def decodificar(datos: bytes, codigos: Mapping[Par, bytes]) -> bytes:
    """Deshace :func:`codificar`: cada código de par vuelve a sus dos casillas."""
    inverso = {c: a + b for (a, b), c in codigos.items()}
    return b"".join(inverso.get(c, c) for c in casillas(datos))


# --------------------------------------------------------------------------- dibujo

@dataclass(frozen=True)
class Dibujo:
    """Dibujo de un par: píxeles en coordenadas de glifo (columna 0 = primera tinta) y su ancho."""

    px: dict[tuple[int, int], int]
    ancho: int
    estrechado: bool


def _columnas(bitmap: Sequence[Sequence[int]]) -> tuple[int, int] | None:
    xs = [x for row in bitmap for x, v in enumerate(row) if v]
    return (min(xs), max(xs)) if xs else None


def _remuestrear(cols: list[list[int]], nuevo: int) -> list[list[float]]:
    """Estrecha una lista de columnas (cada una, lista por fila) a ``nuevo`` columnas por área."""
    viejo = len(cols)
    if nuevo >= viejo:
        return [[float(v) for v in c] for c in cols]
    alto = len(cols[0])
    escala = viejo / nuevo
    salida = []
    for j in range(nuevo):
        a, b = j * escala, (j + 1) * escala
        acum = [0.0] * alto
        x = int(a)
        while x < b and x < viejo:
            peso = min(b, x + 1) - max(a, x)
            for y in range(alto):
                acum[y] += cols[x][y] * peso
            x += 1
        salida.append([v / escala for v in acum])
    return salida


def _letra_columnas(bitmap: Sequence[Sequence[int]]) -> list[list[int]]:
    ext = _columnas(bitmap)
    if ext is None:
        return []
    x0, x1 = ext
    return [[bitmap[y][x] for y in range(len(bitmap))] for x in range(x0, x1 + 1)]


def _anchos(wa: int, wb: int, sep: int, ancho_max: int) -> tuple[int, int, bool]:
    if wa + sep + wb <= ancho_max:
        return wa, wb, False
    disponible = max(2, ancho_max - sep)
    if wa == 0 or wb == 0:
        return min(wa, disponible), min(wb, disponible), True
    na = max(1, round(wa * disponible / (wa + wb)))
    nb = max(1, disponible - na)
    return na, nb, True


def componer(bitmap_a: Sequence[Sequence[int]], bitmap_b: Sequence[Sequence[int]], ancho_max: int,
             sep: int = 1, hueco_vacio: int = 2, maximo: int = 15) -> Dibujo:
    """Par de dos letras (mapas de bits alfa 0..``maximo``, mismo alto): A, ``sep`` px, B.

    Si no cabe en ``ancho_max`` columnas, las dos letras se estrechan en la misma proporción (por área,
    conservando la altura). Una letra sin tinta (espacio) cuenta como ``hueco_vacio`` columnas.
    """
    ca, cb = _letra_columnas(bitmap_a), _letra_columnas(bitmap_b)
    alto = len(bitmap_a) if bitmap_a else len(bitmap_b)
    wa, wb = len(ca), len(cb)
    if not ca and not cb:
        raise ValueError("par sin tinta")
    if not ca or not cb:          # letra + espacio: el espacio es un hueco sin tinta
        wa_, wb_ = (hueco_vacio, wb) if not ca else (wa, hueco_vacio)
        na, nb, estrecho = _anchos(wa_, wb_, 0, ancho_max)
        tinta = cb if not ca else ca
        n_tinta = nb if not ca else na
        cols = _remuestrear(tinta, n_tinta)
        px = {(x, y): min(maximo, round(v)) for x, c in enumerate(cols) for y, v in enumerate(c) if round(v) > 0}
        return Dibujo(px, n_tinta, estrecho)
    na, nb, estrecho = _anchos(wa, wb, sep, ancho_max)
    cols = _remuestrear(ca, na) + [[0.0] * alto for _ in range(sep)] + _remuestrear(cb, nb)
    px = {(x, y): min(maximo, round(v)) for x, c in enumerate(cols) for y, v in enumerate(c) if round(v) > 0}
    return Dibujo(px, len(cols), estrecho)


def componer_la4(bytes_a: Sequence[Sequence[int]], bytes_b: Sequence[Sequence[int]], ancho_max: int,
                 sep: int = 0, hueco_vacio: int = 2) -> Dibujo:
    """Como :func:`componer` para hojas LA4 (un byte por píxel: luminancia alta, alfa baja).

    Alfa y luminancia se estrechan por separado (la luminancia ponderada por el alfa). Con ``sep = 0``
    los contornos de las dos letras se tocan, como las letras nativas de FONT12T.
    """
    def partir(bm: Sequence[Sequence[int]]) -> tuple[list[list[int]], list[list[int]]]:
        alfa = [[v & 0xF for v in fila] for fila in bm]
        lum = [[(v >> 4) * (v & 0xF) for v in fila] for fila in bm]
        return alfa, lum

    aa, la = partir(bytes_a)
    ab, lb = partir(bytes_b)
    ext_a, ext_b = _columnas(aa), _columnas(ab)
    if ext_a is None and ext_b is None:
        raise ValueError("par sin tinta")
    alto = len(aa) if aa else len(ab)

    def cols(alfa: list[list[int]], lum: list[list[int]], ext: tuple[int, int] | None):
        if ext is None:
            return [], []
        x0, x1 = ext
        return ([[alfa[y][x] for y in range(alto)] for x in range(x0, x1 + 1)],
                [[lum[y][x] for y in range(alto)] for x in range(x0, x1 + 1)])

    ca_a, ca_l = cols(aa, la, ext_a)
    cb_a, cb_l = cols(ab, lb, ext_b)
    wa = len(ca_a) or hueco_vacio
    wb = len(cb_a) or hueco_vacio
    s = sep if ca_a and cb_a else 0
    na, nb, estrecho = _anchos(wa, wb, s, ancho_max)
    columnas_a: list[list[float]] = []
    columnas_l: list[list[float]] = []
    for c_a, c_l, n in ((ca_a, ca_l, na), (cb_a, cb_l, nb)):
        if not c_a:
            columnas_a += [[0.0] * alto for _ in range(n)]
            columnas_l += [[0.0] * alto for _ in range(n)]
        else:
            columnas_a += _remuestrear(c_a, n)
            columnas_l += _remuestrear(c_l, n)
        if c_a is ca_a and s:
            columnas_a += [[0.0] * alto for _ in range(s)]
            columnas_l += [[0.0] * alto for _ in range(s)]
    px: dict[tuple[int, int], int] = {}
    for x, (c_a, c_l) in enumerate(zip(columnas_a, columnas_l)):
        for y, (a, lw) in enumerate(zip(c_a, c_l)):
            alfa = min(15, round(a))
            if alfa <= 0:
                continue
            lum = min(15, max(0, round(lw / a))) if a > 0 else 0
            px[(x, y)] = (lum << 4) | alfa
    # recorta columnas vacías del borde (un par con espacio)
    xs = [x for x, _ in px]
    x0 = min(xs)
    px = {(x - x0, y): v for (x, y), v in px.items()}
    return Dibujo(px, max(xs) - x0 + 1, estrecho)


def metricas_centradas(ancho: int, celda: int, tracking: int = 1) -> tuple[int, int, int]:
    """CWDH ``(left, width, advance)`` de un par de ``ancho`` columnas en una fuente de ``celda``.

    El avance es ``ancho + tracking`` (como una letra nativa). ``left`` coloca la tinta centrada en la
    casilla cuando se dibuja a paso fijo (``x = lápiz + trunc((celda - advance) / 2) + left``).
    """
    adv = ancho + tracking
    d = max(0, (celda - ancho) // 2)
    left = d - int((celda - adv) / 2)
    return left, ancho, adv
