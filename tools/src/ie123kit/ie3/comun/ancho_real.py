"""Enrutado a ancho real de llamadas concretas del motor de texto 2 (FONT8) en ina_main3ogre.cro (IE3).

El motor 2 (vtable+8 del gestor; IE3 0x19e4c) da a FONT8 el ancho por defecto del ITX123 (6/7 px DS, o +0x34 en
el modo «_2»): letras a paso fijo («X a v i e r»). La capa ficha_registro_proporcional (v3.2) lo mantiene así
para todo FONT8. Aquí se abre una vía por llamada: si el argumento de línea de depuración (r2, [sp+0xa4] en el
motor; el motor no lo usa salvo las marcas −1 y −2) vale LINEA_ANCHO_REAL (−3), se salta el ancho por defecto y
el bucle por letra usa el avance BCFNT (la métrica de FONT8 ya va compensada: capa fuentes/font8_proporcional).

Todo son palabras de 4 B en su sitio (``ParchePalabra``); la cueva va en un hueco de .text ya liberado.
Idempotente: cada palabra se acepta en su estado japonés o ya parcheado.
"""
from __future__ import annotations

import struct
from collections.abc import Iterable, Sequence

from ie123kit.nucleo.ejecutable.parches_cro import ParchePalabra, aplicar

LINEA_ANCHO_REAL = -3
MVN_R2_2 = 0xE3E02002            # mvn r2, #2  -> r2 = −3
PALABRA_LINEA = LINEA_ANCHO_REAL & 0xFFFFFFFF

# Motor 2, rama del ancho por defecto de FONT8 (tipo 1)
FONT8_POR_DEFECTO = 0x19FF0      # ldr ip, [sp, #0x60]
FONT8_SIGUE = 0x19FF4            # cmp ip, #1
SIN_POR_DEFECTO = 0x1A064        # ldr ip, [sp, #0xa8] (addW del ITX)
LDR_IP_SP60 = 0xE59DC060


def rama(origen: int, destino: int, cond: int = 0xE, enlace: bool = False) -> int:
    """Codifica ``b``/``bl`` ARM de ``origen`` a ``destino`` (offsets del mismo módulo)."""
    delta = destino - (origen + 8)
    if delta % 4 or not -(1 << 25) <= delta < (1 << 25):
        raise ValueError(f"rama fuera de alcance {origen:#x} -> {destino:#x}")
    return (cond << 28) | (0xB if enlace else 0xA) << 24 | ((delta >> 2) & 0xFFFFFF)


def cueva_font8(cueva: int) -> list[ParchePalabra]:
    """Cueva de 5 palabras en ``cueva`` (debe estar a cero) + desvío en el motor."""
    cuerpo = [
        (0xE59DC0A4, "ldr ip, [sp, #0xa4]  ; línea de depuración"),
        (0xE37C0003, "cmn ip, #3"),
        (rama(cueva + 8, SIN_POR_DEFECTO, cond=0x0), "beq sin ancho por defecto"),
        (LDR_IP_SP60, "ldr ip, [sp, #0x60]  ; instrucción desplazada"),
        (rama(cueva + 16, FONT8_SIGUE), "b vuelta al motor"),
    ]
    parches = [ParchePalabra(cueva + 4 * i, 0, w, t) for i, (w, t) in enumerate(cuerpo)]
    parches.append(ParchePalabra(FONT8_POR_DEFECTO, LDR_IP_SP60, rama(FONT8_POR_DEFECTO, cueva), "b cueva ancho real"))
    return parches


def aplicar_idempotente(cro: bytes, parches: Sequence[ParchePalabra]) -> tuple[bytes, dict]:
    """``aplicar`` que salta las palabras ya parcheadas y exige que las demás estén en su estado de partida."""
    pendientes = []
    for p in parches:
        actual = struct.unpack_from("<I", cro, p.direccion)[0]
        if actual == p.despues:
            continue
        pendientes.append(p)
    if not pendientes:
        return bytes(cro), {"ya_aplicado": True, "parches": []}
    salida, informe = aplicar(cro, pendientes)
    informe["ya_aplicado"] = False
    return salida, informe


def llamadas_linea(sitios: Iterable[tuple[int, int, str]]) -> list[ParchePalabra]:
    """Pone la línea −3 en cada llamada: ``(dirección, palabra_antes, tipo)`` con tipo 'mov' (mvn r2,#2 en la
    instrucción) o 'pool' (palabra literal del pool que carga r2)."""
    out = []
    for direccion, antes, tipo in sitios:
        nueva = MVN_R2_2 if tipo == "mov" else PALABRA_LINEA
        out.append(ParchePalabra(direccion, antes, nueva, f"línea −3 ({tipo})"))
    return out
