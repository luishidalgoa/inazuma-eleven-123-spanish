import json

import pytest

from ie123kit.ie3.bomber import compare_rows, crear_corpus
from ie123kit.ie3.comun.perfiles import cargar_perfil


def row(pack="evet", event_id="1", instruction="2", argument="3", opcode="0x3070", string_id="m0000", text="Hola"):
    return {
        "pack": pack,
        "event_id": event_id,
        "instruction": instruction,
        "argument": argument,
        "opcode": opcode,
        "string_id": string_id,
        "text": text,
    }


def test_compara_identico_solo_y_conflicto():
    base = row()
    distinto = row(text="Adios")
    solo_rayo = row(event_id="2", text="Rayo")
    solo_fuego = row(event_id="3", text="Fuego")

    rows, counts = compare_rows([base, solo_rayo], [distinto, solo_fuego])

    assert counts["COMUN_DISTINTO"] == 1
    assert counts["SOLO_RAYO"] == 1
    assert counts["SOLO_FUEGO"] == 1
    assert {r["classification"] for r in rows} == {"COMUN_DISTINTO", "SOLO_RAYO", "SOLO_FUEGO"}


def test_perfil_bomber_es_logico_y_comparte_recurso_spark():
    spark = cargar_perfil("spark")
    bomber = cargar_perfil("bomber")

    assert bomber.recurso == spark.recurso == "inazuma3/data_iz/script"
    assert bomber.nombre == "bomber"
    assert "fuego_explosivo" in bomber.corpus
    assert bomber.compartido == "spark_bomber"


def test_corpus_bomber_falla_si_hay_conflictos(tmp_path):
    root = tmp_path
    source = root / "translation/ie3/rayo_celeste/dialogo_oficial.csv"
    source.parent.mkdir(parents=True)
    source.write_text("event_id,japones,es_final,estado\n1,JP,ES,oficial\n", encoding="utf-8")
    report = root / "work/informes/fuego_vs_rayo"
    report.mkdir(parents=True)
    (report / "summary.json").write_text(
        json.dumps({"total": {"COMUN_DISTINTO": 1, "SOLO_FUEGO": 0, "SOLO_RAYO": 0}}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="difieren"):
        crear_corpus(root, report)
