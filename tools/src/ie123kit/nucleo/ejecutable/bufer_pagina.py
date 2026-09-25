"""Búfer de página del diálogo: localizar y ampliar (132 B -> 256 B) en los CRO de la recopilación.

Motor común a IE1, IE2 e IE3 (probado en juego en el IE3, 2026-09-22). La función que dibuja una
página de diálogo copia el texto hasta 0x0C a un búfer de la pila de 132 B (``add r0, sp, #B`` +
``bl`` de copia) sin comprobar el tamaño. Con ancho completo (2 B por letra) caben ~65 letras por
caja: con 37 caracteres por línea el reparto dejaba una sola línea por caja.

Ampliación sin código nuevo, solo inmediatos en su sitio:

  - marco de la función ``sub sp,sp,#F`` / ``add sp,sp,#F`` -> ``F + 0x100`` (entrada y salidas);
  - referencias al búfer ``add rN, sp, #B`` -> ``#F`` (zona nueva de 256 B al final del marco);
  - accesos ``[sp, #k]`` con ``k >= F`` (registros guardados y argumentos) -> ``k + 0x100``.

``localizar`` encuentra el bucle de copia por su forma (``ldrb [rX]; cmp r0,#0xc; …; add r2, fp, #1;
add r0, sp, #B; bl``), delimita la función (``push {…lr}`` anterior hasta el siguiente) y audita TODOS
sus accesos a ``sp``. Si aparece algo que no sabe desplazar (``ldm``/``stm`` desde sp con escritura,
``add`` de registro con sp, operandos no codificables) no parchea.
"""
from __future__ import annotations

import re

from capstone import CS_ARCH_ARM, CS_MODE_ARM, Cs

AMPLIACION = 0x100
_MD = Cs(CS_ARCH_ARM, CS_MODE_ARM)
_IMM = re.compile(r"sp, #(0x[0-9a-f]+|\d+)")


def _ins(d: bytes, a: int):
    return next(_MD.disasm(d[a:a + 4], a), None)


def _imm12_arm(valor: int) -> int | None:
    """Operando inmediato ARM (rot, imm8) de 12 bits para ``valor``, o None si no es codificable."""
    for rot in range(16):
        v = ((valor << (2 * rot)) | (valor >> (32 - 2 * rot))) & 0xFFFFFFFF if rot else valor
        if v < 256:
            return (rot << 8) | v
    return None


def localizar(d: bytes, inicio: int = 0, fin: int | None = None) -> dict:
    """Devuelve {funcion, marco, bufer, llamada} de la copia de página, o lanza ValueError."""
    fin = fin or len(d)
    hallados = []
    for a in range(inicio, fin - 16, 4):
        i = _ins(d, a)
        if not i or i.mnemonic != "add" or not i.op_str.startswith("r2, fp, #1"):
            continue
        j, k = _ins(d, a + 4), _ins(d, a + 8)
        m = j and j.mnemonic == "add" and re.fullmatch(r"r0, sp, #(0x[0-9a-f]+|\d+)", j.op_str)
        if not m or not k or k.mnemonic != "bl":
            continue
        previo = [_ins(d, a - 4 * n) for n in range(1, 8)]
        if not any(p and p.mnemonic == "cmp" and p.op_str == "r0, #0xc" for p in previo):
            continue
        hallados.append((a + 4, int(m.group(1), 0)))
    if len(hallados) != 1:
        raise ValueError(f"copia de página: {len(hallados)} candidatas {[hex(x) for x, _ in hallados]}")
    ref, bufer = hallados[0]
    a = ref
    while True:
        i = _ins(d, a)
        if i and i.mnemonic == "push" and "lr" in i.op_str:
            break
        a -= 4
    funcion = a
    b = a + 4
    while True:
        i = _ins(d, b)
        if i and i.mnemonic == "push" and "lr" in i.op_str:
            break
        b += 4
    marcos = [(x, _ins(d, x)) for x in range(funcion, b, 4)]
    subs = [i for _, i in marcos if i and i.mnemonic == "sub" and re.fullmatch(r"sp, sp, #\S+", i.op_str)]
    if len(subs) != 1:
        raise ValueError(f"marco: {len(subs)} sub sp")
    marco = int(subs[0].op_str.split("#")[1], 0)
    return {"funcion": funcion, "fin": b, "marco": marco, "bufer": bufer, "copia": ref}


def parches(d: bytes, loc: dict) -> list[tuple[int, bytes, bytes, str]]:
    """[(dirección, antes, después, texto)] para ampliar el búfer; ValueError si algo no es seguro."""
    F, B = loc["marco"], loc["bufer"]
    nuevo_marco = _imm12_arm(F + AMPLIACION)
    nuevo_bufer = _imm12_arm(F)
    if nuevo_marco is None or nuevo_bufer is None:
        raise ValueError("inmediatos no codificables")
    out = []
    for a in range(loc["funcion"], loc["fin"], 4):
        i = _ins(d, a)
        if not i or "sp" not in i.op_str or i.mnemonic == "andeq":
            continue  # andeq con sp = palabra de datos de la reserva de literales, no código
        w = int.from_bytes(d[a:a + 4], "little")
        s = f"{i.mnemonic} {i.op_str}"
        m = _IMM.search(i.op_str)
        k = int(m.group(1), 0) if m else None
        if i.mnemonic in ("push", "pop") or s in ("mov r2, sp", "mov r0, sp", "mov r1, sp", "mov r3, sp"):
            continue
        if i.mnemonic == "add" and i.op_str.startswith("sp, sp, #") and k is not None and k <= 0x10:
            continue  # libera los r0-r3 apilados en la entrada (push {r0, r1, r2, …}), no el marco
        if i.mnemonic in ("sub", "add") and i.op_str.startswith("sp, sp, #"):
            if k != F:
                raise ValueError(f"{a:#x}: {s} (marco distinto)")
            nw = (w & ~0xFFF) | nuevo_marco
        elif i.mnemonic == "add" and k == B and re.fullmatch(r"r\d+, sp, #\S+", i.op_str):
            nw = (w & ~0xFFF) | nuevo_bufer
        elif k is not None and k >= F:
            if i.mnemonic in ("ldr", "str", "ldrb", "strb") and "[sp, #" in i.op_str and k + AMPLIACION < 0x1000:
                nw = w + AMPLIACION
            elif i.mnemonic == "add" and re.fullmatch(r"r\d+, sp, #\S+", i.op_str) and _imm12_arm(k + AMPLIACION) is not None:
                nw = (w & ~0xFFF) | _imm12_arm(k + AMPLIACION)
            else:
                raise ValueError(f"{a:#x}: {s} (acceso por encima del marco que no sé desplazar)")
        elif k is None and ("sp, r" in i.op_str or (i.mnemonic.startswith(("ldm", "stm")) and "sp!" in i.op_str)):
            raise ValueError(f"{a:#x}: {s} (acceso a sp por registro)")
        elif k is not None and B <= k < B + 0x84 and i.mnemonic not in ("add",):
            raise ValueError(f"{a:#x}: {s} (acceso directo dentro del búfer viejo)")
        else:
            continue
        nb = nw.to_bytes(4, "little")
        j = next(_MD.disasm(nb, a))
        out.append((a, d[a:a + 4], nb, f"{s} -> {j.mnemonic} {j.op_str}"))
    return out
