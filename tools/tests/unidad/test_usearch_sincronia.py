"""IE1/IE2: usearch.dat derivado del nombre actual de unitbase.dat (latín en +0x10; datos sintéticos, sin ROM)."""
import struct

import pytest

from ie123kit.nucleo.registros import usearch as U
from ie123kit.nucleo.texto.ancho_completo import encode_fullwidth

#: dos bigramas de FONT12 de mentira: el código SJIS 0x9ABA vale «ck» y 0xE943 vale «nd»
REGISTRO = {"bigramas": [{"sjis": "9ABA", "par": "ck"}, {"sjis": "E943", "par": "nd"}]}


@pytest.fixture(scope="module")
def dec():
    return U.Decodificador([REGISTRO])


def _ub(ident: int, corto: bytes, principal: bytes | None = None) -> bytes:
    r = bytearray(U.R_UNITBASE)
    r[0x00:0x10] = (principal if principal is not None else corto).ljust(16, b"\0")
    r[0x10:0x20] = corto.ljust(16, b"\0")
    struct.pack_into("<H", r, 0x42, ident)
    return bytes(r)


def _us(ident: int, nombre_jp: str = "あいう", *, nivel: int = 0x3C, valido: int = 1, flags: int = 3) -> bytes:
    r = bytearray(U.R_USEARCH)
    r[0x00:0x10] = nombre_jp.encode("cp932").ljust(16, b"\0")
    r[0x10:0x20] = nombre_jp.encode("cp932").ljust(16, b"\0")  # lectura kana
    struct.pack_into("<H", r, 0x24, ident)
    r[0x26], r[0x2A], r[0x2B] = nivel, valido, flags
    r[0x2C:0x30] = struct.pack("<I", 0xAABBCCDD)
    return bytes(r)


def _lleno(*registros: bytes, total: int = 6, relleno) -> bytes:
    lista = list(registros) + [relleno] * (total - len(registros))
    return b"".join(lista)


def _par(esquema="ie1", scout=None):
    return U.ESQUEMAS[esquema]


def _montar(nombres: dict[int, bytes], *, us_extra=()):
    """unitbase con un registro por id (el registro 0 vacío) y usearch con un registro por id."""
    ub = _lleno(_ub(0, b"\x81\x40"), *[_ub(i, n) for i, n in nombres.items()], total=len(nombres) + 3,
                relleno=_ub(0, b"\x81\x40"))
    us = _lleno(*[_us(i) for i in nombres], *us_extra, total=len(nombres) + 3, relleno=_us(0, "ダミー", flags=1))
    return us, ub


def test_escribe_bytes_exactos_del_teclado_en_0x10_y_no_toca_nada_mas(dec):
    us, ub = _montar({7: b"Arcade"})
    nuevo, inf = U.sincronizar(_par(), us, ub, dec)
    r = nuevo[0:48]
    assert r[0x10:0x20] == bytes.fromhex("826082928283828182848285") + bytes(4)  # A r c a d e
    assert r[:0x10] == us[:0x10]  # +0x00 sigue en kana (lo lee el clasificador de la lista «Por nombre»)
    assert r[0x20:] == us[0x20:48] and r[0x2B] == us[0x2B] == 3  # flags (bit 0 incluido), id y filtros intactos
    assert inf.escritos == inf.cambiados == 1


def test_expande_bigramas_y_espacios_de_ancho_completo(dec):
    nombre = b"Ma" + bytes.fromhex("9ABA") + b"\x81\x40" + b"J"  # «Mack J»: bigrama + espacio de 2 B + ASCII
    us, ub = _montar({3: nombre})
    nuevo, _ = U.sincronizar(_par(), us, ub, dec)
    assert nuevo[0x10:0x20] == encode_fullwidth("Mack J").ljust(16, b"\0")


