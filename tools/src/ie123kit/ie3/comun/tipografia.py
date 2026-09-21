"""Adaptación tipográfica latina de IE3 desde los recursos europeos oficiales.

El contenedor BCFNT japonés se conserva para no alterar su tamaño, CMAP ni los
glifos japoneses. Cada carácter latino adaptado recibe, como una sola unidad, el
raster y CWDH de la fuente europea. La diferencia de baseline se resuelve
por traslación estricta: nunca se recorta ni se fusiona tinta.

FONT12 añade el píxel de respiración general ya usado por el parche histórico.
FONT8 usa las métricas oficiales sin bigramas: cada letra de un nombre vuelve a
ser un glifo independiente.
"""
from __future__ import annotations

import struct
import tempfile
from pathlib import Path

from ie123kit.ie3.comun.text import TextTable
from ie123kit.nucleo.config.congelados import cargar

PORTADORES_EXTRA = {"È": 0x03A0}
_PLAN = cargar("font_patch").PLAN
_BASE = {accented: plain for accented, plain, _kind, _cp in _PLAN}
_BASE["È"] = "E"
_PORTADORES = {visible: cp for visible, _base, _kind, cp in _PLAN}
_PORTADORES.update(PORTADORES_EXTRA)
_REEMPLAZOS = {"ª": "a", "º": "o", "“": '"', "”": '"', "—": "-", "…": "."}


class FuenteBCFNT(cargar("font_patch").Font):
    """Lector A4 con coordenadas de textura BCFNT (sin tocar el congelado).

    El tamaño de hoja puede incluir espacio sobrante: no determina el stride.
    Cada celda empieza después de un margen de un píxel. Referencia independiente:
    libctru/font.c, fontCalcGlyphPos.
    """

    def __init__(self, path):
        super().__init__(path)
        if self.t["sheet_size"] * 2 != self.t["sheet_w"] * self.t["sheet_h"]:
            raise ValueError("FuenteBCFNT requiere textura A4")
        self.sx = self.t["cell_w"] + 1
        self.sy = self.t["cell_h"] + 1

    def _poff(self, gi, x, y):
        return super()._poff(gi, x + 1, y + 1)

# CWDH oficial europeo + 1 px para letras. Es la misma política de tracking
# documentada en sjis_portador._advance; espacios y puntuación normal conservan
# su avance oficial. Los signos invertidos reciben también el píxel aplicado a
# sus portadores por el parche histórico.
AVANCES_FONT12 = {
    " ": 3, "!": 2, '"': 5, "#": 8, "$": 8, "%": 11, "&": 10,
    "'": 2, "(": 4, ")": 4, "*": 6, "+": 8, ",": 2, "-": 5,
    ".": 2, "/": 6, "0": 8, "1": 4, "2": 7, "3": 8, "4": 8,
    "5": 8, "6": 7, "7": 8, "8": 8, "9": 8, ":": 2, ";": 2,
    "<": 6, "=": 7, ">": 6, "?": 7, "@": 11, "A": 11, "B": 9,
    "C": 10, "D": 10, "E": 8, "F": 8, "G": 10, "H": 9, "I": 3,
    "J": 6, "K": 9, "L": 8, "M": 11, "N": 9, "O": 10, "P": 9,
    "Q": 10, "R": 9, "S": 9, "T": 9, "U": 9, "V": 10, "W": 14,
    "X": 10, "Y": 10, "Z": 9, "[": 4, "\\": 6, "]": 4, "^": 6,
    "_": 7, "`": 3, "a": 8, "b": 8, "c": 8, "d": 8, "e": 8,
    "f": 6, "g": 8, "h": 7, "i": 3, "j": 5, "k": 8, "l": 3,
    "m": 11, "n": 7, "o": 8, "p": 8, "q": 8, "r": 6, "s": 8,
    "t": 6, "u": 7, "v": 8, "w": 11, "x": 8, "y": 8, "z": 7,
    "{": 7, "|": 9, "}": 4, "~": 4,
}

