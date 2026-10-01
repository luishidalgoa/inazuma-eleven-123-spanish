"""Los 8 esquemas JSON del contrato y sus dos validadores (jsonschema y el de respaldo)."""

from __future__ import annotations

import builtins
import json

import pytest

from ie123kit.nucleo.juego import InfoObjetivo
from ie123kit.nucleo.tipos import AssetRef, Incidencia, Progreso, Rect, Resultado, componer_id
from ie123kit.servicio import esquemas

RUTA = "inazuma1/data_iz/a_title/title_t.arc"
SUB = "ie01_title_t_tlogo.tga"


@pytest.fixture
def sin_jsonschema(monkeypatch: pytest.MonkeyPatch):
    """Fuerza la rama del validador mínimo propio."""
    importar_real = builtins.__import__

    def falso(nombre, *args, **kw):
        if nombre == "jsonschema":
            raise ImportError("simulado")
        return importar_real(nombre, *args, **kw)

    monkeypatch.setattr(builtins, "__import__", falso)


def test_nombres_y_ficheros() -> None:
    assert len(esquemas.NOMBRES) == 8
    assert set(esquemas.NOMBRES) == {
        "incidencia", "progreso", "assetref", "resultado",
        "info_objetivo", "manifiesto_candidata", "registro_activos", "evento_trabajo",
    }


@pytest.mark.parametrize("nombre", esquemas.NOMBRES)
def test_cargan_y_son_json_schema(nombre: str) -> None:
    doc = esquemas.cargar(nombre)
    assert doc["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert doc["$id"] == f"https://inazuma123.local/esquemas/{nombre}.schema.json"
    assert doc["additionalProperties"] is False
    json.dumps(doc, ensure_ascii=False)


def test_esquema_desconocido() -> None:
    with pytest.raises(ValueError):
        esquemas.cargar("no_existe")


# ------------------------------------------------------------------ instancias reales


def _instancias() -> dict[str, object]:
    ref = AssetRef(
        id=componer_id("ie1", "grafico", RUTA, SUB),
        objetivo="ie1",
        tipo="grafico",
        ruta_romfs=RUTA,
        cadena_contenedores=("fa", "arcv"),
        subruta=SUB,
        rects=(Rect(0, 0, 8, 8, "zona"),),
        tamano=128,
        editable=True,
        sha256="00" * 32,
    )
    info = InfoObjetivo("ie1", "Inazuma Eleven", ("inazuma1/",), ("cro/ina_main1.cro",), frozenset({"graficos"}))
    return {
        "incidencia": Incidencia("EXCEDE_PX", "aviso", "se sale", activo_id=ref.id).to_json(),
        "progreso": Progreso("extraer", 1, 3, "vamos").to_json(),
        "assetref": ref.to_json(),
        "resultado": Resultado.correcto({"n": 1}, artefactos=("a.png",)).to_json(),
        "info_objetivo": info.to_json(),
        "manifiesto_candidata": {
            "esquema": 1,
            "nombre": "probe_ie1_v68",
            "base": "base.3ds",
            "base_sha256": "aa" * 32,
            "capas": [{"ruta": "capas/ui", "sha256": "bb" * 32}],
            "salidas": {"romfs/inazuma1/archive.fa": "cc" * 32},
            "objetivos": ["ie1"],
            "runtime_verified": False,
            "generado_en": "2026-09-16T10:00:00Z",
        },
        "registro_activos": {
            "esquema": 1,
            "objetivo": "ie1",
            "base_sha256": "aa" * 32,
            "generado_en": "2026-09-16T10:00:00Z",
            "activos": [ref.to_json()],
        },
        "evento_trabajo": {
            "trabajo": "t-1",
            "ts": "2026-09-16T10:00:00Z",
            "tipo": "progreso",
            "datos": Progreso("extraer", 1, 3).to_json(),
        },
    }


@pytest.mark.parametrize("nombre", esquemas.NOMBRES)
def test_instancias_validas(nombre: str) -> None:
    assert esquemas.validar(_instancias()[nombre], nombre) == []


@pytest.mark.parametrize("nombre", esquemas.NOMBRES)
def test_instancias_validas_sin_jsonschema(nombre: str, sin_jsonschema: None) -> None:
    assert esquemas.validar(_instancias()[nombre], nombre) == []


ROTAS = {
    "incidencia": {"codigo": "NO_EXISTE", "severidad": "error", "mensaje": "", "extra": 1},
    "progreso": {"fase": "x", "actual": "uno", "total": 3, "mensaje": ""},
    "assetref": {"id": "ie1:grafico:x"},
    "resultado": {"ok": "sí", "datos": {}, "incidencias": [], "artefactos": [],
                  "duracion_s": 0.0, "api_version": "1.0"},
    "info_objetivo": {"id": "ie1", "nombre": "x", "prefijos_romfs": [], "cros": [],
                      "capacidades": ["magia"]},
    "manifiesto_candidata": {"esquema": 1, "nombre": "x"},
    "registro_activos": {"esquema": 1, "objetivo": "ie1", "base_sha256": "a",
                         "generado_en": "z", "activos": [{"id": "roto"}]},
    "evento_trabajo": {"trabajo": "t", "ts": "z", "tipo": "explosion", "datos": {}},
}


@pytest.mark.parametrize("nombre", esquemas.NOMBRES)
def test_instancias_rotas(nombre: str) -> None:
    assert esquemas.validar(ROTAS[nombre], nombre)


@pytest.mark.parametrize("nombre", esquemas.NOMBRES)
def test_instancias_rotas_sin_jsonschema(nombre: str, sin_jsonschema: None) -> None:
    assert esquemas.validar(ROTAS[nombre], nombre)
