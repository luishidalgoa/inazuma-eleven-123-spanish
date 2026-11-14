"""Hook de nombres en la fachada: construir sincroniza SIEMPRE, verificar falla y instalar se niega (sin ROM, sin work/ real).

Una capa sintética de nombres cambia un nombre de unitbase.dat sin tocar usearch.dat: la build tiene que corregirlo sola
(o fallar), y una candidata construida sin el paso (opt-out de tests) o editada después no puede darse por buena.
"""

from __future__ import annotations

import json
import struct
from pathlib import Path

import pytest
from fa_sintetico import escribir_fa
from juego_falso import FICHEROS

from ie123kit.nucleo.contenedores.fa_flujo import FaFlujo
from ie123kit.nucleo.registros import usearch as U
from ie123kit.nucleo.texto.ancho_completo import encode_fullwidth
from ie123kit.servicio import api as modulo_api
from ie123kit.servicio import sincronia_usearch as S
from ie123kit.servicio.api import SolicitudConstruccion

OBJETIVO = "falso"
IE1 = U.ESQUEMAS["ie1"]
REGISTRO = {"bigramas": [{"sjis": "9ABA", "par": "ck"}]}


def _ub(ident: int, nombre: bytes) -> bytes:
    r = bytearray(96)
    r[0:16] = r[16:32] = nombre.ljust(16, b"\0")
    struct.pack_into("<H", r, 0x42, ident)
    return bytes(r)


def _us(ident: int) -> bytes:
    r = bytearray(48)
    r[0:16] = r[16:32] = "あいう".encode("cp932").ljust(16, b"\0")
    struct.pack_into("<H", r, 0x24, ident)
    r[0x26], r[0x2A], r[0x2B] = 0x3C, (1 if ident else 0), (3 if ident else 1)
    return bytes(r)


UNITBASE_ORIGINAL = _ub(0, b"\x81\x40") + _ub(1, b"Mark") + _ub(2, b"Axel")
USEARCH_ORIGINAL = _us(1) + _us(2) + _us(0)


@pytest.fixture
def sin_bloqueo(monkeypatch):
    """El bloqueo tipográfico v20 necesita las fuentes reales; aquí no es lo que se prueba."""
    monkeypatch.setattr(modulo_api, "_comprobar_bloqueo", lambda bloqueo, archive, raiz: None)


def _registrar_bigramas(raiz: Path) -> None:
    for relativa in S.REGISTROS_BIGRAMAS:
        ruta = raiz / relativa
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(json.dumps(REGISTRO), encoding="utf-8")


def _base(proyecto, *, unitbase: bytes = UNITBASE_ORIGINAL) -> SolicitudConstruccion:
    base = Path(proyecto.candidata("probe_ie1_v67"))
    base.mkdir(parents=True, exist_ok=True)
    ficheros = {**FICHEROS, IE1.ruta_usearch: USEARCH_ORIGINAL, IE1.ruta_unitbase: unitbase}
    escribir_fa(base / "archive.fa", ficheros)
    capa = proyecto.raiz / "work" / "ie1" / "capas" / "v68" / "renombra"
    destino = capa / "extra" / IE1.ruta_unitbase
    destino.parent.mkdir(parents=True)
    # la «capa de nombres»: renombra a Mark (id 1) y no sabe que existe usearch
    destino.write_bytes(_ub(0, b"\x81\x40") + _ub(1, b"Mack") + _ub(2, b"Axel"))
    return SolicitudConstruccion(base="probe_ie1_v67", objetivos=(OBJETIVO,), capas=(str(capa),), salida="probe_ie1_v68")


def _usearch_de(proyecto, nombre: str) -> bytes:
    with FaFlujo(Path(proyecto.candidata(nombre)) / "archive.fa") as fa:
        return fa.leer(IE1.ruta_usearch)


def test_una_capa_que_cambia_un_nombre_sin_tocar_usearch_se_corrige_sola(
        servicio, proyecto_sintetico, sin_bloqueo) -> None:
    _registrar_bigramas(proyecto_sintetico.raiz)
    res = servicio.construir(_base(proyecto_sintetico))
    assert res.ok, [i.mensaje for i in res.incidencias]
    assert res.datos["sincronia_usearch"] == "ok"
    usearch = _usearch_de(proyecto_sintetico, "probe_ie1_v68")
    assert usearch[0x10:0x20] == encode_fullwidth("Mack").ljust(16, b"\0")  # el nombre nuevo, ya tecleable
    assert usearch[:0x10] == USEARCH_ORIGINAL[:0x10]  # +0x00 kana: lo lee el clasificador de «Por nombre»
    assert usearch[0x2B] == 3  # los flags no se tocan
    build = json.loads(Path(res.datos["build_json"]).read_text(encoding="utf-8"))
    assert build["pasos_finales"][0]["entradas_escritas"] == [IE1.ruta_usearch]
    # y la candidata construida pasa la verificación
    assert servicio.verificar("probe_ie1_v68").ok


def test_verificar_falla_si_la_candidata_no_esta_sincronizada_e_instalar_se_niega(
        servicio, proyecto_sintetico, sin_bloqueo) -> None:
    _registrar_bigramas(proyecto_sintetico.raiz)
    res = servicio.construir(_base(proyecto_sintetico), omitir_sincronia_usearch=True)
    assert res.ok and res.datos["sincronia_usearch"].startswith("omitida")
    assert "pasos_finales" not in json.loads(Path(res.datos["build_json"]).read_text(encoding="utf-8"))

    ver = servicio.verificar("probe_ie1_v68")
    assert not ver.ok
    assert {i.codigo for i in ver.incidencias} == {"USEARCH_DESINCRONIZADO"}
    assert "USEARCH_DESINCRONIZADO" in ver.incidencias[0].mensaje

    inst = servicio.instalar("probe_ie1_v68")
    assert not inst.ok and inst.incidencias[0].codigo == "USEARCH_DESINCRONIZADO"
    assert "instalar" in inst.incidencias[0].mensaje


