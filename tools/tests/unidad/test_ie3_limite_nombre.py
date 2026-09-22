"""Intérprete independiente del subconjunto ARM del hook, sin ROM ni Unicorn."""

import hashlib
import struct

import pytest

from ie123kit.ie3.comun import limite_nombre as mod

MASK = 0xFFFFFFFF


def _ror(value, count):
    return ((value >> count) | (value << ((32 - count) % 32))) & MASK


def _sub_flags(a, b):
    result = (a - b) & MASK
    return bool(result >> 31), result == 0, a >= b, bool(((a ^ b) & (a ^ result)) >> 31)


def _condition(cond, flags):
    _n, z, c, _v = flags
    return {0: z, 1: not z, 2: c, 14: True}.get(cond, False)


def run_arm(words, entry, registers, memory, flags=(False, False, False, False), base=0):
    """Decode ARM32 real: B, LDR, ADD/SUB/CMP y NOP, fail-closed demás."""
    regs = list(registers)
    regs[15] = base + entry
    trace = []
    for _ in range(60):
        pc = regs[15]
        offset = pc - base
        if offset in (0x180EA0, 0x180B08, 0x1811A8):
            return regs, flags, offset, trace
        trace.append(offset)
        word = words[offset]
        regs[15] += 4
        if not _condition(word >> 28, flags):
            continue
        if word == 0xE320F000:
            continue
        if word & 0x0F000000 == 0x0A000000:
            imm = word & 0xFFFFFF
            if imm & 0x800000:
                imm -= 1 << 24
            regs[15] = pc + 8 + 4 * imm
            continue
        if word & 0x0FF00000 == 0x05900000:
            rn, rd = (word >> 16) & 15, (word >> 12) & 15
            regs[rd] = memory[regs[rn] + (word & 4095)]
            continue
        assert word & 0x0C000000 == 0, hex(word)
        rn, rd, opcode = (word >> 16) & 15, (word >> 12) & 15, (word >> 21) & 15
        a = pc + 8 if rn == 15 else regs[rn]
        if word & (1 << 25):
            b = _ror(word & 255, 2 * ((word >> 8) & 15))
        else:
            assert word & 0xFF0 == 0, hex(word)
            b = regs[word & 15]
        if opcode == 10:
            flags = _sub_flags(a, b)
        elif opcode == 2:
            regs[rd] = (a - b) & MASK
        elif opcode == 4:
            regs[rd] = (a + b) & MASK
        else:
            raise AssertionError(hex(word))
    raise AssertionError("bucle del parche")


def state(base=0, caller=mod.RETORNO_NOMBRE, occupied=0, logical=8):
    regs = [0xABC000 + n for n in range(16)]
    regs[1], regs[2], regs[6], regs[13] = logical, 64, 0x400000 + occupied, 0x600000
    memory = {regs[13] + 0xBC: base + caller, regs[13] + 0xC4: 0x400000,
              regs[13] + 0x28: 64}
    return regs, memory


@pytest.mark.parametrize("base", [0, 0x100000, 0x08000000, 0x0FE00000])
@pytest.mark.parametrize("logical", [8, 62, 64, 65, 71, 80, 81, 98, 134, 135])
def test_exact_name_return_and_aslr_preserve_all_live_state(base, logical):
    regs, memory = state(base, logical=logical)
    original_memory = dict(memory)
    after, flags, stop, _trace = run_arm(mod.DESPUES, mod.HOOK, regs, memory, base=base)
    assert stop == 0x180EA0
    assert after[2] == 134
    assert flags == _sub_flags(logical, 134)
    assert all(after[i] == regs[i] for i in range(15) if i not in (0, 2))
    assert memory == original_memory
    assert memory[regs[13] + 0x28] == 64


@pytest.mark.parametrize("base", [0, 0x08000000])
@pytest.mark.parametrize("caller", [mod.RETORNO_NOMBRE - 4, mod.RETORNO_NOMBRE + 4,
                                    0x03A9A8, 0x04F4BC, 0x180000, 0x1FFFFC])
def test_other_callers_keep_original_comparison_even_with_full_buffer(base, caller):
    for logical in (8, 64, 65, 71, 80, 100):
        regs, memory = state(base, caller=caller, occupied=512, logical=logical)
        after, flags, stop, trace = run_arm(mod.DESPUES, mod.HOOK, regs, memory, base=base)
        assert stop == 0x180EA0
        assert after[2] == 64
        assert flags == _sub_flags(logical, 64)
        assert 0x180A58 not in trace
        assert all(after[i] == regs[i] for i in range(15) if i != 0)


