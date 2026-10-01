"""Tipos del contrato: construcción, validación y forma JSON."""

from __future__ import annotations

import json
import threading

import pytest

from ie123kit.nucleo.errores import CanceladoError
from ie123kit.nucleo.tipos import (
    API_VERSION,
    CODIGOS,
    AssetRef,
    CancelToken,
    Incidencia,
    Progreso,
    Rect,
    Resultado,
    componer_id,
    partir_id,
)

RUTA = "inazuma1/data_iz/a_title/title_t.arc"
SUB = "ie01_title_t_tlogo.tga"
ID = f"ie1:grafico:{RUTA}#{SUB}"


def _assetref(**kw) -> AssetRef:
    base = {"objetivo": "ie1", "tipo": "grafico", "ruta_romfs": RUTA, "subruta": SUB}
    base.update(kw)
    base["id"] = componer_id(base["objetivo"], base["tipo"], base["ruta_romfs"], base.get("subruta"))
    return AssetRef(**base)


def test_codigos_estables() -> None:
    assert len(CODIGOS) == 14
    assert "NOT_SUPPORTED" in CODIGOS


def test_componer_y_partir_id() -> None:
    assert componer_id("ie1", "grafico", RUTA, SUB) == ID
    assert partir_id(ID) == ("ie1", "grafico", RUTA, SUB)
    sin_sub = componer_id("ie1", "texto", RUTA)
    assert "#" not in sin_sub
    assert partir_id(sin_sub) == ("ie1", "texto", RUTA, None)
    with pytest.raises(ValueError):
        partir_id("sin_separadores")


def test_rect_json() -> None:
    r = Rect(1, 2, 3, 4, "cuerpo")
    assert r.to_json() == {"x0": 1, "y0": 2, "x1": 3, "y1": 4, "parte": "cuerpo"}
    json.dumps(r.to_json(), ensure_ascii=False)


def test_incidencia_omite_opcionales() -> None:
    i = Incidencia("EXCEDE_PX", "aviso", "se sale por 3 px")
    assert i.to_json() == {"codigo": "EXCEDE_PX", "severidad": "aviso", "mensaje": "se sale por 3 px"}
    con_extras = Incidencia("EXCEDE_PX", "error", "m", activo_id=ID, ruta="a/b", ubicacion="l1", pista="acorta")
    assert con_extras.to_json()["activo_id"] == ID
    json.dumps(con_extras.to_json(), ensure_ascii=False)


def test_incidencia_valida_vocabulario() -> None:
    with pytest.raises(ValueError):
        Incidencia("CODIGO_INVENTADO")
    with pytest.raises(ValueError):
        Incidencia("EXCEDE_PX", "grave")


def test_assetref_json_y_validaciones() -> None:
    ref = _assetref(cadena_contenedores=("fa", "arcv"), rects=(Rect(0, 0, 8, 8, "zona"),), tamano=64, editable=True)
    datos = ref.to_json()
    assert datos["id"] == ID
    assert datos["cadena_contenedores"] == ["fa", "arcv"]
    assert datos["rects"][0]["parte"] == "zona"
    assert "vista_previa" not in datos and "sha256" not in datos
    json.dumps(datos, ensure_ascii=False)

    sin_opcionales = AssetRef(id=componer_id("ie1", "texto", RUTA), objetivo="ie1", tipo="texto", ruta_romfs=RUTA)
    assert "subruta" not in sin_opcionales.to_json()
    assert "rects" not in sin_opcionales.to_json()

    with pytest.raises(ValueError):
        _assetref(estado="a_medias")
    with pytest.raises(ValueError):
        _assetref(origen="psp")
    with pytest.raises(ValueError):
        _assetref(cadena_contenedores=("zip",))
    with pytest.raises(ValueError):
        AssetRef(id="ie1:grafico:otra", objetivo="ie1", tipo="grafico", ruta_romfs=RUTA)


def test_resultado_helpers() -> None:
    ok = Resultado.correcto({"n": 2}, artefactos=("a.png",))
    assert ok.ok and ok.api_version == API_VERSION
    assert ok.to_json() == {
        "ok": True,
        "datos": {"n": 2},
        "incidencias": [],
        "artefactos": ["a.png"],
        "duracion_s": 0.0,
        "api_version": API_VERSION,
    }
    mal = Resultado.fallo([Incidencia("BLOQUEO_V20", "error", "hash distinto")])
    assert not mal.ok and mal.to_json()["incidencias"][0]["codigo"] == "BLOQUEO_V20"

    ns = Resultado.no_soportado("aún no", activo_id=ID)
    assert not ns.ok and len(ns.incidencias) == 1
    assert ns.incidencias[0].codigo == "NOT_SUPPORTED"
    assert ns.incidencias[0].activo_id == ID
    json.dumps(ns.to_json(), ensure_ascii=False)


def test_resultado_datos_no_compartidos() -> None:
    a, b = Resultado.correcto(), Resultado.correcto()
    a.datos["x"] = 1
    assert b.datos == {}


def test_progreso() -> None:
    p = Progreso("extraer", 1, 3, "vamos")
    assert p.to_json() == {"fase": "extraer", "actual": 1, "total": 3, "mensaje": "vamos"}
    Progreso("indeterminado", 7, 0)
    with pytest.raises(ValueError):
        Progreso("f", -1, 3)
    with pytest.raises(ValueError):
        Progreso("f", 1, -3)
    with pytest.raises(ValueError):
        Progreso("f", 4, 3)


def test_cancel_token_entre_hilos() -> None:
    token = CancelToken()
    assert not token.cancelado
    token.comprobar()
    assert token.to_json() == {"cancelado": False}

    hilo = threading.Thread(target=token.cancelar)
    hilo.start()
    hilo.join()
    assert token.cancelado
    assert token.to_json() == {"cancelado": True}
    with pytest.raises(CanceladoError):
        token.comprobar()
