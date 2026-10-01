"""Resultado del entrenamiento del IE3: familias de frases, código nuevo (interpretado) y literales."""
from __future__ import annotations

import struct

import pytest
from capstone import CS_ARCH_ARM, CS_MODE_ARM, Cs

from ie123kit.ie3.comun import entrenamiento as E
from ie123kit.nucleo.texto.sjis_portador import es_encode

#: Frases con la misma forma que las europeas (inventadas para la prueba, no son el texto oficial).
TEXTOS = {
    130: "Ti", 131: "Fí", 134: "Co", 132: "De", 133: "Ra", 136: "Ag", 135: "Va", 137: "PE", 138: "PT",
    169: "¡%s sube Ti en %d!\n¡%s llega al tope de Ti!", 170: "¡%s sube Ti en %d!",
    336: "¡%s sube Fí en %d!\n¡Fí al tope!", 337: "¡%s sube Fí en %d!",
    338: "¡%s sube Co en %d!\n¡Co al tope!", 339: "¡%s sube Co en %d!",
    340: "¡%s sube De en %d!\n¡De al tope!", 341: "¡%s sube De en %d!",
    342: "¡%s gana Ra en %d!\n¡Ra al tope!", 343: "¡%s gana Ra en %d!",
    344: "¡%s sube Ag en %d!\n¡Ag al tope!", 345: "¡%s sube Ag en %d!",
    346: "¡%s gana Va en %d!\n¡Va al tope!", 347: "¡%s gana Va en %d!",
    770: "Los PE de %s suben %d.\n¡%s con PE al tope!", 772: "Los PE de %s suben %d.",
    771: "Los PT de %s suben %d.\n¡%s con PT al tope!", 773: "Los PT de %s suben %d.",
    171: "Pasión necesaria", 172: "Faltan puntos.",
}
MAX = {k: m for k, (_s, m, _n) in enumerate(E.CASOS)}
NORMAL = {k: n for k, (_s, _m, n) in enumerate(E.CASOS)}
NOMBRE_OFF, NOMBRE = 0x1C, "Mark"


def test_familias_agrupan_y_ordenan_argumentos():
    fams, casos = E.familias(TEXTOS)
    assert len(fams) == 4
    assert [k for k, _s in casos] == [0, 1, 1, 1, 2, 1, 2, 3, 3]
    assert fams[3].args == (E.STAT, E.NOMBRE, E.SUBIDA, E.NOMBRE, E.STAT)


@pytest.mark.parametrize("caso", range(9))
@pytest.mark.parametrize("maximo", [False, True])
def test_simular_da_la_frase_oficial(caso, maximo):
    esperado = (TEXTOS[MAX[caso]] if maximo else TEXTOS[NORMAL[caso]]).replace("%s", NOMBRE).replace("%d", "3")
    assert E.simular(TEXTOS, caso, NOMBRE, 3, maximo) == esperado


def test_normal_que_no_es_prefijo_se_rechaza():
    malos = {**TEXTOS, 337: "¡%s sube algo en %d!"}
    with pytest.raises(ValueError):
        E.familias(malos)


def test_argumentos_fuera_del_esquema_se_rechazan():
    malos = {**TEXTOS, 169: "¡%d para %s en Ti!\n¡%s Ti!", 170: "¡%d para %s en Ti!"}
    with pytest.raises(ValueError):
        E.familias(malos)


# ------------------------------------------------------------------------ intérprete del código nuevo
def _cro_construido() -> bytearray:
    regiones, _inf = E.construir_region(TEXTOS)
    cro = bytearray(0xB5800)
    for ini, datos in regiones.items():
        cro[ini:ini + len(datos)] = datos
    return cro


def _cadena(mem: bytearray, p: int) -> bytes:
    return bytes(mem[p:mem.index(0, p)])


def _sprintf(mem, fmt: bytes, args: list) -> bytes:
    out, it, i = b"", iter(args), 0
    while i < len(fmt):
        if fmt[i:i + 2] == b"%s":
            out += _cadena(mem, next(it))
            i += 2
        elif fmt[i:i + 2] == b"%d":
            out += str(next(it)).encode()
            i += 2
        else:
            out += fmt[i:i + 1]
            i += 1
    return out


