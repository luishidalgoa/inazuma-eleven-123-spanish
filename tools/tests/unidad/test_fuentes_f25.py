"""Motores de fuentes, menús y banner de la F2.5 (#51) sin ROM: fuentes y contenedores sintéticos."""

from __future__ import annotations

import pytest

from ie123kit.nucleo.fuentes import bigramas, rebanadas, ritmo

# --------------------------------------------------------------------------- fuente falsa


class FuenteFalsa:
    """Fuente mínima: cada letra es un bloque sólido de ``ancho`` columnas y 3 filas."""

    def __init__(self, anchos: dict[str, int], celda: int = 15, alto: int = 4):
        self.anchos = anchos
        self.cmap = {ord(ch): i for i, ch in enumerate(anchos, start=1)}
        self.metrics = {0: (0, 1, 1)}
        self._bm = {0: [[0] * celda for _ in range(alto)]}
        for ch, gi in ((c, self.cmap[ord(c)]) for c in anchos):
            w = anchos[ch]
            self.metrics[gi] = (0, w, w + 1)
            self._bm[gi] = [[15 if x < w and y < 3 else 0 for x in range(celda)] for y in range(alto)]

    def gi(self, cp: int):
        return self.cmap.get(cp)

    def bitmap(self, gi: int):
        return self._bm[gi]


def _cp(ch: str) -> int:
    return ord(ch)


# --------------------------------------------------------------------------- ritmo


def test_coste_hueco_de_la_v89() -> None:
    assert ritmo.coste_hueco(0, False) == ritmo.INF
    assert ritmo.coste_hueco(1, False) == ritmo.coste_hueco(2, False) == 0.0
    assert ritmo.coste_hueco(3, False) == 0.8
    assert ritmo.coste_hueco(7, False) == 6.0 + 2.5 * 2
    assert ritmo.coste_hueco(3, True) == ritmo.INF
    assert ritmo.coste_hueco(5, True) == 0.0
    assert ritmo.coste_hueco(10, True) == pytest.approx(0.15 * 4)


def test_trozo_centrado_y_metricas() -> None:
    mq = ritmo.Maqueta(FuenteFalsa({"a": 3, "b": 3}), _cp)
    m = mq.trozo("ab")
    assert m is not None and m["g"] == 2
    assert m["S1"] - m["S0"] + 1 == 3 + 2 + 3
    assert m["S0"] == (15 - 8) // 2
    left, ancho, adv = ritmo.metricas(m, "ab")
    assert ancho == 8 and adv == m["D"] + 8 + 1
    assert int((15 - adv) / 2) + left == m["D"]
    # con espacio detrás, la tinta empieza en la columna 1 y el avance deja 5 px de aire
    m2 = mq.trozo("ab ")
    assert m2["S0"] == 1 and ritmo.metricas(m2, "ab ")[2] == m2["D"] + m2["ancho"] + 5


def test_particion_prefiere_trozos_admitidos() -> None:
    mq = ritmo.Maqueta(FuenteFalsa({"a": 3, "b": 3, "c": 3}), _cp)
    coste_sin, sin = ritmo.particion("abc", mq, lambda c: False)
    coste_con, con = ritmo.particion("abc", mq, lambda c: c == "ab")
    assert all(len(c) == 1 or ritmo.variante(c) for c in sin)
    assert "ab" in con and coste_con <= coste_sin
    assert "".join(ritmo.texto(c) for c in con) == "abc"


def test_parametros_por_juego() -> None:
    p = ritmo.ParametrosRitmo(celda=16, pal_min=3, fin_trozo=14)
    mq = ritmo.Maqueta(FuenteFalsa({"a": 3, "b": 3}, celda=16), _cp, p)
    assert mq.trozo("ab")["S0"] == (16 - 8) // 2
    assert ritmo.coste_hueco(3, True, p) != ritmo.INF


# --------------------------------------------------------------------------- registro


def _doc(*filas):
    return {"version": "prueba", "bigramas": [dict(f) for f in filas]}


