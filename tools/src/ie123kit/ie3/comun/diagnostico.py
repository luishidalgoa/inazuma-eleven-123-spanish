"""Build de diagnostico: mete reglas graduadas en el dialogo para MEDIR la caja.

Todo lo que se sabe del ancho y del alto de la caja de IE3 esta deducido del
desensamblado y de mirar capturas. Eso ya ha fallado varias veces (❌#14 a ❌#17
de FURIGANA_LECCIONES). Esto lo mide directamente.

------------------------------------------------------------------
Que se escribe
------------------------------------------------------------------

En lugar del texto espanol se escribe una REGLA:

    A234567890B234567890C234567890D234567890E2345

La letra marca la decena: `A`=1, `B`=11, `C`=21, `D`=31, `E`=41. Basta con leer
en pantalla el ultimo caracter visible para saber cuantos caben. Por ejemplo, si
la linea acaba en `C2345` es que caben 25.

Se escriben tres lineas seguidas, asi que de paso se ve cuantas dibuja la caja y
si la tercera se corta.

------------------------------------------------------------------
Que preguntas responde
------------------------------------------------------------------

1. **Cuantos caracteres entran por linea.** Se lee del corte de la regla.
2. **Cuantas lineas dibuja la caja.** Se cuenta.
3. **Si se come el principio (❌#16).** Si la primera linea no empieza por `A`,
   el motor esta leyendo desde un offset desplazado, y el numero por el que
   empieza dice cuantos bytes se ha comido.

La tercera es la importante: es la unica forma de confirmar o descartar el
modelo del offset sin adivinar.

------------------------------------------------------------------
Como se aplica
------------------------------------------------------------------

Siempre a MISMO TAMANO: la regla se recorta al presupuesto de bytes que ya
tenia el registro. Asi el diagnostico no introduce el fallo que pretende medir.
Si en un registro no caben ni 12 caracteres, se deja el japones.
"""

from __future__ import annotations

from ie123kit.ie3.comun.ssd import group_ruby, parse_flat_text
from ie123kit.ie3.comun.text import TextTable

#: Regla de 45 caracteres. La letra marca la decena.
REGLA = ("A234567890B234567890C234567890D234567890E2345")

#: Por debajo de esto la regla no dice nada util.
MINIMO = 12


def regla(largo):
    """Los primeros `largo` caracteres de la regla."""
    if largo <= len(REGLA):
        return REGLA[:largo]
    # Si hiciera falta mas, se continua el patron.
    extra = "FGHIJKLMNOPQRSTUVWXYZ"
    texto = REGLA
    i = 0
    while len(texto) < largo:
        texto += extra[i % len(extra)] + "234567890"
        i += 1
    return texto[:largo]


def parchear_bloque(bloque, eventos_objetivo, eid, tabla=None, lineas=3,
                    ancho=45):
    """
    Sustituye los dialogos de `eid` por reglas, a mismo tamano.

    Devuelve (bloque_nuevo, cuantos). El bloque conserva su tamano exacto y el
    de cada registro, asi que ningun offset se mueve.
    """
    from ie123kit.ie3.comun.reinsert import _emitir, _tam
    from ie123kit.nucleo.texto.sjis_portador import es_encode

    if eid not in eventos_objetivo:
        return bloque, 0

    tabla = tabla or TextTable.identity()
    salida = bytearray()
    puestos = 0

    for linea, lecturas in group_ruby(parse_flat_text(bloque, tabla)):
        tam = _tam(linea)
        presupuesto = tam - 4 - 1
        cuerpo = None

        if presupuesto >= MINIMO and linea.text.strip():
            # tres lineas de regla, recortadas a lo que quepa en bytes
            texto = "\\n".join(regla(ancho) for _ in range(lineas))
            cuerpo = es_encode(texto, presupuesto)
            # no dejar una linea a medias del separador
            while cuerpo.endswith(b"\\"):
                cuerpo = cuerpo[:-1]

        if cuerpo:
            salida.extend(_emitir(linea.instruction, linea.argument, cuerpo, tam))
            puestos += 1
        else:
            salida.extend(
                _emitir(linea.instruction, linea.argument, linea.raw, tam)
            )

        for r in lecturas:
            salida.extend(_emitir(r.instruction, r.argument, r.raw, _tam(r)))

    nuevo = bytes(salida)
    if len(nuevo) != len(bloque):
        raise ValueError(
            f"el bloque de diagnostico cambio de tamano: "
            f"{len(bloque)} -> {len(nuevo)}"
        )
    return nuevo, puestos
