"""API de lectura por ruta de FaArchive (F2.2, #48). Datos sintéticos: ni un byte de ROM."""

from __future__ import annotations

import struct
import sys
from pathlib import Path

import pytest

from ie123kit.nucleo.contenedores.fa import FaArchive, reemplazar_entrada

CONTRATO = Path(__file__).resolve().parent.parent / "contrato"
if str(CONTRATO) not in sys.path:
    sys.path.insert(0, str(CONTRATO))

from fa_sintetico import escribir_fa

FICHEROS = {
    "inazuma1/data_iz/a_menu/status_t.arc": b"ARCV-status",
    "inazuma1/data_iz/a_menu/formation_b.arc": b"ARCV-formation",
    "inazuma1/data_iz/a_title/title_t.arc": b"ARCV-title",
    "inazuma1/data_iz/script/eve.pkh": b"PKH",
}


@pytest.fixture
def archivo(tmp_path: Path) -> Path:
    return escribir_fa(tmp_path / "archive.fa", FICHEROS)


def test_index_coincide_con_entries(archivo: Path) -> None:
    arc = FaArchive(str(archivo))
    assert arc.index == {p: (o, s) for p, o, s in arc.entries}
    assert arc.index is arc.index  # cacheado, no se recalcula


def test_entries_sigue_siendo_una_lista_de_ternas(archivo: Path) -> None:
    arc = FaArchive(str(archivo))
    assert [p for p, _o, _s in arc.entries] == list(FICHEROS)


def test_read_devuelve_los_bytes(archivo: Path) -> None:
    arc = FaArchive(str(archivo))
    for ruta, datos in FICHEROS.items():
        assert arc.read(ruta) == datos


def test_exists(archivo: Path) -> None:
    arc = FaArchive(str(archivo))
    assert arc.exists("inazuma1/data_iz/a_title/title_t.arc")
    assert not arc.exists("inazuma1/data_iz/a_title/title_b.arc")


def test_read_ausente_sugiere_rutas_parecidas(archivo: Path) -> None:
    arc = FaArchive(str(archivo))
    with pytest.raises(KeyError) as exc:
        arc.read("inazuma1/data_iz/a_menu/status_b.arc")
    mensaje = str(exc.value)
    assert "status_b.arc" in mensaje
    assert "parecidas" in mensaje
    assert "inazuma1/data_iz/a_menu/status_t.arc" in mensaje
    assert mensaje.count("inazuma1/") <= 6  # la ruta pedida + hasta 5 sugerencias


def test_read_ausente_sin_parecidos_no_rompe(archivo: Path) -> None:
    arc = FaArchive(str(archivo))
    with pytest.raises(KeyError):
        arc.read("zzz")


def test_glob_por_prefijo(archivo: Path) -> None:
    arc = FaArchive(str(archivo))
    obtenido = arc.glob("inazuma1/data_iz/a_menu/")
    assert list(obtenido) == [
        "inazuma1/data_iz/a_menu/formation_b.arc",
        "inazuma1/data_iz/a_menu/status_t.arc",
    ]
    assert obtenido["inazuma1/data_iz/a_menu/status_t.arc"] == b"ARCV-status"


def test_glob_con_comodines(archivo: Path) -> None:
    arc = FaArchive(str(archivo))
    assert list(arc.glob("*/a_title/*.arc")) == ["inazuma1/data_iz/a_title/title_t.arc"]
    assert list(arc.glob("*.pkh")) == ["inazuma1/data_iz/script/eve.pkh"]
    assert arc.glob("*.nope") == {}


def test_reemplazar_entrada_alinea_a_16_y_reapunta(archivo: Path, tmp_path: Path) -> None:
    ruta = "inazuma1/data_iz/a_menu/status_t.arc"
    copia = tmp_path / "candidata.fa"
    copia.write_bytes(archivo.read_bytes())
    arc = FaArchive(str(copia))
    tamano_previo = copia.stat().st_size
    with copia.open("r+b") as fh:
        reemplazar_entrada(fh, arc, ruta, b"NUEVO" * 7)

    nuevo = FaArchive(str(copia))
    offset, tamano = nuevo.index[ruta]
    assert offset % 16 == 0
    assert offset >= tamano_previo
    assert tamano == 35
    assert nuevo.read(ruta) == b"NUEVO" * 7
    # el resto de entradas no se toca
    for otra, datos in FICHEROS.items():
        if otra != ruta:
            assert nuevo.read(otra) == datos


def test_reemplazar_entrada_actualiza_el_fileentry(archivo: Path, tmp_path: Path) -> None:
    ruta = "inazuma1/data_iz/script/eve.pkh"
    copia = tmp_path / "candidata.fa"
    copia.write_bytes(archivo.read_bytes())
    arc = FaArchive(str(copia))
    with copia.open("r+b") as fh:
        reemplazar_entrada(fh, arc, ruta, b"PKH-nuevo")

    datos = copia.read_bytes()
    nuevo = FaArchive(str(copia))
    offset, tamano = nuevo.index[ruta]
    campo = None
    for i in range(nuevo.fe_cnt):
        fo = nuevo.fe_off + i * 16
        rel, largo = struct.unpack_from("<II", datos, fo + 8)
        if rel == offset - nuevo.data_off and largo == tamano:
            campo = fo
    assert campo is not None
    assert tamano == len(b"PKH-nuevo")


def test_reemplazar_entrada_ruta_desconocida(archivo: Path, tmp_path: Path) -> None:
    copia = tmp_path / "candidata.fa"
    copia.write_bytes(archivo.read_bytes())
    arc = FaArchive(str(copia))
    with copia.open("r+b") as fh, pytest.raises(ValueError, match="missing archive entry"):
        reemplazar_entrada(fh, arc, "no/existe.arc", b"x")


def test_revertir_entradas_devuelve_el_original(archivo: Path, tmp_path: Path) -> None:
    from ie123kit.nucleo.contenedores.fa import entradas_distintas, revertir_entradas

    ruta = "inazuma1/data_iz/a_menu/status_t.arc"
    copia = tmp_path / "copia.fa"
    copia.write_bytes(archivo.read_bytes())
    with open(copia, "r+b") as fh:
        reemplazar_entrada(fh, FaArchive(str(copia)), ruta, b"TRADUCIDO")
    base = FaArchive(str(archivo))
    assert entradas_distintas(base, FaArchive(str(copia))) == [ruta]
    with open(copia, "r+b") as fh:
        hechas = revertir_entradas(fh, FaArchive(str(copia)), base, [ruta, "no/existe.arc"])
    assert hechas == [ruta]
    assert entradas_distintas(base, FaArchive(str(copia))) == []