def test_acentos_son_portadores_y_enie_es_83a5(dec):
    nombre = encode_fullwidth("Íñigo")
    us, ub = _montar({3: nombre})
    nuevo, _ = U.sincronizar(_par(), us, ub, dec)
    assert nuevo[0x10:0x20] == encode_fullwidth("Íñigo").ljust(16, b"\0")
    assert b"\x83\xa5" in nuevo[0x10:0x20]  # ñ = portador 0x83A5


def test_trunca_a_8_letras_sin_nul(dec):
    us, ub = _montar({3: b"Tomlinson"})
    nuevo, inf = U.sincronizar(_par(), us, ub, dec)
    assert nuevo[0x10:0x20] == encode_fullwidth("Tomlinso") and len(nuevo[0x10:0x20].rstrip(b"\0")) == 16
    assert inf.truncados == 1
    # tecleando 8 letras se encuentra; con las 9 (no se puede teclear) no
    assert U.simular_busqueda(nuevo, encode_fullwidth("Tomlinso")) == [0]
    assert U.simular_busqueda(nuevo, encode_fullwidth("Tomlinson")) == []


def test_descarta_lo_que_el_teclado_no_escribe_y_los_espacios_finales(dec):
    us, ub = _montar({3: b"O'Gaines  "})
    nuevo, inf = U.sincronizar(_par(), us, ub, dec)
    assert nuevo[0x10:0x20] == encode_fullwidth("OGaines").ljust(16, b"\0")
    assert inf.descartados == {"'": 1}


def test_solo_toca_lo_que_el_comparador_puede_devolver(dec):
    nombres = {1: b"Alfa", 2: b"Beta", 3: b"Gama", 4: b"Delta", 5: b"Eta"}
    us = _lleno(_us(1), _us(2, nivel=0xC9), _us(3, nivel=0xFF), _us(4, valido=2), _us(5, nivel=0xD7), total=8,
                relleno=_us(0, "ダミー", flags=1))
    ub = _lleno(*[_ub(i, n) for i, n in nombres.items()], total=8, relleno=_ub(0, b"\x81\x40"))
    nuevo, inf = U.sincronizar(_par(), us, ub, dec)
    assert nuevo[0:48] != us[0:48]
    assert nuevo[48:48 * 5] == us[48:48 * 5]  # C9, FF, +0x2a != 1 y D7 sin tocar
    assert nuevo[48 * 5:] == us[48 * 5:]  # relleno con id 0 sin tocar
    assert inf.no_buscables == 4
    # con alcance «todos» entran C9, FF y +0x2a != 1, pero nunca los de código secreto (0xD7)
    todos, _ = U.sincronizar(_par(), us, ub, dec, alcance="todos")
    assert todos[48:48 * 4] != us[48:48 * 4]
    assert todos[48 * 4:48 * 5] == us[48 * 4:48 * 5]
    with pytest.raises(ValueError):
        U.sincronizar(_par(), us, ub, dec, alcance="otro")


def test_no_toca_lo_que_aun_esta_en_kana(dec):
    us, ub = _montar({1: "あいう".encode("cp932"), 2: b"Beta"})
    nuevo, inf = U.sincronizar(_par(), us, ub, dec)
    assert nuevo[:48] == us[:48] and inf.sin_traduccion == 1


def test_usa_el_principal_si_el_corto_sigue_en_japones(dec):
    ub = _lleno(_ub(1, "あ".encode("cp932"), principal=b"Beta"), total=3, relleno=_ub(0, b"\x81\x40"))
    us = _lleno(_us(1), total=3, relleno=_us(0, "ダミー", flags=1))
    nuevo, _ = U.sincronizar(_par(), us, ub, dec)
    assert nuevo[0x10:0x20] == encode_fullwidth("Beta").ljust(16, b"\0")


def test_idempotente_y_sin_efectos_en_el_resto(dec):
    us, ub = _montar({1: b"Alfa", 2: b"Beta"})
    uno, _ = U.sincronizar(_par(), us, ub, dec)
    dos, inf = U.sincronizar(_par(), uno, ub, dec)
    assert uno == dos and inf.cambiados == 0
    assert len(uno) == len(us)


