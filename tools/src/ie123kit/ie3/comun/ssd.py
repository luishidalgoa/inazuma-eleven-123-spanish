"""
Scripts de evento de Inazuma Eleven 3 (contenido de eve.pkb y evet.pkb).

------------------------------------------------------------------
eve.pkb -> bloques SSD (script del evento + su tabla de textos)
------------------------------------------------------------------

Cabecera (0x20 bytes):

    0x00  char[4]  "SSD\\0"
    0x04  u32      version (0x00030001 en IE3)
    0x08  u32      tamano total del bloque
    0x0C  u16      numero de instrucciones
    0x0E  u16      contador auxiliar
    0x10  u32      longitud de la seccion de codigo (empieza en 0x20)
    0x14  u32      longitud de la tabla de textos
    0x18  u32      0
    0x1C  u32      0

Invariante comprobada en los 3359 + 3367 + 3621 + 3634 bloques de los tres
juegos: 0x20 + longitud_codigo + longitud_textos == tamano == len(bloque).

Instruccion (cabecera de 8 bytes + argumentos de 4 bytes):

    0x00  u16  numero de instruccion dentro del evento
    0x02  u16  tamano total de la instruccion
    0x04  u16  opcode
    0x06  u8   numero de argumentos
    0x07  u8   flags

Entrada de la tabla de textos (cabecera de 4 bytes + texto):

    0x00  u16  numero de la instruccion que usa el texto
    0x02  u8   numero de argumento dentro de esa instruccion
    0x03  u8   tamano total de la entrada
    0x04  ...   texto terminado en NUL y rellenado hasta el tamano

El par (instruccion, argumento) es la clave ESTABLE del texto: no depende
de offsets y sobrevive a que la traduccion cambie de longitud.

------------------------------------------------------------------
evet.pkb -> tabla plana de dialogos (sin cabecera SSD)
------------------------------------------------------------------

Es la misma entrada de 4 bytes de la tabla de textos, repetida hasta el
final del bloque, pero con instruccion y argumento siempre a 0.

En japones, detras de cada dialogo van sus lecturas furigana: el dialogo
lleva marcas %1F / %2F (una por kanji anotado) y a continuacion vienen
tantas entradas de lectura como marcas. En espanol no hay furigana, asi
que agrupamos solo cuando la entrada siguiente PARECE una lectura (kana
suelto), y asi la misma funcion sirve para los dos idiomas.
"""

import re
import struct

SSD_MAGIC = b"SSD\x00"
SSD_HEADER_SIZE = 0x20
INSTRUCTION_HEADER = 8
STRING_HEADER = 4

RUBY_MARK = re.compile(r"%(\d)F")

KANA = (
    "ぁゖ"  # hiragana
    "ァヺ"  # katakana
)


class SSDError(RuntimeError):
    pass


class ScriptString:
    __slots__ = ("instruction", "argument", "offset", "raw", "text", "opcode",
                 "size")

    def __init__(self, instruction, argument, offset, raw, text, opcode=-1,
                 size=0):
        self.instruction = instruction
        self.argument = argument
        self.offset = offset
        self.raw = raw
        self.text = text
        # Opcode de la instruccion que usa este texto, o -1 si el texto
        # cuelga de una instruccion que no existe (pasa en algun bloque
        # suelto) o si venimos de evet, que no tiene seccion de codigo.
        self.opcode = opcode
        # Tamano DECLARADO del registro. No se puede recalcular a partir del
        # cuerpo: IE3 deja de 1 a 3 bytes de residuo de una cadena anterior
        # detras del NUL, asi que el registro suele ser mas grande que el
        # minimo alineado.
        self.size = size

    @property
    def key(self):
        return (self.instruction, self.argument)

    @property
    def string_id(self):
        return f"{self.instruction:05d}.{self.argument}"

    def __repr__(self):
        return f"<ScriptString {self.string_id} {self.text[:24]!r}>"


def is_ssd(data):
    return data[:4] == SSD_MAGIC


