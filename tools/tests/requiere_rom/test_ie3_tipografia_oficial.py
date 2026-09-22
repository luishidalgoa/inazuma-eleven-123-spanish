"""Raster oficial comprobado con direcciones independientes del escritor."""
import struct

import pytest

from ie123kit.ie3.comun.nombres import caracteres_cortos
from ie123kit.ie3.comun.text import TextTable
from ie123kit.ie3.comun.tipografia import (
    FuenteBCFNT, _PORTADORES, _codepoint_destino, _codepoint_origen,
    adaptar_font12, adaptar_font8_nombres,
)
from ie123kit.nucleo.config.raiz import find_root
from ie123kit.nucleo.contenedores.fa import FaArchive

pytestmark = pytest.mark.requiere_rom


def _address(t, gi, x, y):
    sheet, cell = divmod(gi, t["ncols"]*t["nrows"])
    row, col = divmod(cell, t["ncols"])
    xx = col*(t["cell_w"]+1)+1+x
    yy = row*(t["cell_h"]+1)+1+y
    tile = (yy//8)*(t["sheet_w"]//8)+xx//8
    morton = sum(((xx >> i) & 1) << (2*i) |
                 ((yy >> i) & 1) << (2*i+1) for i in range(3))
    return t["sheet_data"]+sheet*t["sheet_size"]+tile*32+morton//2, (morton%2)*4


@pytest.mark.parametrize("name", ["FONT12", "FONT8"])
def test_official_raster_bearings_and_untargeted_bytes(tmp_path, name):
    root = find_root()
    official_path = root / "work/ie3/rayo_celeste/fuentes/3ds_eu/romfs/archive_sz.fa"
    base_path = root / f"work/shared/fa_extract/font/{name}.bcfnt"
    if not official_path.is_file() or not base_path.is_file():
        pytest.skip("requiere originales locales JP/ES")
    official = FaArchive(str(official_path))
    table = TextTable.from_codetable(official.read("font/CodeTable.bin"))
    source = official.read(f"font/{name}.bcfnt")
    original = base_path.read_bytes()
    if name == "FONT12":
        visible = set(map(chr, range(32,127))) | set(_PORTADORES)
        output, report = adaptar_font12(original, source, table)
    else:
        base = FaArchive(str(root/"work/shared/base_3ds/romfs/archive.fa"))
        unit = "inazuma3/data_iz/logic/unitbase.dat"
        chars = caracteres_cortos(base.read(unit), official.read("es/"+unit), table)
        del base
        visible = (chars | set(_PORTADORES)) - {" "}
        output, report = adaptar_font8_nombres(original, source, table, chars)
    del official
    assert report["fusiones_borde"] == 0
    assert len(output) == len(original)
    src_path, out_path = tmp_path/"eu.bcfnt", tmp_path/"out.bcfnt"
    src_path.write_bytes(source)
    out_path.write_bytes(output)
    src, dst = FuenteBCFNT(src_path), FuenteBCFNT(out_path)
    original_font = FuenteBCFNT(base_path)
    assert dst.cmap == original_font.cmap
    assert dst.t == original_font.t
    reverse = {real:slot for slot,real in table.mapping.items()}
    allowed = bytearray(len(output))
    changed_glyphs = set()
    for ch in visible:
        sg = src.cmap[_codepoint_origen(ch, reverse)]
        dg = dst.cmap[_codepoint_destino(ch)]
        changed_glyphs.add(dg)
        so, do = src.cwdh_entry_off(sg), dst.cwdh_entry_off(dg)
        sl, sw, sc = struct.unpack_from("<bBB", source, so)
        dl, dw, dc = struct.unpack_from("<bBB", output, do)
        assert dc == sc + int(name == "FONT12" and (ch.isalpha() or ch in "¡¿"))
        assert dw == sw
        assert dl + int((dst.b.width-dc)/2) == sl
        allowed[do:do+3] = b"\xff"*3
        dy = dst.t["baseline"]-src.t["baseline"]
        for y in range(dst.t["cell_h"]):
            for x in range(dst.t["cell_w"]):
                off, shift = _address(dst.t, dg, x, y)
                allowed[off] |= 15 << shift
                expected = 0
                if x < src.t["cell_w"] and 0 <= y-dy < src.t["cell_h"]:
                    ao, ash = _address(src.t, sg, x, y-dy)
                    expected = (source[ao] >> ash) & 15
                assert (output[off] >> shift) & 15 == expected, (ch,x,y)
    # Includes header, CMAP, all Japanese glyphs and every inter-cell margin.
    assert all(((a^b)&(~mask & 255)) == 0
               for a,b,mask in zip(original,output,allowed))
    assert not any(gi in changed_glyphs for cp,gi in dst.cmap.items()
                   if 0x3040 <= cp <= 0x30FF or 0x4E00 <= cp <= 0x9FFF)