def test_un_id_sin_unitbase_se_cuenta_y_no_se_toca(dec):
    us = _lleno(_us(9), total=3, relleno=_us(0, "ダミー", flags=1))
    ub = _lleno(_ub(1, b"Alfa"), total=3, relleno=_ub(0, b"\x81\x40"))
    nuevo, inf = U.sincronizar(_par(), us, ub, dec)
    assert nuevo == us and inf.sin_unitbase == 1


def test_tamanos_incorrectos_fallan(dec):
    with pytest.raises(ValueError):
        U.sincronizar(_par(), b"\0" * 47, b"\0" * 96, dec)
    h = U.verificar(_par(), b"\0" * 47, b"\0" * 96, dec)
    assert h[0].codigo == "USEARCH_TAMANO"


# ------------------------------------------------------------------ la validación avisa de la desincronía


def _codigos(h, gravedad="error"):
    return sorted({x.codigo for x in h if x.gravedad == gravedad})


def test_verificar_detecta_un_unitbase_renombrado_sin_regenerar(dec):
    us, ub = _montar({1: b"Alfa", 2: b"Beta"})
    sincronizado, _ = U.sincronizar(_par(), us, ub, dec)
    assert _codigos(U.verificar(_par(), sincronizado, ub, dec)) == []
    # una capa actualiza el nombre en unitbase y nadie toca usearch
    ub_nuevo = ub[:96 * 2] + _ub(2, b"Betty") + ub[96 * 3:]
    h = U.verificar(_par(), sincronizado, ub_nuevo, dec)
    assert _codigos(h) == ["USEARCH_DESINCRONIZADO"]
    assert [x.ident for x in h if x.gravedad == "error"] == [2]
    # volver a sincronizar lo arregla
    arreglado, _ = U.sincronizar(_par(), sincronizado, ub_nuevo, dec)
    assert _codigos(U.verificar(_par(), arreglado, ub_nuevo, dec)) == []


def test_verificar_ve_el_usearch_japones_y_no_exige_tocar_los_flags(dec):
    us, ub = _montar({1: b"Alfa"})
    assert _codigos(U.verificar(_par(), us, ub, dec)) == ["USEARCH_DESINCRONIZADO"]
    sinc, _ = U.sincronizar(_par(), us, ub, dec)
    assert sinc[0x2B] == us[0x2B] == 3  # el bit 0 se queda como estaba: el comparador mira +0x10 antes y sin él
    assert _codigos(U.verificar(_par(), sinc, ub, dec)) == []


def test_latin_en_0x00_rompe_la_lista_por_nombre_y_es_un_error(dec):
    """Regresión de la ronda 1: con latín en +0x00 el clasificador de filas kana deja el registro fuera."""
    us, ub = _montar({1: b"Alfa", 2: b"Beta"})
    sinc, _ = U.sincronizar(_par(), us, ub, dec)
    assert U.lista_por_nombre(sinc) == U.lista_por_nombre(us) == [0, 1]  # las mismas filas que el japonés
    mal = encode_fullwidth("Alfa").ljust(16, b"\0") + sinc[16:]
    assert U.lista_por_nombre(mal) == [1]
    h = U.verificar(_par(), mal, ub, dec)
    assert "USEARCH_NOMBRE_NO_KANA" in _codigos(h)
    # un registro fuera de la lista (sin bit 1 de +0x2b) no cuenta
    sin_lista = bytearray(mal)
    sin_lista[0x2B] &= ~2
    assert "USEARCH_NOMBRE_NO_KANA" not in _codigos(U.verificar(_par(), bytes(sin_lista), ub, dec))


def test_es_kana_inicial_replica_el_clasificador():
    assert U.es_kana_inicial("あ".encode("cp932")) and U.es_kana_inicial("ン".encode("cp932"))
    assert not U.es_kana_inicial(encode_fullwidth("A")) and not U.es_kana_inicial(b"\x83\x9f")
    assert not U.es_kana_inicial(b"\x81\x40") and not U.es_kana_inicial(b"\0\0")


