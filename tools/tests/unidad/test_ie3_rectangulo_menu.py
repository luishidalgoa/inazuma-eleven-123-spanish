import struct

import pytest

from ie123kit.ie3.comun import rectangulo_menu as mod


def _execute(first, width, base):
    registers = [0x1000 + i for i in range(16)]
    registers[0], registers[5] = width, 0x50000
    original = registers.copy()
    words = {base + k: v for k, v in mod.instrucciones().items()}
    memory = {registers[5] + 0x108: 0 if first is None else 0x60000}
    if first is not None:
        memory[0x60000] = base + first
    pc, equal = base + mod.STUB, False
    for _ in range(12):
        if pc == base + mod.RETORNO:
            return registers, original
        word = words[pc]
        address, pc = pc, pc + 4
        cond = word >> 28
        if (cond == 0 and not equal) or (cond == 1 and equal):
            continue
        if word == 0xE595C108:
            registers[12] = memory[registers[5] + 0x108]
        elif word == 0xE35C0000:
            equal = registers[12] == 0
        elif word == 0x159CC000:
            registers[12] = memory[registers[12]]
        elif word == 0xE04CC00F:
            registers[12] = (registers[12] - address - 8) & 0xFFFFFFFF
        elif word == 0xE59F300C:
            registers[3] = words[address + 8 + 12]
        elif word == 0xE15C0003:
            equal = registers[12] == registers[3]
        elif word == 0x03A00090:
            registers[0] = 144
        elif word == mod.ORIGINAL:
            value = registers[0] & 0xFFFF
            registers[3] = value - 0x10000 if value & 0x8000 else value
        elif word & 0xFF000000 == 0xEA000000:
            delta = word & 0xFFFFFF
            if delta & 0x800000:
                delta -= 1 << 24
            pc = address + 8 + delta * 4
        else:
            raise AssertionError(hex(word))
    raise AssertionError("stub no retorna")


@pytest.mark.parametrize("base", [0, 0x8000000, 0xF000000])
@pytest.mark.parametrize("width", [64, 128])
@pytest.mark.parametrize("first", [None, mod.PRIMER_TEXTO, mod.PRIMER_TEXTO + 1, 0x166228])
def test_real_words_are_scoped_null_safe_and_aslr_independent(base, width, first):
    actual, before = _execute(first, width, base)
    assert actual[3] == (144 if first == mod.PRIMER_TEXTO else width)
    assert all(actual[i] == before[i] for i in range(16) if i not in (0, 3, 12))


def test_displaced_instruction_still_sign_extends_original_width():
    actual, _ = _execute(None, 0xFFFF, 0)
    assert actual[3] == -1


def test_selection_width_does_not_scale_native_glyph_positions():
    # Reader uses command+8 for filtering, command+C for actual native position.
    # These are separate fields written by DrawTextHintOnVram.
    commands = [(13 * i, 7 * i) for i in range(9)]
    def visible(width):
        return [native for logical, native in commands if logical * 1.25 < width * 1.25]
    assert visible(64) == [0, 7, 14, 21, 28]
    assert visible(144) == [0, 7, 14, 21, 28, 35, 42, 49, 56]
    assert mod.FIN < 0x29C000
    with pytest.raises(ValueError, match="inválido"):
        mod.parchear_rectangulo_menu(bytes(100))


@pytest.mark.requiere_rom
def test_official_composition_changes_only_hook_padding_and_segment_end():
    from ie123kit.ie3.comun.colocacion_visible import parchear
    from ie123kit.nucleo.config.raiz import find_root

    path = (find_root() / "work/ie3/shared/candidatas/spark_ogre_integrada_fase4"
            "/romfs/cro/ina_main3ogre.cro")
    if not path.exists():
        pytest.skip("requiere candidata fase4 local")
    before, _ = parchear(path.read_bytes())
    after, report = mod.parchear_rectangulo_menu(before)
    allowed = {i for offset in report["patch_offsets"] for i in range(offset, offset + 4)}
    assert len(after) == len(before)
    assert all(a == b or i in allowed for i, (a, b) in enumerate(zip(before, after)))
    assert struct.unpack_from("<I", after, mod.HOOK)[0] != mod.ORIGINAL
    assert not report["runtime_verified"]
    with pytest.raises(ValueError, match="requiere colocación"):
        mod.parchear_rectangulo_menu(after)


@pytest.mark.requiere_rom
def test_official_reader_filters_logical_coordinate_but_draws_native_coordinate():
    from ie123kit.nucleo.compresion.blz import decompress
    from ie123kit.nucleo.config.raiz import find_root

    path = find_root() / "work/shared/base_3ds/exefs.bin"
    if not path.exists():
        pytest.skip("requiere ExeFS JP oficial")
    exe = path.read_bytes()
    offset, size = struct.unpack_from("<II", exe, 8)
    code = decompress(exe[512 + offset:512 + offset + size])
    anchors = {
        # UV derecha * ancho textura * factor de display.
        0x651A4: "200a61eee00afdeee00af8eea00a62eee00afdeee08af8ee",
        # Comparaciones del command+8 contra izquierda/derecha: fuera -> omitir.
        0x65428: ("b800d4e1000aa0e1400aa0e1100a00eec00ab8eec08ab4ee10faf1ee"
                  "0901008a100a00eec00ab8eee80ab4ee10faf1ee0401002a"),
        # X final = origen + command+C - primer_command+C + ajuste; no ancho.
        0x655F8: ("fc50d4e1fea0d4e1ddc1d4e10b7045e054509de5140094e5071081e0"
                  "05504ae0052082e0dc31d4e102708ce00028a0e101a083e0"),
        # El productor almacena XY lógicos y nativos en campos separados.
        0x64A28: ("b820d4e10bcaa0e10f2a02e22c2a82e1b820c4e1ba20d4e10acaa0e1"
                  "0f2a02e22c2a82e1ba20c4e1b4b0c4e1"),
        0x64A68: "4c209de5141084e550109de5bc20c4e1be10c4e1",
    }
    for offset, expected_hex in anchors.items():
        expected = bytes.fromhex(expected_hex)
        assert code[offset:offset + len(expected)] == expected, hex(offset)
