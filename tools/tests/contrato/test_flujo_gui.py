"""Cliente sin cabeza de referencia para la GUI (F2.5, #51): el ciclo completo de la API 1.0.

abrir → objetivos → activos → exportar → editar → importar(simular) → importar → construir →
verificar → instalar, sobre un proyecto sintético (sin ROM). Gate (1) de la F2.5: solo cambia la
entrada editada, el bloqueo tipográfico se comprueba (y pasa) sobre la candidata, y todos los
resultados y eventos serializan según sus esquemas.

El bloqueo real necesita las fuentes aprobadas del juego, que un proyecto sintético no tiene: aquí se
sustituye por un registrador que exige que se llame con la candidata nueva. El mismo ciclo con el
bloqueo real está en ``tests/requiere_rom/test_flujo_gui_real.py``.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import pytest
from juego_falso import FICHEROS, OBJETIVO, JuegoFalso

from ie123kit.nucleo import util
from ie123kit.nucleo.contenedores.fa import FaArchive
from ie123kit.nucleo.juego import Aportacion
from ie123kit.nucleo.tipos import Progreso, Resultado
from ie123kit.servicio import contrato, esquemas
from ie123kit.servicio.api import ServicioToolkit, SolicitudConstruccion, descubrir_juegos
from ie123kit.servicio.trabajos import Trabajos


class JuegoGui(JuegoFalso):
    """JuegoFalso cuya importación confirmada crea una capa ``gui_*`` y la aporta a ``construir``."""

    def _capas(self, ws: Any) -> Path:
        return Path(ws.work) / OBJETIVO / "capas" / "graficos"

    def importar(self, ws, ref, origen, simular=True, progreso=None, cancel=None) -> Resultado:
        res = super().importar(ws, ref, origen, simular=True, progreso=progreso, cancel=cancel)
        if simular or not res.ok:
            return res
        capa = self._capas(ws) / f"gui_{len(list(self._capas(ws).glob('gui_*'))) + 1:03d}"
        destino = capa / "extra" / res.datos["diff"]["ruta_romfs"]
        destino.parent.mkdir(parents=True)
        (capa / "capa.toml").write_text(f'[capa]\nobjetivo = "{OBJETIVO}"\ntema = "graficos"\n', encoding="utf-8")
        destino.write_bytes(Path(origen).read_bytes())
        if progreso is not None:
            progreso(Progreso("importar", 2, 2, "capa creada"))
        return Resultado.correcto(datos={"simulado": False, "capa": str(capa), "diff": res.datos["diff"]},
                                  artefactos=(str(destino),))

    def aportaciones(self, ws, capas: Iterable[str] | None = None, progreso=None, cancel=None) -> Aportacion:
        entradas = {}
        for capa in sorted(self._capas(ws).glob("gui_*")):
            extra = capa / "extra"
            for f in sorted(extra.rglob("*")):
                if f.is_file():
                    entradas[f.relative_to(extra).as_posix()] = f
        return Aportacion(entradas_fa=entradas)


@pytest.fixture
def cliente(proyecto_sintetico, tmp_path, monkeypatch):
    """Servicio con el JuegoGui, eventos a JSONL y Azahar y el bloqueo sustituidos."""
    from ie123kit.nucleo.construir import instalar
    from ie123kit.nucleo.validar import bloqueo

    llamadas: list[Path] = []
    monkeypatch.setattr(bloqueo, "comprobar", lambda archive, raiz=None: llamadas.append(Path(archive)))
    monkeypatch.setattr(instalar, "_azahar_en_ejecucion", lambda: False)
    ws = type(proyecto_sintetico).abrir(proyecto_sintetico.raiz, entorno={"IE123_AZAHAR": str(tmp_path / "mods")})
    trabajos = Trabajos(dir_eventos=tmp_path / "eventos", max_hilos=1)
    servicio = ServicioToolkit(ws, juegos=descubrir_juegos(extra={OBJETIVO: JuegoGui()}), trabajos=trabajos)
    yield servicio, llamadas, tmp_path
    trabajos.cerrar()


def _ok(metodo: str, res: Resultado) -> dict:
    assert res.ok, res.incidencias
    datos = res.to_json()
    json.dumps(datos, ensure_ascii=False)
    assert contrato.validar_resultado(metodo, res) == []
    return datos["datos"]


def test_ciclo_gui_completo(cliente) -> None:
    servicio, bloqueos, tmp = cliente
    eventos: list[Progreso] = []
    assert contrato.compatible(servicio.API_VERSION) and servicio.API_VERSION == "1.0"

    objetivos = _ok("objetivos", servicio.objetivos(progreso=eventos.append))
    assert OBJETIVO in [o["id"] for o in objetivos["objetivos"]]
    activo = next(a for a in _ok("activos", servicio.activos(OBJETIVO))["activos"]
                  if a["ruta_romfs"] == "falso/dos.bin")

    res = servicio.exportar(OBJETIVO, [activo["id"]], tmp / "exportado", progreso=eventos.append)
    _ok("exportar", res)
    fichero = Path(res.artefactos[0])
    fichero.write_bytes(b"DOS" + fichero.read_bytes()[3:])          # «editar»: 3 bytes, mismo tamaño

    antes = util.sha256_arbol(servicio.ws.raiz)
    simulado = _ok("importar", servicio.importar(OBJETIVO, activo["id"], fichero, simular=True))
    assert simulado["simulado"] is True
    assert util.sha256_arbol(servicio.ws.raiz) == antes, "simular no puede escribir"

    importado = _ok("importar", servicio.importar(OBJETIVO, activo["id"], fichero, simular=False,
                                                  progreso=eventos.append))
    assert Path(importado["capa"]).name.startswith("gui_")

    base = servicio.ws.work / "shared" / "base_3ds" / "romfs"
    solicitud = SolicitudConstruccion(base=str(base), objetivos=(OBJETIVO,), capas=(), salida="probe_ie1_v2")
    construida = _ok("construir", servicio.construir(solicitud, progreso=eventos.append))
    archive = Path(construida["archive"])
    assert bloqueos == [archive], "el bloqueo se comprueba siempre sobre la candidata nueva"
    a, b = FaArchive(str(base / "archive.fa")), FaArchive(str(archive))
    distintas = [p for p, o, s in a.entries if a.file_bytes(o, s) != b.read(p)]
    assert distintas == ["falso/dos.bin"], "solo cambia la entrada editada"
    assert b.read("falso/dos.bin") == b"DOS" + FICHEROS["falso/dos.bin"][3:]

    verificada = _ok("verificar", servicio.verificar("probe_ie1_v2"))
    assert verificada["bloqueo_v20"] == "ok" and verificada["archive_sha256"] == construida["archive_sha256"]

    instalada = _ok("instalar", servicio.instalar("probe_ie1_v2"))
    assert Path(instalada["destino"]).is_relative_to(tmp / "mods")
    assert (Path(instalada["destino"]) / "archive.fa").is_file()

    assert eventos
    for p in eventos:
        assert esquemas.validar(p.to_json(), "progreso") == [], p


def test_trabajo_en_segundo_plano_emite_eventos_segun_esquema(cliente) -> None:
    servicio, _, tmp = cliente
    activo = servicio.activos(OBJETIVO).datos["activos"][0]
    res = servicio.enviar_trabajo("exportar", objetivo=OBJETIVO, ids=[activo["id"]], destino=tmp / "bg")
    assert res.ok
    trabajo = servicio.trabajos.esperar(res.datos["trabajo"], timeout=30)
    assert str(trabajo.estado) == "hecho"
    lineas = [json.loads(x) for x in (tmp / "eventos" / f"{res.datos['trabajo']}.jsonl")
              .read_text(encoding="utf-8").splitlines() if x.strip()]
    assert lineas
    for linea in lineas:
        assert esquemas.validar(linea, "evento_trabajo") == [], linea


@pytest.mark.parametrize("nombre", esquemas.TODOS)
def test_los_ejemplos_publicados_validan(nombre: str) -> None:
    ejemplos = esquemas.ejemplos(nombre)
    assert ejemplos, f"{nombre}: el esquema publicado no trae ejemplos"
    for ejemplo in ejemplos:
        assert esquemas.validar(ejemplo, nombre) == []


def test_contrato_cubre_el_ciclo_de_la_gui() -> None:
    for metodo, info in contrato.METODOS.items():
        assert hasattr(ServicioToolkit, metodo), metodo
        assert info.esquema_datos in esquemas.DATOS
    assert contrato.compatible("1.0") and contrato.compatible("1.0", "1.3")
    assert not contrato.compatible("1.2", "1.0") and not contrato.compatible("0.1") and not contrato.compatible("x")
