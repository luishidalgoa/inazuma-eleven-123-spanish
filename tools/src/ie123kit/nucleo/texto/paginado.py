"""Modelo del ajuste automático de la ventana de diálogo y reparto del texto en páginas.

Porteo de ``comun82.py`` (IE1 v84, modelo del motor), ``comun17.py`` (IE2 v17, modelo ampliado con
la rejilla de dibujo y el búfer de página) y ``comun19.py`` (IE2 v19, envoltorio ``reparte``). Los
límites de cada juego no están aquí: se pasan en un :class:`ModeloMotor` (IE1 en
``ie123kit.ie1.texto.dialogo``, IE2 en ``ie123kit.ie2.comun.reglas``). La misma función vale para
IE3 en cuanto se midan sus límites.

Motor (evidencia de IE1 en ina_main1.cro 0x424f4; de IE2 en ina_main2.cro 0x48398):

- el preproceso convierte ``\\n``/``\\f`` (dos bytes ASCII en el registro) en 0x0A/0x0C;
- el ajuste recorre carácter a carácter con límite ``ancho_ventana + extra``; cada carácter avanza
  ``avance`` px (FONT12: 12, no depende del carácter). Si ``x + avance >= límite`` se inserta un
  salto; un 0x0A en la última línea de la página pasa a 0x0C. Corta por carácter, no por palabra;
- IE2 añade la rejilla de dibujo (``ancho_dibujo``, corte si ``x + avance > ancho``) y el búfer de
  página de la pila: página = ``2·caracteres + (líneas − 1)`` bytes, tope ``pagina_max``;
- ``%s`` y ``%d`` se expanden ANTES del ajuste, así que se simulan con su ancho reservado; ``%NF``
  (furigana) no ocupa.

Nada aquí cambia texto: :func:`repartir` y :func:`partir_paginas` solo mueven saltos (Norma 3).
El transporte de ancho completo es el bloqueado v20 (``nucleo.texto.ancho_completo``); se usa por
parámetro y nunca se copia.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from functools import lru_cache
from types import MappingProxyType

__all__ = [
    "PAGINA",
    "SALTO",
    "ModeloMotor",
    "a_legible",
    "ajuste",
    "caracteres",
    "dibujo",
    "largo",
    "paginas",
    "partir_paginas",
    "preprocesar",
    "problemas",
    "reajusta",
    "repartir",
    "simular",
]

#: Salto de línea y de página tal como van en el registro (dos bytes ASCII cada uno).
SALTO, PAGINA = r"\n", r"\f"

_NF = re.compile(rb"%\d*F")
_PCT = re.compile(r"%[sd]")
_TOK = re.compile(r"(\\n|\\f)")
_RELLENO = "Ｘ".encode("cp932")
_ANCHOS_PCT = MappingProxyType({"%s": 12, "%d": 5})


@dataclass(frozen=True)
class ModeloMotor:
    """Límites medidos del ajuste de una ventana de diálogo.

    ``ancho_ventana`` es el valor de la ventana (IE1 ``[+0x1316]`` = 0xF0; IE2 parcheado
    ``[+0x131e]`` = 0x1A0). ``ancho_dibujo`` y ``pagina_max`` son opcionales: ``None`` = el juego
    no tiene ese segundo corte (IE1). ``registro_max`` es el tope de bytes de un registro.
    """

    ancho_ventana: int
    extra: int = 0x20
    avance: int = 12
    lineas: int = 3
    ancho_dibujo: int | None = None
    pagina_max: int | None = None
    registro_max: int | None = None
    anchos_pct: Mapping[str, int] = field(default_factory=lambda: _ANCHOS_PCT)
    #: Opcional (2026-09-22): ancho real dibujado de una línea en unidades de la fuente, y tope por
    #: línea de la página (``px_linea[k]`` para la línea k; la última suele ser menor por el icono).
    #: Con ``None`` el reparto solo cuenta caracteres, como antes.
    medir_px: Callable[[str], int] | None = field(default=None, compare=False)
    px_linea: tuple[int, ...] | None = None

    @property
    def limite(self) -> int:
        return self.ancho_ventana + self.extra

    @property
    def max_car(self) -> int:
        """Caracteres por línea que caben sin que el motor inserte un salto."""
        por_ajuste = max(n for n in range(1, 256) if (n - 1) * self.avance + self.avance < self.limite)
        if self.ancho_dibujo is None:
            return por_ajuste
        por_dibujo = max(n for n in range(1, 256) if n * self.avance <= self.ancho_dibujo)
        return min(por_ajuste, por_dibujo)


# ------------------------------------------------------------------ motor sobre bytes


def simular(cuerpo: bytes, modelo: ModeloMotor) -> bytes:
    """Cuerpo tal como llega al ajuste: ``%s``/``%d`` a su ancho reservado y ``%NF`` fuera."""
    t = _NF.sub(b"", cuerpo)
    for codigo, ancho in modelo.anchos_pct.items():
        t = t.replace(codigo.encode(), _RELLENO * ancho)
    return t


def preprocesar(cuerpo: bytes) -> bytes:
    """``\\n``/``\\f`` -> 0x0A/0x0C. Falla con códigos ``%`` (hay que :func:`simular` antes)."""
    out, i = bytearray(), 0
    while i < len(cuerpo):
        b = cuerpo[i]
        if b == 0x25:
            raise ValueError("código % no modelado")
        if b == 0x5C:
            i += 1
            c = cuerpo[i]
            out.append({0x6E: 0x0A, 0x66: 0x0C}.get(c, c))
            i += 1
            continue
        if b & 0x80:
            out += cuerpo[i:i + 2]
            i += 2
        else:
            out.append(b)
            i += 1
    return bytes(out)


def ajuste(cuerpo: bytes, modelo: ModeloMotor, *, simulado: bool = False) -> bytes:
    """Texto tal como lo deja el ajuste automático del motor (0x0A/0x0C insertados).

    Con ``simulado=True`` el cuerpo ya viene de :func:`simular`.
    """
    s = bytearray(preprocesar(cuerpo if simulado else simular(cuerpo, modelo)))
    sl, out, x, ln, i = modelo.limite, bytearray(), 0, 0, 0
    while i < len(s):
        c = s[i]
        if c == 0x0A:
            ln += 1
            x = 0
            if ln >= modelo.lineas:
                s[i] = 0x0C
                ln = 0
        elif c == 0x0C:
            x = ln = 0
        else:
            w = modelo.avance
            if x + w >= sl:
                ln += 1
                if ln < modelo.lineas:
                    out.append(0x0A)
                else:
                    out.append(0x0C)
                    ln = 0
                x = 0
            x += w
        if s[i] & 0x80:
            out.append(s[i])
            i += 1
        out.append(s[i])
        i += 1
    return bytes(out)


def caracteres(linea: bytes) -> int:
    """Caracteres de una línea en bytes (un carácter de ancho completo ocupa 2 B)."""
    n, i = 0, 0
    while i < len(linea):
        i += 2 if linea[i] & 0x80 else 1
        n += 1
    return n


def dibujo(linea: bytes, modelo: ModeloMotor) -> list[bytes]:
    """Corte de la rejilla de dibujo: ``x + avance > ancho_dibujo`` abre línea."""
    if modelo.ancho_dibujo is None:
        return [linea]
    out, x, cur, i = [], 0, bytearray(), 0
    while i < len(linea):
        n = 2 if linea[i] & 0x80 else 1
        if x + modelo.avance > modelo.ancho_dibujo:
            out.append(bytes(cur))
            cur, x = bytearray(), 0
        cur += linea[i:i + n]
        x += modelo.avance
        i += n
    out.append(bytes(cur))
    return out


def paginas(cuerpo: bytes, modelo: ModeloMotor) -> list[bytes]:
    """Páginas (en bytes, con 0x0A entre líneas) tal como las dibuja el motor."""
    return ajuste(cuerpo, modelo).split(b"\x0c")


def problemas(cuerpo: bytes, modelo: ModeloMotor) -> list[str]:
    """Comprobación del modelo completo sobre un registro; lista vacía = cabe."""
    p = []
    for k, pg in enumerate(paginas(cuerpo, modelo)):
        if modelo.pagina_max is not None and len(pg) > modelo.pagina_max:
            p.append(f"página {k}: {len(pg)} B > {modelo.pagina_max}")
        lineas = pg.split(b"\n")
        if len(lineas) > modelo.lineas:
            p.append(f"página {k}: {len(lineas)} líneas")
        for ln in lineas:
            if caracteres(ln) > modelo.max_car:
                p.append(f"página {k}: línea de {caracteres(ln)} caracteres")
            if len(dibujo(ln, modelo)) != 1:
                p.append(f"página {k}: el dibujo parte la línea")
    return p


def reajusta(cuerpo: bytes, modelo: ModeloMotor) -> bool:
    """True si el motor inserta algún salto (convertir un ``\\n`` de última línea en 0x0C no cuenta)."""
    pre = preprocesar(simular(cuerpo, modelo))
    return ajuste(cuerpo, modelo).replace(b"\x0c", b"\n") != pre.replace(b"\x0c", b"\n")


def a_legible(cuerpo: bytes) -> str:
    """Registro en transporte de ancho completo -> texto legible (los controles quedan intactos).

    Igual que ``a_espanol`` de las capas (v77): U+3000 -> espacio, U+FF01..U+FF5E -> ASCII y los
    portadores de ``ACCENTS`` (bloqueo v20) -> su letra acentuada.
    """
    from ie123kit.nucleo.texto.ancho_completo import ACCENTS

    inverso = {portador: ch for ch, portador in ACCENTS.items()}
    return "".join(
        inverso.get(c, " " if c == "　" else (chr(ord(c) - 0xFEE0) if 0xFF01 <= ord(c) <= 0xFF5E else c))
        for c in cuerpo.decode("cp932")
    )


# ------------------------------------------------------------------ reparto de texto español


def largo(linea: str, modelo: ModeloMotor) -> int:
    """Caracteres que ocupa una línea española, con ``%s``/``%d`` a su ancho reservado."""
    n = sum(modelo.anchos_pct[m.group()] for m in _PCT.finditer(linea))
    return n + len(_PCT.sub("", linea))


def _transporte_v20(texto: str) -> bytes:
    from ie123kit.nucleo.texto.ancho_completo import encode_fullwidth

    return encode_fullwidth(texto)


def repartir(texto: str, modelo: ModeloMotor, transportar: Callable[[str], bytes] | None = None) -> str:
    """Texto íntegro -> páginas de ``lineas × max_car`` (y ``<= pagina_max`` B), sin cortar palabras.

    Programación dinámica sobre los cortes de página entre palabras. Coste: cada página 100; cortar
    tras fin de frase 0, tras coma, punto y coma o dos puntos 60, en otro sitio 150; página de menos
    de 12 caracteres +200 (evita «río...» sueltos). Los saltos del texto se ignoran. Si una palabra
    no cabe sola en una línea se lanza ``ValueError`` (nunca se acorta nada).
    """
    transportar = lru_cache(maxsize=None)(transportar or _transporte_v20)
    max_car = modelo.max_car

    def cabe(linea: str, k: int = 0) -> bool:
        if largo(linea, modelo) > max_car:
            return False
        if modelo.medir_px is not None and modelo.px_linea:
            tope = modelo.px_linea[min(k, len(modelo.px_linea) - 1)]
            return modelo.medir_px(linea) <= tope
        return True

    def envolver(palabras: list[str]):
        filas, actual = [], ""
        for w in palabras:
            if not cabe(w, len(filas)):
                return None
            cand = f"{actual} {w}" if actual else w
            if actual and not cabe(cand, len(filas)):
                filas.append(actual)
                actual = w
                if not cabe(w, len(filas)):
                    return None
            else:
                actual = cand
        if actual:
            filas.append(actual)
        return filas

    def bytes_pagina(filas: list[str]) -> int:
        return sum(len(simular(transportar(x), modelo)) for x in filas) + len(filas) - 1

    ws = " ".join(texto.replace(PAGINA, " ").replace(SALTO, " ").split()).split()
    n = len(ws)
    if not n:
        return ""
    inf = float("inf")
    mejor = [inf] * (n + 1)
    previo = [0] * (n + 1)
    mejor[0] = 0

    def coste_corte(j: int) -> int:
        if j == n:
            return 0
        w = ws[j - 1]
        if re.search(r"[.!?…]$", w):
            return 0
        if re.search(r"[,;:]$", w):
            return 60
        return 150

    for j in range(1, n + 1):
        for i in range(j - 1, -1, -1):
            if mejor[i] == inf:
                continue
            filas = envolver(ws[i:j])
            if filas is None or len(filas) > modelo.lineas:
                break
            if modelo.pagina_max is not None and bytes_pagina(filas) > modelo.pagina_max:
                break
            c = mejor[i] + 100 + coste_corte(j)
            if sum(largo(x, modelo) for x in filas) < 12 and n > 1 and (i > 0 or j < n):
                c += 200
            if c < mejor[j]:
                mejor[j], previo[j] = c, i
    if mejor[n] == inf:
        raise ValueError("no cabe: " + " ".join(ws))
    cortes, j = [], n
    while j:
        cortes.append((previo[j], j))
        j = previo[j]
    pags = [envolver(ws[i:j]) for i, j in reversed(cortes)]
    return PAGINA.join(SALTO.join(p) for p in pags)


def partir_paginas(texto: str, modelo: ModeloMotor,
                   legible: Callable[[bytes], str] = a_legible) -> tuple[str, int]:
    """Registro existente (cp932 decodificado) -> mismo texto con ``\\n`` cambiados por ``\\f``.

    Solo corta donde una página del motor pasaría de ``pagina_max`` B; prefiere el último ``\\n``
    de la página tras fin de frase. Tamaño idéntico (ambos 2 B). Devuelve ``(texto, cortes)``.
    """
    if modelo.pagina_max is None:
        return texto, 0
    partes = _TOK.split(texto)
    trozos, seps = partes[0::2], partes[1::2]

    def b(t: str) -> int:
        return len(simular(t.encode("cp932"), modelo))

    cortes = 0
    inicio, n_lineas, tam = 0, 1, b(trozos[0])
    k = 0
    while k < len(seps):
        sig = b(trozos[k + 1])
        if seps[k] == PAGINA or n_lineas >= modelo.lineas:
            inicio, n_lineas, tam = k + 1, 1, sig
        elif tam + 1 + sig > modelo.pagina_max:
            j = k
            for c in range(k, inicio - 1, -1):
                if seps[c] == SALTO and re.search(r"[.!?…](\s|%)*$", legible(trozos[c].encode("cp932"))):
                    j = c
                    break
            seps[j] = PAGINA
            cortes += 1
            k = j
            continue
        else:
            n_lineas += 1
            tam += 1 + sig
        k += 1
    out = [trozos[0]]
    for s, t in zip(seps, trozos[1:], strict=True):
        out += [s, t]
    return "".join(out), cortes
