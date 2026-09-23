"""Colocación IE3 fase4; lectura de la fuente aprobada, nunca modificación.

El consumidor convierte ASCII espacio a U+3000 antes de medir/dibujar. La
compensación de centrado se incluye exactamente una vez en los límites de tinta.
Las coordenadas son relativas a la ventana, no una captura del emulador.
"""
from __future__ import annotations

import struct

from ie123kit.ie3.comun.maqueta import LINEAS, MAX_CAR, SALTO, lineas_de
from ie123kit.ie3.comun.tipografia import _codepoint_destino
from ie123kit.nucleo.texto.sjis_portador import GREEK

ORIGEN_ANTES = 12
ORIGEN = 8
IZQUIERDA = 7
DERECHA = 312
# Reserva conservadora del indicador16px en la última fila. Su posición final
# depende de animación/padre: no se presenta como una medida de captura.
DERECHA_ULTIMA = DERECHA - 16


class Medidor:
    """FuenteBCFNT de solo lectura; posiciones NW, tracking y espacio del motor."""

    def __init__(self, fuente, tracking=0, *, word_spacing=None, extra_line=3, vertical_percent=115):
        self.fuente = fuente
        self.tracking = tracking
        self.word_spacing = word_spacing
        self.extra_line = extra_line
        self.vertical_percent = vertical_percent
        self._glyphs, self._bounds = {}, {}

    def glifo(self, ch):
        if ch in self._glyphs:
            return self._glyphs[ch]
        cp = 0x3000 if ch == " " else _codepoint_destino(ch)
        gi = self.fuente.cmap.get(cp)
        if gi is None:
            raise ValueError(f"glifo no modelado: {ch!r} U+{cp:04X}")
        off = self.fuente.cwdh_entry_off(gi)
        if off is None:
            raise ValueError(f"CWDH ausente: {ch!r}")
        left, width, advance = struct.unpack_from("<bBB", self.fuente.data, off)
        shift = left + int((self.fuente.b.width - advance) / 2)
        pixels = tuple((shift+x, y, v) for y, row in enumerate(self.fuente.read_cell(gi))
                       for x, v in enumerate(row[:width]) if v)
        # Desplazamiento entre palabras del consumidor, no edición de CWDH.
        if ch == " " and self.word_spacing is not None:
            if pixels or self.word_spacing < 1:
                raise ValueError("el ajuste de separador exige espacio sin tinta y avance positivo")
            advance = self.word_spacing
        self._glyphs[ch] = advance + self.tracking, pixels
        return self._glyphs[ch]

    def medir(self, texto, origen=ORIGEN):
        pen, boxes, spaces = 0, [], []
        for ch in texto.translate(GREEK):
            advance, box = self.limites_glifo(ch)
            if box is not None:
                boxes.append((origen+pen+box[0], box[1], origen+pen+box[2], box[3]))
            if ch == " ":
                spaces.append({"x": origen+pen, "avance": advance, "codepoint_runtime": "U+3000"})
            pen += advance
        return {"avance": pen, "izquierda": min((b[0] for b in boxes), default=origen),
                "derecha": max((b[2] for b in boxes), default=origen-1),
                "arriba": min((b[1] for b in boxes), default=0),
                "abajo": max((b[3] for b in boxes), default=-1), "espacios": spaces}

    def limites_glifo(self, ch):
        if ch in self._bounds:
            return self._bounds[ch]
        advance, px = self.glifo(ch)
        self._bounds[ch] = advance, (None if not px else (
            min(x for x, _, _ in px), min(y for _, y, _ in px),
            max(x for x, _, _ in px), max(y for _, y, _ in px)))
        return self._bounds[ch]

    def exceso(self, texto, derecha=DERECHA):
        """Métrica de encaje conectada al mismo algoritmo de wrapping."""
        m = self.medir(texto)
        return max(IZQUIERDA-m["izquierda"], m["derecha"]-derecha)

    def maquetar(self, texto):
        if "\\f" in texto or "%" in texto or "\n" in texto or "\r" in texto:
            return None
        lines = lineas_de(texto, MAX_CAR, 0, medir=self.exceso)
        if len(lines) > LINEAS:
            # Solo dentro de esta caja estática: los saltos de línea son
            # colocación, no controles de página. Reusar el mismo algoritmo
            # con las palabras del mensaje permite redistribuir las filas.
            lines = lineas_de(texto.replace(SALTO, " "), MAX_CAR, 0, medir=self.exceso)
        if len(lines) == LINEAS and self.exceso(lines[-1], DERECHA_ULTIMA) > 0:
            # No contar el área reservada del indicador como ancho disponible.
            # Se reutiliza el mismo wrapping, con una cota uniforme conservadora.
            lines = lineas_de(texto.replace(SALTO, " "), MAX_CAR, 0,
                              medir=lambda s: self.exceso(s, DERECHA_ULTIMA))
        if len(lines) > LINEAS or any(len(s.translate(GREEK)) > MAX_CAR or self.exceso(s) > 0 for s in lines):
            return None
        # El algoritmo histórico normaliza los separadores simples. No aceptar
        # pérdida adicional de contenido ni espacios repetidos en esta revisión.
        result = SALTO.join(lines)
        if texto.replace(SALTO, " ") != result.replace(SALTO, " "):
            return None
        return result


