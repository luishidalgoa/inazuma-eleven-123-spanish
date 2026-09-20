"""Tests sin ROM de lo portado en la F2.6: nota del SED, contenedor SWD y preparación de voz.

Todo con datos sintéticos (Norma 2: aquí no entra nada del juego).
"""
from __future__ import annotations

import struct

import numpy as np
import pytest

from ie123kit.juego_principal import voz_titulo as VT
from ie123kit.nucleo.media import procyon as PR
from ie123kit.nucleo.media import voz

# ------------------------------------------------------------------ nota del SED


def test_nota_con_ticks_conserva_el_tamano_y_cambia_los_4_bytes() -> None:
    nueva = PR.nota_con_ticks(VT.NOTA_JP, 548)
    assert len(nueva) == len(VT.NOTA_JP)
    assert nueva[:4] == VT.NOTA_JP[:4] and nueva[6] == 0x93 and nueva[9] == 0x98
    assert int.from_bytes(nueva[4:6], "big") == 548
    assert int.from_bytes(nueva[7:9], "little") == 548
    assert sum(a != b for a, b in zip(nueva, VT.NOTA_JP)) == 4
    assert PR.nota_con_ticks(VT.NOTA_JP, 300) == VT.NOTA_JP


def test_nota_con_ticks_rechaza_patrones_y_duraciones_invalidas() -> None:
    with pytest.raises(ValueError):
        PR.nota_con_ticks(b"\x00" * 10, 100)
    with pytest.raises(ValueError):
        PR.nota_con_ticks(VT.NOTA_JP[:-1] + b"\x99", 100)
    with pytest.raises(ValueError):          # la nota del patrón no lleva 2 B de duración
        PR.nota_con_ticks(VT.NOTA_JP[:3] + b"\x01" + VT.NOTA_JP[4:], 100)
    with pytest.raises(ValueError):
        PR.nota_con_ticks(VT.NOTA_JP, 0x10000)


def test_sed_con_ticks_solo_toca_la_nota_y_exige_una_aparicion() -> None:
    sed = b"cabecera" + VT.NOTA_JP + b"cola"
    nuevo = PR.sed_con_ticks(sed, VT.NOTA_JP, 548)
    assert len(nuevo) == len(sed)
    assert nuevo[:8] == sed[:8] and nuevo[-4:] == sed[-4:]
    assert PR.notas(nuevo[8:18])[0][3] == 548
    with pytest.raises(ValueError):
        PR.sed_con_ticks(sed + VT.NOTA_JP, VT.NOTA_JP, 548)
    with pytest.raises(ValueError):
        PR.sed_con_ticks(b"nada", VT.NOTA_JP, 548)


def test_ticks_para_anade_el_margen_de_la_capa() -> None:
    assert VT.ticks_para(0) == VT.TICKS_MARGEN
    assert VT.ticks_para(5.366) == 548
    assert VT.ticks_para(2.979) == 308


# ------------------------------------------------------------------ contenedor SWD sintético


def _cwav(muestras: int, relleno: bytes) -> bytes:
    """CWAV mínimo para ``muestras_3ds``: magia, tamaño en +0x0C y número de muestras en +0x54."""
    cw = bytearray(0x60 + len(relleno))
    cw[0:4] = b"CWAV"
    struct.pack_into("<I", cw, 0x0C, len(cw))
    struct.pack_into("<I", cw, 0x54, muestras)
    cw[0x60:] = relleno
    return bytes(cw)


def _swd(cwavs: list[tuple[int, bytes]]) -> bytes:
    """SWD 3DS sintético con ``[(id, CWAV)]`` en ``pcmd`` y una entrada de ``wavi`` por muestra."""
    n = len(cwavs)
    wavi = bytearray(2 * n + (-2 * n % 4))
    entradas = bytearray()
    pcmd = bytearray()
    for k, (ident, cw) in enumerate(cwavs):
        ptr = len(wavi) + len(entradas)
        struct.pack_into("<H", wavi, 2 * k, ptr)
        e = bytearray(0x40)
        struct.pack_into("<H", e, 2, ident)
        struct.pack_into("<I", e, 0x24, len(pcmd))
        entradas += e
        pcmd += cw + b"\0" * (-len(cw) % 32)
    wavi += entradas
    cab = bytearray(0x60 + 3 * 16)
    struct.pack_into("<H", cab, 0x46, n)
    wo = len(cab)
    for j, (tag, off, ln) in enumerate([(b"wavi", wo, len(wavi)), (b"pcmd", wo + len(wavi), len(pcmd)),
                                        (b"eod ", 0, 0)]):
        p = 0x60 + 16 * j
        cab[p:p + 4] = tag
        struct.pack_into("<II", cab, p + 8, off, ln)
    struct.pack_into("<I", cab, 0x08, wo + len(wavi) + len(pcmd))
    struct.pack_into("<I", cab, 0x40, len(pcmd))
    return bytes(cab) + bytes(wavi) + bytes(pcmd)