def test_una_edicion_posterior_del_unitbase_tambien_se_detecta(servicio, proyecto_sintetico, sin_bloqueo) -> None:
    from ie123kit.nucleo.contenedores.fa_flujo import reemplazar_en_disco

    _registrar_bigramas(proyecto_sintetico.raiz)
    assert servicio.construir(_base(proyecto_sintetico)).ok
    archive = Path(proyecto_sintetico.candidata("probe_ie1_v68")) / "archive.fa"
    # alguien reescribe el unitbase DESPUÉS de construir (y el sha del build.json se desactualiza)
    reemplazar_en_disco(archive, {IE1.ruta_unitbase: _ub(0, b"\x81\x40") + _ub(1, b"Marcos") + _ub(2, b"Axel")})
    archive.with_suffix(".build.json").unlink()
    ver = servicio.verificar("probe_ie1_v68")
    assert not ver.ok and ver.incidencias[0].codigo == "USEARCH_DESINCRONIZADO"


def test_sin_registro_de_bigramas_construir_falla_claro_y_no_deja_nada(servicio, proyecto_sintetico, sin_bloqueo) -> None:
    solicitud = _base(proyecto_sintetico)  # NO se registran los bigramas: como en CI
    res = servicio.construir(solicitud)
    assert not res.ok
    assert res.incidencias[0].codigo == "USEARCH_SIN_DECODIFICADOR"  # código propio, no «desincronizado»
    assert "USEARCH_SIN_DECODIFICADOR" in res.incidencias[0].mensaje
    destino = Path(proyecto_sintetico.candidata("probe_ie1_v68"))
    assert not destino.exists(), "quedó un directorio de candidata a medias"
    # verificar e instalar dicen lo mismo en vez de dar por buena una candidata que no se puede comprobar
    base = servicio.verificar("probe_ie1_v67")
    assert not base.ok and "USEARCH_SIN_DECODIFICADOR" in base.incidencias[0].mensaje
    assert {i.codigo for i in base.incidencias} == {"USEARCH_SIN_DECODIFICADOR"}
    inst = servicio.instalar("probe_ie1_v67")
    assert not inst.ok and inst.incidencias[0].codigo == "USEARCH_SIN_DECODIFICADOR"


def test_una_build_sin_pares_usearch_no_necesita_work(servicio, proyecto_sintetico, sin_bloqueo) -> None:
    """Las builds de contrato (sin IE1/IE2/IE3) no cambian: nada que sincronizar ni decodificar."""
    base = Path(proyecto_sintetico.candidata("probe_ie1_v67"))
    base.mkdir(parents=True, exist_ok=True)
    escribir_fa(base / "archive.fa", FICHEROS)
    res = servicio.construir(
        SolicitudConstruccion(base="probe_ie1_v67", objetivos=(OBJETIVO,), capas=(), salida="probe_ie1_v68"))
    assert res.ok, [i.mensaje for i in res.incidencias]
    assert servicio.verificar("probe_ie1_v68").ok


def test_golden_se_evalua_antes_y_aparte_de_la_sincronia(servicio, proyecto_sintetico, sin_bloqueo, monkeypatch) -> None:
    """Una candidata histórica (anterior al hook) tiene usearch desincronizado: eso es OTRA incidencia y no puede
    ocultar el resultado del golden (ni al revés)."""
    from ie123kit.nucleo.compat import golden

    _registrar_bigramas(proyecto_sintetico.raiz)
    solicitud = _base(proyecto_sintetico)
    res = servicio.construir(solicitud, omitir_sincronia_usearch=True)
    assert res.ok

    monkeypatch.setattr(golden, "comprobar_grupo", lambda nombre, raiz=None: (2, ["distinto work/x/archive.fa"]))
    ver = servicio.verificar("probe_ie1_v68", golden=True)
    codigos = [i.codigo for i in ver.incidencias]
    assert not ver.ok
    assert "NOT_SUPPORTED" in codigos and "USEARCH_DESINCRONIZADO" in codigos  # las dos, no solo la segunda
    assert any(i.mensaje.startswith("golden: distinto") for i in ver.incidencias)

    # golden en verde + usearch desincronizado: sigue fallando, y solo por usearch
    monkeypatch.setattr(golden, "comprobar_grupo", lambda nombre, raiz=None: (2, []))
    ver = servicio.verificar("probe_ie1_v68", golden=True)
    assert not ver.ok and {i.codigo for i in ver.incidencias} == {"USEARCH_DESINCRONIZADO"}

    # golden en rojo + candidata sincronizada: falla solo por el golden
    ok = servicio.construir(SolicitudConstruccion(base="probe_ie1_v67", objetivos=(OBJETIVO,),
                                                  capas=solicitud.capas, salida="probe_ie1_v69"))
    assert ok.ok
    monkeypatch.setattr(golden, "comprobar_grupo", lambda nombre, raiz=None: (2, ["ausente work/y/archive.fa"]))
    ver = servicio.verificar("probe_ie1_v69", golden=True)
    assert not ver.ok and {i.codigo for i in ver.incidencias} == {"NOT_SUPPORTED"}