def test_verificar_avisa_de_huerfanos_y_codigos(dec):
    us = _lleno(_us(9), total=3, relleno=_us(0, "ダミー", flags=1))
    ub = _lleno(_ub(1, b"Alfa"), total=3, relleno=_ub(0, b"\x81\x40"))
    assert _codigos(U.verificar(_par(), us, ub, dec)) == ["USEARCH_ID_HUERFANO"]
    # código de 2 B sin entrada en los bigramas ni valor SJIS
    us, ub = _montar({1: b"Al\xfd\xfe"})
    assert "UNITBASE_CODIGO_SIN_BIGRAMA" in _codigos(U.verificar(_par(), us, ub, dec))


def test_un_nombre_que_vuelve_a_kana_es_error_si_el_registro_es_alcanzable(dec):
    us, ub = _montar({1: b"Alfa"})
    sinc, _ = U.sincronizar(_par(), us, ub, dec)
    kana = _lleno(_ub(1, "あいう".encode("cp932")), total=4, relleno=_ub(0, b"\x81\x40"))
    h = U.verificar(_par(), sinc, kana, dec)
    assert _codigos(h) == ["USEARCH_NOMBRE_VUELTO_A_KANA"] and _codigos(h, "aviso") == []
    assert "conserva el latín anterior" in next(x.mensaje for x in h)
    # el usearch japonés intacto con un unitbase en kana: simplemente sin traducir (nada obsoleto: aviso)
    assert _codigos(U.verificar(_par(), us, kana, dec)) == []
    assert _codigos(U.verificar(_par(), us, kana, dec), "aviso") == ["USEARCH_SIN_TRADUCCION"]
    # el hook no puede arreglarlo (no hay kana que restaurar): sigue siendo error tras sincronizar
    de_nuevo, inf = U.sincronizar(_par(), sinc, kana, dec)
    assert de_nuevo == sinc and inf.sin_traduccion == 1
    assert _codigos(U.verificar(_par(), de_nuevo, kana, dec)) == ["USEARCH_NOMBRE_VUELTO_A_KANA"]


def test_un_nombre_vuelto_a_kana_no_alcanzable_no_es_error(dec):
    us, ub = _montar({1: b"Alfa"})
    sinc, _ = U.sincronizar(_par(), us, ub, dec)
    inalcanzable = bytearray(sinc)
    inalcanzable[0x26] = 0xC9  # el comparador nunca lo devuelve
    kana = _lleno(_ub(1, "あいう".encode("cp932")), total=4, relleno=_ub(0, b"\x81\x40"))
    assert _codigos(U.verificar(_par(), bytes(inalcanzable), kana, dec)) == []


def test_excepcion_revisada_de_nombre_vuelto_a_kana_es_aviso(dec, monkeypatch):
    us, ub = _montar({1: b"Alfa"})
    sinc, _ = U.sincronizar(_par(), us, ub, dec)
    kana = _lleno(_ub(1, "あいう".encode("cp932")), total=4, relleno=_ub(0, b"\x81\x40"))
    assert U.EXCEPCIONES_VUELTO_A_KANA == {"ie1": {}, "ie2": {}}  # vacía: hoy no hay ninguna revisada
    monkeypatch.setitem(U.EXCEPCIONES_VUELTO_A_KANA, "ie1", {1: "motivo de prueba"})
    h = U.verificar(_par(), sinc, kana, dec)
    assert _codigos(h) == [] and _codigos(h, "aviso") == ["USEARCH_NOMBRE_VUELTO_A_KANA"]
    assert "motivo de prueba" in h[0].mensaje


