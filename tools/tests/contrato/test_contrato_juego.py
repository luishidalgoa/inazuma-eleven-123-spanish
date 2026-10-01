"""Contrato uniforme de JuegoBase: JuegoFalso y los objetivos reales descubiertos (hoy NOT_SUPPORTED)."""

from __future__ import annotations

import json
from itertools import pairwise
from typing import Any

import pytest
from juego_falso import JuegoFalso  # sys.path lo prepara conftest.py

from ie123kit.nucleo import util
from ie123kit.nucleo.errores import CanceladoError
from ie123kit.nucleo.juego import CAPACIDAD_POR_TIPO, CAPACIDADES, Aportacion, JuegoBase, Regla
from ie123kit.nucleo.tipos import AssetRef, CancelToken, Progreso, Resultado, componer_id
from ie123kit.servicio import esquemas
from ie123kit.servicio.api import descubrir_juegos

REALES = descubrir_juegos()
IDS = [*sorted(REALES), "falso"]


def _juego(ident: str, falso: JuegoFalso) -> JuegoBase:
    return falso if ident == "falso" else REALES[ident]


def _comprobar_resultado(res: Any) -> None:
    assert isinstance(res, Resultado)
    json.dumps(res.to_json(), ensure_ascii=False)
    assert esquemas.validar(res.to_json(), "resultado") == []


def test_hay_objetivos() -> None:
    assert len(IDS) >= 2, IDS


@pytest.mark.parametrize("ident", IDS)
def test_es_juego_base(ident: str, juego_falso: JuegoFalso) -> None:
    assert isinstance(_juego(ident, juego_falso), JuegoBase)


@pytest.mark.parametrize("ident", IDS)
def test_info_valida_contra_esquema(ident: str, juego_falso: JuegoFalso) -> None:
    info = _juego(ident, juego_falso).info().to_json()
    assert esquemas.validar(info, "info_objetivo") == []
    json.dumps(info, ensure_ascii=False)


@pytest.mark.parametrize("ident", IDS)
def test_perfil_texto_es_v20(ident: str, juego_falso: JuegoFalso) -> None:
    perfil = _juego(ident, juego_falso).perfil_texto()
    assert getattr(perfil, "nombre", None) == "tipografia_v20"
    assert getattr(perfil, "bloqueado", True) is True


@pytest.mark.parametrize("ident", IDS)
def test_capacidad_no_declarada_devuelve_not_supported(ident: str, juego_falso: JuegoFalso,
                                                       proyecto_sintetico, tmp_path) -> None:
    juego = _juego(ident, juego_falso)
    info = juego.info()
    capacidades = set(info.capacidades)
    ruta = "falso/uno.bin"
    ref = AssetRef(
        id=componer_id(info.id, "grafico", ruta),
        objetivo=info.id,
        tipo="grafico",
        ruta_romfs=ruta,
        cadena_contenedores=("fa",),
    )
    res = juego.exportar(proyecto_sintetico, ref, tmp_path / "salida")
    _comprobar_resultado(res)
    if "graficos" not in capacidades:
        assert not res.ok
        assert any(i.codigo == "NOT_SUPPORTED" for i in res.incidencias)


@pytest.mark.parametrize("ident", IDS)
def test_activos_no_lanza(ident: str, juego_falso: JuegoFalso, proyecto_sintetico) -> None:
    juego = _juego(ident, juego_falso)
    try:
        salida = juego.activos(proyecto_sintetico)
    except NotImplementedError:
        pytest.skip(f"{ident} aún no implementa activos()")
        return
    if isinstance(salida, Resultado):
        _comprobar_resultado(salida)
    else:
        assert isinstance(salida, list)
        for ref in salida:
            datos = ref.to_json()
            json.dumps(datos, ensure_ascii=False)
            assert esquemas.validar(datos, "assetref") == [], (ident, datos)


@pytest.mark.parametrize("ident", IDS)
def test_aportaciones_uniformes(ident: str, juego_falso: JuegoFalso, proyecto_sintetico) -> None:
    """`aportaciones()` siempre devuelve una Aportacion con sus cuatro campos."""
    aporte = _juego(ident, juego_falso).aportaciones(proyecto_sintetico, [])
    assert isinstance(aporte, Aportacion)
    for campo in ("entradas_fa", "eventos", "literales_cro", "romfs_sueltos"):
        assert isinstance(getattr(aporte, campo), dict), (ident, campo)


@pytest.mark.parametrize("ident", IDS)
def test_reglas_validacion_serializables(ident: str, juego_falso: JuegoFalso) -> None:
    reglas = _juego(ident, juego_falso).reglas_validacion()
    assert isinstance(reglas, list)
    for regla in reglas:
        assert isinstance(regla, Regla)
        datos = regla.to_json()
        assert set(datos) == {"codigo", "descripcion", "ambito"}
        assert all(isinstance(v, str) and v for v in datos.values()), (ident, datos)
        json.dumps(datos, ensure_ascii=False)


