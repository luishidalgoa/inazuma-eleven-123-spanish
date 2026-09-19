"""ie1.texto.eventos: TSV de ida y vuelta, reglas de reinserción y paquete mch.

Norma 2: ni un byte procede de la ROM. El contenedor lo escribe el helper sintético de
la suite de contrato (solo lectura) y los SSD se construyen aquí.
"""

import csv
import importlib.util
import struct
import sys
from pathlib import Path

import pytest

from ie123kit.ie1.texto import eventos, mch
from ie123kit.nucleo.compresion import lz10
from ie123kit.nucleo.eventos import ssd
from ie123kit.nucleo.eventos.instrucciones import DIR_SCRIPT

DIALOGO, ROTULO = eventos.OPCODE_DIALOGO, 0x4037
EID, EID_MCH = 10010001, 94001500


def _escribir_fa(ruta, ficheros):
    modulo = "fa_sintetico_contrato"
    if modulo not in sys.modules:
        origen = Path(__file__).resolve().parent.parent / "contrato" / "fa_sintetico.py"
        spec = importlib.util.spec_from_file_location(modulo, origen)
        cargado = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cargado)
        sys.modules[modulo] = cargado
    return sys.modules[modulo].escribir_fa(ruta, ficheros)


def _instruccion(ident, opcode, indices):
    argc = len(indices)
    tipos = 4 * ((argc + 7) // 8)
    tabla = bytearray(tipos)
    for a in range(argc):
        tabla[a // 2] |= 3 << (4 * (a % 2))
    valores = b"".join(struct.pack("<I", i) for i in indices)
    return struct.pack("<HHHBB", ident, 8 + tipos + 4 * argc, opcode, argc, 0) + bytes(tabla) + valores


def _texto(ident, argumento, cuerpo):
    largo = (4 + len(cuerpo) + 1 + 3) & ~3
    return struct.pack("<HBB", ident, argumento, largo) + cuerpo + bytes(largo - 4 - len(cuerpo))


def _ssd(instrucciones, textos):
    codigo, tabla = b"".join(instrucciones), b"".join(textos)
    cabecera = struct.pack("<4sIIHHIIII", b"SSD\0", 0x00030001, 32 + len(codigo) + len(tabla),
                           len(instrucciones), len(textos), len(codigo), len(tabla), 0, 0)
    return cabecera + codigo + tabla


def _evento(dialogo=b"hola"):
    return _ssd([_instruccion(1, DIALOGO, [0]), _instruccion(2, ROTULO, [1, 1, 1])],
                [_texto(1, 1, dialogo), _texto(2, 3, b"rotulo")])


def _pkh(entradas):
    cab = b"PackNum 20260101" + struct.pack("<I", 0x30 + 12 * len(entradas))
    return cab + bytes(0x30 - len(cab)) + b"".join(struct.pack("<III", *e) for e in entradas)


def _paquete(eventos_datos):
    pkb, entradas = bytearray(), []
    for eid, datos in eventos_datos:
        bloque = lz10.compress(datos)
        entradas.append((eid, len(pkb), len(bloque)))
        pkb += bloque + bytes((-(len(pkb) + len(bloque))) % 4)
    return _pkh(entradas), bytes(pkb)


def _archivo(tmp_path, dialogo=b"hola"):
    ficheros = {}
    for pack, eid in (("eve", EID), ("mch", EID_MCH)):
        pkh, pkb = _paquete([(eid, _evento(dialogo))])
        ficheros[f"{DIR_SCRIPT}/{pack}.pkh"] = pkh
        ficheros[f"{DIR_SCRIPT}/{pack}.pkb"] = pkb
    return _escribir_fa(tmp_path / "archive.fa", ficheros)


def _filas(ruta):
    with ruta.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def _traducir(ruta, indice, texto):
    filas = _filas(ruta)
    for fila in filas:
        if int(fila["id"]) == indice:
            fila["traduccion"] = texto
    with ruta.open("w", encoding="utf-8", newline="") as fh:
        escritor = csv.DictWriter(fh, fieldnames=list(eventos.CABECERA_TSV), delimiter="\t", lineterminator="\n")
        escritor.writeheader()
        escritor.writerows(filas)


# --------------------------------- exportar ---------------------------------

def test_exportar_cabecera_y_una_fila_por_dialogo(tmp_path):
    archive = _archivo(tmp_path)
    escritos = eventos.exportar(archive, tmp_path / "textos")
    assert escritos == [tmp_path / "textos" / "eve" / f"{EID}.tsv"]
    filas = _filas(escritos[0])
    assert list(filas[0]) == list(eventos.CABECERA_TSV)
    assert [f["jp"] for f in filas] == ["hola"]          # el rótulo (arg 3) no se exporta
    assert filas[0]["max_bytes"] == "247"
    assert filas[0]["max_px"] == str(eventos.ANCHO_CAJA_PX)
    assert filas[0]["estado"] == "pendiente"


def test_exportar_mch(tmp_path):
    archive = _archivo(tmp_path)
    escritos = eventos.exportar(archive, tmp_path / "textos", pack="mch")
    assert escritos == [tmp_path / "textos" / "mch" / f"{EID_MCH}.tsv"]
    assert mch.evento_editable(EID_MCH) and not mch.evento_editable(10010001)


# --------------------------------- importar ---------------------------------

def test_ida_y_vuelta_sin_cambios(tmp_path):
    archive = _archivo(tmp_path)
    eventos.exportar(archive, tmp_path / "textos")
    informe = eventos.importar(archive, tmp_path / "textos")
    assert informe == {"eventos_preparados": 0, "incidencias": [], "ficheros": []}


def test_simular_no_escribe(tmp_path):
    archive = _archivo(tmp_path)
    tsv = eventos.exportar(archive, tmp_path / "textos")[0]
    _traducir(tsv, 0, "adios")
    informe = eventos.importar(archive, tmp_path / "textos", salida=tmp_path / "stage")
    assert informe["eventos_preparados"] == 1
    assert informe["incidencias"] == [] and informe["ficheros"] == []
    assert not (tmp_path / "stage").exists()


def test_escribe_ssd_valido(tmp_path):
    archive = _archivo(tmp_path)
    tsv = eventos.exportar(archive, tmp_path / "textos")[0]
    _traducir(tsv, 0, "adios")
    informe = eventos.importar(archive, tmp_path / "textos", simular=False, salida=tmp_path / "stage")
    esperado = tmp_path / "stage" / "events" / f"{EID}.ssd"
    assert informe["ficheros"] == [str(esperado)]
    registros = ssd.parse(esperado.read_bytes())[2]
    assert registros[0].body != b"hola" and registros[1].body == b"rotulo"


def test_escribe_ssd_mch_en_events_mch(tmp_path):
    archive = _archivo(tmp_path)
    tsv = eventos.exportar(archive, tmp_path / "textos", pack="mch")[0]
    _traducir(tsv, 0, "adios")
    informe = eventos.importar(archive, tmp_path / "textos", pack="mch", simular=False, salida=tmp_path / "stage")
    assert informe["ficheros"] == [str(tmp_path / "stage" / "events_mch" / f"{EID_MCH}.ssd")]


# ---------------------------------- reglas ----------------------------------

def _codigos(tmp_path, texto, dialogo=b"hola"):
    archive = _archivo(tmp_path, dialogo)
    tsv = eventos.exportar(archive, tmp_path / "textos")[0]
    _traducir(tsv, 0, texto)
    informe = eventos.importar(archive, tmp_path / "textos", simular=False, salida=tmp_path / "stage")
    assert informe["eventos_preparados"] == 0 and informe["ficheros"] == []
    assert not (tmp_path / "stage").exists()
    return [i["codigo"] for i in informe["incidencias"]]


def test_regla_nf_huerfano(tmp_path):
    assert _codigos(tmp_path, "hola %2F") == ["NF_HUERFANO"]


def test_regla_paginas_distintas(tmp_path):
    assert _codigos(tmp_path, r"hola\fadios") == ["PAGINAS_DISTINTAS"]


def test_regla_excede_px(tmp_path):
    assert _codigos(tmp_path, "supercalifragilisticoespialidosoyademas") == ["EXCEDE_PX"]


def test_regla_excede_bytes(tmp_path):
    # 24 "palabra" ocupan 4 páginas con el layout v20; el jp sintético lleva las mismas.
    largo = " ".join(["palabra"] * 24)
    assert _codigos(tmp_path, largo, dialogo=b"a\\fb\\fc\\fd") == ["EXCEDE_BYTES"]


def test_regla_glifo_no_soportado(tmp_path):
    assert _codigos(tmp_path, "hola ☃") == ["GLIFO_NO_SOPORTADO"]


def test_indice_desconocido(tmp_path):
    archive = _archivo(tmp_path)
    tsv = eventos.exportar(archive, tmp_path / "textos")[0]
    filas = _filas(tsv)
    filas[0]["id"] = "9"
    filas[0]["traduccion"] = "adios"
    with tsv.open("w", encoding="utf-8", newline="") as fh:
        escritor = csv.DictWriter(fh, fieldnames=list(eventos.CABECERA_TSV), delimiter="\t", lineterminator="\n")
        escritor.writeheader()
        escritor.writerows(filas)
    informe = eventos.importar(archive, tmp_path / "textos")
    assert [i["codigo"] for i in informe["incidencias"]] == ["INDICE_DESCONOCIDO"]


def test_evento_desconocido_en_el_nombre(tmp_path):
    archive = _archivo(tmp_path)
    carpeta = tmp_path / "textos" / "eve"
    carpeta.mkdir(parents=True)
    (carpeta / "12345678.tsv").write_text("\t".join(eventos.CABECERA_TSV) + "\n", encoding="utf-8")
    informe = eventos.importar(archive, tmp_path / "textos")
    assert [i["codigo"] for i in informe["incidencias"]] == ["EVENTO_DESCONOCIDO"]


def test_salida_requerida(tmp_path):
    archive = _archivo(tmp_path)
    tsv = eventos.exportar(archive, tmp_path / "textos")[0]
    _traducir(tsv, 0, "adios")
    with pytest.raises(Exception, match="SALIDA_REQUERIDA"):
        eventos.importar(archive, tmp_path / "textos", simular=False)
