import pytest

from ie123kit.ie3.comun.literales_visibles import _adr_retarget, _adr_target, _codificar, _pack


@pytest.mark.parametrize("target", [0x16621C, 0x16624C, 0x165C38, 0x165F40])
def test_adr_roundtrip_preserves_register_condition_and_no_flags(target):
    old = 0xE28F1FB7
    pc = 0x165F38
    patched = _adr_retarget(old, pc, target)
    assert _adr_target(patched, pc) == target
    assert patched >> 28 == old >> 28
    assert patched & 0x001FF000 == old & 0x001FF000


def test_packing_can_use_adjacent_group_capacity_without_truncating():
    data, offsets = _pack([b"a\0", b"LONG\0", b"z\0"], 16)
    assert offsets == [0, 4, 12]
    assert len(data) == 16
    assert data[4:9] == b"LONG\0"
    with pytest.raises(ValueError, match="no cabe"):
        _pack([b"A" * 9, b"B" * 9], 16)


def test_utf_carriers_complete_and_nul_terminated():
    data = _codificar(("Equipación", "Supertécnicas"))
    assert data.count(b"\0") == 2
    assert not data.endswith(b"?")
    with pytest.raises(ValueError, match="no codificable"):
        _codificar(("😀",))


def test_non_adr_and_unrepresentable_pointer_rejected():
    with pytest.raises(ValueError, match="no es ADR"):
        _adr_retarget(0xE3A00000, 0x1000, 0x2000)
    with pytest.raises(ValueError, match="no representable"):
        _adr_retarget(0xE28F1000, 0x1000, 0x12345678)
