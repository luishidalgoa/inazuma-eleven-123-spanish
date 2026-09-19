"""Tests sin ROM de los motores portados en la F2.4 (#50): paginado, SPF_, teclado, DSP-ADPCM,
Procyon/sound.pb, subtítulos incrustados y parches de CRO. Datos sintéticos; la equivalencia con las
capas de work/ está en tests/requiere_rom/test_equivalencia_motores_ie2.py."""

from __future__ import annotations

import itertools
import math
import struct

import numpy as np
import pytest

from ie123kit.nucleo.errores import ValidacionError

# ------------------------------------------------------------------ paginado


def test_modelos_por_juego_dan_los_limites_medidos():
    from ie123kit.ie1.texto.dialogo import MODELO_IE1
    from ie123kit.ie2.comun.dialogo import MODELO_IE2, MODELO_IE2_ORIGINAL

    assert MODELO_IE1.max_car == 22 and MODELO_IE1.pagina_max is None
    assert MODELO_IE2.max_car == 37 and MODELO_IE2.pagina_max == 131 and MODELO_IE2.registro_max == 247
    assert MODELO_IE2_ORIGINAL.max_car == 22


def test_ajuste_del_motor_corta_por_caracter_y_pasa_a_pagina():
    from ie123kit.nucleo.texto import paginado as P

    modelo = P.ModeloMotor(ancho_ventana=0xF0)
    linea = "Ａ".encode("cp932") * 23
    assert P.ajuste(linea, modelo) == "Ａ".encode("cp932") * 22 + b"\n" + "Ａ".encode("cp932")
    assert P.reajusta(linea, modelo)
    tres = b"\\n".join(["Ａ".encode("cp932")] * 4)
    assert P.ajuste(tres, modelo).count(b"\x0c") == 1
    assert not P.reajusta(tres, modelo)            # convertir el \n de la 3.ª línea no cuenta


def test_simular_reserva_el_ancho_de_pct_y_quita_furigana():
    from ie123kit.nucleo.texto import paginado as P

    modelo = P.ModeloMotor(ancho_ventana=0x1A0)
    assert P.simular(b"%s%3F", modelo) == "Ｘ".encode("cp932") * 12
    assert P.largo("Hola %s y %d", modelo) == len("Hola  y ") + 12 + 5
    with pytest.raises(ValueError):
        P.preprocesar(b"%s")


def test_problemas_detecta_pagina_de_mas_de_131_bytes():
    from ie123kit.ie2.comun.dialogo import MODELO_IE2
    from ie123kit.nucleo.texto import paginado as P

    fila = "Ａ".encode("cp932") * 30
    cuerpo = b"\\n".join([fila, fila, fila])       # 3 × 60 B + 2 = 182 B > 131
    assert any("B > 131" in p for p in P.problemas(cuerpo, MODELO_IE2))
    assert P.problemas(fila, MODELO_IE2) == []
    assert P.dibujo("Ａ".encode("cp932") * 38, MODELO_IE2)[1] == "Ａ".encode("cp932")


def test_repartir_no_corta_palabras_ni_cambia_texto():
    from ie123kit.nucleo.texto import paginado as P

    modelo = P.ModeloMotor(ancho_ventana=0x1A0, ancho_dibujo=0x1C0, pagina_max=131)
    texto = " ".join(["palabra"] * 40) + ". Fin."
    salida = P.repartir(texto, modelo, lambda t: t.encode("ascii"))
    assert salida.replace(P.PAGINA, " ").replace(P.SALTO, " ").split() == texto.split()
    for pagina in salida.split(P.PAGINA):
        lineas = pagina.split(P.SALTO)
        assert len(lineas) <= 3 and all(len(x) <= 37 for x in lineas)
    with pytest.raises(ValueError):
        P.repartir("x" * 40, modelo, lambda t: t.encode("ascii"))


