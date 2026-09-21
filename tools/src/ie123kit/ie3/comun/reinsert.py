"""Reinserción del diálogo español de IE3 en el recopilatorio japonés.

Toca SOLO ``evet.pkb``, que es donde está el diálogo de IE3 (``eve.pkb`` lleva
rótulos y nombres de sitio, unas 850 líneas frente a 34 000). Un bloque de
``evet`` es una tabla plana SIN comprimir de registros

    u16 instrucción (siempre 0)   u8 argumento (siempre 0)   u8 tamaño
    cuerpo terminado en NUL y rellenado hasta ese tamaño

recorrida en secuencia por el tamaño de cada registro.

------------------------------------------------------------------
Por qué no cambia ni un offset
------------------------------------------------------------------

En japonés, detrás de cada línea van sus LECTURAS furigana: la línea lleva
marcas ``%1F`` / ``%2F`` (una por kanji anotado) y a continuación vienen tantos
registros de lectura como marcas.

El español no lleva furigana, así que esas lecturas hay que vaciarlas de todas
formas (si no, salen kana sueltos). Y como hay que vaciarlas, **sus bytes se le
dan a la línea**: la línea crece y las lecturas se encogen al mínimo, dentro del
mismo grupo.

El resultado es que **el bloque mide exactamente lo mismo y tiene exactamente
los mismos registros**, solo cambia el reparto de bytes dentro del grupo. Por
eso no hace falta saber si el motor referencia por índice o por offset: ni los
índices ni los offsets posteriores se mueven. Tampoco hay que reconstruir el
``.pkh``, ni recomprimir nada (``evet`` no va comprimido).

Recuperar los bytes de las lecturas sube la cobertura del 41,5 % al 53,7 %
(medido sobre las 34 101 líneas de Rayo Celeste con traducción oficial).

------------------------------------------------------------------
Qué NO se hace
------------------------------------------------------------------

**No se trunca nunca.** Si el español no cabe en el grupo, la línea se queda en
japonés. La Norma 3 de ``CLAUDE.md`` dice que el diálogo no se condensa para que
quepa, y dejar media frase es peor que dejarla sin traducir.

La codificación y el ajuste de línea salen tal cual de las piezas del bloqueo
v20 (``sjis_portador.es_encode`` y el ``reflow`` de ``_legado.reinsert``): aquí
no se decide nada de tipografía.
"""

from __future__ import annotations

import re
import struct

from ie123kit.ie3.comun.maqueta import maquetar_una_caja
from ie123kit.ie3.comun.ssd import SSD_HEADER_SIZE as SSD_CABECERA
from ie123kit.ie3.comun.ssd import group_ruby, parse_flat_text
from ie123kit.ie3.comun.text import TextTable
from ie123kit.nucleo.texto.sjis_portador import GREEK, es_encode


def _codificable(texto: str) -> bool:
    """False si Shift-JIS-portador tendría que sustituir algo por `?`."""
    try:
        texto.translate(GREEK).encode("shift-jis")
    except UnicodeEncodeError:
        return False
    return True


def _maquetar(texto):
    """
    Saltos de linea para UNA caja, o None si no cabe.

    Comprobado en emulador dos veces: el motor de IE3 dibuja una sola caja por
    dialogo. Paginar con ``\f`` hacia que se perdiera texto, que es el fallo
    que se vio en las v102-v104. Ver ie123kit.ie3.comun.maqueta.
    """
    return maquetar_una_caja(texto)


#: Registro mínimo: 4 de cabecera + NUL, redondeado al alineado de 4.
MIN_REGISTRO = 8

#: El tamaño va en un u8 y tiene que ser múltiplo de 4.
MAX_REGISTRO = 252

MARCA_FURIGANA = re.compile(r"%[1-9]F")


def _tam(registro):
    """
    Tamaño que ocupa el registro en el bloque, tal y como lo DECLARA él mismo.

    No vale recalcularlo desde el cuerpo: IE3 deja de 1 a 3 bytes de residuo de
    una cadena anterior detrás del NUL, así que el registro casi siempre es más
    grande que el mínimo alineado. Recalcularlo encogía el bloque.
    """
    return registro.size


def _emitir(instruccion, argumento, cuerpo, tamano):
    """Un registro de `tamano` bytes exactos con `cuerpo` dentro."""
    if not 4 + len(cuerpo) + 1 <= tamano <= MAX_REGISTRO:
        raise ValueError("el cuerpo no cabe en el registro")
    salida = struct.pack("<HBB", instruccion, argumento, tamano) + cuerpo
    return salida + bytes(tamano - len(salida))


def _reparto(total, n_lecturas, necesita_linea):
    """
    Reparte `total` bytes entre la línea y sus `n_lecturas`, o None si no cabe.

    La línea se lleva lo que necesite (con el tope del u8) y las lecturas el
    resto, nunca menos del mínimo ni más del tope.
    """
    if n_lecturas == 0:
        # Sin lecturas no hay bytes que mover: la línea tiene que caber tal cual.
        return (total,) if necesita_linea <= total <= MAX_REGISTRO else None

    linea = min(max(necesita_linea, MIN_REGISTRO), MAX_REGISTRO)
    resto = total - linea

    if resto < MIN_REGISTRO * n_lecturas:
        return None                       # ni vaciando las lecturas cabe
    if resto > MAX_REGISTRO * n_lecturas:
        return None                       # sobran bytes que no caben en las lecturas

    lecturas = [MIN_REGISTRO] * n_lecturas
    sobrante = resto - MIN_REGISTRO * n_lecturas
    for i in range(n_lecturas):
        hueco = min(sobrante, MAX_REGISTRO - lecturas[i])
        lecturas[i] += hueco
        sobrante -= hueco
        if not sobrante:
            break

    return (linea, *lecturas)