def _ejecutar(cro: bytearray, entrada: int, subida: int, maximo: bool) -> bytes:
    """Interpreta desde ``entrada`` hasta llegar a 0xb55c0; devuelve el texto de sp+0x20."""
    md = Cs(CS_ARCH_ARM, CS_MODE_ARM)
    mem = bytearray(cro) + bytearray(0x3000)
    sp, r7, r8 = 0xB6000, 0xB7000, 0xB8000
    mem[r8 + NOMBRE_OFF:r8 + NOMBRE_OFF + 5] = NOMBRE.encode() + b"\0"
    struct.pack_into("<I", mem, r7 + 0x7C, int(maximo))
    reg = {"r2": 0, "r3": 0, "r4": 0, "r5": 0, "r6": subida, "r7": r7, "r8": r8, "sp": sp}  # r2-r5: basura
    z, pc = False, entrada

    def val(op: str) -> int:
        op = op.strip()
        return int(op[1:], 0) if op.startswith("#") else reg[op]

    for _ in range(2000):
        if pc == 0xB55C0:
            return _cadena(mem, sp + 0x20)
        i = next(md.disasm(bytes(mem[pc:pc + 4]), pc))
        m, ops = i.mnemonic, [o.strip() for o in i.op_str.split(",")]
        siguiente = pc + 4
        if m == "add" and ops[1] == "pc":
            reg[ops[0]] = pc + 8 + val(ops[2])
        elif m == "add":
            reg[ops[0]] = val(ops[1]) + val(ops[2])
        elif m == "str":
            base, desp = ops[1].strip("[]"), (ops[2].strip("]#") if len(ops) > 2 else "0")
            struct.pack_into("<I", mem, reg[base] + int(desp, 0), reg[ops[0]])
        elif m == "ldr":
            reg[ops[0]] = struct.unpack_from("<I", mem, reg[ops[1].strip("[]")] + int(ops[2].strip("]#"), 0))[0]
        elif m == "bl":
            assert int(ops[0][1:], 0) == 0x530
            args = [reg["r2"], reg["r3"]] + list(struct.unpack_from("<3I", mem, sp))
            texto = _sprintf(mem, _cadena(mem, reg["r1"]), args)
            mem[reg["r0"]:reg["r0"] + len(texto) + 1] = texto + b"\0"
        elif m in ("cmp", "cmpne"):
            if m == "cmp" or not z:
                z = val(ops[0]) == val(ops[1])
        elif m == "ldrb":
            reg["r0"] += int(ops[2].strip("]!#"), 0)
            reg[ops[0]] = mem[reg["r0"]]
        elif m == "mov":
            reg[ops[0]] = val(ops[1])
        elif m == "strb":
            mem[reg[ops[1].strip("[]")]] = reg[ops[0]] & 0xFF
        elif m in ("b", "bne"):
            if m == "b" or not z:
                siguiente = int(ops[0][1:], 0)
        else:
            raise AssertionError(f"instrucción no prevista {pc:#x}: {m} {i.op_str}")
        pc = siguiente
    raise AssertionError("no termina")


@pytest.mark.parametrize("caso", range(9))
@pytest.mark.parametrize("maximo", [False, True])
def test_codigo_nuevo_escribe_la_frase_oficial(caso, maximo):
    cro = _cro_construido()
    # el switch japonés salta a 0xb53dc + 24·k (la tabla de saltos no cambia)
    texto = _ejecutar(cro, 0xB53DC + 24 * caso, 7, maximo)
    esperado = (TEXTOS[MAX[caso]] if maximo else TEXTOS[NORMAL[caso]]).replace("%s", NOMBRE).replace("%d", "7")
    assert texto == es_encode(esperado, 1 << 30)


def test_caso_por_defecto_da_texto_vacio():
    assert _ejecutar(_cro_construido(), 0xB54A8, 1, True) == b""


def test_region_no_japonesa_se_rechaza_y_la_propia_es_idempotente():
    with pytest.raises(ValueError):
        E.aplicar_entrenamiento(bytes(0xB5800), TEXTOS)
    cro = bytes(_cro_construido())
    salida, inf = E.aplicar_entrenamiento(cro, TEXTOS)
    assert salida == cro and inf["ya_aplicado"]


def test_literal_en_su_hueco():
    jp = "ひつようねっけつＰ"
    cro = bytearray(64)
    cro[8:8 + 18] = jp.encode("cp932")
    salida, _inf = E.aplicar_literal(bytes(cro), 8, jp, 20, "Pasión necesaria")
    assert salida[8:28] == es_encode("Pasión necesaria", 99).ljust(20, b"\0")
    assert E.aplicar_literal(salida, 8, jp, 20, "Pasión necesaria")[1]["ya_aplicado"]
    with pytest.raises(ValueError):
        E.aplicar_literal(bytes(cro), 8, jp, 20, "Un texto demasiado largo")
