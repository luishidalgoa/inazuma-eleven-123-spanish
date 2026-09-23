import pytest

from ie123kit.ie3.comun.geometria_submenus import CAMBIOS_TITULO, cota_titulo


@pytest.mark.parametrize("length", [0, 4, 10, 14])
def test_title_commands_and_terminator_fit(length):
    proof = cota_titulo(b"A" * length + b"\0")
    assert proof["glyphs_upper_bound"] == length
    assert proof["command_bytes_upper_bound"] == (length+1)*32
    assert proof["command_bytes_upper_bound"] <= proof["buffer_bytes"] == 512


def test_copy15_does_not_guarantee_terminator_for_long_input():
    with pytest.raises(ValueError, match="sin NUL"):
        cota_titulo(b"A" * 15 + b"\0")


def test_multibyte_upper_bound_is_conservative_without_new_encoder():
    assert cota_titulo(b"\x83\x41"*7+b"\0")["command_bytes_upper_bound"] == 480


def test_only_three_coordinated_constants():
    assert set(CAMBIOS_TITULO) == {0x175758, 0x269DF4, 0x269FDC}
    assert CAMBIOS_TITULO[0x175758] == (0xE3A01003, 0xE3A01004)
    assert CAMBIOS_TITULO[0x269DF4] == (0xE3A00040, 0xE3A00080)
    assert CAMBIOS_TITULO[0x269FDC] == (0xE3A03040, 0xE3A03080)