# Los acentos europeos no siempre comparten CWDH con su base (`í` mide 5 px
# con tracking, frente a 3 px de `i`). Mantenerlos explícitos evita volver a
# desacoplar el bitmap realmente copiado de la métrica usada por el layout.
AVANCES_ESPECIALES_FONT12 = {
    "á": 8, "é": 8, "í": 5, "ó": 8, "ú": 7, "ü": 7, "ñ": 7,
    "Á": 11, "É": 8, "Í": 4, "Ó": 10, "Ú": 9, "Ñ": 9,
    "¡": 3, "¿": 8, "È": 8,
}


def avance_font12(ch: str) -> int:
    """Avance visible de un carácter en la FONT12 oficial con tracking."""
    if ch in AVANCES_ESPECIALES_FONT12:
        return AVANCES_ESPECIALES_FONT12[ch]
    base = _BASE.get(ch, ch)
    return AVANCES_FONT12.get(base, 8)


def margen_compensado(left: int, nominal: int, avance: int) -> int:
    """Compensa BuildTextCommand: trunc((FINF.width - charWidth) / 2).

    La conversión ARM trunca hacia cero, también cuando el avance supera FINF.
    No afecta al avance que usa el lápiz ni al ancho del raster muestreado.
    """
    resultado = left - int((nominal - avance) / 2)
    if not -128 <= resultado <= 127:
        raise ValueError("margen compensado fuera de CWDH s8")
    return resultado


def _ajustar_grid(grid: list[list[int]], ancho: int, alto: int,
                  dx: int, dy: int) -> tuple[list[list[int]], int]:
    """Traslada sin alterar muestras; rechaza tinta que no cabe."""
    salida = [[0] * ancho for _ in range(alto)]
    fusiones = 0
    for y, fila in enumerate(grid):
        for x, value in enumerate(fila):
            if not value:
                continue
            tx, ty = x + dx, y + dy
            if not (0 <= tx < ancho and 0 <= ty < alto):
                raise ValueError(f"tinta fuera de celda: ({x}, {y}) -> ({tx}, {ty})")
            salida[ty][tx] = value
    return salida, fusiones


def _codepoint_origen(visible: str, reverse: dict[int, int]) -> int:
    fuente = _REEMPLAZOS.get(visible, visible)
    if len(fuente) != 1:
        raise ValueError(f"carácter no trasladable como un glifo: {visible!r}")
    return reverse.get(ord(fuente), ord(fuente))


def _codepoint_destino(visible: str) -> int:
    if visible in _PORTADORES:
        return _PORTADORES[visible]
    destino = _REEMPLAZOS.get(visible, visible)
    if len(destino) != 1:
        raise ValueError(f"carácter sin destino único: {visible!r}")
    return ord(destino)


def _copiar_glifo(destino, origen, visible: str, reverse: dict[int, int],
                  tracking: bool) -> tuple[int, int]:
    destino_cp = _codepoint_destino(visible)
    origen_cp = _codepoint_origen(visible, reverse)
    destino_gi = destino.cmap.get(destino_cp)
    origen_gi = origen.cmap.get(origen_cp)
    if destino_gi is None or origen_gi is None:
        raise ValueError(
            f"glifo ausente para {visible!r}: destino U+{destino_cp:04X}, "
            f"origen U+{origen_cp:04X}"
        )

    dy = destino.t["baseline"] - origen.t["baseline"]
    grid, fusiones = _ajustar_grid(
        origen.read_cell(origen_gi), destino.t["cell_w"],
        destino.t["cell_h"], 0, dy,
    )
    destino.write_cell(destino_gi, grid)

    origen_off = origen.cwdh_entry_off(origen_gi)
    destino_off = destino.cwdh_entry_off(destino_gi)
    if origen_off is None or destino_off is None:
        raise ValueError(f"CWDH ausente para {visible!r}")
    left, glyph_width, char_width = struct.unpack_from(
        "<bBB", origen.data, origen_off
    )
    if tracking and (visible.isalpha() or visible in "¡¿"):
        char_width += 1
    left = margen_compensado(left, destino.b.width, char_width)
    struct.pack_into(
        "<bBB", destino.data, destino_off, left, glyph_width, char_width
    )
    return char_width, fusiones


