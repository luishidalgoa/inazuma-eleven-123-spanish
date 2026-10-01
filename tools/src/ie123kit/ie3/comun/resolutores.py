"""Resolutores de texto para el diálogo del IE3 que no empareja el corpus (funciones puras, sin E/S).

Los usan las capas de work/ (dialogo/restantes_2) y los podrá usar la app gráfica. Entrada y salida son datos:

- :func:`memoria_unanime`: japonés → la ÚNICA traducción oficial que le dan los corpus (solo si existe re-extraída).
- :func:`reparto_valido`: comprueba que unas partes reconstruyen exactamente una frase oficial cortada en separadores.
- :func:`indexar_lineas`: tabla (perfil, evento, instrucción) → (texto, método) desde listas de decisiones.
- :func:`repite_vecina`: si una frase ya la muestra una caja vecina (para no duplicarla).
- :func:`intercambiar_referencia`: la Referencia de un 301D con los operandos 1↔2 intercambiados (ver
  ``ie3.comun.transformaciones``), para compilar el español como si el bytecode ya estuviera cambiado.
- :func:`cortar_en_dos`: parte una frase oficial en dos por su corte más natural (página, fin de oración, coma)
  para repartirla en dos registros (inserción de un 301D).
- :func:`quitar_furigana`: el japonés sin marcas ``%nF`` (no cuentan como controles del español).
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import replace

__all__ = ["cortar_en_dos", "indexar_lineas", "intercambiar_referencia", "memoria_unanime", "quitar_furigana", "reparto_valido",
           "repite_vecina"]

_FURIGANA = re.compile(r"%\d+F")
SALTO = "\\n"          # salto de línea literal del texto (barra + n)
PAGINA = "\\f"         # salto de página literal (barra + f)


def memoria_unanime(filas: Iterable[Mapping], oficiales: set[str],
                    estados: tuple[str, ...] = ("oficial", "memoria")) -> dict[str, str]:
    """``filas`` con claves japones/es_final/estado (formato de translation/…/dialogo_oficial.csv)."""
    alt: dict[str, set[str]] = defaultdict(set)
    for r in filas:
        if r["estado"] in estados and r["es_final"] and r["es_final"] in oficiales:
            alt[r["japones"]].add(r["es_final"])
    return {jp: next(iter(es)) for jp, es in alt.items() if len(es) == 1}


def reparto_valido(frase: str, partes: list[str]) -> bool:
    """Las partes, unidas por el separador original (espacio o ``\\n`` literal), dan exactamente ``frase``."""
    if not partes or any(not p or p.startswith(SALTO) or p.endswith(SALTO) for p in partes):
        return False
    pos = 0
    for k, p in enumerate(partes):
        if frase[pos:pos + len(p)] != p:
            return False
        pos += len(p)
        if k < len(partes) - 1:
            if frase[pos:pos + 2] == SALTO:
                pos += 2
            elif frase[pos:pos + 1] == " ":
                pos += 1
            else:
                return False
    return pos == len(frase)


def indexar_lineas(lineas: Iterable[Mapping], metodo: str) -> dict[tuple[str, int, int], tuple[str, str]]:
    """Cada línea: evento, ins, es y perfiles (lista). Las que no traen ``es`` (omitidas) no se indexan."""
    out = {}
    for x in lineas:
        if not x.get("es"):
            continue
        for perfil in x["perfiles"]:
            out[(perfil, int(x["evento"]), int(x["ins"]))] = (x["es"], metodo)
    return out


def repite_vecina(frase: str, vecinas: Iterable[str | None]) -> bool:
    return any(v is not None and v == frase for v in vecinas)


def intercambiar_referencia(ref):
    ins = ref.instruccion
    if len(ins.tipos) < 3:
        raise ValueError("intercambio: el 301D necesita al menos 3 operandos")
    t, v = list(ins.tipos), list(ins.valores)
    t[1], t[2], v[1], v[2] = t[2], t[1], v[2], v[1]
    return replace(ref, instruccion=replace(ins, tipos=tuple(t), valores=tuple(v)))


def quitar_furigana(japones: str) -> str:
    return _FURIGANA.sub("", japones)


_FIN = re.compile(r"[.!?…»\"”)]$")


def cortar_en_dos(texto: str, cabe) -> tuple[str, str] | None:
    """Corta ``texto`` en dos partes que cumplan ``cabe(parte) -> bool``, sin quitar ni cambiar palabras.

    Solo corta en un separador (``\\f``, ``\\n`` literales o espacio), que desaparece. Preferencia: salto de página;
    luego fin de oración; luego coma; después cualquier separador. Dentro de cada clase, el corte más equilibrado.
    Devuelve None si ningún corte deja las dos partes dentro de ``cabe``.
    """
    cortes = []
    i = 0
    while i < len(texto):
        for sep in (PAGINA, SALTO, " "):
            if texto.startswith(sep, i):
                izq, der = texto[:i], texto[i + len(sep):]
                if izq.strip() and der.strip():
                    if sep == PAGINA:
                        clase = 0
                    elif _FIN.search(izq.rstrip()):
                        clase = 1
                    elif izq.rstrip().endswith(","):
                        clase = 2
                    elif sep == SALTO:
                        clase = 3
                    else:
                        clase = 4
                    cortes.append((clase, abs(len(izq) - len(der)), izq, der))
                i += len(sep) - 1
                break
        i += 1
    for clase, _, izq, der in sorted(cortes):
        if cabe(izq) and cabe(der):
            return izq, der
    return None
