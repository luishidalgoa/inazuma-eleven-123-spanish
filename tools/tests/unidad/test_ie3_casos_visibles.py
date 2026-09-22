import struct

import pytest

from ie123kit.ie3.comun.casos_visibles import ID_MISION_INTRO, mision_intro_actual, nombres_completos, titulos_rpg
from ie123kit.ie3.comun.ssd import parse_ssd
from ie123kit.ie3.comun.text import TextTable


def test_complete_name_by_identity_preserves_short_metadata_and_pointer():
    jp, es, now = (bytearray(208) for _ in range(3))
    for data in (jp, es, now):
        struct.pack_into("<H", data, 104 + 78, 3170)
        data[104 + 44:104 + 48] = b"META"
    jp[104:104 + 4] = "名前".encode("cp932")
    es[104:104 + 13] = b"Paolo Bianchi"
    now[:] = jp
    now[104 + 28:104 + 35] = b"Bianchi"
    result, report = nombres_completos(bytes(jp), bytes(es), bytes(now), TextTable.identity())
    assert result[104:132].split(b"\0")[0] == b"Paolo Bianchi"
    assert result[132:] == now[132:]
    assert report["applied"][0]["id"] == 3170
    assert nombres_completos(bytes(jp), bytes(es), result, TextTable.identity())[0] == result


def test_complete_name_rejects_unknown_current_metadata():
    jp = bytearray(104)
    now = bytearray(jp)
    now[102] = 1
    with pytest.raises(ValueError, match="metadata"):
        nombres_completos(bytes(jp), bytes(jp), bytes(now), TextTable.identity())


def title_fixture(text="El Meteoro Blanco"):
    dat = bytearray(48 * 32)
    for i in range(48):
        struct.pack_into("<H", dat, i * 32 + 30, i)
    jp = bytearray(48 * 32)
    es = bytearray(jp)
    jp[38 * 32:38 * 32 + 16] = "しろいりゅうせい".encode("cp932")
    es[38 * 32:38 * 32 + len(text)] = text.encode()
    return bytes(dat), bytes(dat), bytes(jp), bytes(es), TextTable.identity()


def test_rpg_title_uses_reference_and_conservative_consumer_capacity():
    args = title_fixture()
    result, report = titulos_rpg(*args)
    assert result[0x4C0:0x4E0].split(b"\0")[0] == b"El Meteoro Blanco"
    assert report["consumer_capacity"] == 19
    long = title_fixture("L" * 19)
    assert titulos_rpg(*long)[0] == long[2]


def test_rpg_title_cannot_copy_changed_conditions():
    args = list(title_fixture())
    bad = bytearray(args[1])
    bad[0] ^= 1
    args[1] = bytes(bad)
    with pytest.raises(ValueError, match="condiciones"):
        titulos_rpg(*args)


def mission_fixture(ident, opcode, text, wrong_branch=False):
    specs = [(ident-2, 0x6014, (1,), (0,)),
             (ident-1, 0x6001, (1, 1), (2, ident+2+(1 if wrong_branch else 0))),
             (ident, opcode, (1, 1, 3), (ID_MISION_INTRO, 1, 0)),
             (ident+1, 0x3075, (1, 1, 1), (0, 0, 500)),
             (ident+2, 0x6002, (1, 1), (2, ident-1))]
    code = b""
    for ix, op, types, values in specs:
        packed = sum(t << (4*i) for i, t in enumerate(types))
        code += struct.pack("<HHHBBI", ix, 12+4*len(types), op, len(types), 0, packed)
        code += struct.pack("<" + "I"*len(values), *values)
    raw = text.encode("cp932")
    size = (len(raw)+8)//4*4
    strings = struct.pack("<HBB", ident, 3, size) + (raw+b"\0").ljust(size-4, b"\0")
    return b"SSD\0" + struct.pack("<IIHHIIII", 0x30001, 32+len(code)+len(strings), 5, 1,
                                     len(code), len(strings), 0, 0) + code + strings


def test_mission_matches_changed_instruction_ids_but_same_game_identity_and_branches():
    jp = mission_fixture(1817, 0x201C, "大変だ！！女の子を助けよう！")
    es = mission_fixture(1869, 0x201D, "Ayuda a la chica!")
    result, report = mision_intro_actual(jp, es, jp, TextTable.identity())
    assert report["instruction_es"] == 1869
    assert report["no_growth"]
    before, _ = parse_ssd(jp, TextTable.identity())
    assert result[:32+before["code_len"]] == jp[:32+before["code_len"]]
    assert parse_ssd(result, TextTable.identity())[1][0].text == "Ayuda a la chica!"
    assert mision_intro_actual(jp, es, result, TextTable.identity())[0] == result


def test_mission_rejects_nearby_but_different_control_flow():
    jp = mission_fixture(1817, 0x201C, "大変だ！！女の子を助けよう！")
    es = mission_fixture(1869, 0x201D, "Ayuda!", wrong_branch=True)
    with pytest.raises(ValueError, match="ramas"):
        mision_intro_actual(jp, es, jp, TextTable.identity())


def test_mission_cannot_grow_into_padding():
    jp = mission_fixture(1817, 0x201C, "目的")
    es = mission_fixture(1869, 0x201D, "Muy largo!")
    with pytest.raises(ValueError, match="sin crecimiento"):
        mision_intro_actual(jp, es, jp, TextTable.identity())