def test_partir_paginas_solo_cambia_saltos_y_conserva_el_tamano():
    from ie123kit.ie2.comun.dialogo import MODELO_IE2
    from ie123kit.nucleo.texto import paginado as P

    fila = "Ａ" * 30
    texto = "\\n".join([fila + "。", fila, fila])
    nuevo, cortes = P.partir_paginas(texto, MODELO_IE2, legible=lambda b: b.decode("cp932").replace("。", "."))
    assert cortes == 1 and len(nuevo) == len(texto)
    assert nuevo.replace("\\f", "\\n") == texto
    assert P.partir_paginas(texto, P.ModeloMotor(ancho_ventana=0xF0)) == (texto, 0)


def test_reparte_rechaza_texto_no_espanol():
    from ie123kit.ie2.comun.dialogo import reparte

    assert reparte("こんにちは".encode("cp932"), glifos=()) == (None, "no es texto español")


# ------------------------------------------------------------------ SPF_ y teclado


def _spf(entradas: dict[str, bytes]) -> bytes:
    """SFP sintético: bloque de 4 B, datos alineados a bloque tras los nombres."""
    n = len(entradas)
    tabla = 0x20 + 16 * n
    nombres = b"".join(k.encode() + b"\0" for k in entradas)
    base = tabla + len(nombres)
    base += -base % 4
    cab = bytearray(FIRMA_SPF + b"\0" * 0x1C)
    struct.pack_into("<II", cab, 0x0C, 4, base)
    filas, datos, off_nombre = bytearray(), bytearray(), tabla
    for k, v in entradas.items():
        filas += struct.pack("<4I", off_nombre, len(v), len(datos) // 4, 0)
        off_nombre += len(k) + 1
        datos += v + b"\0" * (-len(v) % 4)
    cuerpo = bytes(cab) + bytes(filas) + nombres
    return cuerpo + b"\0" * (base - len(cuerpo)) + bytes(datos)


FIRMA_SPF = b"SFP\0"


def _fcode() -> bytes:
    base = bytearray(b"xy" * 156) + b"\r\n"
    base[52 + 48:52 + 52] = b"BBBB"
    base[104 + 48:104 + 52] = b"CCCC"
    return bytes(base)


def test_spf_entradas_sustituir_y_lz10():
    from ie123kit.nucleo.contenedores import spf

    plano = _spf({"A.TXT": b"hola", "B.BIN": b"123456"})
    assert {k: v.tamano for k, v in spf.entradas(plano).items()} == {"A.TXT": 4, "B.BIN": 6}
    assert spf.leer(plano, "dir/a.txt") == b"hola"
    nuevo = spf.sustituir(plano, {"A.TXT": b"adio"})
    assert spf.leer(nuevo, "A.TXT") == b"adio" and spf.leer(nuevo, "B.BIN") == b"123456"
    with pytest.raises(ValidacionError):
        spf.sustituir(plano, {"A.TXT": b"corto"})
    with pytest.raises(ValidacionError):
        spf.sustituir(plano, {"C.TXT": b"x"})
    assert spf.descomprimir(spf.empaquetar(nuevo)) == nuevo
    with pytest.raises(ValidacionError):
        spf.descomprimir(b"XXXX")


def test_teclado_ie2_sustituye_solo_las_fcode():
    from ie123kit.ie2.comun import teclado as T
    from ie123kit.nucleo.contenedores import spf
    from ie123kit.nucleo.texto.teclado import parchear_fcode

    plano = _spf({"FCODE0.TXT": _fcode(), "FCODE1.TXT": _fcode(), "FCODE2.TXT": _fcode(), "NGWORD": b"ng"})
    salida, informe = T.paquete_latino(spf.empaquetar(plano))
    nuevo = spf.descomprimir(salida)
    for nombre, modo in T.MODOS.items():
        assert spf.leer(nuevo, nombre) == parchear_fcode(_fcode(), modo)
    assert spf.leer(nuevo, "NGWORD") == b"ng" and informe["intactas"] == ["NGWORD"]
    with pytest.raises(ValueError):
        T.paquete_latino(spf.empaquetar(plano), original=lambda n: b"otra")


# ------------------------------------------------------------------ DSP-ADPCM, Procyon y sound.pb


def test_dsp_adpcm_ida_y_vuelta_de_un_seno():
    from ie123kit.nucleo.media import dsp_adpcm as D

    pcm = [int(8000 * math.sin(2 * math.pi * 440 * i / 32728)) for i in range(700)]
    datos, coefs, ps = D.codificar(pcm)
    assert len(datos) == (700 + 13) // 14 * 8 and len(coefs) == 8 and ps == datos[0]
    dec = np.array(D.decodificar(datos, coefs, len(pcm)), dtype=float)
    ruido = np.mean((dec - np.array(pcm)) ** 2)
    assert 10 * math.log10(np.mean(np.array(pcm, dtype=float) ** 2) / max(ruido, 1e-9)) > 20


def test_cwav_mono_reescribe_la_cabecera():
    from ie123kit.nucleo.media import dsp_adpcm as D

    plantilla = bytearray(0xE0)
    plantilla[:4], plantilla[0x40:0x44], plantilla[0xC0:0xC4] = b"CWAV", b"INFO", b"DATA"
    plantilla[0x48] = 2
    cw = D.cwav_mono(bytes(plantilla), [0] * 100, 32728)
    assert struct.unpack_from("<I", cw, 0x0C)[0] == len(cw)
    assert struct.unpack_from("<II", cw, 0x4C) == (32728, 0) and struct.unpack_from("<I", cw, 0x54)[0] == 100
    with pytest.raises(ValueError):
        D.cwav_mono(b"\0" * 0xE0, [0], 32728)


def test_sound_pb_montar_y_leer():
    from ie123kit.nucleo.contenedores import sound_pb as SP

    pb, ph = SP.montar_3ds([("A.SED", b"aa"), ("B.SWD", b"bbb")], {"A.SED": b"xyz1"})
    assert SP.leer_3ds(ph, pb) == [("A.SED", b"xyz1"), ("B.SWD", b"bbb")]
    with pytest.raises(ValueError):
        SP.montar_3ds([("N" * 25, b"")])


def test_procyon_notas_ima_y_remuestreo():
    from ie123kit.ie2.comun.voces import remuestrear
    from ie123kit.nucleo.media import procyon as PR

    eventos = bytes.fromhex("a007") + bytes.fromhex("7f60ff") + bytes.fromhex("92ff") + b"\x98"
    notas = PR.notas(eventos)
    assert notas[0] == [0, 7 * 12 + 0, 0x7F, 0xFF] and notas[-1] == ["fin", 0xFF]
    with pytest.raises(ValueError):
        PR.notas(b"\xfe")
    ima = struct.pack("<hB", 0, 0) + b"\0" + bytes([0x77] * 8)
    pcm = PR.ima_nds(ima)
    assert len(pcm) == 16 and pcm == sorted(pcm)
    assert remuestrear([1, 2, 3], 100, 100) == [1, 2, 3]


# ------------------------------------------------------------------ subtítulos


def _dat(registros) -> bytes:
    out = bytearray()
    for ini, fin, cuerpo in registros:
        carga = cuerpo + b"\0"
        carga += b"\0" * (-len(carga) % 4)
        out += struct.pack("<III", ini, fin, len(carga)) + carga
    return bytes(out + b"\xff\xff\xff\xff")


def test_subtitulos_dat_partir_y_repartir():
    from ie123kit.nucleo.media import subtitulos as S

    dat = _dat([(10, 40, b"Hola. Adios amigo"), (50, 60, b"\xb2")])
    assert [r.inicio for r in S.leer_dat(dat)] == [10, 50]
    pistas = S.pistas(dat, ancho=lambda t: 10 * len(t), ancho_max=60)
    assert [p["texto"] for p in pistas] == ["Hola.", "Adios", "amigo", "á"]
    assert pistas[0]["inicio"] == 10 and pistas[2]["fin"] == 40
    assert all(a["fin"] == b["inicio"] for a, b in itertools.pairwise(pistas[:3]))
    with pytest.raises(ValueError):
        S.leer_dat(b"\0" * 4)
    assert S.decodificar_nds(b"\xff") is None


def test_subtitulos_tick_y_maquina_del_cro():
    from ie123kit.nucleo.media import subtitulos as S

    assert [S.tick(k) for k in (0, 1, 24, 48)] == [0, 1, 30, 60]
    subs = [{"inicio": 30, "fin": 60, "texto": "a"}, {"inicio": 50, "fin": 90, "texto": "b"}]
    idx = S.por_fotograma(subs, 96)
    assert idx[23] == -1 and idx[24] == 0 and idx[47] == 0 and idx[48] == 1 and idx[72] == -1


def test_subtitulos_quemar_con_alfa_sintetico(monkeypatch):
    from ie123kit.nucleo.media import subtitulos as S

    estilo = S.EstiloSubtitulo(fuente=__import__("pathlib").Path("x.ttf"), alto=4, ancho_pantalla=3, blanco=200)
    banda = np.zeros((4, 3), np.uint8)
    banda[0, 0] = 255
    monkeypatch.setattr(S, "alfa", lambda texto, est: banda)
    Y = np.full((2, 3, 6), 16, np.uint8)
    S.quemar(Y, [{"texto": "t"}], np.array([0, -1]), estilo)
    assert Y[0, 0, 3] == 200 and Y[0, 0, 0] == 16 and (Y[1] == 16).all()


# ------------------------------------------------------------------ parches de CRO


def _cro(reloc_en: int | None = None) -> bytes:
    """CRO mínima: un segmento en 0x200 y una tabla 0x128 con una entrada opcional."""
    d = bytearray(0x400)
    struct.pack_into("<II", d, 0xC8, 0x180, 1)
    struct.pack_into("<III", d, 0x180, 0x200, 0x100, 0)
    struct.pack_into("<II", d, 0xF8, 0x1A0, 0)
    struct.pack_into("<II", d, 0x130, 0x1A0, 0)
    if reloc_en is None:
        struct.pack_into("<II", d, 0x128, 0x1A0, 0)
    else:
        struct.pack_into("<II", d, 0x128, 0x1A0, 1)
        struct.pack_into("<I", d, 0x1A0, (reloc_en - 0x200) << 4)
    struct.pack_into("<I", d, 0x210, 0xE3A010F0)
    struct.pack_into("<I", d, 0x214, 0xE3A02003)
    return bytes(d)


def test_parche_de_palabra_con_contexto_y_relocaciones():
    from ie123kit.nucleo.ejecutable import parches_cro as PC

    parche = [PC.ParchePalabra(0x210, 0xE3A010F0, 0xE3A01E1A, "ancho")]
    salida, informe = PC.aplicar(_cro(), parche, [PC.Contexto(0x214, 0xE3A02003)])
    assert struct.unpack_from("<I", salida, 0x210)[0] == 0xE3A01E1A
    assert informe["bytes_distintos"] == ["0x210", "0x211"]
    assert informe["parches"][0]["desensamblado_despues"] in ([], ["mov r1, #0x1a0"])
    with pytest.raises(ValidacionError, match="cro_relocacion_solapada"):
        PC.aplicar(_cro(reloc_en=0x212), parche)
    with pytest.raises(ValidacionError, match="cro_contexto"):
        PC.aplicar(_cro(), parche, [PC.Contexto(0x214, 0)])
    with pytest.raises(ValidacionError, match="cro_palabra_inesperada"):
        PC.aplicar(_cro(), [PC.ParchePalabra(0x214, 0xE3A010F0, 0)])


def test_parches_ie2_declarados():
    from ie123kit.ie2.comun import cro

    assert [hex(p.direccion) for p in cro.PARCHES_ANCHO_DIALOGO] == ["0x66a24", "0x4cabc", "0x4d6a0"]
    assert all(p.antes != p.despues for p in cro.PARCHES_ANCHO_DIALOGO)