def test_swd_sintetico_roundtrip_y_sustitucion_de_una_muestra() -> None:
    a, b = _cwav(10, b"\xaa" * 40), _cwav(20, b"\xbb" * 8)
    swd = _swd([(7, a), (162, b)])
    ch, ents = PR.muestras_3ds(swd)
    assert [e["id"] for e in ents] == [7, 162]
    assert [e["cwav"] for e in ents] == [a, b]
    assert [e["muestras"] for e in ents] == [10, 20]
    assert VT.cwav_muestra(swd, 162) == b
    with pytest.raises(KeyError):
        VT.cwav_muestra(swd, 99)

    # sin cambios: el SWD se reconstruye igual (pcmd ya estaba alineado a 32 B)
    assert PR.swd_con_cwavs(swd, {}) == swd

    nuevo = _cwav(50, b"\xcc" * 100)
    salida = PR.swd_con_cwavs(swd, {162: nuevo})
    ch2, ents2 = PR.muestras_3ds(salida)
    assert [e["cwav"] for e in ents2] == [a, nuevo]
    assert ch2["pcmd"][0] == ch["pcmd"][0]                       # la cabecera no se mueve
    assert len(salida) == struct.unpack_from("<I", salida, 0x08)[0]
    assert struct.unpack_from("<I", salida, 0x40)[0] == ch2["pcmd"][1]
    assert salida[:ch["wavi"][0]] != swd[:ch["wavi"][0]]          # solo tamaños y posiciones


# ------------------------------------------------------------------ preparación de voz


def _voz(sr: int, huecos: list[float], frase_s: float = 0.4) -> np.ndarray:
    """Señal sintética: frases de ``frase_s`` (seno a 0,5) separadas por los silencios de ``huecos``."""
    piezas = []
    for k, h in enumerate([*huecos, None]):
        t = np.arange(int(frase_s * sr)) / sr
        piezas.append(0.5 * np.sin(2 * np.pi * 220 * t))
        if h is not None:
            piezas.append(np.zeros(int(h * sr)))
        del k
    return np.concatenate(piezas)


def test_tramos_y_agrupar_distinguen_los_huecos_largos() -> None:
    sr = 8000
    x = _voz(sr, [0.05, 0.40])
    t = voz.tramos(x, sr)
    assert len(t) == 3
    grupos, huecos = voz.agrupar(t, sr, 0.12, 0.10)
    assert len(grupos) == 2
    assert [h["accion"] for h in huecos] == ["se conserva", "-> 0.1"]
    assert 0.03 <= huecos[0]["s"] <= 0.07 and 0.37 <= huecos[1]["s"] <= 0.43


def test_montar_frases_recorta_el_hueco_largo_y_cierra_los_extremos() -> None:
    sr = 8000
    x = _voz(sr, [0.40])
    y, grupos, huecos = voz.montar_frases(x, sr)
    assert len(grupos) == 2 and len(huecos) == 1
    assert len(y) < len(x)                                       # el silencio de 0,4 s baja a 0,1 s
    assert abs(len(x) - len(y) - int(0.30 * sr)) <= int(0.02 * sr)
    assert abs(y[0]) < 1e-9 and abs(y[-1]) < 1e-9                # fundidos de entrada y de salida


def test_remuestrear_conserva_la_duracion() -> None:
    pytest.importorskip("scipy")
    sr = 8000
    x = _voz(sr, [])
    z = voz.remuestrear(x, sr, 16000)
    assert abs(len(z) / 16000 - len(x) / sr) < 1e-6


def test_recortar_voz_quita_el_silencio_de_los_bordes() -> None:
    sr = 8000
    x = np.concatenate([np.zeros(sr // 2), 8000 * np.sin(2 * np.pi * 220 * np.arange(sr) / sr),
                        np.zeros(sr // 2)]).astype(np.float64)
    y, (a, b) = voz.recortar_voz(x, sr)
    assert sr // 2 - int(0.02 * sr) <= a <= sr // 2
    assert 3 * sr // 2 <= b <= 3 * sr // 2 + int(0.02 * sr)
    assert len(y) == b - a and abs(y[0]) < 1.0 and abs(y[-1]) < 1.0
