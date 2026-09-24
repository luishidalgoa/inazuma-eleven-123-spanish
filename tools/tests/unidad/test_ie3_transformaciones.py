"""Cambios de bytecode declarados del IE3 (ie123kit.ie3.comun.transformaciones) con eventos sintéticos."""

import struct

import pytest

from ie123kit.ie3.comun import transformaciones as T
from ie123kit.ie3.comun.referencias import instrucciones, leer_referencias


def _ins(ident, opcode, tipos, valores, flags=0):
    words = (len(tipos) + 7) // 8
    tw = bytearray(4 * words)
    for i, t in enumerate(tipos):
        tw[i // 2] |= t << (4 * (i % 2))
    size = 8 + 4 * words + 4 * len(valores)
    return struct.pack("<HHHBB", ident, size, opcode, len(tipos), flags) + bytes(tw) + struct.pack(
        f"<{len(valores)}I", *valores)


def _texto(ins, slot, cuerpo: bytes):
    size = (len(cuerpo) + 8) & ~3
    return struct.pack("<HBB", ins, slot, size) + cuerpo + bytes(size - 4 - len(cuerpo))


def _ssd(ins_list, textos):
    codigo, tabla = b"".join(ins_list), b"".join(textos)
    cab = bytearray(b"SSD\0" + struct.pack("<I", 0x30001) + bytes(24))
    out = cab + codigo + tabla
    struct.pack_into("<I", out, 8, len(out))
    struct.pack_into("<HH", out, 12, len(ins_list), len(textos))
    struct.pack_into("<II", out, 16, len(codigo), len(tabla))
    return bytes(out)


def _evet(*cuerpos):
    return b"".join(_texto(0, 0, c) for c in cuerpos)


@pytest.fixture(autouse=True)
def _limpio():
    T.cargar([])
    yield
    T.cargar([])


def test_intercambio_ida_y_vuelta():
    ev = _evet(b"texto %1F %s", b"yomi", b"yomi2")
    tam = [len(_texto(0, 0, c)) for c in (b"texto %1F %s", b"yomi", b"yomi2")]
    ssd = _ssd([_ins(1, 0x4002, (1,), (7,)),
                _ins(2, 0x301D, (3, 3, 4, 3), (10, 11, 1, 12))],
               [_texto(2, 1, f"@0,{sum(tam)}".encode()), _texto(2, 2, b"x"), _texto(2, 4, b"y")])
    T.cargar([{"tipo": "intercambio", "perfil": "p", "evento": 5, "instruccion": 2}])
    s2, e2 = T.aplicar("p", 5, ssd, ev)
    i = {x.ident: x for x in instrucciones(s2)}[2]
    assert i.tipos == (3, 4, 3, 3) and i.valores == (10, 1, 11, 12)
    refs, *_ = leer_referencias(s2, e2)
    assert len(refs) == 1 and len(refs[0].registros) == 3
    assert T.aplicar("p", 5, s2, e2) == (s2, e2)            # idempotente
    assert T.revertir("p", 5, s2, e2) == (ssd, ev)


def test_insercion_renumera_y_revierte():
    ev = _evet(b"frase japonesa larga")
    n = len(ev)
    ssd = _ssd([_ins(1, 0x3001, (), ()),
                _ins(2, 0x301D, (3,), (20,), flags=5),
                _ins(3, 0x3002, (4,), (4,)),
                _ins(4, 0x3003, (4, 1), (2, 9))],
               [_texto(2, 1, f"@0,{n}".encode())])
    d = {"tipo": "insercion", "perfil": "p", "evento": 7, "instruccion": 2, "marca": 0x7E5E,
         "parte1_hex": b"parte uno".hex(), "parte2_hex": b"parte dos".hex()}
    T.cargar([d])
    s2, e2 = T.aplicar("p", 7, ssd, ev)
    ins = {x.ident: x for x in instrucciones(s2)}
    assert [x.ident for x in instrucciones(s2)] == [1, 2, 3, 4, 5]
    assert ins[3].opcode == 0x301D and ins[3].valores == (0x7E5E,) and s2[ins[3].offset + 7] == 5
    assert ins[4].valores == (5,)          # apuntaba a la 4, que ahora es la 5
    assert ins[5].valores == (2, 9)        # apuntaba a la 2 (no se mueve)
    refs, _, regs, _, _ = leer_referencias(s2, e2)
    textos = {r.instruccion.ident: regs[r.registros[0]].raw for r in refs}
    assert textos == {2: b"parte uno", 3: b"parte dos"}
    assert T.aplicar("p", 7, s2, e2) == (s2, e2)
    s3, e3 = T.revertir("p", 7, s2, e2)
    assert instrucciones(s3) == instrucciones(ssd)
    assert len(leer_referencias(s3, e3)[2]) == 1


def test_sin_declaraciones_no_toca_nada():
    ssd = _ssd([_ins(1, 0x3001, (), ())], [])
    assert T.aplicar("p", 1, ssd, b"") == (ssd, b"")
    assert T.revertir("p", 1, ssd, b"") == (ssd, b"")


def test_tipo_desconocido():
    with pytest.raises(ValueError):
        T.cargar([{"tipo": "otro", "perfil": "p", "evento": 1}])


def test_dos_inserciones_en_un_evento():
    ev = _evet(b"primera larga", b"segunda larga")
    n1 = len(_texto(0, 0, b"primera larga"))
    ssd = _ssd([_ins(1, 0x301D, (3,), (20,)), _ins(2, 0x3002, (4,), (3,)), _ins(3, 0x301D, (3,), (21,))],
               [_texto(1, 1, f"@0,{n1}".encode()), _texto(3, 1, f"@{n1},{len(ev) - n1}".encode())])
    d = [{"tipo": "insercion", "perfil": "p", "evento": 9, "instruccion": i, "marca": 0x7E5E,
          "parte1_hex": f"{i}a".encode().hex(), "parte2_hex": f"{i}b".encode().hex()} for i in (1, 3)]
    T.cargar(d)
    s2, e2 = T.aplicar("p", 9, ssd, ev)
    refs, _, regs, _, _ = leer_referencias(s2, e2)
    assert [regs[r.registros[0]].raw for r in refs] == [b"1a", b"1b", b"3a", b"3b"]
    assert {x.ident: x for x in instrucciones(s2)}[3].valores == (4,)   # 0x3002 apuntaba a la 3 original, que ahora es la 4
    assert T.aplicar("p", 9, s2, e2) == (s2, e2)
    s3, e3 = T.revertir("p", 9, s2, e2)
    assert instrucciones(s3) == instrucciones(ssd)
