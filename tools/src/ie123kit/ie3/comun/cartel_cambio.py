"""Cartel de cambio de jugador del partido del IE3 («%2d %-10s → %2d %-10s»): búfer de sprintf a 128 B.

Análisis (docs/IE3_NOMBRES_CORTOS_LIMITE.md, #87). La función (``ina_main3ogre.cro`` 1.0, 0x1ab388) prepara
el texto de un cambio de jugador para las cajas ``this+0x490`` (22 × 2 casillas):

1. copia el nombre corto del unitbase (+0x1C) a ``sp+0x108`` (16 B), lo rellena con espacios ASCII hasta
   10 bytes y lo pasa a ancho completo (``0x175cb8``: cada byte ASCII -> 2 bytes Shift-JIS; el espacio de
   relleno se vuelve «　» = 81 40) en ``sp+0x28`` / ``sp+0x48`` (32 B cada uno);
2. ``sprintf(sp+0x118, "%2d %-10s \\x81\\xa8 %2d %-10s", ...)``: **el búfer mide 28 B** (0x118..0x134) y encima
   están r4..fp y lr guardados (``sub sp, sp, #0x134``).

El texto ocupa 10 + A + B bytes + NUL (A y B: bytes de cada nombre ya en ancho completo). Con el japonés
(5 caracteres = 10 B) son 31 B: ya pisaba 3 B del r4 guardado, sin consecuencias. Con un nombre latino de L
letras (L < 10) son 2·(L + (10 − L)//2) B; con dos nombres de 6-7 letras, A = B = 16 y el texto acaba en
«　»+NUL justo sobre el r7 guardado (sp+0x140): **r7 = 0x00004081**, la firma del cuelgue (#87). Con nombres
más largos se pisan r8..fp y lr (salto a basura); con bigramas cambia la longitud y la corrupción (otra firma).

Parche sin código nuevo (como :mod:`ie123kit.nucleo.ejecutable.bufer_rubi`): el marco crece 0x80 B y el
sprintf escribe en la zona nueva ``sp+0x134`` (128 B; con dos nombres de 14 letras hacen falta 67 B). La
conversión posterior (``sp+0x68``, 132 B libres hasta ``sp+0xec``) necesita como mucho 75 B. Ningún otro
acceso de la función llega a ``sp+0x134`` (sin argumentos en pila): se comprueba al aplicar.
"""
from __future__ import annotations

import re
import struct

from capstone import CS_ARCH_ARM, CS_MODE_ARM, Cs

from ie123kit.nucleo.ejecutable.parches_cro import ParchePalabra, aplicar

__all__ = ["FIRMA", "LARGO", "ORIGEN", "PARCHES", "aplicar_cartel_cambio", "bytes_texto", "localizar", "parches"]

#: Prólogo de la función (sin relocalizaciones): push {r4-fp, lr}; ldr sl, [pc, #0x264]; mov r7, r0;
#: sub sp, sp, #0x134; mov r5, #0.
FIRMA = bytes.fromhex("f04f2de964a29fe50070a0e14ddf4de20050a0e3")
#: Offset de la función en ``ina_main3ogre.cro`` japonesa 1.0 (solo informativo: se localiza por la firma).
ORIGEN = 0x1AB388
#: Largo de la función (hasta el ``pop`` final, 0x1ab5f4) para la auditoría de accesos a la pila.
LARGO = 0x270
#: (offset relativo, palabra original, palabra nueva, texto).
PARCHES = (
    (0x00C, 0xE24DDF4D, 0xE24DDF6D, "sub sp, sp, #0x134 -> #0x1b4 (marco + 0x80)"),
    (0x044, 0xE3A02018, 0xE3A02080, "mov r2, #0x18 -> #0x80 (borrado del búfer nuevo entero)"),
    (0x054, 0xE28D0F46, 0xE28D0F4D, "add r0, sp, #0x118 -> #0x134 (búfer que se borra)"),
    (0x148, 0xE28D0F46, 0xE28D0F4D, "add r0, sp, #0x118 -> #0x134 (destino del sprintf)"),
    (0x154, 0xE28D0F46, 0xE28D0F4D, "add r0, sp, #0x118 -> #0x134 (origen de la conversión a ancho completo)"),
    (0x268, 0xE28DDF4D, 0xE28DDF6D, "add sp, sp, #0x134 -> #0x1b4"),
)
_MD = Cs(CS_ARCH_ARM, CS_MODE_ARM)
_SP = re.compile(r"\bsp, #(0x[0-9a-f]+|\d+)")


def bytes_texto(largo_a: int, largo_b: int) -> int:
    """Bytes que escribe el sprintf (con el NUL) para dos nombres cortos latinos de ``largo_a``/``largo_b`` B."""
    def ancho(n: int) -> int:
        return 2 * (n + (10 - n) // 2) if n < 10 else 2 * n
    return 10 + ancho(largo_a) + ancho(largo_b) + 1


def localizar(cro: bytes) -> int:
    """Offset de la función (firma única, original o ya parcheada). ValueError si no está o hay varias."""
    ampliada = FIRMA[:12] + struct.pack("<I", PARCHES[0][2]) + FIRMA[16:]
    hits = [m.start() for f in (FIRMA, ampliada) for m in re.finditer(re.escape(f), cro)]
    if len(hits) != 1:
        raise ValueError(f"cartel de cambio: {len(hits)} coincidencias de la firma")
    return hits[0]


def _auditar(cro: bytes, f: int) -> None:
    """Ningún acceso a la pila de la función, salvo los parcheados, debe llegar a sp+0x118 o más."""
    tocados = {f + rel for rel, *_ in PARCHES}
    for i in _MD.disasm(cro[f:f + LARGO], f):
        if i.address in tocados:
            continue
        m = _SP.search(i.op_str)
        if m and int(m.group(1), 0) >= 0x118:
            raise ValueError(f"acceso a la pila no previsto en {i.address:#x}: {i.mnemonic} {i.op_str}")
        if re.search(r"\bsp, (r\d|sb|sl|fp|ip|lr)\b", i.op_str):
            raise ValueError(f"acceso a la pila por registro en {i.address:#x}: {i.mnemonic} {i.op_str}")


def parches(cro: bytes, f: int | None = None) -> list[ParchePalabra]:
    """Parches de la función en ``f`` (o localizada); ValueError si alguna palabra no es la esperada."""
    f = localizar(cro) if f is None else f
    _auditar(cro, f)
    out = []
    for rel, antes, despues, texto in PARCHES:
        actual = struct.unpack_from("<I", cro, f + rel)[0]
        if actual != antes:
            raise ValueError(f"cartel de cambio: {f + rel:#x} = {actual:#x}, se esperaba {antes:#x}")
        out.append(ParchePalabra(f + rel, antes, despues, texto))
    return out


def aplicar_cartel_cambio(cro: bytes) -> tuple[bytes, dict]:
    """Aplica el parche (idempotente). Devuelve ``(cro, informe)``."""
    f = localizar(cro)
    if struct.unpack_from("<I", cro, f + PARCHES[0][0])[0] == PARCHES[0][2]:
        for rel, _antes, despues, _t in PARCHES:
            if struct.unpack_from("<I", cro, f + rel)[0] != despues:
                raise ValueError(f"cartel de cambio a medio aplicar en {f + rel:#x}")
        return bytes(cro), {"ya_aplicado": True, "funcion": hex(f), "parches": []}
    salida, informe = aplicar(cro, parches(cro, f))
    informe["ya_aplicado"] = False
    informe["funcion"] = hex(f)
    return salida, informe
