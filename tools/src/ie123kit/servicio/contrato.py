"""Contrato estable de la API de servicio 1.0 para la GUI (F2.5, #51).

La GUI solo habla con :class:`ie123kit.servicio.api.ServicioToolkit`. Este módulo fija lo que puede dar
por supuesto:

- :data:`API_VERSION` sigue versionado semántico: la GUI abre un proyecto si :func:`compatible` con su
  versión (misma versión mayor y menor del servicio >= la suya). Una versión menor solo AÑADE métodos,
  parámetros opcionales o campos de ``datos``; quitar o cambiar algo es una versión mayor.
- :data:`METODOS` describe los métodos del ciclo abrir → objetivos → activos → exportar → editar →
  importar(simular) → importar → construir → verificar → instalar: qué esquema tiene su ``datos``, si
  escribe en disco y si admite cancelación.
- Los ``TypedDict`` ``Datos*`` son los tipos de ``Resultado.datos`` de cada método (los mismos campos
  obligatorios que sus esquemas ``datos_*.schema.json``).
- :func:`validar_resultado` comprueba un ``Resultado`` (o su JSON) contra ``resultado.schema.json`` y,
  si es correcto, su ``datos`` contra el esquema del método.

Documentación: ``docs/toolkit/API_SERVICIO.md``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TypedDict

from ie123kit.nucleo.tipos import API_VERSION
from ie123kit.servicio import esquemas

__all__ = [
    "API_VERSION",
    "CICLO_GUI",
    "METODOS",
    "DatosActivos",
    "DatosConstruir",
    "DatosExportar",
    "DatosImportar",
    "DatosInstalar",
    "DatosObjetivos",
    "DatosVerificar",
    "Metodo",
    "compatible",
    "validar_resultado",
]


@dataclass(frozen=True)
class Metodo:
    """Un método público de ``ServicioToolkit`` que devuelve ``Resultado``."""

    nombre: str
    esquema_datos: str | None
    escribe: bool
    simulable: bool = False
    descripcion: str = ""


METODOS: dict[str, Metodo] = {m.nombre: m for m in (
    Metodo("objetivos", "datos_objetivos", False, descripcion="Objetivos habilitados del proyecto."),
    Metodo("activos", "datos_activos", False, descripcion="Activos de un objetivo (filtro por tipo o texto)."),
    Metodo("exportar", "datos_exportar", True,
           descripcion="Vuelca activos a ficheros editables (PNG, TSV, JSON…) fuera de work/<objetivo>/capas."),
    Metodo("importar", "datos_importar", True, simulable=True,
           descripcion="Valida un fichero editado; sin simular crea una capa nueva gui_*/ con capa.toml."),
    Metodo("construir", "datos_construir", True,
           descripcion="Construye una candidata nueva (base + capas); el bloqueo tipográfico siempre se comprueba."),
    Metodo("verificar", "datos_verificar", False, descripcion="Bloqueo tipográfico y hashes de una candidata."),
    Metodo("instalar", "datos_instalar", True, descripcion="Copia la candidata a los mods de Azahar (LayeredFS)."),
)}

#: Orden del ciclo de edición de la GUI (``editar`` ocurre fuera del servicio, en el fichero exportado).
CICLO_GUI: tuple[str, ...] = ("abrir", "objetivos", "activos", "exportar", "editar", "importar(simular)",
                              "importar", "construir", "verificar", "instalar")


def _partes(version: str) -> tuple[int, int]:
    mayor, _, menor = str(version).partition(".")
    return int(mayor), int(menor or 0)


def compatible(version_cliente: str, version_servicio: str = API_VERSION) -> bool:
    """¿Puede un cliente escrito para ``version_cliente`` usar este servicio?"""
    try:
        cm, cn = _partes(version_cliente)
        sm, sn = _partes(version_servicio)
    except ValueError:
        return False
    return cm == sm and sn >= cn


def validar_resultado(metodo: str, resultado: Any) -> list[str]:
    """Errores de esquema de un ``Resultado`` (objeto o JSON) devuelto por ``metodo``."""
    datos = resultado.to_json() if hasattr(resultado, "to_json") else resultado
    errores = esquemas.validar(datos, "resultado")
    if datos.get("api_version") != API_VERSION:
        errores.append(f"api_version {datos.get('api_version')!r} != {API_VERSION!r}")
    info = METODOS.get(metodo)
    if info is None:
        errores.append(f"método desconocido en el contrato: {metodo!r}")
        return errores
    if datos.get("ok") and info.esquema_datos is not None:
        errores += [f"datos.{e}" for e in esquemas.validar(datos.get("datos", {}), info.esquema_datos)]
    return errores


# --------------------------------------------------------------------------- tipos de ``datos``


class _InfoObjetivo(TypedDict):
    id: str
    nombre: str
    prefijos_romfs: list[str]
    cros: list[str]
    capacidades: list[str]


class DatosObjetivos(TypedDict):
    objetivos: list[_InfoObjetivo]


class DatosActivos(TypedDict):
    activos: list[dict[str, Any]]


class DatosExportar(TypedDict):
    exportados: list[str]


class DatosImportar(TypedDict, total=False):
    simulado: bool          # siempre presente
    capa: str               # capa gui_* creada (sin simular)
    diff: dict[str, Any] | list[dict[str, Any]]


class DatosConstruir(TypedDict):
    archive: str
    archive_sha256: str
    cro: str | None
    cros: list[str]
    build_json: str
    candidata: str
    informe: dict[str, Any]


class DatosVerificar(TypedDict, total=False):
    candidata: str
    archive: str
    bloqueo_v20: str
    archive_sha256: str
    archive_sha256_esperado: str
    golden: dict[str, Any]


class DatosInstalar(TypedDict, total=False):
    candidata: str
    emulador: str
    destino: str
    ficheros: list[dict[str, Any]]
    runtime_verified: bool
