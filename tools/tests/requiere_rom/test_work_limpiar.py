"""`ie123 work limpiar` sobre el work/ REAL: lo que nunca puede proponer borrar.

Marcado `requiere_rom` porque necesita el `work/` local (en CI no existe y se salta).
No borra nada: solo comprueba la LISTA que devuelve `limpieza.objetivos()`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ie123kit.nucleo.config.raiz import find_root
from ie123kit.nucleo.construir import limpieza

pytestmark = pytest.mark.requiere_rom

RAIZ = find_root()
WORK = RAIZ / "work"


@pytest.fixture(autouse=True)
def _hay_work() -> None:
    if not WORK.is_dir():
        pytest.skip("no hay work/ local")


def _relativas() -> list[str]:
    return [Path(p).resolve().as_posix() for p in limpieza.objetivos()]


def test_nunca_lista_la_base_3ds_ni_las_fuentes() -> None:
    for ruta in _relativas():
        assert "/work/shared/base_3ds" not in ruta, ruta
        assert "/fuentes/" not in ruta and not ruta.endswith("/fuentes"), ruta


def test_nunca_lista_los_congelados_del_bloqueo_v20() -> None:
    nombres = {Path(p).name for p in _relativas()}
    assert not (nombres & set(limpieza.CONGELADOS))


def test_nunca_lista_una_candidata_marcada_conservar() -> None:
    candidatas = WORK / "shared" / "candidatas"
    conservadas = [p.name for p in candidatas.glob("*") if (p / ".conservar").exists()] \
        if candidatas.is_dir() else []
    listadas = _relativas()
    for nombre in conservadas:
        assert not any(f"/candidatas/{nombre}" in r for r in listadas), nombre


def test_juego_principal_es_un_ambito_de_work() -> None:
    assert "juego_principal" in limpieza.AMBITOS
    assert (WORK / "juego_principal").is_dir(), "falta work/juego_principal (ie123 proyecto init)"


def test_los_ambitos_cubren_todo_lo_que_hay_en_work() -> None:
    """Regla 1 de docs/ARQUITECTURA.md: nada nuevo en la raíz de work/."""
    sueltos = sorted(p.name for p in WORK.iterdir() if p.is_dir() and p.name not in limpieza.AMBITOS)
    assert sueltos == [], f"carpetas fuera de los cinco ámbitos: {sueltos}"
