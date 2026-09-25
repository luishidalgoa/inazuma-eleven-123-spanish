"""Compactación por streaming de archive.fa. Datos sintéticos: ni un byte de ROM."""

from __future__ import annotations

import struct
import sys
from pathlib import Path

import pytest

from ie123kit.nucleo.contenedores.compactar import compactar_fa, huellas_entradas, leer_entradas
from ie123kit.nucleo.contenedores.fa import FaArchive, reemplazar_entrada

CONTRATO = Path(__file__).resolve().parent.parent / "contrato"
if str(CONTRATO) not in sys.path:
    sys.path.insert(0, str(CONTRATO))

from fa_sintetico import escribir_fa

FICHEROS = {
    "inazuma1/data_iz/a_menu/status_t.arc": b"ARCV-status" * 3,
    "inazuma1/data_iz/a_menu/formation_b.arc": b"ARCV-formation",
    "inazuma3/data_iz/a_title/title_t.arc": b"ARCV-title" * 5,
    "inazuma3/data_iz/script/eve.pkh": b"PKH",
    "vacio/cero.bin": b"",
}


def _leer_todo(ruta: Path) -> dict[str, bytes]:
    arc = FaArchive(str(ruta))
    return {p: arc.read(p) for p, _o, _s in arc.entries}


@pytest.fixture
def inflado(tmp_path: Path) -> Path:
    """Contenedor con dos rondas de reemplazos: deja datos huérfanos anexados."""
    ruta = escribir_fa(tmp_path / "archive.fa", FICHEROS)
    for ronda in range(2):
        arc = FaArchive(str(ruta))
        with ruta.open("r+b") as fh:
            reemplazar_entrada(fh, arc, "inazuma3/data_iz/script/eve.pkh", b"PKH-nuevo-%d" % ronda * 40)
            reemplazar_entrada(fh, arc, "inazuma1/data_iz/a_menu/status_t.arc", b"S%d" % ronda * 100)
    return ruta


def test_compacta_y_conserva_todas_las_entradas(inflado: Path, tmp_path: Path) -> None:
    antes = _leer_todo(inflado)
    destino = tmp_path / "salida" / "archive.fa"
    informe = compactar_fa(inflado, destino)
    assert _leer_todo(destino) == antes
    assert informe.entradas == len(FICHEROS) == informe.verificadas
    assert informe.destino_bytes < informe.origen_bytes
    assert informe.origen_bytes == inflado.stat().st_size


def test_datos_alineados_a_16_y_en_orden_de_offset(inflado: Path, tmp_path: Path) -> None:
    destino = tmp_path / "c.fa"
    compactar_fa(inflado, destino)
    data_off, entradas = leer_entradas(destino)
    offsets = sorted(e.offset for e in entradas if e.tamano)
    assert all((data_off + o) % 16 == 0 for o in offsets)
    # sin huecos mayores que el relleno de alineado
    fin = max(e.offset + e.tamano for e in entradas)
    assert destino.stat().st_size == data_off + fin


def test_cabecera_y_tablas_identicas_salvo_offsets(inflado: Path, tmp_path: Path) -> None:
    destino = tmp_path / "c.fa"
    compactar_fa(inflado, destino)
    data_off, entradas = leer_entradas(inflado)
    a = bytearray(inflado.read_bytes()[:data_off])
    b = bytearray(destino.read_bytes()[:data_off])
    for e in entradas:
        a[e.registro + 8:e.registro + 12] = b"\0\0\0\0"
        b[e.registro + 8:e.registro + 12] = b"\0\0\0\0"
    assert a == b


def test_entradas_compartidas_siguen_compartidas(tmp_path: Path) -> None:
    ruta = escribir_fa(tmp_path / "a.fa", {"d/x.bin": b"X" * 20, "d/y.bin": b"Y" * 7})
    _data_off, entradas = leer_entradas(ruta)
    datos = bytearray(ruta.read_bytes())
    x, y = entradas
    struct.pack_into("<II", datos, y.registro + 8, x.offset, x.tamano)  # y apunta a x
    ruta.write_bytes(bytes(datos))
    destino = tmp_path / "c.fa"
    informe = compactar_fa(ruta, destino)
    assert informe.bloques_unicos == 1
    _, nuevas = leer_entradas(destino)
    assert nuevas[0].offset == nuevas[1].offset
    assert huellas_entradas(destino) == huellas_entradas(ruta)


def test_idempotente(inflado: Path, tmp_path: Path) -> None:
    uno, dos = tmp_path / "1.fa", tmp_path / "2.fa"
    compactar_fa(inflado, uno)
    compactar_fa(uno, dos)
    assert uno.read_bytes() == dos.read_bytes()


def test_progreso_y_rechazos(inflado: Path, tmp_path: Path) -> None:
    visto: list[tuple[int, int]] = []
    compactar_fa(inflado, tmp_path / "c.fa", progreso=lambda h, t: visto.append((h, t)))
    assert visto[-1][0] == visto[-1][1] == len(visto)
    with pytest.raises(ValueError):
        compactar_fa(inflado, inflado)
    malo = tmp_path / "malo.fa"
    malo.write_bytes(b"NOPE" + bytes(60))
    with pytest.raises(ValueError):
        compactar_fa(malo, tmp_path / "x.fa")
    assert not (tmp_path / "x.fa").exists()
