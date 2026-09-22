"""
Codificacion de texto de Inazuma Eleven 3 (3DS).

El motor es el mismo en japones y en europeo: el texto se guarda en
Shift-JIS (cp932). Lo que cambia en las versiones europeas es la FUENTE:
Level-5 reaprovecho los huecos de glifos que en japones ocupaban el katakana
de medio ancho (y unos pocos signos de ancho completo) para dibujar ahi las
letras acentuadas latinas.

La tabla de correspondencia esta dentro del propio juego:

    font/CodeTable.bin   320 bytes = 160 u16 little-endian = 80 PARES

    entrada i          -> codepoint REAL que se ve en pantalla
    entrada 80 + i     -> codepoint del hueco japones que lo transporta

Ejemplo comprobado en el juego:

    par 19: real = U+00F3 'o' acentuada, hueco = U+FF84 'katakana TO'
    U+FF84 se codifica en Shift-JIS como el byte 0xC4
    => el byte 0xC4 en el texto espanol significa 'ó'

Con eso, descodificar es:

    1. data.decode("cp932")        -> cadena con los huecos japoneses
    2. .translate(tabla)           -> cadena real

No hace falta adivinar nada: la tabla la publica el propio juego.
Para el japones la tabla esta vacia y el paso 2 no hace nada.

Codigos de control que quedan en el texto (se conservan tal cual):

    %1F %2F ...   marcas de formato/voz del motor
    \\n           salto de linea, guardado literalmente como barra + n
"""

import struct

CODETABLE_PATH = "font/CodeTable.bin"


class TextTable:
    """Tabla de sustitucion hueco -> caracter real."""

    def __init__(self, mapping=None):
        # mapping: {codepoint_hueco: codepoint_real}
        self.mapping = dict(mapping or {})
        self._translate = {k: chr(v) for k, v in self.mapping.items()}
        self._reverse = {chr(v): chr(k) for k, v in self.mapping.items()}

    def __len__(self):
        return len(self.mapping)

    @classmethod
    def identity(cls):
        return cls({})

    @classmethod
    def from_codetable(cls, blob):
        if len(blob) % 4:
            raise ValueError(
                f"CodeTable.bin deberia tener un numero par de u16 "
                f"(mide {len(blob)} bytes)"
            )

        values = struct.unpack(f"<{len(blob) // 2}H", blob)
        half = len(values) // 2

        mapping = {}
        for i in range(half):
            real = values[i]
            slot = values[half + i]
            if real == 0 or slot == 0 or real == slot:
                continue
            mapping[slot] = real

        return cls(mapping)

    def decode(self, data, errors="replace"):
        """bytes del juego -> str legible."""
        text = data.decode("cp932", errors=errors)
        if self._translate:
            text = text.translate(self._translate)
        return text

    def encode(self, text, errors="strict"):
        """str legible -> bytes del juego (para reinsertar la traduccion)."""
        if self._reverse:
            text = "".join(self._reverse.get(c, c) for c in text)
        return text.encode("cp932", errors=errors)

    def describe(self):
        """Filas (bytes, hueco, caracter real) para documentar/validar."""
        rows = []
        for slot, real in sorted(self.mapping.items(), key=lambda kv: kv[1]):
            try:
                raw = chr(slot).encode("cp932")
            except UnicodeEncodeError:
                raw = b""
            rows.append((raw, slot, real))
        return rows


def load_text_table(archive):
    """Saca la tabla del contenedor B123 del juego; identidad si no la trae."""
    try:
        blob = archive.read(CODETABLE_PATH)
    except (KeyError, Exception):  # noqa: B014 - el contenedor lanza varias cosas
        return TextTable.identity()
    return TextTable.from_codetable(blob)


def clean_for_csv(text):
    """Normaliza para meterlo en un CSV sin romper filas."""
    return text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\\n")