def parse_instructions(data):
    """
    Recorre la seccion de codigo y devuelve {numero_instruccion: opcode}.

    Hace falta porque el opcode es lo unico que distingue de verdad un texto
    que se ve en pantalla (nombre de sitio, objetivo) de un nombre de recurso
    o de una cadena de depuracion. Sin el habria que adivinarlo por la pinta
    del texto, que es justo lo que este proyecto quiere evitar.
    """
    if len(data) < SSD_HEADER_SIZE:
        raise SSDError("bloque SSD mas corto que su cabecera")

    code_len = struct.unpack_from("<I", data, 0x10)[0]
    pos = SSD_HEADER_SIZE
    end = SSD_HEADER_SIZE + code_len

    if end > len(data):
        raise SSDError(
            f"la seccion de codigo ({code_len} bytes) se sale del bloque"
        )

    out = {}
    while pos + INSTRUCTION_HEADER <= end:
        number, size, opcode = struct.unpack_from("<HHH", data, pos)

        if size < INSTRUCTION_HEADER:
            raise SSDError(
                f"instruccion de tamano {size} en {pos:#x} (minimo "
                f"{INSTRUCTION_HEADER})"
            )
        if pos + size > end:
            raise SSDError(
                f"la instruccion de {pos:#x} se sale de la seccion de codigo"
            )

        out[number] = opcode
        pos += size

    if pos != end:
        raise SSDError(
            f"la seccion de codigo no termina donde deberia "
            f"({pos:#x} != {end:#x})"
        )

    return out


def parse_ssd(data, table, strict=True):
    """Devuelve (info_cabecera, [ScriptString]) de un bloque SSD."""
    if not is_ssd(data):
        raise SSDError(f"el bloque no empieza por {SSD_MAGIC!r}")

    if len(data) < SSD_HEADER_SIZE:
        raise SSDError("bloque SSD mas corto que su cabecera")

    version = struct.unpack_from("<I", data, 0x04)[0]
    declared = struct.unpack_from("<I", data, 0x08)[0]
    n_instructions = struct.unpack_from("<H", data, 0x0C)[0]
    code_len, string_len = struct.unpack_from("<II", data, 0x10)

    if declared != len(data):
        raise SSDError(
            f"la cabecera declara {declared} bytes y el bloque mide {len(data)}"
        )

    if SSD_HEADER_SIZE + code_len + string_len != len(data):
        raise SSDError(
            f"las secciones no cuadran: 0x20 + {code_len} + {string_len} "
            f"!= {len(data)}"
        )

    info = {
        "version": version,
        "instructions": n_instructions,
        "code_len": code_len,
        "string_len": string_len,
    }

    opcodes = parse_instructions(data)
    info["opcodes"] = len(opcodes)

    strings = []
    pos = SSD_HEADER_SIZE + code_len
    end = len(data)

    while pos < end:
        if pos + STRING_HEADER > end:
            raise SSDError(f"tabla de textos truncada en {pos:#x}")

        instruction, argument, size = struct.unpack_from("<HBB", data, pos)

        if size < STRING_HEADER or pos + size > end:
            raise SSDError(
                f"entrada de texto invalida en {pos:#x} (tamano {size})"
            )

        raw = data[pos + STRING_HEADER:pos + size].split(b"\x00")[0]

        strings.append(
            ScriptString(
                instruction,
                argument,
                pos,
                raw,
                table.decode(raw),
                opcodes.get(instruction, -1),
                size,
            )
        )

        pos += size

    if pos != end and strict:
        raise SSDError("la tabla de textos no termina donde deberia")

    return info, strings


def parse_flat_text(data, table):
    """Bloque de evet.pkb: entradas de texto seguidas, sin cabecera."""
    strings = []
    pos = 0
    end = len(data)

    while pos < end:
        if pos + STRING_HEADER > end:
            raise SSDError(f"tabla plana truncada en {pos:#x}")

        instruction, argument, size = struct.unpack_from("<HBB", data, pos)

        if size < STRING_HEADER or pos + size > end:
            raise SSDError(
                f"entrada plana invalida en {pos:#x} (tamano {size})"
            )

        raw = data[pos + STRING_HEADER:pos + size].split(b"\x00")[0]

        strings.append(
            ScriptString(
                instruction,
                argument,
                pos,
                raw,
                table.decode(raw),
                -1,
                size,
            )
        )

        pos += size

    return strings


def looks_like_ruby(text):
    """Una lectura furigana es kana suelto, corta y sin codigos de control."""
    if not text or len(text) > 12:
        return False
    if "%" in text or "\\n" in text:
        return False
    return all(
        "ぁ" <= c <= "ゖ" or "ァ" <= c <= "ヺ" or c == "ー"
        for c in text
    )


def group_ruby(strings):
    """
    Agrupa [dialogo, lectura, lectura, ...] -> [(dialogo, [lecturas])].

    Solo consume entradas siguientes si el dialogo lleva marcas %nF Y la
    entrada siguiente parece de verdad una lectura. En espanol no se cumple
    nunca, asi que devuelve la lista intacta.
    """
    grouped = []
    i = 0
    n = len(strings)

    while i < n:
        head = strings[i]
        wanted = len(RUBY_MARK.findall(head.text))
        readings = []
        j = i + 1

        while wanted > 0 and j < n and looks_like_ruby(strings[j].text):
            readings.append(strings[j])
            j += 1
            wanted -= 1

        grouped.append((head, readings))
        i = j

    return grouped