def _abrir_fuentes(japonesa: bytes, europea: bytes, prefijo: str):
    temporal = tempfile.TemporaryDirectory(prefix=prefijo)
    carpeta = Path(temporal.name)
    ruta_jp = carpeta / "jp.bcfnt"
    ruta_es = carpeta / "es.bcfnt"
    ruta_jp.write_bytes(japonesa)
    ruta_es.write_bytes(europea)
    return temporal, FuenteBCFNT(str(ruta_jp)), FuenteBCFNT(str(ruta_es))


def adaptar_font12(japonesa_parcheada: bytes, europea: bytes,
                   tabla_europea: TextTable) -> tuple[bytes, dict]:
    """Traslada raster+CWDH oficiales y aplica un píxel general de tracking."""
    temporal, destino, origen = _abrir_fuentes(
        japonesa_parcheada, europea, "ie3_font12_"
    )
    try:
        reverse = {real: slot for slot, real in tabla_europea.mapping.items()}
        visibles = [chr(cp) for cp in range(0x20, 0x7F)]
        visibles += [visible for visible, _base, _kind, _cp in _PLAN]
        visibles += list(PORTADORES_EXTRA)
        fusiones = 0
        for visible in visibles:
            avance, unidas = _copiar_glifo(
                destino, origen, visible, reverse, tracking=True
            )
            if avance != avance_font12(visible):
                raise ValueError(
                    f"avance FONT12 inesperado para {visible!r}: "
                    f"{avance} != {avance_font12(visible)}"
                )
            fusiones += unidas
        resultado = bytes(destino.data)
        baseline = destino.t["baseline"]
    finally:
        temporal.cleanup()
    if len(resultado) != len(japonesa_parcheada):
        raise ValueError("la adaptación FONT12 cambió el tamaño del BCFNT")
    return resultado, {
        "glifos": len(visibles),
        "raster": "europeo_oficial_celdas_correctas_traslacion_estricta",
        "regla": "CWDH_ES + 1px en letras/portadores",
        "baseline_destino": baseline,
        "centrado_motor_compensado": True,
        "ancho_nominal": destino.b.width,
        "fusiones_borde": fusiones,
        "portador_E_grave": "U+03A0 / 83AE",
    }


def adaptar_font8_nombres(japonesa_parcheada: bytes, europea: bytes,
                          tabla_europea: TextTable,
                          caracteres: set[str]) -> tuple[bytes, dict]:
    """Adapta los glifos individuales usados por nombres; no crea bigramas."""
    temporal, destino, origen = _abrir_fuentes(
        japonesa_parcheada, europea, "ie3_font8_"
    )
    try:
        reverse = {real: slot for slot, real in tabla_europea.mapping.items()}
        aplicados: set[int] = set()
        fusiones = 0
        # Conservar también el soporte de español que antes añadía el parche
        # histórico, pero con las mismas coordenadas correctas que los nombres.
        for visible in sorted(caracteres | set(_PORTADORES)):
            # FONT8 no declara U+0020 en su CMAP; el renderer resuelve el
            # espacio sin bitmap. No hay raster ni CWDH que trasplantar.
            if visible.isspace():
                continue
            destino_cp = _codepoint_destino(visible)
            if destino_cp in aplicados:
                continue
            _avance, unidas = _copiar_glifo(
                destino, origen, visible, reverse, tracking=False
            )
            aplicados.add(destino_cp)
            fusiones += unidas
        resultado = bytes(destino.data)
        baseline = destino.t["baseline"]
    finally:
        temporal.cleanup()
    if len(resultado) != len(japonesa_parcheada):
        raise ValueError("la adaptación FONT8 cambió el tamaño del BCFNT")
    return resultado, {
        "glifos": len(aplicados),
        "raster": "europeo_oficial_por_caracter",
        "baseline_destino": baseline,
        "centrado_motor_compensado": True,
        "ancho_nominal": destino.b.width,
        "fusiones_borde": fusiones,
        "bigramas": 0,
    }