def test_unitbase_con_dos_nombres_distintos_se_senala_con_aviso(dec):
    us, ub = _montar({1: b"Alfa"})
    ub = _lleno(_ub(0, b"\x81\x40"), _ub(1, b"Alfa", principal=b"Alfonso"), total=4, relleno=_ub(0, b"\x81\x40"))
    sinc, _ = U.sincronizar(_par(), us, ub, dec)
    assert sinc[0x10:0x20] == encode_fullwidth("Alfa").ljust(16, b"\0")  # manda +0x10 del unitbase
    h = U.verificar(_par(), sinc, ub, dec)
    assert _codigos(h) == [] and "USEARCH_UNITBASE_NOMBRES_DISTINTOS" in _codigos(h, "aviso")
    # mismos nombres en los dos campos: sin aviso
    _, ub_igual = _montar({1: b"Alfa"})
    assert "USEARCH_UNITBASE_NOMBRES_DISTINTOS" not in _codigos(U.verificar(_par(), sinc, ub_igual, dec), "aviso")


def test_verificar_avisa_de_truncados_y_no_tecleables_sin_fallar(dec):
    us, ub = _montar({1: b"O'Gaines", 2: b"Greenfield"})
    sinc, _ = U.sincronizar(_par(), us, ub, dec)
    h = U.verificar(_par(), sinc, ub, dec)
    assert _codigos(h) == []
    assert _codigos(h, "aviso") == ["USEARCH_NO_TECLEABLE", "USEARCH_TRUNCADO"]


def test_scoutspcode_debe_coincidir_con_los_registros_d7(dec):
    esquema = _par("ie2")
    us = _lleno(_us(2461, nivel=0xD7), total=3, relleno=_us(0, "ダミー", flags=1))
    ub = _lleno(_ub(2461, b"Binder"), total=3, relleno=_ub(0, b"\x81\x40"))
    scout = struct.pack("<H", 2461) + bytes(20) + bytes(22)
    assert _codigos(U.verificar(esquema, us, ub, dec, scout)) == []
    scout_mal = struct.pack("<H", 2462) + bytes(20) + bytes(22)
    assert _codigos(U.verificar(esquema, us, ub, dec, scout_mal)) == ["SCOUTSPCODE_IDS"]


# ------------------------------------------------------------------ la réplica del comparador


def test_busqueda_por_prefijo_y_distingue_mayusculas(dec):
    us, ub = _montar({1: b"Arcade", 2: b"Archer", 3: b"Beta"})
    antes = U.simular_busqueda(us, encode_fullwidth("Arc"))
    assert antes == []  # el usearch japonés no encuentra nada
    nuevo, _ = U.sincronizar(_par(), us, ub, dec)
    assert U.simular_busqueda(nuevo, encode_fullwidth("Arc")) == [0, 1]
    assert U.simular_busqueda(nuevo, encode_fullwidth("Arcade")) == [0]
    assert U.simular_busqueda(nuevo, encode_fullwidth("arc")) == []  # distingue mayúsculas
    assert U.simular_busqueda(nuevo, b"") == []


def test_cualquier_prefijo_tecleable_de_cada_nombre_se_encuentra(dec):
    nombres = {1: b"Mark", 2: b"Axel", 3: b"Nathan", 4: b"Jude", 5: b"Alumno 1"}
    us, ub = _montar(nombres)
    nuevo, _ = U.sincronizar(_par(), us, ub, dec)
    for k, (i, n) in enumerate(nombres.items()):
        completo = encode_fullwidth(n.decode())
        for letras in range(1, len(completo) // 2 + 1):
            assert k in U.simular_busqueda(nuevo, completo[:2 * letras]), (n, letras)


def test_decodificador_conflictos_y_no_latino():
    d = U.Decodificador([REGISTRO, {"bigramas": [{"sjis": "9ABA", "par": "xx"}, {"sjis": "9ABB", "par": "zz"}]}])
    assert d.conflictos == [(0x9ABA, "ck", "xx")]
    assert d.decodificar(bytes.fromhex("9ABA9ABB")).texto == "ckzz"
    kana = d.decodificar("あい".encode("cp932"))
    assert kana.no_latino and not kana.traducido
    assert d.decodificar(b"\x82").desconocidos == (0x8200,)
