"""Búfer de texto del pintor con furigana (motor 1 + rubí): 136 B -> 512 B, en las CRO de IE1, IE2 e IE3.

El pintor (IE3 ina_main3ogre 0x181370, IE1 ina_main1 0xe6d0c, IE2 ina_main2 0x122568 en la 1.0; la misma función
en los tres) copia el texto con la rutina de furigana a un búfer de su pila en ``sp+0xa38`` **sin comprobar el
tamaño**. Detrás: ``[sp+0xac0]``/``[sp+0xac4]`` (se escriben después de copiar: un texto de más de 136 B sale
corrompido), ``d8``/``d9`` en ``sp+0xad0`` y los registros guardados (r7 en ``sp+0xafc``). Con la copia de 1 byte
(capa copia_1byte, v16) los textos en español ocupan más: en el IE3 uno de 198 B pisó el r7 guardado con «　»+NUL
(0x00004081) y el llamador pasó ``this`` nulo a ``BuildTextCommand`` (cuelgue al terminar el primer tiempo, #87).

Ampliación sin código nuevo (como ``nucleo.ejecutable.bufer_pagina``): el marco crece ``AMPLIACION`` bytes por
encima de las variables locales y el búfer pasa a esa zona nueva (``sp+F``, 512 B). :func:`localizar` da con el
pintor por su prólogo (firma exacta de 16 instrucciones); :func:`parches` audita TODA la función y desplaza
``sub/add sp,sp,#F``, los accesos ``[sp,#k]`` con ``k >= F`` (registros guardados y argumentos) y las bases
``add rX, sp, #0x800`` que solo se usan para llegar a los argumentos; la base del búfer apunta a ``sp+F``. Si
aparece un acceso a la pila que no sabe desplazar, no parchea. Vale igual para la 1.4 (se relocaliza con
:mod:`ie123kit.nucleo.ejecutable.relocalizar`, o se aplica directamente: la firma también está).
"""
from __future__ import annotations

import re
import struct

from capstone import CS_ARCH_ARM, CS_MODE_ARM, Cs

from ie123kit.nucleo.ejecutable.parches_cro import ParchePalabra, aplicar

__all__ = ["AMPLIACION", "FIRMA", "aplicar_bufer_rubi", "localizar", "parches"]

AMPLIACION = 0x200
#: Prólogo del pintor (16 palabras, sin relocalizaciones ni ramas): push, vpush, sub sp,#0xad0, bases sp+0x800,
#: vldr de argumentos, búfer de furigana sp+0x438 y de texto sp+0xa38.
FIRMA = bytes.fromhex(
    "ff5f2de90300a0e1048b2dedadde4de2021b8de2023b8de2c93f83e2026b8de2"
    "c78ad1edc88a91edcb9a91ed012b8de28e6f86e2800193e8382082e20610a0e1")
_MD = Cs(CS_ARCH_ARM, CS_MODE_ARM)
_IMM = re.compile(r"#(0x[0-9a-f]+|\d+)")


def _imm12(valor: int) -> int | None:
    for rot in range(16):
        v = ((valor << (2 * rot)) | (valor >> (32 - 2 * rot))) & 0xFFFFFFFF if rot else valor
        if v < 256:
            return (rot << 8) | v
    return None


def localizar(cro: bytes) -> int:
    """Offset del pintor (una sola coincidencia de :data:`FIRMA`, alineada) o ValueError."""
    hits, p = [], cro.find(FIRMA)
    while p >= 0:
        if p % 4 == 0:
            hits.append(p)
        p = cro.find(FIRMA, p + 1)
    if len(hits) != 1:
        raise ValueError(f"pintor con furigana: {len(hits)} coincidencias")
    return hits[0]


def _con_imm(w: int, nuevo: int) -> int:
    enc = _imm12(nuevo)
    if enc is None:
        raise ValueError(f"inmediato {nuevo:#x} no codificable")
    return (w & ~0xFFF) | enc


