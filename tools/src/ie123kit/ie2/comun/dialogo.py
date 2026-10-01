"""Diálogo de IE2: límites del motor parcheado y reparto seguro de un registro.

Porteo de ``work/ie2/shared/capas/dialogo/saltos37/comun19.py`` (``reparte``) sobre el motor
genérico ``nucleo.texto.paginado``. Límites (medidos en ina_main2.cro con la CRO parcheada por la
capa ``menus_cro/ancho_dialogo``; ver ``docs/FURIGANA_LECCIONES.md``):

- reajuste 0x48398 con ``[ventana+0x131e]`` = 0x1A0 -> 448 px / 37 caracteres por línea;
- dibujo 0x121a78 con el ancho global 0x1C0 (0x4d6a0) -> también 37;
- 3 líneas por página y búfer de página de 131 B (copia 0x4d5c4-0x4d638, pila sp+0x40..0xc3);
- 247 B por registro.

El texto nunca cambia: solo se mueven los saltos (Norma 3). Un registro solo se rehace si el viaje
de ida y vuelta ``texto -> transporte`` lo reproduce byte a byte.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable

from ie123kit.nucleo.texto import paginado as P

__all__ = [
    "MODELO_IE2",
    "MODELO_IE2_ORIGINAL",
    "SUSTITUIR",
    "es_espanol",
    "espanol",
    "normalizar",
    "palabras",
    "pct",
    "reparte",
    "sin_glifo",
]

#: Motor de IE2 con la CRO parcheada (37 × 3, 131 B por página, 247 B por registro).
MODELO_IE2 = P.ModeloMotor(ancho_ventana=0x1A0, ancho_dibujo=0x1C0, pagina_max=131, registro_max=247)

#: Motor de IE2 sin parchear (0xF0 -> 22 × 3; la rejilla original de 0x120 corta en 24).
MODELO_IE2_ORIGINAL = P.ModeloMotor(ancho_ventana=0xF0, ancho_dibujo=0x120, pagina_max=131, registro_max=247)

#: Caracteres sin glifo útil (práctica de IE1: sin comillas ni apóstrofos). ``-`` y ``~`` no tienen
#: ancho completo en shift_jis: − (0x817C) y 〜 (0x8160).
SUSTITUIR = {"”": "", "“": "", '"': "", "'": "", "’": "", "　": " ", "-": "−", "~": "〜", "～": "〜"}

_JAPONES = re.compile(r"[぀-ヿ一-鿿]")
_LATINO = re.compile(r"[A-Za-zÁÉÍÓÚáéíóúñÑ]")
_CONTROL = re.compile(r"%[0-9]*[A-Za-z]|\\[nf]")


def normalizar(texto: str) -> str:
    for a, b in SUSTITUIR.items():
        texto = texto.replace(a, b)
    return texto


def pct(texto: str) -> tuple[int, int]:
    return texto.count("%s"), texto.count("%d")


def espanol(cuerpo: bytes) -> str:
    """Registro -> texto español normalizado (controles intactos)."""
    return normalizar(P.a_legible(cuerpo).replace("－", "−").replace("～", "〜"))


def es_espanol(cuerpo: bytes) -> bool:
    t = espanol(cuerpo)
    return bool(_LATINO.search(t)) and not _JAPONES.search(t)


def palabras(texto: str) -> list[str]:
    return texto.replace(P.SALTO, " ").replace(P.PAGINA, " ").split()


def sin_glifo(cuerpo: bytes, glifos: Iterable[int]) -> list[str]:
    """Caracteres del registro sin glifo en la fuente del diálogo (``glifos`` = códigos del cmap)."""
    conjunto = glifos if isinstance(glifos, (set, frozenset)) else frozenset(glifos)
    t = _CONTROL.sub("", cuerpo.decode("cp932"))
    return sorted({c for c in t if ord(c) not in conjunto})


def _transporte_v20(texto: str) -> bytes:
    from ie123kit.nucleo.texto.ancho_completo import encode_fullwidth

    return encode_fullwidth(texto)


def reparte(cuerpo: bytes, glifos: Iterable[int], modelo: P.ModeloMotor = MODELO_IE2,
            transportar: Callable[[str], bytes] | None = None) -> tuple[bytes | None, str]:
    """Registro -> ``(nuevo cuerpo, texto)`` repartido con ``modelo``; ``(None, motivo)`` si no es seguro.

    Mismo orden de comprobaciones que la capa: texto español, ida y vuelta exacta, reparto,
    mismas palabras, mismos ``%s``/``%d``, todos los caracteres con glifo, sin reajuste del motor y
    sin problemas del modelo.
    """
    transportar = transportar or _transporte_v20
    if not es_espanol(cuerpo):
        return None, "no es texto español"
    try:
        exacto = transportar(espanol(cuerpo)) == cuerpo
    except Exception:  # noqa: BLE001 - cualquier fallo del transporte = no se rehace
        exacto = False
    if not exacto:
        return None, "ida y vuelta no exacta"
    antes = espanol(cuerpo)
    try:
        texto = P.repartir(antes, modelo, transportar)
    except ValueError as e:
        return None, str(e)[:120]
    nuevo = transportar(texto)
    if palabras(espanol(nuevo)) != palabras(antes):
        return None, "palabras distintas"
    if pct(nuevo.decode("cp932")) != pct(cuerpo.decode("cp932")):
        return None, "%s/%d distintos"
    faltan = sin_glifo(nuevo, glifos)
    if faltan:
        return None, "sin glifo: " + "".join(faltan)
    if P.reajusta(nuevo, modelo):
        return None, "el motor reajusta"
    p = P.problemas(nuevo, modelo)
    if p:
        return None, "; ".join(p)
    return nuevo, texto