@pytest.mark.parametrize("ident", IDS)
def test_tipos_sin_capacidad_son_not_supported(ident: str, juego_falso: JuegoFalso,
                                               proyecto_sintetico, tmp_path) -> None:
    """Todo tipo cuya capacidad NO esté declarada se rechaza con `NOT_SUPPORTED`.

    Un objetivo sin capacidades (ie2/ie3 hoy) rechaza los seis tipos; uno que declara
    algunas (juego_principal, el falso) sigue teniendo que rechazar los que le faltan, y
    así la comprobación no se apaga en cuanto un objetivo empieza a declarar capacidades.
    Solo se salta con las seis declaradas, que desde F2.3 es el caso de ie1.
    """
    juego = _juego(ident, juego_falso)
    info = juego.info()
    tipos = [t for t, cap in CAPACIDAD_POR_TIPO.items() if cap not in info.capacidades]
    if not tipos:
        pytest.skip(f"{ident} declara todas las capacidades: {sorted(info.capacidades)}")
    entrada = tmp_path / "entrada.bin"
    entrada.write_bytes(b"x")
    for tipo in tipos:
        ruta = f"{(info.prefijos_romfs or ('x/',))[0]}dato.bin"
        ref = AssetRef(id=componer_id(info.id, tipo, ruta), objetivo=info.id, tipo=tipo, ruta_romfs=ruta)
        for res in (
            juego.exportar(proyecto_sintetico, ref, tmp_path / "salida"),
            juego.importar(proyecto_sintetico, ref, entrada, simular=True),
        ):
            _comprobar_resultado(res)
            assert not res.ok, (ident, tipo)
            assert [i.codigo for i in res.incidencias] == ["NOT_SUPPORTED"], (ident, tipo)


@pytest.mark.parametrize("ident", IDS)
def test_simular_nunca_toca_el_arbol(ident: str, juego_falso: JuegoFalso,
                                     proyecto_sintetico, tmp_path) -> None:
    """`importar(simular=True)` deja el árbol del proyecto byte a byte igual."""
    juego = _juego(ident, juego_falso)
    refs = juego.activos(proyecto_sintetico)
    if not refs:
        ruta = "falso/uno.bin"
        refs = [AssetRef(id=componer_id(juego.info().id, "grafico", ruta),
                         objetivo=juego.info().id, tipo="grafico", ruta_romfs=ruta)]
    entrada = tmp_path / "simulada.bin"
    antes = util.sha256_arbol(proyecto_sintetico.raiz)
    for ref in refs[:3]:
        entrada.write_bytes(b"Z" * (ref.tamano or 1))
        res = juego.importar(proyecto_sintetico, ref, entrada, simular=True)
        _comprobar_resultado(res)
    assert util.sha256_arbol(proyecto_sintetico.raiz) == antes


def test_capacidades_declaradas_son_del_vocabulario(juego_falso: JuegoFalso) -> None:
    for ident in IDS:
        capacidades = _juego(ident, juego_falso).info().capacidades
        assert set(capacidades) <= set(CAPACIDADES), (ident, sorted(capacidades))


def test_exportar_falso_progreso_monotono(juego_falso: JuegoFalso, proyecto_sintetico, tmp_path) -> None:
    ref = juego_falso.activos(proyecto_sintetico)[0]
    eventos: list[Progreso] = []
    res = juego_falso.exportar(proyecto_sintetico, ref, tmp_path / "exp", progreso=eventos.append)
    _comprobar_resultado(res)
    assert res.ok, res.to_json()
    assert len(eventos) == 3
    assert {e.total for e in eventos} == {3}
    for previo, siguiente in pairwise(eventos):
        assert siguiente.actual >= previo.actual
    for e in eventos:
        assert 0 <= e.actual <= e.total


def test_cancel_detiene_la_exportacion(juego_falso: JuegoFalso, proyecto_sintetico, tmp_path) -> None:
    ref = juego_falso.activos(proyecto_sintetico)[0]
    cancel = CancelToken()
    cancel.cancelar()
    with pytest.raises(CanceladoError):
        juego_falso.exportar(proyecto_sintetico, ref, tmp_path / "exp", cancel=cancel)


def test_importar_tamano_inesperado_da_incidencia(juego_falso: JuegoFalso, proyecto_sintetico, tmp_path) -> None:
    ref = juego_falso.activos(proyecto_sintetico)[0]
    malo = tmp_path / "malo.bin"
    malo.write_bytes(b"x")
    res = juego_falso.importar(proyecto_sintetico, ref, malo, simular=True)
    _comprobar_resultado(res)
    assert not res.ok
    assert [i.codigo for i in res.incidencias] == ["EXCEDE_BYTES"]


def test_importar_simular_no_escribe(juego_falso: JuegoFalso, proyecto_sintetico, tmp_path) -> None:
    ref = juego_falso.activos(proyecto_sintetico)[0]
    entrada = tmp_path / "nuevo.bin"
    entrada.write_bytes(b"Z" * ref.tamano)
    antes = util.sha256_arbol(proyecto_sintetico.raiz)
    res = juego_falso.importar(proyecto_sintetico, ref, entrada, simular=True)
    _comprobar_resultado(res)
    assert res.ok and res.datos["simulado"] is True
    assert util.sha256_arbol(proyecto_sintetico.raiz) == antes