def test_registro_valida_y_solo_crece() -> None:
    reg = bigramas.Registro.desde_documento(_doc({"par": "ab", "sjis": "989F"}, {"par": "cd", "sjis": "98A0"}))
    assert reg.codigos() == {"989F", "98A0"}
    nuevo = bigramas.Registro.desde_documento(reg.documento | {"bigramas": list(reg.documento["bigramas"])})
    nuevo.anadir("ef", "98A1")
    nuevo.comprobar_sucesor(reg)
    with pytest.raises(bigramas.RegistroInvalido):
        nuevo.anadir("gh", "98A1")          # código en uso
    with pytest.raises(bigramas.RegistroInvalido):
        nuevo.anadir("ab", "98A2")          # clave en uso
    reasignado = bigramas.Registro.desde_documento(_doc({"par": "xx", "sjis": "989F"}))
    with pytest.raises(bigramas.RegistroInvalido):
        reasignado.comprobar_sucesor(reg)
    reasignado.comprobar_sucesor(bigramas.Registro.desde_documento(_doc({"par": "ab", "sjis": "989F"})),
                                 liberados=["989f"])


def test_registro_rechaza_codigos_malos() -> None:
    with pytest.raises(bigramas.RegistroInvalido):
        bigramas.Registro.desde_documento(_doc({"par": "ab", "sjis": "989F"}, {"par": "cd", "sjis": "989F"}))
    with pytest.raises(bigramas.RegistroInvalido):
        bigramas.Registro.desde_documento(_doc({"par": "ab", "sjis": "41"}))


def test_variante_conserva_su_clave() -> None:
    reg = bigramas.Registro.desde_documento(_doc({"par": "a", "clave": "a", "sjis": "989F"}))
    assert reg.por_clave()["a"].par == "a"


# --------------------------------------------------------------------------- rebanadas


def test_rebanado_puro_cubre_la_tira() -> None:
    F = FuenteFalsa({"a": 3, "b": 3})
    out, _px = rebanadas.resolver(F, 15, 15, "ab", _cp, [], 4)
    assert out
    costes = {k: v[0] for k, v in out.items()}
    assert min(costes.values()) == 1          # una sola rebanada de <= 15 columnas basta
    piezas = out[min(out, key=lambda k: out[k][0])][1]
    for p in piezas:
        _left, ancho, adv = rebanadas.metricas_rebanada(p, 15)
        assert 1 <= adv <= 15 and ancho == p["b"] - p["a"] + 1


def test_reparto_reutiliza_letras_nativas() -> None:
    F = FuenteFalsa({"a": 3, "b": 3})
    existentes = {"a": [(b"a", F.gi(ord("a")))], "b": [(b"b", F.gi(ord("b")))]}
    R = rebanadas.Reparto(F, 15, 15, _cp, 1, (1, 2), existentes, {5: 0.0})  # tinta nativa de «a» en 5
    frente = R.resolver("ab", 3)
    assert any(c == 0 for (_k, c) in frente)  # sin códigos nuevos: las dos letras nativas


def test_tira_nucleo_y_rebanar() -> None:
    F = FuenteFalsa({"a": 3, "b": 3})
    px = rebanadas.tira_nucleo(F, "ab", _cp, umbral=8, hueco=2, inicio=1)
    xs = sorted({x for x, _ in px})
    assert xs[0] == 1 and xs[-1] == 1 + 3 + 2 + 3 - 1
    trozos = rebanadas.rebanar(px, 5)
    assert sum(len(r) for _, r in trozos) == len(px)


def test_elegir_respeta_el_presupuesto() -> None:
    frentes = {"x": {0: ((1, 5.0), "caro"), 2: ((0, 0.0), "barato")}, "y": {1: ((0, 1.0), "y1")}}
    assert rebanadas.elegir(frentes, 2)[0] == 1
    assert rebanadas.elegir(frentes, 3)[0] == 3


