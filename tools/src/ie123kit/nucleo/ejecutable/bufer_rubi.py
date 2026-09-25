"""Búferes de texto de los dos pintores con furigana (motor 1 + rubí) a 1 KB, en las CRO de IE1, IE2 e IE3.

Los dos pintores copian el texto con la rutina de furigana a un búfer de su pila **sin comprobar el tamaño**:

- ``pintor_rubi_a`` (IE3 ina_main3ogre 0x181370, IE1 ina_main1 0xe6d0c, IE2 ina_main2 0x122568; 1.0): búfer en
  ``sp+0xa38``, variables en ``sp+0xac0``/``0xac4`` (136 B útiles), ``d8``/``d9`` en ``sp+0xad0`` y r7 guardado
  en ``sp+0xafc`` (a 196 B).
- ``pintor_rubi_b`` (IE3 0x17fc4c, 70 llamadas; IE2 0x1208e8; no está en el IE1): búfer en ``sp+0xa28``, cuenta de
  la copia en ``sp+0xb28`` (256 B útiles), ``d8``/``d9`` en ``sp+0xb30`` y r7 guardado en ``sp+0xb5c`` (a 308 B).

Con la copia de 1 byte (capa copia_1byte, v16) los textos en español ocupan más. En el IE3, tras un evento del
partido (fuera de juego), un texto terminado en «　» pisó el r7 guardado con «　»+NUL (0x00004081) y el llamador
(dibujado del frame, 1.0 0x28ee74) pasó ``this`` = [0x4081] = 0 a ``BuildTextCommand`` (1.4: cuelgue en PC 0; 1.0:
pantallas congeladas con la música sonando), #87. Ampliar solo el pintor A no bastó: se amplían los dos.

Ampliación sin código nuevo (como ``nucleo.ejecutable.bufer_pagina``): el marco crece ``AMPLIACION`` bytes por
encima de las variables locales y el búfer pasa a esa zona nueva (``sp+F``, 1 KB). :func:`localizar` da con cada
pintor por su prólogo (firma exacta de 16 instrucciones); :func:`parches` audita TODA la función y desplaza
``sub/add sp,sp,#F``, los accesos ``[sp,#k]`` con ``k >= F`` (registros guardados y argumentos) y las bases
``add rX, sp, #0x800`` que solo se usan para llegar a los argumentos; la base del búfer (la que se pasa en r1 a la
copia) apunta a ``sp+F``. Si aparece un acceso a la pila que no sabe desplazar, no parchea. Vale igual para la 1.4
(se relocaliza con :mod:`ie123kit.nucleo.ejecutable.relocalizar`, o se aplica directamente: las firmas también
están).
"""
from __future__ import annotations

import re
import struct

from capstone import CS_ARCH_ARM, CS_MODE_ARM, Cs

from ie123kit.nucleo.ejecutable.parches_cro import ParchePalabra, aplicar

__all__ = ["AMPLIACION", "FIRMA", "FIRMAS", "aplicar_bufer_rubi", "localizar", "localizar_todos", "parches"]

AMPLIACION = 0x400
#: Prólogo del pintor (16 palabras, sin relocalizaciones ni ramas): push, vpush, sub sp,#0xad0, bases sp+0x800,
#: vldr de argumentos, búfer de furigana sp+0x438 y de texto sp+0xa38.
FIRMA = bytes.fromhex(
    "ff5f2de90300a0e1048b2dedadde4de2021b8de2023b8de2c93f83e2026b8de2"
    "c78ad1edc88a91edcb9a91ed012b8de28e6f86e2800193e8382082e20610a0e1")
#: Segundo pintor del motor 1 con furigana (IE3 0x17fc4c, IE2 0x1208e8; 70 llamadas en el IE3): marco 0xb30,
#: búfer de texto en sp+0xa28 con la cuenta de la copia en sp+0xb28 (256 B útiles) y r7 guardado en sp+0xb5c:
#: un texto de ~310 B terminado en «　» deja r7 = 0x00004081, el mismo síntoma que el primero.
FIRMA_B = bytes.fromhex(
    "ff5f2de90300b0e1048b2dedb3de4de2023b8de2021b8de2df3f83e278bb9de5"
    "000593e8904b9de58c9b9de59c7b9de5e18ad1ede28a91ede59a91ed6b00000a")
#: Firma de cada pintor -> nombre.
FIRMAS = {FIRMA: "pintor_rubi_a", FIRMA_B: "pintor_rubi_b"}
_MD = Cs(CS_ARCH_ARM, CS_MODE_ARM)
_IMM = re.compile(r"#(0x[0-9a-f]+|\d+)")


def _imm12(valor: int) -> int | None:
    for rot in range(16):
        v = ((valor << (2 * rot)) | (valor >> (32 - 2 * rot))) & 0xFFFFFFFF if rot else valor
        if v < 256:
            return (rot << 8) | v
    return None


def localizar(cro: bytes, firma: bytes = FIRMA) -> int:
    """Offset del pintor (una sola coincidencia de ``firma``, alineada) o ValueError."""
    hits, p = [], cro.find(firma)
    while p >= 0:
        if p % 4 == 0:
            hits.append(p)
        p = cro.find(firma, p + 1)
    if len(hits) != 1:
        raise ValueError(f"pintor con furigana: {len(hits)} coincidencias")
    return hits[0]


