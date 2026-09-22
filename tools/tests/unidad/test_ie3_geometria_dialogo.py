import struct
from types import SimpleNamespace

import pytest

from ie123kit.ie3.comun.geometria_dialogo import Medidor, parchear_origen
from ie123kit.ie3.comun.maqueta import lineas_de


class Font:
    def __init__(self):
        self.cmap = {ord(c): i for i, c in enumerate("aiW ")}
        self.cmap[0x3000] = 4
        self.data = b"".join(struct.pack("<bBB", *x) for x in
                             ((-3, 7, 8), (-6, 2, 3), (0, 13, 14), (-6, 0, 3), (7, 0, 7)))
        self.b = SimpleNamespace(width=15)

    def cwdh_entry_off(self, gi):
        return gi * 3

    def read_cell(self, gi):
        return [[15] * self.data[gi * 3 + 1]]


def test_space_runtime_and_centering_only_once():
    f = Font()
    before = bytes(f.data)
    m = Medidor(f)
    r = m.medir("a a")
    assert r["avance"] == 23
    assert (r["izquierda"], r["derecha"]) == (8, 29)
    assert r["espacios"] == [{"x": 16, "avance": 7, "codepoint_runtime": "U+3000"}]
    assert f.data == before


def test_existing_algorithm_accepts_geometry_without_changing_defaults():
    assert lineas_de("a a a", max_tinta=3, medir=len) == ["a a", "a"]
    assert lineas_de("a a a") == ["a a a"]


def test_reflow_no_truncation_or_new_page():
    m = Medidor(Font())
    text = " ".join(["WWWWWW"] * 6)
    r = m.maquetar(text)
    assert r is not None
    assert r.replace("\\n", " ") == text
    assert len(r.split("\\n")) == 2
    assert all(m.exceso(s) <= 0 for s in r.split("\\n"))
    assert m.maquetar(" ".join(["WWWWWW"] * 20)) is None
    assert m.maquetar("a  a") is None
    assert m.maquetar("a\\fa") is None
    assert m.maquetar("a %s") is None


def test_reject_unmodelled_character_and_wrong_cro():
    with pytest.raises(ValueError, match="no modelado"):
        Medidor(Font()).medir("ñ")
    with pytest.raises(ValueError, match="ancla"):
        parchear_origen(bytes(0x3ABCC))
