"""Enrutado a ancho real de llamadas concretas del motor de texto 2 (FONT8), común a IE2 (ina_main2) e IE3 (ina_main3ogre).

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
from dataclasses import dataclass

from ie123kit.nucleo.ejecutable.parches_cro import ParchePalabra, aplicar

LINEA_ANCHO_REAL = -3
MVN_R2_2 = 0xE3E02002            # mvn r2, #2  -> r2 = −3
PALABRA_LINEA = LINEA_ANCHO_REAL & 0xFFFFFFFF

LDR_IP_SP60 = 0xE59DC060


@dataclass(frozen=True)
class Motor2:
    """Direcciones del motor 2 en una CRO: rama del ancho por defecto de FONT8 (tipo 1)."""

    por_defecto: int        # ldr ip, [sp, #0x60]
    sigue: int              # cmp ip, #1
    sin_por_defecto: int    # ldr ip, [sp, #0xa8] (addW del ITX)


IE3_MOTOR2 = Motor2(0x19FF0, 0x19FF4, 0x1A064)          # ina_main3ogre.cro
IE2_MOTOR2 = Motor2(0x335AC, 0x335B0, 0x33620)          # ina_main2.cro (IE3 + 0x195bc)
IE1_MOTOR2 = Motor2(0x2EEC8, 0x2EECC, 0x2EF3C)          # ina_main1.cro
# compatibilidad
FONT8_POR_DEFECTO, FONT8_SIGUE, SIN_POR_DEFECTO = IE3_MOTOR2.por_defecto, IE3_MOTOR2.sigue, IE3_MOTOR2.sin_por_defecto


def rama(origen: int, destino: int, cond: int = 0xE, enlace: bool = False) -> int:
    """Codifica ``b``/``bl`` ARM de ``origen`` a ``destino`` (offsets del mismo módulo)."""
    delta = destino - (origen + 8)
    if delta % 4 or not -(1 << 25) <= delta < (1 << 25):
        raise ValueError(f"rama fuera de alcance {origen:#x} -> {destino:#x}")
    return (cond << 28) | (0xB if enlace else 0xA) << 24 | ((delta >> 2) & 0xFFFFFF)


def cueva_font8(cueva: int, motor: Motor2 = IE3_MOTOR2) -> list[ParchePalabra]:
    """Cueva de 5 palabras en ``cueva`` (debe estar a cero) + desvío en el motor."""
    cuerpo = [
        (0xE59DC0A4, "ldr ip, [sp, #0xa4]  ; línea de depuración"),
        (0xE37C0003, "cmn ip, #3"),
        (rama(cueva + 8, motor.sin_por_defecto, cond=0x0), "beq sin ancho por defecto"),
        (LDR_IP_SP60, "ldr ip, [sp, #0x60]  ; instrucción desplazada"),
        (rama(cueva + 16, motor.sigue), "b vuelta al motor"),
    ]
    parches = [ParchePalabra(cueva + 4 * i, 0, w, t) for i, (w, t) in enumerate(cuerpo)]
    parches.append(ParchePalabra(motor.por_defecto, LDR_IP_SP60, rama(motor.por_defecto, cueva), "b cueva ancho real"))
    return parches


def cueva_font8_global(cueva: int, motor: Motor2) -> list[ParchePalabra]:
    """Variante global (6 palabras): FONT8 a ancho real en TODAS las llamadas del motor 2 salvo las marcadas
    con línea −1 (campos de nombre, paso fijo) o −2 (rótulos de baldosas). Los textos con bigramas siguen a paso
    fijo por la rutina «¿hay bigramas?» del bucle por letra."""
    cuerpo = [
        (0xE59DC0A4, "ldr ip, [sp, #0xa4]  ; línea de depuración"),
        (0xE37C0001, "cmn ip, #1"),
        (0x137C0002, "cmnne ip, #2"),
        (rama(cueva + 12, motor.sin_por_defecto, cond=0x1), "bne sin ancho por defecto"),
        (LDR_IP_SP60, "ldr ip, [sp, #0x60]  ; instrucción desplazada"),
        (rama(cueva + 20, motor.sigue), "b vuelta al motor"),
    ]
    parches = [ParchePalabra(cueva + 4 * i, 0, w, t) for i, (w, t) in enumerate(cuerpo)]
    parches.append(ParchePalabra(motor.por_defecto, LDR_IP_SP60, rama(motor.por_defecto, cueva), "b cueva ancho real"))
    return parches


def retirar(cro: bytes, parches: Sequence[ParchePalabra]) -> bytes:
    """Devuelve a su estado de partida las palabras de ``parches`` que estén aplicadas (cambio de variante)."""
    d = bytearray(cro)
    for p in parches:
        if struct.unpack_from("<I", d, p.direccion)[0] == p.despues:
            struct.pack_into("<I", d, p.direccion, p.antes)
    return bytes(d)


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


#: dirección de ``cGameTextSystem::s_pInstance`` en el code.bin común (.data; sin relocación)
S_PINSTANCE = 0x2A16D8


def rutina_reinicio(direccion: int, s_pinstance: int = S_PINSTANCE) -> list[ParchePalabra]:
    """Rutina de 8 palabras (hueco a cero): pone G+0xeef6c = 0 (ancho fijo que deja el último dibujo) y
    r2 = LINEA_ANCHO_REAL; solo usa ip y r2. Se llama con ``bl`` en lugar del ``ldr r2, =línea`` de una llamada."""
    cuerpo = [
        (0xE59FC014, "ldr ip, [pc, #0x14]  ; &s_pInstance"),
        (0xE59CC000, "ldr ip, [ip]"),
        (0xE28CCAEF, "add ip, ip, #0xef000"),
        (0xE3A02000, "mov r2, #0"),
        (0xE14C29B4, "strh r2, [ip, #-0x94]  ; G+0xeef6c = 0"),
        (MVN_R2_2, "mvn r2, #2  ; línea −3"),
        (0xE12FFF1E, "bx lr"),
        (s_pinstance, ".word &s_pInstance"),
    ]
    return [ParchePalabra(direccion + 4 * i, 0, w, t) for i, (w, t) in enumerate(cuerpo)]


def llamada_reinicio(sitio: int, antes: int, rutina: int) -> ParchePalabra:
    """``ldr r2, =línea`` (palabra ``antes``) -> ``bl rutina``."""
    return ParchePalabra(sitio, antes, rama(sitio, rutina, enlace=True), "bl reinicio (ancho real)")


def rutina_reinicio_caja(direccion: int, s_pinstance: int = S_PINSTANCE, *, eef4c: bool = False,
                         gestor: bool = False) -> list[ParchePalabra]:
    """Como ``rutina_reinicio`` y además sale del modo «_2» de baldosas (G+0xeef7c = 0) y quita el cursor absoluto
    (G+0xeef54 = −100), como la caja de partida del IE3 (0x29bfd4). ``eef4c``: también G+0xeef4c = 0 (réplica exacta
    del IE3); ``gestor``: también pone a 0 el ancho forzado del gestor de texto ([r0+0x28]; r0 = gestor en la
    llamada). Usa ip y r2; deja r2 = LINEA_ANCHO_REAL."""
    cuerpo = [
        (0xE59CC000, "ldr ip, [ip]"),
        (0xE28CCAEF, "add ip, ip, #0xef000"),
        (0xE3A02000, "mov r2, #0"),
        (0xE14C29B4, "strh r2, [ip, #-0x94]  ; G+0xeef6c = 0"),
        (0xE50C2084, "str r2, [ip, #-0x84]   ; G+0xeef7c = 0 (sin modo _2)"),
    ]
    if eef4c:
        cuerpo.append((0xE50C20B4, "str r2, [ip, #-0xb4]   ; G+0xeef4c = 0"))
    if gestor:
        cuerpo.append((0xE5802028, "str r2, [r0, #0x28]    ; gestor: sin ancho forzado"))
    cuerpo += [
        (0xE3E02063, "mvn r2, #0x63"),
        (0xE50C20AC, "str r2, [ip, #-0xac]   ; G+0xeef54 = -100"),
        (MVN_R2_2, "mvn r2, #2  ; línea −3"),
        (0xE12FFF1E, "bx lr"),
    ]
    # ldr ip, [pc, #d]: la palabra literal va al final
    d = 4 * (len(cuerpo) + 1) - 8
    cuerpo = [(0xE59FC000 | d, "ldr ip, [pc, #...]  ; &s_pInstance")] + cuerpo + [(s_pinstance, ".word &s_pInstance")]
    return [ParchePalabra(direccion + 4 * i, 0, w, t) for i, (w, t) in enumerate(cuerpo)]


#: Motor 1: salto al cálculo de avance (0x...f48 de blog_proporcional/objetivos_proporcional) desde la comprobación
#: «¿ancho forzado ≤ 0?». La cueva añade: con línea −3 ([sp+0x94]) se usa el avance BCFNT también fuera del modo DS.
def cueva_motor1_linea(cueva: int, rama_ble: int, antes_ble: int, gancho: int, calculo: int) -> list[ParchePalabra]:
    """``rama_ble``: la ``ble gancho`` del motor 1 (palabra ``antes_ble``); ``calculo``: primera instrucción del
    cálculo proporcional dentro del gancho (tras su comprobación de modo DS). 4 palabras."""
    cuerpo = [
        (0xE59D1094, "ldr r1, [sp, #0x94]  ; línea de depuración"),
        (0xE3710003, "cmn r1, #3"),
        (rama(cueva + 8, calculo, cond=0x0), "beq cálculo proporcional"),
        (rama(cueva + 12, gancho), "b gancho original"),
    ]
    parches = [ParchePalabra(cueva + 4 * i, 0, w, t) for i, (w, t) in enumerate(cuerpo)]
    parches.append(ParchePalabra(rama_ble, antes_ble, rama(rama_ble, cueva, cond=0xD), "ble cueva línea −3"))
    return parches


def bigramas_por_letra(sitio: int, antes_b: int, cueva: int) -> list[ParchePalabra]:
    """Motor 2 (IE1/IE2): la regla «¿hay bigramas?» decidía por LÍNEA (si algún byte del texto es ≥ 0x88, todo el
    texto a paso fijo). Pasa a decidir por LETRA: solo la letra actual (r4 en el bucle) con primer byte ≥ 0x88
    (código de bigrama o kanji) toma su celda; el resto, el avance real.

    ``sitio``: la pareja «ldr r1, [sp, #0xd8]; b recorrido» tras la comprobación de la línea −1 (IE2 0x211650,
    IE1 0x197ed0); ``antes_b``: la palabra de esa ``b``. Cueva de 3 palabras."""
    return [
        ParchePalabra(sitio, 0xE59D10D8, 0xE5D41000, "ldrb r1, [r4]  ; primer byte de la letra actual"),
        ParchePalabra(sitio + 4, antes_b, rama(sitio + 4, cueva), "b cueva bigramas por letra"),
        ParchePalabra(cueva, 0, 0xE3510088, "cmp r1, #0x88"),
        ParchePalabra(cueva + 4, 0, 0x33A01000, "movlo r1, #0  ; no es bigrama: avance real"),
        ParchePalabra(cueva + 8, 0, 0xE12FFF1E, "bx lr"),
    ]
