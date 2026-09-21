from ie123kit.ie3.comun.charset import CHARSET, comprobar_codificacion
from ie123kit.nucleo.config.congelados import cargar


def test_charset_portador_is_stable():
    rows = comprobar_codificacion()
    assert "".join(ch for ch, _encoded, _carrier in rows) == CHARSET
    plan = {ch: cp for ch, _base, _accent, cp in cargar("font_patch").PLAN}
    carriers = {ch: carrier for ch, _encoded, carrier in rows}
    assert all(carriers[ch] == cp for ch, cp in plan.items())
    encoded = {ch: raw for ch, raw, _carrier in rows}
    assert encoded["È"] == chr(0x03A0).encode("shift-jis")
