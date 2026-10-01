"""IE3 · nombres cortos del unitbase en 6 casillas como mucho, con pares de letras (#87).

Diagnóstico (bisección de datos en Azahar, 2026-09-26): el nombre corto (+0x1C, 16 B) se dibuja a paso
fijo, una casilla por carácter (1 byte latino o 2 bytes Shift-JIS), y el motor admite 6 como mucho (el
japonés llega a 5 de ancho completo). Con 7 o más letras se salen letras de las placas de la alineación y
el partido se cuelga (r7 = 0x4081 en el dibujo por fotograma). Con esos nombres en japonés, no.

Arreglo (autorización tipográfica del usuario del 2026-09-26, solo para estos nombres): juntar pares de
letras en códigos kanji sin uso redibujados como el par, hasta que cada nombre ocupe <= 6 casillas. El
nombre sigue completo (nunca se abrevia) y la primera casilla no se toca (el Registro calcula la pestaña
con el primer carácter). El último byte del campo (+0x1C+15) es la marca de la capa
``lista_registro_latina`` y se conserva.

API sin E/S: :func:`leer_cortos`, :func:`plan`, :func:`reescribir`, :func:`dibujar_en_fuente` y
:func:`comprobar`. La capa de ``work/ie3/shared/capas/nombres/`` elige los
códigos, abre el archive.fa y escribe.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from ie123kit.nucleo.fuentes import celdas, pares_celda
from ie123kit.nucleo.fuentes.pares_celda import Par

__all__ = [
    "CORTO",
    "LARGO",
    "LIMITE",
    "PRESUPUESTO",
    "TAMANO",
    "Plan",
    "bytes_la4",
    "codepoint_casilla",
    "comprobar",
    "coste_par",
    "dibujar_en_fuente",
    "leer_cortos",
    "plan",
    "reescribir",
    "visible",
]

TAMANO = 0x68
CORTO = 0x1C
LARGO = 16
LIMITE = 6
#: ancho máximo de tinta de un par por fuente (FONT8: paso 10 de la pestaña; FONT12: paso 15; FONT12T: 16)
PRESUPUESTO = {"font/FONT8.bcfnt": 9, "font/FONT12.bcfnt": 13, "font/FONT12T.bcfnt": 14}


def leer_cortos(unitbase: bytes) -> list[bytes]:
    """Texto (sin NUL) del nombre corto de cada registro de 0x68 B."""
    if len(unitbase) % TAMANO:
        raise ValueError("unitbase del IE3 con tamaño no múltiplo de 0x68")
    return [unitbase[i + CORTO:i + CORTO + LARGO - 1].split(b"\0", 1)[0]
            for i in range(0, len(unitbase), TAMANO)]


def reescribir(unitbase: bytes, nuevos: Mapping[int, bytes]) -> bytes:
    """Escribe cada nombre corto nuevo (índice -> bytes) y conserva el byte de marca +0x1C+15."""
    salida = bytearray(unitbase)
    for i, texto in nuevos.items():
        if len(texto) > LARGO - 1:
            raise ValueError(f"nombre corto de {len(texto)} B en el registro {i}: máximo {LARGO - 1}")
        base = i * TAMANO + CORTO
        salida[base:base + LARGO - 1] = texto.ljust(LARGO - 1, b"\0")
    return bytes(salida)


def visible(casilla: bytes, inverso: Mapping[str, str]) -> str:
    """Carácter visible de una casilla (el portador griego vuelve a su acento con ``inverso``)."""
    ch = casilla.decode("cp932")
    return inverso.get(ch, ch)


def codepoint_casilla(casilla: bytes) -> int:
    """Codepoint con que la BCFNT dibuja la casilla: ASCII tal cual; 2 bytes, su Unicode cp932."""
    return casilla[0] if len(casilla) == 1 else ord(casilla.decode("cp932"))


@dataclass
class Plan:
    """Pares elegidos y nueva partición de cada nombre largo."""

    pares: list[Par]
    particiones: dict[bytes, tuple[bytes | Par, ...]] = field(default_factory=dict)

    def codificar(self, texto: bytes, codigos: Mapping[Par, bytes]) -> bytes:
        partes = self.particiones.get(texto)
        return texto if partes is None else pares_celda.codificar(partes, codigos)


def plan(textos: Iterable[bytes], coste: Callable[[Par], float] | None = None,
         admitido: Callable[[Par], bool] | None = None, limite: int = LIMITE) -> Plan:
    """Pares mínimos (heurística voraz) y partición de cada texto que pasa de ``limite`` casillas."""
    largos = sorted({t for t in textos if len(pares_celda.casillas(t)) > limite})
    cas = [pares_celda.casillas(t) for t in largos]
    pares = pares_celda.elegir_pares(cas, limite, coste=coste, admitido=admitido)
    part = {t: pares_celda.particion(c, pares, limite, coste=coste) for t, c in zip(largos, cas)}
    return Plan(pares, part)


# --------------------------------------------------------------------------- fuentes

def bytes_la4(fuente: celdas.FuenteBCFNT, gi: int) -> list[list[int]]:
    """Bytes LA4 crudos del glifo ``gi`` (sin el margen de 1 px), para no perder luminancia y alfa."""
    t, f = fuente.t, fuente.f
    if t["fmt"] != 9:
        raise ValueError("bytes_la4: solo LA4 (fmt 9)")
    sheet, cell = divmod(gi, f.PER)
    ox = (cell % t["ncols"]) * fuente.sx
    oy = (cell // t["ncols"]) * fuente.sy
    tw = t["sheet_w"] // 8
    base = f.doff + sheet * t["sheet_size"]
    filas = []
    for y in range(fuente.sy - 1):
        fila = []
        for x in range(fuente.sx - 1):
            X, Y = ox + 1 + x, oy + 1 + y
            tile = (Y // 8) * tw + (X // 8)
            fila.append(f.data[base + tile * 64 + fuente._morton8(X % 8, Y % 8)])
        filas.append(fila)
    return filas


def _mapa(fuente: celdas.FuenteBCFNT, casilla: bytes) -> list[list[int]]:
    gi = fuente.gi(codepoint_casilla(casilla))
    if gi is None:
        raise KeyError(f"la fuente no tiene la casilla {casilla!r}")
    return bytes_la4(fuente, gi) if fuente.fmt == 9 else fuente.bitmap(gi)


def _ancho_natural(fuente: celdas.FuenteBCFNT, par: Par, sep: int = 1) -> int:
    anchos = []
    for c in par:
        bm = _mapa(fuente, c)
        xs = [x for row in bm for x, v in enumerate(row) if v]
        anchos.append(max(xs) - min(xs) + 1 if xs else 2)
    return anchos[0] + sep + anchos[1]


def coste_par(fuentes: Mapping[str, celdas.FuenteBCFNT],
              presupuesto: Mapping[str, int] = PRESUPUESTO) -> Callable[[Par], float]:
    """Coste de dibujar un par: cuánto hay que estrecharlo (suma relativa por fuente; 0 si cabe)."""
    cache: dict[Par, float] = {}

    def coste(p: Par) -> float:
        if p not in cache:
            try:
                cache[p] = sum(max(0, _ancho_natural(f, p) - presupuesto[n]) / presupuesto[n]
                               for n, f in fuentes.items())
            except KeyError:
                cache[p] = float("inf")
        return cache[p]

    return coste


def dibujar_en_fuente(fuente: celdas.FuenteBCFNT, codigos: Mapping[Par, bytes], ancho_max: int,
                      sep: int = 1) -> dict[str, dict[str, Any]]:
    """Redibuja en ``fuente`` cada código como su par y le pone métricas centradas en la casilla.

    Devuelve, por código (hex), glifo, CWDH anterior y nuevo, ancho, si se estrechó y la huella.
    """
    celda = fuente.t["cell_w"]
    esc = celdas.escritor(fuente)
    salida: dict[str, dict[str, Any]] = {}
    # primero se leen todas las letras (ningún código es una letra, pero así el orden no importa)
    mapas = {p: (_mapa(fuente, p[0]), _mapa(fuente, p[1])) for p in codigos}
    for p, codigo in codigos.items():
        a, b = mapas[p]
        if fuente.fmt == 9:
            d = pares_celda.componer_la4(a, b, ancho_max, sep=sep)
        else:
            d = pares_celda.componer(a, b, ancho_max, sep=sep)
        alto = fuente.sy - 1
        px = {(x, y): v for (x, y), v in d.px.items() if y < alto}
        if d.ancho > fuente.sx - 1:
            raise ValueError(f"par {p!r} más ancho que la celda")
        gi = fuente.gi(ord(codigo.decode("cp932")))
        if gi is None:
            raise KeyError(f"el código {codigo.hex().upper()} no tiene glifo")
        viejo = list(fuente.metrics[gi])
        celdas.pintar(fuente, gi, px, esc)
        left, width, adv = pares_celda.metricas_centradas(d.ancho, celda)
        fuente.set_metrics(gi, left, width, adv)
        salida[codigo.hex().upper()] = {"glifo": gi, "cwdh_antes": viejo, "cwdh": [left, width, adv],
                                        "ancho": d.ancho, "estrechado": d.estrechado,
                                        "pixeles_sha1": _sha(px)}
    return salida


def _sha(px: Mapping[tuple[int, int], int]) -> str:
    import hashlib
    import json

    return hashlib.sha1(json.dumps(sorted(px.items())).encode()).hexdigest()


def comprobar(originales: Sequence[bytes], nuevos: Sequence[bytes], codigos: Mapping[Par, bytes],
              limite: int = LIMITE) -> list[str]:
    """Errores: nombre que no vuelve igual al decodificar, que pasa de ``limite`` o con la 1.ª casilla cambiada."""
    errores = []
    for i, (o, n) in enumerate(zip(originales, nuevos)):
        if pares_celda.decodificar(n, codigos) != o:
            errores.append(f"{i}: {o!r} no vuelve igual ({n!r})")
        c = pares_celda.casillas(n)
        if len(c) > limite:
            errores.append(f"{i}: {o!r} ocupa {len(c)} casillas")
        if o and c and c[0] != pares_celda.casillas(o)[0]:
            errores.append(f"{i}: {o!r} cambia la primera casilla")
    return errores
