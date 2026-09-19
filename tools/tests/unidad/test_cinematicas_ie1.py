"""ie1.media.cinematicas: catálogo declarativo, SRT y rotación obligatoria 0x16.

Ningún test depende de mobipeg ni de ffmpeg: la herramienta externa se sustituye por un
doble que escribe un MOFLEX sintético (Norma 2: ni un byte de la ROM).
"""

import struct

import pytest

from ie123kit.ie1.media import cinematicas
from ie123kit.nucleo.config import herramientas
from ie123kit.nucleo.media import moflex
from ie123kit.nucleo.media.subtitulos_dat import Subtitle


def _descriptor(layout):
    return b"\x4c\x32" + bytes(12) + b"\x03\x0d" + bytes(12) + bytes([layout])


def _moflex_sintetico(layout=0x06):
    return b"cabecera" + _descriptor(layout) + _descriptor(layout)


def _sin_herramientas(monkeypatch):
    monkeypatch.setattr(herramientas, "localizar", lambda nombre, **k: None)


def _con_herramienta(monkeypatch, ruta):
    monkeypatch.setattr(herramientas, "localizar", lambda nombre, **k: ruta)


# --------------------------------- catálogo ---------------------------------

def test_catalogo_21_peliculas_con_rutas_relativas():
    lista = cinematicas.peliculas()
    assert len(lista) == 21
    assert len({p["id"] for p in lista}) == 21
    for pelicula in lista:
        for clave in ("id", "ruta_romfs", "subtitulos_dat"):
            assert pelicula[clave]
        for ruta in (pelicula["ruta_romfs"], pelicula["subtitulos_dat"]):
            assert not ruta.startswith(("/", "\\")) and ".." not in ruta.split("/")
            assert ruta.startswith("inazuma1/data_iz/movie/")
        assert pelicula["ruta_romfs"].endswith(".moflex")


def test_peliculas_devuelve_copias():
    primera = cinematicas.peliculas()[0]
    primera["id"] = "tocado"
    assert cinematicas.peliculas()[0]["id"] != "tocado"


def test_srt_usa_ticks_de_30hz():
    texto = cinematicas.srt([Subtitle(0, 30, "uno"), Subtitle(45, 90, "dos")])
    assert "00:00:00,000 --> 00:00:01,000" in texto
    assert "00:00:01,500 --> 00:00:03,000" in texto
    assert texto.startswith("1\n") and "\n2\n" in texto


# -------------------------- herramienta ausente -----------------------------

def test_exportar_sin_ffmpeg(tmp_path, monkeypatch):
    _sin_herramientas(monkeypatch)
    origen = tmp_path / "op00.moflex"
    origen.write_bytes(_moflex_sintetico())
    with pytest.raises(herramientas.HerramientaAusente) as exc:
        cinematicas.exportar(origen, tmp_path / "salida")
    assert exc.value.codigo == "HERRAMIENTA_AUSENTE"


def test_importar_sin_mobipeg(tmp_path, monkeypatch):
    _sin_herramientas(monkeypatch)
    mp4 = tmp_path / "op00.mp4"
    mp4.write_bytes(b"falso")
    with pytest.raises(herramientas.HerramientaAusente) as exc:
        cinematicas.importar(mp4, tmp_path / "op00.moflex")
    assert exc.value.codigo == "HERRAMIENTA_AUSENTE"
    assert not (tmp_path / "op00.moflex").exists()


# ------------------------------- ida y vuelta -------------------------------

def test_exportar_escribe_mp4_y_srt(tmp_path, monkeypatch):
    origen = tmp_path / "am0102.moflex"
    origen.write_bytes(_moflex_sintetico())
    dat = tmp_path / "am0102.dat"
    dat.write_bytes(struct.pack("<III", 0, 30, 4) + b"uno\0" + b"\xff" * 4)
    falso = tmp_path / "ffmpeg.exe"
    falso.write_bytes(b"")
    _con_herramienta(monkeypatch, falso)

    def _run(orden, **kwargs):
        destino = tmp_path / "salida" / "am0102.mp4"
        destino.write_bytes(b"mp4")
        return type("P", (), {"returncode": 0, "stdout": b"", "stderr": b""})()

    monkeypatch.setattr(moflex.subprocess, "run", _run)
    informe = cinematicas.exportar(origen, tmp_path / "salida", subtitulos=dat)
    assert informe["id"] == "am0102" and informe["subtitulos"] == 1
    assert (tmp_path / "salida" / "am0102.mp4").is_file()
    assert "uno" in (tmp_path / "salida" / "am0102.srt").read_text(encoding="utf-8")


def test_importar_simulado_no_escribe(tmp_path, monkeypatch):
    falso = tmp_path / "mobipeg.exe"
    falso.write_bytes(b"")
    _con_herramienta(monkeypatch, falso)
    mp4 = tmp_path / "op00.mp4"
    mp4.write_bytes(b"falso")

    def _no(*a, **k):
        raise AssertionError("no debe lanzarse el codificador al simular")

    monkeypatch.setattr(cinematicas.subprocess, "run", _no)
    informe = cinematicas.importar(mp4, tmp_path / "op00.moflex")
    assert informe["simulado"] is True and informe["layout"] == 0x16
    assert not (tmp_path / "op00.moflex").exists()


def test_importar_fuerza_layout_0x16(tmp_path, monkeypatch):
    falso = tmp_path / "mobipeg.exe"
    falso.write_bytes(b"")
    _con_herramienta(monkeypatch, falso)
    mp4 = tmp_path / "op00.mp4"
    mp4.write_bytes(b"falso")
    destino = tmp_path / "salida" / "op00.moflex"

    def _run(orden, **kwargs):
        # El muxer de mobipeg emite 0x06; el parcial se escribe con esa rotación.
        parcial = destino.with_suffix(destino.suffix + ".partial")
        parcial.write_bytes(_moflex_sintetico(0x06))
        return type("P", (), {"returncode": 0, "stdout": b"", "stderr": b""})()

    monkeypatch.setattr(cinematicas.subprocess, "run", _run)
    informe = cinematicas.importar(mp4, destino, simular=False)
    assert informe["layout"] == 0x16 and informe["descriptores"] == 2
    assert moflex.disposicion_rotacion(destino) == [0x16, 0x16]
    assert not destino.with_suffix(destino.suffix + ".partial").exists()


def test_importar_falla_si_el_codificador_no_produce_nada(tmp_path, monkeypatch):
    falso = tmp_path / "mobipeg.exe"
    falso.write_bytes(b"")
    _con_herramienta(monkeypatch, falso)
    mp4 = tmp_path / "op00.mp4"
    mp4.write_bytes(b"falso")
    monkeypatch.setattr(cinematicas.subprocess, "run",
                        lambda *a, **k: type("P", (), {"returncode": 1, "stdout": b"", "stderr": b""})())
    with pytest.raises(RuntimeError, match="mobipeg"):
        cinematicas.importar(mp4, tmp_path / "op00.moflex", simular=False)