def parches(cro: bytes, funcion: int, ampliacion: int = AMPLIACION) -> list[ParchePalabra]:
    """Palabras que amplían el marco del pintor de ``funcion`` (auditoría completa; ValueError si no es seguro)."""
    instr = []
    a = funcion
    while True:
        i = next(_MD.disasm(cro[a:a + 4], a), None)
        instr.append((a, i))
        if i is not None and i.mnemonic == "pop" and "pc" in i.op_str:
            break
        a += 4
        if a - funcion > 0x1000:
            raise ValueError("fin del pintor no encontrado")
    subs = [i for _a, i in instr if i and i.mnemonic == "sub" and i.op_str.startswith("sp, sp, #")]
    if len(subs) != 1:
        raise ValueError("marco: sub sp ambiguo")
    marco = int(_IMM.search(subs[0].op_str).group(1), 0)
    # bases sp+k del prólogo (hasta la llamada a la copia): búfer o camino a los argumentos
    bases: dict[str, tuple[int, int]] = {}
    usos: dict[str, list[tuple[int, int, str]]] = {}
    fin_prologo = next(a for a, i in instr if i and i.mnemonic == "bl")
    for a, i in instr:
        if a >= fin_prologo or i is None:
            continue
        m = re.fullmatch(r"(r\d+), sp, #(0x[0-9a-f]+|\d+)", i.op_str)
        if i.mnemonic == "add" and m and int(m.group(2), 0) >= 0x800:
            bases[m.group(1)] = (a, int(m.group(2), 0))
            continue
        for reg, (_ab, k) in bases.items():
            m2 = re.fullmatch(rf"({reg}), {reg}, #(0x[0-9a-f]+|\d+)", i.op_str)
            m3 = re.search(rf"\[{reg}(?:, #(0x[0-9a-f]+|\d+))?\]", i.op_str)
            if i.mnemonic == "add" and m2:
                usos.setdefault(reg, []).append((a, k + int(m2.group(2), 0), "add"))
            elif m3:
                usos.setdefault(reg, []).append((a, k + int(m3.group(1) or "0", 0), "mem"))
    salida: list[ParchePalabra] = []

    def poner(a: int, nuevo: int, texto: str) -> None:
        w = struct.unpack_from("<I", cro, a)[0]
        salida.append(ParchePalabra(a, w, nuevo, texto))

    hechos = set()
    for reg, (ab, k) in bases.items():
        u = usos.get(reg, [])
        if not u:
            raise ValueError(f"base {reg} sin usos")
        if all(off >= marco for _a, off, _t in u):          # solo argumentos: la base sube con el marco
            poner(ab, _con_imm(struct.unpack_from("<I", cro, ab)[0], k + ampliacion), f"add {reg}, sp, #{k + ampliacion:#x}")
            hechos.add(ab)
        elif len(u) == 1 and u[0][2] == "add" and u[0][1] < marco:  # búfer de texto: a la zona nueva
            a_add = u[0][0]
            poner(a_add, _con_imm(struct.unpack_from("<I", cro, a_add)[0], marco - k),
                  f"add {reg}, {reg}, #{marco - k:#x}  ; búfer en sp+{marco:#x}")
            hechos.add(a_add)
        else:
            raise ValueError(f"base {reg}: usos mezclados {u}")
    for a, i in instr:
        if i is None or a in hechos or "sp" not in i.op_str:
            continue
        w = struct.unpack_from("<I", cro, a)[0]
        s = f"{i.mnemonic} {i.op_str}"
        m = _IMM.search(i.op_str)
        k = int(m.group(1), 0) if m else None
        if i.mnemonic in ("push", "pop", "vpush", "vpop") or (i.mnemonic.startswith(("stm", "ldm")) and "!" not in s):
            continue
        if i.op_str.startswith("sp, sp, #"):
            if k == marco:
                poner(a, _con_imm(w, marco + ampliacion), f"{i.mnemonic} sp, sp, #{marco + ampliacion:#x}")
            elif not (i.mnemonic == "add" and k is not None and k <= 0x10):
                raise ValueError(f"{a:#x}: {s}")
        elif k is not None and "[sp, #" in i.op_str:
            if k >= marco:
                if i.mnemonic not in ("ldr", "str", "ldrb", "strb") or k + ampliacion > 0xFFF:
                    raise ValueError(f"{a:#x}: {s} no cabe")
                poner(a, w + ampliacion, f"{i.mnemonic} ... [sp, #{k + ampliacion:#x}]")
        elif i.mnemonic == "add" and re.fullmatch(r"r\d+, sp, #\S+", i.op_str):
            if k >= marco:
                poner(a, _con_imm(w, k + ampliacion), f"add ..., sp, #{k + ampliacion:#x}")
        elif re.search(r"\[sp\]$", i.op_str) or re.fullmatch(r"r\d+, sp", i.op_str):
            continue
        else:
            raise ValueError(f"{a:#x}: {s} (acceso a la pila que no sé desplazar)")
    return sorted(salida, key=lambda p: p.direccion)


def aplicar_bufer_rubi(cro: bytes) -> tuple[bytes, dict]:
    """Localiza el pintor y amplía su búfer (idempotente: si el marco ya está ampliado no toca nada)."""
    try:
        funcion = localizar(cro)
    except ValueError:
        ampliado = FIRMA[:12] + bytes.fromhex("cdde4de2")
        if cro.find(ampliado) >= 0:
            return bytes(cro), {"ya_aplicado": True, "parches": []}
        raise
    salida, informe = aplicar(cro, parches(cro, funcion))
    informe["ya_aplicado"] = False
    informe["funcion"] = hex(funcion)
    return salida, informe
