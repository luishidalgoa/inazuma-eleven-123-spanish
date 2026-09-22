"""Ejecución independiente del ARM real: separadores, alcance y capacidad."""
import struct

import pytest

from ie123kit.ie3.comun import colocacion_visible as mod

MASK = 0xFFFFFFFF


def run(entry, *, caller, text=mod.PRIMER_LITERAL_MENU, char=32, used=0, base=0, width=64, height=128):
    words = mod.instrucciones()
    memory = {base+o: w for o, w in words.items()}
    regs = [0x11000+i for i in range(16)]
    regs[0], regs[2], regs[4], regs[6], regs[13] = 7, width, 0x50000, 0x60000+used, 0x70000
    initial = regs.copy()
    memory.update({regs[13]+0xBC: base+caller, regs[13]+0xC0: base+text,
                   regs[13]+0xC4: 0x60000, regs[13]+0x28: width, regs[13]+0xCC: height,
                   regs[13]+0x48: 7, regs[4]: char})
    pc, z, carry = base+entry, False, False
    for _ in range(80):
        off = pc-base
        if off in (0x180E98, 0x180AB8, 0x1811A8):
            return regs, initial, memory, off
        w = memory[pc]
        old_pc, pc = pc, pc+4
        cond = w >> 28
        if not {0: z, 1: not z, 2: carry, 14: True}[cond]:
            continue
        if w & 0x0F000000 == 0x0A000000:
            delta = w & 0xFFFFFF
            if delta & 0x800000:
                delta -= 1 << 24
            pc = old_pc+8+delta*4
            continue
        rn, rd = (w >> 16) & 15, (w >> 12) & 15
        value = lambda r, current_pc=old_pc: current_pc+8 if r == 15 else regs[r]
        if w & 0x0C000000 == 0x04000000:
            address = value(rn)+(w & 4095)
            if w & (1 << 20):
                regs[rd] = memory[address]
                if w & (1 << 22):
                    regs[rd] &= 255
            else:
                memory[address] = regs[rd]
            continue
        if w & 0x0FC000F0 == 0x00000090:
            regs[(w >> 16) & 15] = regs[w & 15]*regs[(w >> 8) & 15] & MASK
            continue
        opcode = (w >> 21) & 15
        if w & (1 << 25):
            imm, shift = w & 255, ((w >> 8) & 15)*2
            operand = ((imm >> shift) | (imm << ((32-shift) % 32))) & MASK
        else:
            operand = value(w & 15)
            shift, kind = (w >> 7) & 31, (w >> 5) & 3
            assert not w & 16
            if kind == 1:
                operand >>= shift or 32
            else:
                assert kind == 0
                operand = (operand << shift) & MASK
        a = value(rn)
        if opcode == 2:
            regs[rd] = (a-operand) & MASK
        elif opcode == 10:
            z, carry = a == operand, a >= operand
        elif opcode == 13:
            regs[rd] = operand
        else:
            raise AssertionError(hex(w))
    raise AssertionError("hook no termina")


@pytest.mark.parametrize("base", [0, 0x8000000, 0xF000000])
@pytest.mark.parametrize("char", [32, 65, 0x81, 0x83, 0])
@pytest.mark.parametrize("caller", [mod.RETORNO_CUERPO, mod.RETORNO_CUERPO+4, mod.RETORNO_MENU])
def test_only_body_ascii_space_has_smaller_placement(base, char, caller):
    regs, old, mem, stop = run(mod.STUB_ESPACIO, caller=caller, char=char, base=base)
    assert stop == 0x180E98
    expected = 3 if caller == mod.RETORNO_CUERPO and char == 32 else 7
    assert mem[regs[13]+0x48] == expected
    assert all(regs[i] == old[i] for i in range(15) if i not in (0, 3, 12))


@pytest.mark.parametrize("base", [0, 0x8000000])
@pytest.mark.parametrize("text_delta", [-1, 0, 10, 55, 56, 2000])
@pytest.mark.parametrize("caller", [mod.RETORNO_MENU, mod.RETORNO_CUERPO, 0x160FB8])
def test_menu_limit_is_scoped_to_exact_literal_block(base, text_delta, caller):
    regs, old, mem, stop = run(mod.STUB_MENU, caller=caller, base=base,
                               text=mod.PRIMER_LITERAL_MENU+text_delta)
    assert stop == 0x180AB8
    selected = 0 <= text_delta < 56
    assert regs[2] == (144 if selected else 64)
    assert mem[regs[13]+0x28] == 64
    assert all(regs[i] == old[i] for i in range(15) if i not in (0, 2, 3, 12))


@pytest.mark.parametrize("width,height", [(64, 64), (64, 128), (128, 128)])
def test_menu_guard_reserves_terminator_without_changing_buffer(width, height):
    capacity = width*height//2
    for used in (capacity-64, capacity-32, capacity, capacity+32):
        _, _, _, stop = run(mod.STUB_MENU, caller=mod.RETORNO_MENU,
                             width=width, height=height, used=used)
        assert stop == (0x180AB8 if used < capacity-32 else 0x1811A8)


def test_unknown_input_rejected():
    with pytest.raises(ValueError, match="exacto"):
        mod.parchear(bytes(512))


def test_trampolines_fit_before_data_and_do_not_touch_previous_endpoint():
    assert mod.STUB_ESPACIO >= mod.FIN_CODIGO_ANTERIOR+8
    assert max(mod.instrucciones())+4 == mod.FIN < 0x29C000
    assert struct.pack("<I", mod.CAMBIOS[0x3AB70][1]) == bytes.fromhex("6430a0e3")