def localizar_todos(cro: bytes) -> dict[str, int]:
    """``{nombre: offset}`` de los pintores de :data:`FIRMAS` presentes (0 o 1 coincidencia cada uno)."""
    salida = {}
    for firma, nombre in FIRMAS.items():
        if cro.find(firma) >= 0:
            salida[nombre] = localizar(cro, firma)
    return salida


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
        m = re.fullmatch(r"(r\d+|sb|sl|fp|ip), sp, #(0x[0-9a-f]+|\d+)", i.op_str)
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
    # Fuera del prólogo, una base sp+K que llegue (con su desplazamiento) a la zona de argumentos no se sabe
    # desplazar: se rechaza en vez de dejarla apuntando a sitio viejo.
    for n, (a, i) in enumerate(instr):
        m = re.fullmatch(r"(r\d+|sb|sl|fp|ip), sp, #(0x[0-9a-f]+|\d+)", i.op_str) if i else None
        if a < fin_prologo or not m or i.mnemonic != "add" or int(m.group(2), 0) < 0x400:
            continue
        reg, k = m.group(1), int(m.group(2), 0)
        for _b, j in instr[n + 1:n + 9]:
            if j is None:
                continue
            m2 = re.fullmatch(rf"{reg}, {reg}, #(0x[0-9a-f]+|\d+)", j.op_str) if j.mnemonic == "add" else None
            m3 = re.search(rf"\[{reg}, #(0x[0-9a-f]+|\d+)\]", j.op_str)
            extra = int((m2 or m3).group(1), 0) if (m2 or m3) else 0
            if k + extra >= marco:
                raise ValueError(f"{a:#x}: base sp+{k:#x} usada hacia sp+{k + extra:#x} (argumentos)")
            if j.op_str.startswith(f"{reg},") and not m2:
                break
    salida: list[ParchePalabra] = []

    def poner(a: int, nuevo: int, texto: str) -> None:
        w = struct.unpack_from("<I", cro, a)[0]
        salida.append(ParchePalabra(a, w, nuevo, texto))

    # el búfer de texto es el que se pasa en r1 a la copia (``mov r1, rX`` justo antes del bl)
    previa = next(i for a, i in instr if a == fin_prologo - 4)
    mb = re.fullmatch(r"r1, (r\d+)", previa.op_str) if previa and previa.mnemonic == "mov" else None
    if not mb or mb.group(1) not in bases:
        raise ValueError("no se reconoce el búfer de texto pasado a la copia")
    bufer = mb.group(1)
    hechos = set()
    for reg, (ab, k) in bases.items():
        u = usos.get(reg, [])
        if not u:
            raise ValueError(f"base {reg} sin usos")
        if reg == bufer:                                    # búfer de texto: a la zona nueva
            if len(u) != 1 or u[0][2] != "add" or u[0][1] >= marco:
                raise ValueError(f"búfer {reg}: usos inesperados {u}")
            a_add = u[0][0]
            poner(a_add, _con_imm(struct.unpack_from("<I", cro, a_add)[0], marco - k),
                  f"add {reg}, {reg}, #{marco - k:#x}  ; búfer en sp+{marco:#x}")
            hechos.add(a_add)
        elif all(off >= marco for _a, off, _t in u):        # solo argumentos: la base sube con el marco
            poner(ab, _con_imm(struct.unpack_from("<I", cro, ab)[0], k + ampliacion), f"add {reg}, sp, #{k + ampliacion:#x}")
            hechos.add(ab)
        elif all(off < marco for _a, off, _t in u):         # otra variable local (tabla de furigana): igual
            continue
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
        elif i.mnemonic == "add" and re.fullmatch(r"(?:r\d+|sb|sl|fp|ip), sp, #\S+", i.op_str):
            if k >= marco:
                poner(a, _con_imm(w, k + ampliacion), f"add ..., sp, #{k + ampliacion:#x}")
        elif re.search(r"\[sp\]$", i.op_str) or re.fullmatch(r"(?:r\d+|sb|sl|fp|ip), sp", i.op_str):
            continue
        else:
            raise ValueError(f"{a:#x}: {s} (acceso a la pila que no sé desplazar)")
    return sorted(salida, key=lambda p: p.direccion)


def aplicar_bufer_rubi(cro: bytes) -> tuple[bytes, dict]:
    """Localiza los pintores de :data:`FIRMAS` y amplía su búfer.

    Idempotente: un pintor ya ampliado (su firma con el ``sub sp`` nuevo) se salta. ValueError si no hay
    ninguno (ni original ni ampliado).
    """
    pendientes: dict[str, int] = {}
    ya: list[str] = []
    for firma, nombre in FIRMAS.items():
        if cro.find(firma) >= 0:
            pendientes[nombre] = localizar(cro, firma)
            continue
        marco = struct.unpack_from("<I", firma, 12)[0] & 0xFFF
        ampliado = firma[:12] + struct.pack("<I", _con_imm(struct.unpack_from("<I", firma, 12)[0],
                                                           _rot(marco) + AMPLIACION))
        if cro.find(ampliado) >= 0:
            ya.append(nombre)
    if not pendientes:
        if ya:
            return bytes(cro), {"ya_aplicado": True, "parches": [], "funciones": {}, "ya_ampliados": ya}
        raise ValueError("no hay pintor con furigana en la CRO")
    todos = [p for f in pendientes.values() for p in parches(cro, f)]
    salida, informe = aplicar(cro, todos)
    informe["ya_aplicado"] = False
    informe["funciones"] = {n: hex(f) for n, f in pendientes.items()}
    informe["ya_ampliados"] = ya
    return salida, informe


def _rot(imm12: int) -> int:
    rot, imm = (imm12 >> 8) * 2, imm12 & 0xFF
    return ((imm >> rot) | (imm << (32 - rot))) & 0xFFFFFFFF if rot else imm