def parchear_origen(cro):
    """Solo cuerpo: ldr r3,[fp,#40] (+2 ITX) → mvn r3,#1 (−2)."""
    offset = 0x3ABC8
    before, after = bytes.fromhex("40309be5"), bytes.fromhex("0130e0e3")
    if cro[offset:offset+4] != before:
        raise ValueError("ancla del origen de cuerpo distinta")
    from ie123kit.ie3.comun.ancho_ventana import direcciones_de_tablas
    if offset in direcciones_de_tablas(cro):
        raise ValueError("origen afectado por relocación")
    out = cro[:offset]+after+cro[offset+4:]
    return out, {"offset": offset, "antes_hex": before.hex(), "despues_hex": after.hex(),
                 "origen_antes": ORIGEN_ANTES, "origen_despues": ORIGEN,
                 "interior": [IZQUIERDA, DERECHA], "solo_cuerpo": True,
                 "ultima_fila_derecha_conservadora": DERECHA_ULTIMA,
                 "indicador_posicion_final_runtime_pendiente": True,
                 "tracking_inalterado": 0, "interlineado_adicional_inalterado": 3,
                 "posicion_vertical_factor_inalterado": [115, 100],
                 "runtime_verified": False}


def render_casos(casos, medidor):
    """Comparación nativa sin retocar raster ni fingir un marco/captura del juego.

Los rectángulos son guías de medición. La Y inicial ilustrativa no se presenta
como una coordenada observada del marco; los incrementos sí siguen el consumidor.
"""
    from PIL import Image, ImageDraw

    out = Image.new("RGB", (680, 44+len(casos)*138), (24, 28, 34))
    draw = ImageDraw.Draw(out)
    draw.text((8, 4), "SIMULACION NATIVA 1:1 - no captura ni marco del juego", fill="white")
    draw.text((8, 22), "Fase3: origen12", fill="white")
    label = "Revision: espacio3 / fila17" if medidor.word_spacing == 3 else "Fase4: origen8 + mismos glifos"
    draw.text((348, 22), label, fill="white")
    report = []
    for index, (key, text) in enumerate(casos):
        formatted = medidor.maquetar(text)
        if formatted is None:
            raise ValueError("caso de regresión no cabe en el modelo")
        top = 44+index*138
        draw.text((8, top), key, fill="white")
        item = {"key": key, "before": text, "after": formatted,
                "vertical_origins_relative": [int(i*(medidor.fuente.b.height+medidor.extra_line)*medidor.vertical_percent/100) for i in range(3)],
                "baseline_texture": medidor.fuente.t["baseline"], "runtime_verified": False}
        for column, origin, value, name in ((0, 12, text, "before"), (340, ORIGEN, formatted, "after")):
            current_measure = Medidor(medidor.fuente, medidor.tracking) if name == "before" else medidor
            tile = Image.new("RGB", (320, 84), (20, 55, 100))
            td = ImageDraw.Draw(tile)
            td.rectangle((IZQUIERDA, 0, DERECHA, 82), outline=(75, 130, 190))
            measures = []
            for line_idx, line in enumerate(value.split(SALTO)):
                y0 = 6+int(line_idx*(current_measure.fuente.b.height+current_measure.extra_line)*current_measure.vertical_percent/100)
                pen = origin
                for ch in line.translate(GREEK):
                    adv, pixels = current_measure.glifo(ch)
                    for x, y, alpha in pixels:
                        px, py = pen+x, y0+y
                        if 0 <= px < tile.width and 0 <= py < tile.height:
                            bg = tile.getpixel((px, py))
                            tile.putpixel((px, py), tuple(int(b+(255-b)*alpha/15) for b in bg))
                    pen += adv
                measures.append(current_measure.medir(line, origin))
            out.paste(tile, (column+4, top+18))
            item[name+"_measures"] = measures
        draw.text((8, top+108), "Guias horizontales; Y inicial ilustrativa. Misma tinta, colocacion del consumidor.", fill="white")
        report.append(item)
    return out, report
