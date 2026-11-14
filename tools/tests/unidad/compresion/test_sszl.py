"""sszl.reenvolver_como: las tres políticas y el tope de crecimiento (F2.2, #48)."""

from __future__ import annotations

import pytest

from ie123kit.nucleo.compresion import sszl
from ie123kit.nucleo.errores import ValidacionError

RAW = b"ARCV" + b"\x00\x01\x02\x03" * 64 + b"texto repetido texto repetido " * 8
NUEVO = b"ARCV" + b"\x04\x05\x06\x07" * 64 + b"otro texto repetido otro texto repetido " * 8


def test_raw_devuelve_los_bytes_tal_cual() -> None:
    assert sszl.reenvolver_como(sszl.compress(RAW), NUEVO, "raw") == NUEVO
    assert sszl.reenvolver_como(RAW, NUEVO, "raw") == NUEVO


def test_sszl_comprime_siempre() -> None:
    resultado = sszl.reenvolver_como(RAW, NUEVO, "sszl")
    assert resultado[:4] == b"SSZL"
    assert sszl.unwrap(resultado) == NUEVO


def test_keep_comprime_solo_si_el_original_venia_envuelto() -> None:
    envuelto = sszl.reenvolver_como(sszl.compress(RAW), NUEVO, "keep")
    assert envuelto[:4] == b"SSZL"
    assert sszl.unwrap(envuelto) == NUEVO
    assert sszl.reenvolver_como(RAW, NUEVO, "keep") == NUEVO


def test_keep_es_el_valor_por_defecto() -> None:
    assert sszl.reenvolver_como(RAW, NUEVO) == NUEVO


def test_politica_desconocida() -> None:
    with pytest.raises(ValueError, match="política de reenvoltura desconocida"):
        sszl.reenvolver_como(RAW, NUEVO, "literal")


def test_crecimiento_maximo_rechaza_una_salida_mayor() -> None:
    original = sszl.compress(RAW)
    with pytest.raises(ValidacionError) as exc:
        sszl.reenvolver_como(original, NUEVO * 4, "sszl", crecimiento_max=1.0)
    assert exc.value.codigo == "sszl_crecimiento"


def test_crecimiento_maximo_holgado_pasa() -> None:
    original = sszl.compress(RAW)
    resultado = sszl.reenvolver_como(original, NUEVO, "sszl", crecimiento_max=4.0)
    assert sszl.unwrap(resultado) == NUEVO


def test_crecimiento_maximo_tambien_aplica_en_raw() -> None:
    with pytest.raises(ValidacionError):
        sszl.reenvolver_como(b"x" * 8, b"y" * 200, "raw", crecimiento_max=2.0)


def _datos_variados() -> bytes:
    import random

    rng = random.Random(7)
    trozos = [bytes(rng.randrange(256) for _ in range(40)) for _ in range(12)]
    salida = bytearray(b"ARCV" + bytes(60))
    for _ in range(400):
        salida += rng.choice(trozos)[: rng.randrange(3, 40)]
        if rng.random() < 0.2:
            salida += bytes(rng.randrange(1, 90))
    return bytes(salida)


def test_compress_optimo_ida_y_vuelta_y_no_mayor_que_el_voraz() -> None:
    raw = _datos_variados()
    optimo = sszl.compress_optimo(raw)
    assert optimo[:4] == b"SSZL"
    assert sszl.unwrap(optimo) == raw
    assert len(optimo) <= len(sszl.compress(raw))


def test_compress_optimo_casos_pequenos() -> None:
    for raw in (b"", b"a", b"ab", b"abc", b"\x00" * 5, b"\x00" * 5000, b"abcabcabcabc" * 3):
        assert sszl.unwrap(sszl.compress_optimo(raw)) == raw


def test_compress_optimo_usa_el_prefijo_de_ceros_sin_pasarse() -> None:
    raw = bytes(300) + b"fin"
    optimo = sszl.compress_optimo(raw)
    assert sszl.unwrap(optimo) == raw
    # 300 ceros caben en 17 copias de 18 B como mucho; con el prefijo, bastan unas pocas
    assert len(optimo) < len(sszl.compress(raw)) + 1


def test_politicas_optimo() -> None:
    envuelto = sszl.compress(RAW)
    r = sszl.reenvolver_como(envuelto, NUEVO, "keep_optimo")
    assert sszl.unwrap(r) == NUEVO
    assert len(r) <= len(sszl.reenvolver_como(envuelto, NUEVO, "keep"))
    assert sszl.reenvolver_como(RAW, NUEVO, "keep_optimo") == NUEVO
    assert sszl.unwrap(sszl.reenvolver_como(RAW, NUEVO, "sszl_optimo")) == NUEVO
