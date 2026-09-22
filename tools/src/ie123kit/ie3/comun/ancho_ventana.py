"""Ensancha el límite lógico de diálogo de IE3: 22 -> 51 caracteres por línea.

Es la misma sonda que la capa `ie2/shared/v15/ancho_dialogo` aplicó a
``ina_main2.cro`` y que está validada en emulador; aquí se traslada a
``ina_main3ogre.cro``, que es el módulo de las tres versiones de IE3.

------------------------------------------------------------------
Por qué hace falta
------------------------------------------------------------------

El motor ajusta el texto con un avance FIJO de 12 px por carácter y un límite de
``ancho + 0x20``. Con el ancho de fábrica (0xF0 = 240) salen

    max n con 12·n < 240 + 32 = 272   ->   22 caracteres por línea

que es justo lo que se midió en el emulador: «¡Bravo, Paolo! ¡El fút» son 22
caracteres clavados. Con las métricas oficiales europeas, el barrido de las
34.691 traducciones elegibles produce líneas de 354 px con un máximo de 51
caracteres; 0x250 da exactamente ese límite lógico.

------------------------------------------------------------------
Los tres sitios
------------------------------------------------------------------

Localizados por el mismo patrón que en IE2, con coincidencia única en los tres:

    0x04F3CC  mov r1,#0xF0  -> mov r1,#0x250   ancho que el manejador del
                                               diálogo pasa en cada caja
                                               (detrás lleva su mov r2,#3)
    0x039CEC  mov r2,#0xF0  -> mov r2,#0x250   valor por defecto de la ventana;
                                               el strh de 0x039CF4 lo guarda en
                                               [ventana+0x131A] (en IE1 es
                                               +0x1316 y en IE2 +0x131E)
    0x03A928  mov r2,#0x120 -> mov r2,#0x270   ancho de la rejilla de dibujo de
                                               la página; sin esto el texto se
                                               reajusta pero se sigue dibujando
                                               cortado a 24 caracteres

Las líneas por página (los ``mov ...,#3``) NO se tocan: siguen siendo 3.

------------------------------------------------------------------
Seguridad
------------------------------------------------------------------

Un CRO es un módulo reubicable: el cargador reescribe las palabras que aparecen
en sus tablas de parches. Escribir encima de una de esas palabras es el «muro
#1» de ``docs/FURIGANA_LECCIONES.md``. Por eso, antes de tocar nada, se
comprueba que ninguna de las tres direcciones aparece en la tabla de
importación (0xF8), en la de reubicación interna (0x128) ni en la 0x130, y que
cada palabra contiene exactamente la instrucción esperada.
"""

from __future__ import annotations

import struct

#: Ancho nuevo de la ventana y de la rejilla de dibujo.
ANCHO = 0x250
REJILLA = 0x270

#: 12·n < ANCHO + 0x20
MAX_CAR = max(n for n in range(1, 80) if 12 * n < ANCHO + 0x20)

#: (dirección, palabra esperada, palabra nueva, para qué)
PARCHES = (
    (0x04F3CC, 0xE3A010F0, 0xE3A01E25,
     "manejador de dialogo: mov r1,#0xF0 -> #0x250"),
    (0x039CEC, 0xE3A020F0, 0xE3A02E25,
     "por defecto de la ventana: mov r2,#0xF0 -> #0x250"),
    (0x03A928, 0xE3A02E12, 0xE3A02E27,
     "rejilla de dibujo: mov r2,#0x120 -> #0x270"),
)

#: Palabras que tienen que seguir intactas alrededor (confirman que es el sitio).
CONTEXTO = (
    (0x04F3D0, 0xE3A02003, "mov r2,#3 (lineas del manejador)"),
    (0x039CF8, 0xE3A01003, "mov r1,#3 (lineas por defecto)"),
)

#: Tablas de parches del CRO, por su offset en la cabecera.
TABLAS = {"importacion": 0xF8, "reubicacion_interna": 0x128, "tabla_0x130": 0x130}


class CROError(RuntimeError):
    pass


def _u32(d, o):
    return struct.unpack_from("<I", d, o)[0]


def direcciones_de_tablas(d):
    """Offsets de fichero que el cargador reescribe al reubicar el módulo."""
    segmentos = [
        struct.unpack_from("<III", d, _u32(d, 0xC8) + 12 * i)
        for i in range(_u32(d, 0xCC))
    ]
    tocadas = set()
    for base in TABLAS.values():
        off, n = _u32(d, base), _u32(d, base + 4)
        for i in range(n):
            so = _u32(d, off + 12 * i)
            seg, desp = so & 0xF, so >> 4
            if seg < len(segmentos):
                tocadas.add(segmentos[seg][0] + desp)
    return tocadas


def comprobar(datos):
    """Verifica que el CRO es el esperado y que se puede parchear. Lanza si no."""
    if datos[0x80:0x84] != b"CRO0":
        raise CROError("no es un CRO (falta el magic CRO0)")

    for direccion, esperado, _nuevo, que in PARCHES:
        real = _u32(datos, direccion)
        if real != esperado:
            raise CROError(
                f"{que}: en 0x{direccion:06X} esperaba 0x{esperado:08X} "
                f"y hay 0x{real:08X}. El CRO no es el que se analizo."
            )

    for direccion, esperado, que in CONTEXTO:
        real = _u32(datos, direccion)
        if real != esperado:
            raise CROError(
                f"contexto {que}: en 0x{direccion:06X} esperaba 0x{esperado:08X} "
                f"y hay 0x{real:08X}."
            )

    tocadas = direcciones_de_tablas(datos)
    for direccion, _e, _n, que in PARCHES:
        if direccion in tocadas:
            raise CROError(
                f"{que}: 0x{direccion:06X} esta en una tabla de reubicacion del "
                f"CRO; el cargador la reescribe y parchearla cuelga el juego."
            )

    return len(tocadas)


def parchear(datos):
    """Devuelve (cro_nuevo, informe). No modifica la entrada."""
    entradas_tabla = comprobar(datos)

    salida = bytearray(datos)
    hechos = []
    for direccion, esperado, nuevo, que in PARCHES:
        struct.pack_into("<I", salida, direccion, nuevo)
        hechos.append({
            "direccion": f"0x{direccion:06X}",
            "antes": f"0x{esperado:08X}",
            "despues": f"0x{nuevo:08X}",
            "que": que,
        })

    return bytes(salida), {
        "ancho": ANCHO,
        "rejilla": REJILLA,
        "caracteres_por_linea": MAX_CAR,
        "lineas_por_caja": 3,
        "parches": hechos,
        "entradas_en_tablas_de_reubicacion": entradas_tabla,
    }