# --------------------------------------------------------------------------- escáner, LZ11, CBMD, SMDH, CGFX


def test_escaner_de_literales() -> None:
    from ie123kit.nucleo.texto import escaneo

    kanji = "漢".encode("cp932")
    buf = b"\0abc" + kanji + b"def\0" + b"\xff" + kanji + b"\0"
    res = escaneo.apariciones({"bin": buf}, [kanji.hex().upper()])
    assert res == {kanji.hex().upper(): {"bin": 1}}      # el segundo va tras un byte no textual
    assert escaneo.valido2(0x88, 0x9F) and not escaneo.valido2(0x88, 0x7F)


def test_lz11_ida_y_vuelta() -> None:
    from ie123kit.nucleo.compresion import lz11

    datos = bytes(range(256)) * 40 + b"x" * 5000
    comprimido = lz11.compress(datos)
    assert comprimido[0] == 0x11 and len(comprimido) < len(datos)
    assert lz11.decompress(comprimido) == datos


def test_cbmd_ida_y_vuelta() -> None:
    from ie123kit.nucleo.contenedores import cbmd

    cwav = b"CWAV" + bytes(60)
    bnr = cbmd.construir(b"\x11" + bytes(37), cwav)
    comun, regional, off = cbmd.leer(bnr)
    assert comun == 0x88 and not any(regional) and off % 0x20 == 0
    lz, cw = cbmd.partes(bnr)
    assert cw == cwav and lz.startswith(b"\x11")


def test_smdh_titulos() -> None:
    from ie123kit.nucleo.ejecutable import smdh

    icono = b"SMDH" + bytes(0x36C0 - 4)
    nuevo = smdh.escribir_titulos(icono, {"short": "Corto", "long": "Largo\nDos", "publisher": "X"})
    for slot in range(16):
        assert smdh.leer_titulos(nuevo, slot) == {"short": "Corto", "long": "Largo\nDos", "publisher": "X"}
    with pytest.raises(ValueError):
        smdh.escribir_titulos(icono, {"short": "x" * 64})


def test_cgfx_rgba4_ida_y_vuelta() -> None:
    from PIL import Image

    from ie123kit.nucleo.graficos import cgfx

    img = Image.new("RGBA", (8, 8))
    for y in range(8):
        for x in range(8):
            img.putpixel((x, y), (x * 34, y * 34, 17 * ((x + y) % 16), 255 if x % 2 else 0))
    raw = cgfx.encode(img, 8, 8, 4)
    assert len(raw) == 8 * 8 * 2
    assert cgfx.encode(cgfx.decode(raw, 8, 8, 4), 8, 8, 4) == raw


# --------------------------------------------------------------------------- informe de códigos liberables


def test_liberar_informa_sin_uso_y_duplicados() -> None:
    from ie123kit.nucleo.fuentes import liberar

    F = FuenteFalsa({"a": 3, "b": 3, "c": 5})
    # Tres códigos: dos con el mismo dibujo (a == b en forma y métricas) y uno sin uso en los textos.
    kanjis = {"989F": "a", "98A0": "b", "98A1": "c"}
    for sjis, letra in kanjis.items():
        F.cmap[ord(bytes.fromhex(sjis).decode("cp932"))] = F.cmap[ord(letra)]
    doc = {"version": "prueba", "libres_x": ["98A2"],
           "bigramas": [{"sjis": s, "par": p, "fuentes": {"font/FONT12.bcfnt": {}}} for s, p in kanjis.items()]}
    textos = {"eve": bytes.fromhex("989F98A0"), "str": b"\0\0"}
    res = liberar.informe(doc, textos, {"font/FONT12.bcfnt": F})
    assert res["solo_informe"] is True
    assert [f["sjis"] for f in res["sin_uso"]] == ["98A1"]
    assert [[f["sjis"] for f in g] for g in res["duplicados"]] == [["989F", "98A0"]]
    assert res["recuperables"] == ["98A0", "98A1"]
    assert res["libres_anotados"] == ["98A2"]
