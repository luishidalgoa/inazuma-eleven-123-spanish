"""Pares de letras por casilla (nucleo.fuentes.pares_celda) y nombres cortos del IE3 (#87), con datos sintéticos."""
from __future__ import annotations

import pytest

from ie123kit.ie3.comun import nombres_cortos_pares as N
from ie123kit.nucleo.fuentes import pares_celda as P


def _c(s: bytes) -> tuple[bytes, ...]:
    return P.casillas(s)


def test_casillas_cuenta_doble_byte_como_una():
    assert _c(b"Mart\x83\xa1nez") == (b"M", b"a", b"r", b"t", b"\x83\xa1", b"n", b"e", b"z")
    assert len(_c(b"Sparrow")) == 7


def test_maximo_juntable_no_toca_la_primera_casilla():
    t = _c(b"Sparrow")
    assert P.maximo_juntable(t, {(b"S", b"p")}) == 0
    assert P.maximo_juntable(t, {(b"r", b"r"), (b"a", b"r")}) == 1   # ar y rr se solapan
    assert P.maximo_juntable(t, {(b"p", b"a"), (b"r", b"r"), (b"o", b"w")}) == 3


def test_elegir_pares_reutiliza_y_cubre():
    textos = [_c(b"Sparrow"), _c(b"Barrows"), _c(b"Downtown"), _c(b"Ken")]
    pares = P.elegir_pares(textos, 6)
    conj = set(pares)
    for t in textos:
        assert P.maximo_juntable(t, conj) >= len(t) - 6
    assert pares == [(b"o", b"w")]       # un solo par sirve a los tres (Downtown lo usa dos veces)


def test_elegir_pares_imposible():
    with pytest.raises(ValueError):
        P.elegir_pares([_c(b"ABCDEFGHIJKLMNO")], 6, admitido=lambda p: p == (b"B", b"C"))


def test_particion_minima_y_codificacion_ida_y_vuelta():
    pares = [(b"r", b"r"), (b"o", b"w"), (b"n", b"t")]
    codigos = {p: bytes((0x98, 0xA0 + i)) for i, p in enumerate(pares)}
    for texto in (b"Sparrow", b"Downtown", b"Ken"):
        partes = P.particion(_c(texto), pares, 6)
        assert len(partes) <= 6
        assert partes[0] == _c(texto)[0]
        dato = P.codificar(partes, codigos)
        assert P.decodificar(dato, codigos) == texto
    assert len(P.particion(_c(b"Sparrow"), pares, 6)) == 6       # solo lo necesario


def test_particion_prefiere_el_par_barato():
    pares = [(b"a", b"r"), (b"r", b"r")]
    partes = P.particion(_c(b"Sparrow"), pares, 6, coste=lambda p: 1.0 if p == (b"a", b"r") else 0.0)
    assert (b"r", b"r") in partes


def _letra(ancho: int, alto: int = 4, v: int = 15) -> list[list[int]]:
    return [[v] * ancho + [0] * (8 - ancho) for _ in range(alto)]


def test_componer_sin_estrechar_y_estrechando():
    d = P.componer(_letra(3), _letra(2), ancho_max=9)
    assert (d.ancho, d.estrechado) == (6, False)
    assert all((3, y) not in d.px for y in range(4))           # 1 px de separación
    d = P.componer(_letra(6), _letra(6), ancho_max=9)
    assert d.estrechado and d.ancho <= 9
    assert max(x for x, _ in d.px) < 9


def test_componer_con_espacio():
    vacio = [[0] * 8 for _ in range(4)]
    d = P.componer(_letra(3), vacio, ancho_max=9)
    assert d.ancho == 3 and not d.estrechado


def test_componer_la4_conserva_luminancia():
    a = [[0xFF] * 3 + [0] * 5 for _ in range(4)]
    b = [[0x0F] * 2 + [0] * 6 for _ in range(4)]
    d = P.componer_la4(a, b, ancho_max=14, sep=1)
    assert d.ancho == 6
    assert d.px[(0, 0)] == 0xFF and d.px[(4, 0)] == 0x0F


def test_metricas_centradas():
    left, width, adv = P.metricas_centradas(9, 11)
    assert (width, adv) == (9, 10)
    assert int((11 - adv) / 2) + left == (11 - 9) // 2


def _unitbase(nombres: list[bytes], marca: int = 0x2A) -> bytes:
    out = bytearray()
    for n in nombres:
        r = bytearray(range(N.TAMANO))
        r[N.CORTO:N.CORTO + 15] = n.ljust(15, b"\0")
        r[N.CORTO + 15] = marca
        out += r
    return bytes(out)


def test_plan_ie3_reescribe_y_conserva_marca():
    nombres = [b"Sparrow", b"Downtown", b"Bluebel.", b"Mart\x83\xa1nez", b"Evans"]
    ub = _unitbase(nombres)
    cortos = N.leer_cortos(ub)
    assert cortos == nombres
    pl = N.plan(cortos)
    codigos = {p: bytes((0xE0, 0x40 + i)) for i, p in enumerate(pl.pares)}
    nuevos = {i: pl.codificar(t, codigos) for i, t in enumerate(cortos)}
    ub2 = N.reescribir(ub, {i: b for i, b in nuevos.items() if b != cortos[i]})
    assert N.comprobar(cortos, N.leer_cortos(ub2), codigos) == []
    for i in range(len(nombres)):
        a, b = ub[i * N.TAMANO:(i + 1) * N.TAMANO], ub2[i * N.TAMANO:(i + 1) * N.TAMANO]
        assert a[:N.CORTO] == b[:N.CORTO] and a[N.CORTO + 15:] == b[N.CORTO + 15:]
    assert N.leer_cortos(ub2)[4] == b"Evans"


def test_comprobar_detecta_errores():
    codigos = {(b"r", b"r"): b"\xe0\x40"}
    assert N.comprobar([b"Sparrow"], [b"Sparrow"], codigos)          # 7 casillas
    assert N.comprobar([b"Sparrow"], [b"Spa\xe0\x40ox"], codigos)    # no vuelve igual
    assert N.comprobar([b"Sparrow"], [b"Spa\xe0\x40ow"], codigos) == []


def test_reescribir_rechaza_texto_largo():
    with pytest.raises(ValueError):
        N.reescribir(_unitbase([b"A"]), {0: b"x" * 16})


def test_en_literal_solo_cuenta_cadenas_de_texto_alineadas():
    from ie123kit.nucleo.fuentes.liberar import en_literal

    k = "漢".encode("cp932")
    assert en_literal(b"\0" + "あ漢".encode("cp932") + b"\0", k) == 1
    assert en_literal(b"\x01\x02" + k + b"\xff\xfe", k) == 0                 # binario: no decodifica
    assert en_literal(b"\0" + b"\x81" + k + b"\0", k) == 0                  # desalineado
