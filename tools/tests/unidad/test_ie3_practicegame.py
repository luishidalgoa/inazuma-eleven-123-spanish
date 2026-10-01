"""ie123kit.ie3.comun.practicegame con registros sintéticos (sin datos de la ROM)."""
import pytest

from ie123kit.ie3.comun import practicegame as pg


def _reg(paso, cab, nombre, dato, segundo, cola, campos):
    r = bytearray(paso)
    r[0:12] = cab
    (a, b), (c, d) = campos
    r[a:a + len(nombre)] = nombre
    r[b:b + 2] = dato
    r[c:c + len(segundo)] = segundo
    r[d:d + 14] = cola
    return bytes(r)


def _jp(nombre, segundo, cab=bytes(range(12)), dato=b"\x01\x00", cola=bytes(range(14))):
    return _reg(74, cab, nombre, dato, segundo, cola, ((12, 36), (38, 60)))


def _eu(nombre, segundo, cab=bytes(range(12)), dato=b"\x01\x00", cola=bytes(range(14))):
    return _reg(94, cab, nombre, dato, segundo, cola, ((12, 46), (48, 80)))


def _cod(t, lim):
    b = t.encode("latin1")
    return (b, "1_byte") if len(b) <= lim else (None, "no_cabe")


def _dec(b):
    return b.decode("latin1")


def test_traduce_campos_y_conserva_datos():
    jp = _jp("女子".encode("cp932"), b"0") + _jp("なし".encode("cp932"), "五郎".encode("cp932"))
    eu = _eu(b"Estrellas", b"0") + _eu("なし".encode("cp932"), b"Paul Peabody")
    r = pg.traducir(jp, eu, _dec, _cod)
    assert r.traducidos == 2
    assert r.datos[12:22] == b"Estrellas\0" and r.datos[74 + 38:74 + 51] == b"Paul Peabody\0"
    assert r.datos[74 + 12:74 + 16] == "なし".encode("cp932")        # igual en EU: no se toca
    assert pg.solo_texto_cambiado(jp, r.datos)
    assert pg.traducir(r.datos, eu, _dec, _cod).datos == r.datos   # idempotente


def test_no_cabe_queda_japones_sin_recortar():
    jp = _jp("長い".encode("cp932"), b"0")
    eu = _eu(b"x" * 22, b"0")
    r = pg.traducir(jp, eu, _dec, _cod, medir=len)
    assert r.datos == jp and r.traducidos == 0
    assert r.conservados == [(0, "nombre", "no_cabe", "x" * 22, 22, 21)]
    ok = pg.traducir(jp, _eu(b"x" * 21, b"0"), _dec, _cod)
    assert ok.datos[12:34] == b"x" * 21 + b"\0"


def test_datos_distintos_no_se_empareja():
    jp = _jp("女子".encode("cp932"), b"0")
    eu = _eu(b"Estrellas", b"0", cola=bytes(14))
    r = pg.traducir(jp, eu, _dec, _cod)
    assert r.datos == jp and r.conservados[0][2] == "datos_distintos"


def test_numero_de_registros_distinto():
    with pytest.raises(ValueError):
        pg.traducir(_jp(b"a", b"0") * 2, _eu(b"a", b"0"), _dec, _cod)


def test_solo_texto_cambiado_detecta_datos():
    jp = _jp(b"a", b"0")
    assert not pg.solo_texto_cambiado(jp, jp[:60] + b"\xff" + jp[61:])