#: Cuerpo máximo de un registro: 252 - 4 de cabecera - 1 del NUL.
MAX_CUERPO = MAX_REGISTRO - 5


def parchear_bloque(bloque, traducciones, tabla=None):
    """
    Devuelve (bloque_nuevo, aplicadas, no_caben).

    `traducciones` es {japonés: español}.

    El bloque conserva siempre tamaño y número de registros: el grupo (un
    dialogo y sus lecturas
    furigana) conserva su tamano TOTAL, el dialogo va primero asi que su propio
    offset no se mueve, y los registros posteriores se quedan donde estaban.
    """
    tabla = tabla or TextTable.identity()
    grupos = group_ruby(parse_flat_text(bloque, tabla))

    salida = bytearray()
    aplicadas = no_caben = 0

    for linea, lecturas in grupos:
        original = _emitir(linea.instruction, linea.argument, linea.raw, _tam(linea))
        original += b"".join(
            _emitir(r.instruction, r.argument, r.raw, _tam(r)) for r in lecturas
        )

        espanol = traducciones.get(linea.text.replace("\n", "\\n"))
        if not espanol:
            salida.extend(original)
            continue

        # Un %NF suelto en el español descuadra el motor: fuera.
        maquetado = _maquetar(MARCA_FURIGANA.sub("", espanol))
        if maquetado is None:
            no_caben += 1
            salida.extend(original)       # no cabe en una caja: japonés
            continue
        if not _codificable(maquetado):
            no_caben += 1
            salida.extend(original)       # carácter sin glifo: japonés intacto
            continue
        cuerpo = es_encode(maquetado, 1 << 30)

        necesita = (4 + len(cuerpo) + 1 + 3) & ~3

        total = _tam(linea) + sum(_tam(r) for r in lecturas)
        reparto = _reparto(total, len(lecturas), necesita)

        if reparto is None:
            no_caben += 1
            salida.extend(original)       # se queda en japonés, sin truncar
            continue

        salida.extend(_emitir(linea.instruction, linea.argument, cuerpo, reparto[0]))
        for lectura, tamano in zip(lecturas, reparto[1:]):
            salida.extend(_emitir(lectura.instruction, lectura.argument, b"", tamano))
        aplicadas += 1

    nuevo = bytes(salida)

    if len(nuevo) != len(bloque):
        raise ValueError(
            f"el bloque cambió de tamaño: {len(bloque)} -> {len(nuevo)}"
        )

    # Esto se comprueba SIEMPRE: el número de registros es lo que sostiene las
    # referencias del script, crezca el bloque o no.
    antes = len(parse_flat_text(bloque, tabla))
    despues = len(parse_flat_text(nuevo, tabla))
    if antes != despues:
        raise ValueError(
            f"el bloque cambió de número de registros: {antes} -> {despues}"
        )

    return nuevo, aplicadas, no_caben


# --------------------------------------------------------------------------
# eve: rótulos de objetivo y nombres de sitio
# --------------------------------------------------------------------------

def parchear_ssd(bloque, traducciones, opcodes, tabla=None):
    """
    Sustituye en un bloque SSD los textos cuyos opcodes salen en pantalla.

    `opcodes` es el conjunto de opcodes que se pueden tocar (ver
    ie123kit.ie3.comun.sheet.TEXT_OPCODES). El resto de la tabla de textos son
    nombres de recurso y mensajes de depuración: cambiarlos rompe el script.

    La sección de código NO se toca, así que las instrucciones y sus operandos
    quedan intactos; solo se reescribe la tabla de textos y se corrigen los dos
    tamaños de la cabecera. Las entradas se referencian por índice, y el número
    de entradas no cambia.

    Devuelve (bloque_nuevo, aplicadas).
    """
    import struct as _s

    from ie123kit.ie3.comun.ssd import parse_ssd

    tabla = tabla or TextTable.identity()
    info, registros = parse_ssd(bloque, tabla)

    code_len = info["code_len"]
    cabecera = bytearray(bloque[:SSD_CABECERA])
    codigo = bloque[SSD_CABECERA:SSD_CABECERA + code_len]

    salida = bytearray()
    aplicadas = 0

    for reg in registros:
        cuerpo = reg.raw
        if reg.opcode in opcodes:
            espanol = traducciones.get(reg.text.replace("\n", "\n"))
            if espanol:
                nuevo = es_encode(MARCA_FURIGANA.sub("", espanol), MAX_CUERPO)
                if nuevo:
                    cuerpo = nuevo
                    aplicadas += 1

        tamano = (4 + len(cuerpo) + 1 + 3) & ~3
        if tamano > MAX_REGISTRO:                 # no cabe: se deja el japonés
            cuerpo = reg.raw
            tamano = reg.size
            aplicadas -= 1
        salida.extend(_emitir(reg.instruction, reg.argument, cuerpo, tamano))

    if not aplicadas:
        return bloque, 0

    total = SSD_CABECERA + code_len + len(salida)
    _s.pack_into("<I", cabecera, 0x08, total)     # tamaño del bloque
    _s.pack_into("<I", cabecera, 0x14, len(salida))  # longitud de la tabla de textos

    nuevo = bytes(cabecera) + codigo + bytes(salida)

    # Se vuelve a leer: si algo no cuadra, salta aquí y no en la consola.
    _comprobado, regs2 = parse_ssd(nuevo, tabla)
    if len(regs2) != len(registros):
        raise ValueError(
            f"la tabla de textos cambió de entradas: "
            f"{len(registros)} -> {len(regs2)}"
        )

    return nuevo, aplicadas