@pytest.mark.parametrize("entry", [0x180A54, 0x180A6C, 0x180A84, 0x180A9C, 0x180AB4])
@pytest.mark.parametrize("flags", [(False, False, False, False), (True, True, True, True)])
def test_all_reused_color_paths_retain_registers_flags_destination(entry, flags):
    regs, memory = state()
    before, oldflags, oldstop, _ = run_arm(mod.ANTES, entry, regs, memory, flags)
    after, newflags, newstop, _ = run_arm(mod.DESPUES, entry, regs, memory, flags)
    assert oldstop == newstop == 0x180B08
    assert before == after
    assert oldflags == newflags == flags


@pytest.mark.parametrize("count", list(range(18)) + [30, 100, 1000])
def test_zero_through_overlong_names_never_write_sixteenth_command(count):
    used, logical, line = 0, 0, 0
    writes = []
    for _ in range(count):
        regs, memory = state(occupied=used, logical=logical + 8)
        _after, flags, stop, _ = run_arm(mod.DESPUES, mod.HOOK, regs, memory)
        if stop == 0x1811A8:
            break
        assert stop == 0x180EA0
        # Original BLE: accepted if Z or N != V is false (signed <=).
        n, z, _c, v = flags
        if not (z or n != v):
            line += 1
            logical = 0
        assert line <= 1
        writes.append((used, used + 32))
        used += 32
        logical += 9
    assert len(writes) == min(count, 15)
    assert used <= 480
    # Original final-capacity check uses unmodified64*16/2=512.
    assert used + 32 <= 512
    writes.append((used, used + 32))  # reserved terminator command
    assert max(end for _, end in writes) <= 512


def test_fifteenth_allowed_sixteenth_rejected_before_draw():
    for occupied, expected in [(448, 0x180EA0), (480, 0x1811A8), (512, 0x1811A8)]:
        regs, memory = state(occupied=occupied)
        _after, _flags, stop, trace = run_arm(mod.DESPUES, mod.HOOK, regs, memory)
        assert stop == expected
        assert trace[-1] in (0x180ABC, 0x180AA0)


def synthetic_cro(monkeypatch):
    data = bytearray(0x181400)
    data[0x80:0x84] = b"CRO0"
    struct.pack_into("<II", data, 0xC8, 0x140, 1)
    struct.pack_into("<III", data, 0x140, 0x180, 0x181000, 0)
    for offset, word in {**mod.ANTES, **mod.ANCLAS}.items():
        struct.pack_into("<I", data, offset, word)
    monkeypatch.setattr(mod, "CRO_FASE3_SHA256", hashlib.sha256(data).hexdigest())
    return bytes(data)


def test_exact_patch_idempotence_and_unchanged_capacity_font_metrics(monkeypatch):
    original = synthetic_cro(monkeypatch)
    after, report = mod.parchear_limite_nombre(original)
    assert len(after) == len(original)
    allowed = {o + i for o in mod.DESPUES for i in range(4)}
    assert all(a == b for i, (a, b) in enumerate(zip(original, after)) if i not in allowed)
    again, second = mod.parchear_limite_nombre(after)
    assert again == after and second["already_applied"]
    assert not report["already_applied"]
    assert report["allocated_command_bytes_unchanged"] == 512
    assert report["stored_width_unchanged"] == 64
    assert report["patch_words"] == 23
    assert not report["runtime_verified"]


def test_unknown_partial_anchor_or_destination_changes_are_rejected(monkeypatch):
    original = synthetic_cro(monkeypatch)
    for offset in (0x400, 0x180E98, mod.HOOK):
        bad = bytearray(original)
        bad[offset] ^= 1
        with pytest.raises(ValueError):
            mod.parchear_limite_nombre(bytes(bad))
    partial = bytearray(original)
    struct.pack_into("<I", partial, mod.HOOK, mod.DESPUES[mod.HOOK])
    with pytest.raises(ValueError, match="parcialmente"):
        mod.parchear_limite_nombre(bytes(partial))


def test_direct_entry_to_reused_slots_is_rejected_even_with_new_fingerprint(monkeypatch):
    original = bytearray(synthetic_cro(monkeypatch))
    struct.pack_into("<I", original, 0x400, mod._salto(0x400, 0x180A58))
    monkeypatch.setattr(mod, "CRO_FASE3_SHA256", hashlib.sha256(original).hexdigest())
    with pytest.raises(ValueError, match="salto preexistente"):
        mod.parchear_limite_nombre(bytes(original))


def test_relocation_write_to_changed_instruction_is_rejected(monkeypatch):
    original = synthetic_cro(monkeypatch)
    monkeypatch.setattr(mod, "direcciones_de_tablas", lambda _: {mod.HOOK})
    with pytest.raises(ValueError, match="destino de relocación"):
        mod.parchear_limite_nombre(original)
