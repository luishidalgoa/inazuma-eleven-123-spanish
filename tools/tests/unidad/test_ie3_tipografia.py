import struct

import pytest

from ie123kit.ie3.comun.maqueta import lineas_de, tinta
from ie123kit.ie3.comun.tipografia import (
    FuenteBCFNT, _ajustar_grid, avance_font12, margen_compensado,
)


def test_official_tracked_font12_advances_drive_layout_regressions():
    narration = "Unos meses antes, en cierto lugar de Italia..."
    paolo = "¡Bravo, Paolo! ¡El fútbol es puro arte en tus botas!"
    paolo_official = "¡Bravo, Paolo! ¡El fútbol es puro arte\\nen tus botas!"

    # 329/371 eran JP; 239/270, el CWDH oficial sin respiración. 274/310
    # conservan el raster+CWDH europeo como pareja y suman 1 px por letra.
    assert tinta(narration) == 274
    assert tinta(paolo) == 310
    assert lineas_de(narration) == [narration]
    assert lineas_de(paolo_official) == [
        "¡Bravo, Paolo! ¡El fútbol es puro arte",
        "en tus botas!",
    ]
    assert avance_font12("È") == avance_font12("E") == 8
    assert avance_font12("¡") == 3
    assert avance_font12("í") == 5


def test_baseline_adjustment_preserves_every_sample_without_merging():
    source = [[0, 0], [1, 7], [0, 3]]
    adjusted, merged = _ajustar_grid(source, 3, 2, 0, -1)

    assert adjusted == [[1, 7, 0], [0, 3, 0]]
    assert merged == 0


@pytest.mark.parametrize("nominal", [15, 11])
@pytest.mark.parametrize("advance", [2, 3, 5, 7, 8, 11, 14, 16])
def test_runtime_center_plus_left_restores_official_bearing(nominal, advance):
    for bearing in (-1, 0, 1):
        result = margen_compensado(bearing, nominal, advance)
        assert int((nominal-advance)/2) + result == bearing


def test_negative_center_truncates_toward_zero():
    assert margen_compensado(0, 11, 14) == 1


@pytest.mark.parametrize("dx,dy", [(0, -1), (-1, 0), (2, 0), (0, 2)])
def test_baseline_adjustment_rejects_nonzero_clipping(dx, dy):
    with pytest.raises(ValueError, match="tinta fuera"):
        _ajustar_grid([[7]], 2, 2, dx, dy)


def _font_fixture(tmp_path, cw, ch, sw, sh, cols, rows):
    data = bytearray(0x100 + sw * sh // 2)
    data[:4] = b"CFNT"
    struct.pack_into("<HHIII", data, 4, 0xFEFF, 20, 0x03000000, len(data), 3)
    data[20:24] = b"FINF"
    struct.pack_into("<I", data, 24, 32)
    struct.pack_into("<III", data, 36, 60, 92, 0)
    data[49] = cw
    data[52:56] = b"TGLP"
    struct.pack_into("<I4BI6HI", data, 56, 32, cw, ch, ch-2, cw,
                     sw*sh//2, 1, 11, cols, rows, sw, sh, 0x100)
    data[84:88] = b"CWDH"
    struct.pack_into("<IHHI", data, 88, 19, 0, 0, 0)
    struct.pack_into("<bBB", data, 100, 0, cw, cw)
    path = tmp_path / "sample.bcfnt"
    path.write_bytes(data)
    return FuenteBCFNT(path)


@pytest.mark.parametrize("geometry,gi,xy", [
    ((10, 12, 256, 32, 23, 2), 23, (1, 14)),
    ((14, 17, 32, 128, 2, 7), 1, (16, 1)),
])
def test_bcfnt_uses_cell_pitch_and_one_pixel_origin(tmp_path, geometry, gi, xy):
    font = _font_fixture(tmp_path, *geometry)
    x, y = xy
    # Address from independent texture coordinates, not the writer being tested.
    morton = sum(((x >> k) & 1) << (2*k) |
                 ((y >> k) & 1) << (2*k+1) for k in range(3))
    address = 0x100 + ((y//8)*(geometry[2]//8)+x//8)*32 + morton//2
    shift = (morton % 2)*4
    font.data[address] = 9 << shift
    assert font.read_cell(gi)[0][0] == 9
    assert sum(map(sum, font.read_cell(gi))) == 9
    grid = [[0]*geometry[0] for _ in range(geometry[1])]
    grid[0][0] = 5
    font.write_cell(gi, grid)
    assert font.data[address] == 5 << shift
    assert sum(font.data[0x100:]) == 5 << shift
