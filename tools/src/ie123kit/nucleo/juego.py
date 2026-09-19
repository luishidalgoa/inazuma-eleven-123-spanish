"""Interfaz uniforme de un objetivo (juego/versión) de la recopilación.

`JuegoBase` define lo que la capa de servicio puede pedir a cualquier objetivo;
los paquetes `ie1`, `ie2/*` e `ie3/*` la implementan en F2.3. Este módulo no
importa juegos ni la capa de servicio.
"""

from __future__ import annotations

import abc
import shutil
import threading
import tomllib
from collections.abc import Callable, Container, Iterable, Mapping
from dataclasses import dataclass, field
from importlib.resources import files
from pathlib import Path
from types import MappingProxyType
from typing import Any, ClassVar

from ie123kit.nucleo.tipos import AssetRef, CancelToken, Progreso, Resultado

__all__ = [
    "CAPACIDADES",
    "CAPACIDAD_POR_TIPO",
    "Aportacion",
    "InfoObjetivo",
    "JuegoBase",
    "PerfilTexto",
    "Regla",
    "capacidad_de_tipo",
    "es_editable",
]

CAPACIDADES: tuple[str, ...] = (
    "graficos",
    "textos",
    "eventos",
    "literales_cro",
    "cinematicas",
    "voces",
)

#: Tipo de activo (vocabulario de `servicio.registro_activos.EXTENSIONES`: 'grafico',
#: 'texto', 'evento', 'literal_cro', 'cinematica', 'voz') -> capacidad que el objetivo
#: debe declarar en su `activos.toml` para poder tratarlo (vocabulario `CAPACIDADES`).
#: Es la ÚNICA traducción entre ambos vocabularios: no la dupliques en otras capas.
CAPACIDAD_POR_TIPO: Mapping[str, str] = MappingProxyType(
    {
        "grafico": "graficos",
        "texto": "textos",
        "evento": "eventos",
        "literal_cro": "literales_cro",
        "cinematica": "cinematicas",
        "voz": "voces",
    }
)


def capacidad_de_tipo(tipo: str) -> str | None:
    """Capacidad necesaria para tratar activos de ese `tipo` (None si no hay ninguna)."""
    return CAPACIDAD_POR_TIPO.get(tipo)


def es_editable(tipo: str, capacidades: Container[str]) -> bool:
    """True si `capacidades` incluye la capacidad que exige ese `tipo` de activo.

    Nunca compares `tipo` con las capacidades directamente: son vocabularios distintos
    y su intersección es vacía (el resultado saldría siempre False).
    """
    capacidad = capacidad_de_tipo(tipo)
    return capacidad is not None and capacidad in capacidades


@dataclass(frozen=True, slots=True)
class InfoObjetivo:
    """Identidad y alcance de un objetivo."""

    id: str
    nombre: str
    prefijos_romfs: tuple[str, ...]
    cros: tuple[str, ...]
    capacidades: frozenset[str]

    def to_json(self) -> dict[str, Any]:
        """Forma JSON de la información del objetivo."""
        return {
            "id": self.id,
            "nombre": self.nombre,
            "prefijos_romfs": list(self.prefijos_romfs),
            "cros": list(self.cros),
            "capacidades": sorted(self.capacidades),
        }


@dataclass(frozen=True, slots=True)
class PerfilTexto:
    """Perfil tipográfico aplicable. Hoy siempre `tipografia_v20`, bloqueado."""

    nombre: str
    bloqueado: bool
    fuentes: tuple[str, ...] = ()

    def to_json(self) -> dict[str, Any]:
        """Forma JSON del perfil."""
        return {"nombre": self.nombre, "bloqueado": self.bloqueado, "fuentes": list(self.fuentes)}


@dataclass(frozen=True, slots=True)
class Regla:
    """Regla de validación que un objetivo declara."""

    codigo: str
    descripcion: str
    ambito: str

    def to_json(self) -> dict[str, Any]:
        """Forma JSON de la regla."""
        return {"codigo": self.codigo, "descripcion": self.descripcion, "ambito": self.ambito}


@dataclass(slots=True)
class Aportacion:
    """Lo que un objetivo aporta a la construcción de una candidata."""

    entradas_fa: dict[str, bytes | Path] = field(default_factory=dict)
    eventos: dict[str, Path] = field(default_factory=dict)
    literales_cro: dict[str, dict] = field(default_factory=dict)
    romfs_sueltos: dict[str, Path] = field(default_factory=dict)


class JuegoBase(abc.ABC):
    """Base de todos los objetivos: lee su `activos.toml` y despacha por tipo de activo."""

    PAQUETE: str = ""

    #: tipo de activo -> capacidad que hay que declarar para poder tratarlo
    #: (alias de `CAPACIDAD_POR_TIPO`; la tabla vive a nivel de módulo, no aquí)
    _DESPACHO: ClassVar[Mapping[str, str]] = CAPACIDAD_POR_TIPO

    def __init__(self) -> None:
        self._datos: dict[str, Any] | None = None
        self._info: InfoObjetivo | None = None

    # ------------------------------------------------------------------ datos declarativos

    def datos_activos(self) -> dict[str, Any]:
        """Contenido de `activos.toml` del paquete del objetivo (cacheado)."""
        if self._datos is None:
            recurso = files(self.PAQUETE).joinpath("activos.toml")
            self._datos = tomllib.loads(recurso.read_text(encoding="utf-8"))
        return self._datos

    def info(self) -> InfoObjetivo:
        """Identidad y alcance del objetivo, leídos de `activos.toml`."""
        if self._info is None:
            datos = self.datos_activos()
            objetivo = datos.get("objetivo", {})
            romfs = datos.get("romfs", {})
            self._info = InfoObjetivo(
                id=objetivo.get("id", ""),
                nombre=objetivo.get("nombre", ""),
                prefijos_romfs=tuple(romfs.get("prefijos_fa", ())),
                cros=tuple(romfs.get("cros", ())),
                capacidades=frozenset(objetivo.get("capacidades", ())),
            )
        return self._info

    def perfil_texto(self, ambito: str | None = None) -> PerfilTexto:
        """Perfil tipográfico; el bloqueo v20 es de toda la recopilación."""
        del ambito
        nombre = self.datos_activos().get("objetivo", {}).get("perfil_texto", "tipografia_v20")
        return PerfilTexto(nombre=nombre, bloqueado=True)

    # ------------------------------------------------------------------ inventario

    def activos(
        self,
        ws: Any,
        tipo: str | None = None,
        filtro: Callable[[AssetRef], bool] | None = None,
    ) -> list[AssetRef]:
        """Activos del objetivo. Vacío hasta que cada juego lo implemente (F2.3)."""
        del ws, tipo, filtro
        return []

    # ------------------------------------------------------------------ despacho por tipo

    def _capacidad_de(self, ref: AssetRef) -> str | None:
        """Capacidad requerida por el tipo del activo, si está declarada."""
        capacidad = self._DESPACHO.get(ref.tipo)
        if capacidad is None or capacidad not in self.info().capacidades:
            return None
        return capacidad

    def exportar(
        self,
        ws: Any,
        ref: AssetRef,
        destino: Path,
        formato: str | None = None,
        progreso: Callable[[Progreso], None] | None = None,
        cancel: CancelToken | None = None,
    ) -> Resultado:
        """Exporta un activo a `destino`, delegando en el gancho de su capacidad."""
        if cancel is not None:
            cancel.comprobar()
        capacidad = self._capacidad_de(ref)
        if capacidad is None:
            return Resultado.no_soportado(
                f"{self.__class__.__name__} no exporta activos de tipo {ref.tipo!r}",
                activo_id=ref.id,
            )
        gancho = getattr(self, f"_exportar_{capacidad}", None)
        if gancho is None:
            return Resultado.no_soportado(f"falta el gancho _exportar_{capacidad}", activo_id=ref.id)
        return gancho(ws, ref, destino, formato=formato, progreso=progreso, cancel=cancel)

    def importar(
        self,
        ws: Any,
        ref: AssetRef,
        origen: Path,
        simular: bool = True,
        progreso: Callable[[Progreso], None] | None = None,
        cancel: CancelToken | None = None,
    ) -> Resultado:
        """Importa un activo desde `origen`, delegando en el gancho de su capacidad."""
        if cancel is not None:
            cancel.comprobar()
        capacidad = self._capacidad_de(ref)
        if capacidad is None:
            return Resultado.no_soportado(
                f"{self.__class__.__name__} no importa activos de tipo {ref.tipo!r}",
                activo_id=ref.id,
            )
        gancho = getattr(self, f"_importar_{capacidad}", None)
        if gancho is None:
            return Resultado.no_soportado(f"falta el gancho _importar_{capacidad}", activo_id=ref.id)
        # Las capas que el gancho crea (``_capa_creada``) se borran si la importación falla:
        # una importación fallida no deja carpetas de capa vacías o a medias en work/ (F2.5).
        previas = getattr(self._capas_en_curso, "lista", None)
        creadas: list[Path] = []
        self._capas_en_curso.lista = creadas
        try:
            res = gancho(ws, ref, origen, simular=simular, progreso=progreso, cancel=cancel)
        except BaseException:
            _borrar_capas(creadas)
            raise
        finally:
            self._capas_en_curso.lista = previas
        if not res.ok:
            _borrar_capas(creadas)
        return res

    #: Capas creadas por la importación en curso (una lista por hilo).
    _capas_en_curso = threading.local()

    def _capa_creada(self, carpeta: Path) -> Path:
        """Anota una carpeta de capa recién creada por la importación en curso y la devuelve."""
        lista = getattr(self._capas_en_curso, "lista", None)
        if lista is not None:
            lista.append(Path(carpeta))
        return carpeta

    # ------------------------------------------------------------------ ganchos por capacidad

    def _no_implementado(self, accion: str, capacidad: str, ref: AssetRef) -> Resultado:
        """Respuesta estándar de un gancho todavía sin implementar."""
        return Resultado.no_soportado(
            f"{self.__class__.__name__}: {accion} de {capacidad} sin implementar",
            activo_id=ref.id,
        )

    def _exportar_graficos(self, ws: Any, ref: AssetRef, destino: Path, **kw: Any) -> Resultado:
        """Gancho de exportación de gráficos (lo rellena cada juego)."""
        del ws, destino, kw
        return self._no_implementado("exportación", "graficos", ref)

    def _importar_graficos(self, ws: Any, ref: AssetRef, origen: Path, **kw: Any) -> Resultado:
        """Gancho de importación de gráficos."""
        del ws, origen, kw
        return self._no_implementado("importación", "graficos", ref)

    def _exportar_textos(self, ws: Any, ref: AssetRef, destino: Path, **kw: Any) -> Resultado:
        """Gancho de exportación de textos."""
        del ws, destino, kw
        return self._no_implementado("exportación", "textos", ref)

    def _importar_textos(self, ws: Any, ref: AssetRef, origen: Path, **kw: Any) -> Resultado:
        """Gancho de importación de textos."""
        del ws, origen, kw
        return self._no_implementado("importación", "textos", ref)

    def _exportar_eventos(self, ws: Any, ref: AssetRef, destino: Path, **kw: Any) -> Resultado:
        """Gancho de exportación de eventos."""
        del ws, destino, kw
        return self._no_implementado("exportación", "eventos", ref)

    def _importar_eventos(self, ws: Any, ref: AssetRef, origen: Path, **kw: Any) -> Resultado:
        """Gancho de importación de eventos."""
        del ws, origen, kw
        return self._no_implementado("importación", "eventos", ref)

    def _exportar_literales_cro(self, ws: Any, ref: AssetRef, destino: Path, **kw: Any) -> Resultado:
        """Gancho de exportación de literales de .cro."""
        del ws, destino, kw
        return self._no_implementado("exportación", "literales_cro", ref)

    def _importar_literales_cro(self, ws: Any, ref: AssetRef, origen: Path, **kw: Any) -> Resultado:
        """Gancho de importación de literales de .cro."""
        del ws, origen, kw
        return self._no_implementado("importación", "literales_cro", ref)

    def _exportar_cinematicas(self, ws: Any, ref: AssetRef, destino: Path, **kw: Any) -> Resultado:
        """Gancho de exportación de cinemáticas."""
        del ws, destino, kw
        return self._no_implementado("exportación", "cinematicas", ref)

    def _importar_cinematicas(self, ws: Any, ref: AssetRef, origen: Path, **kw: Any) -> Resultado:
        """Gancho de importación de cinemáticas."""
        del ws, origen, kw
        return self._no_implementado("importación", "cinematicas", ref)

    def _exportar_voces(self, ws: Any, ref: AssetRef, destino: Path, **kw: Any) -> Resultado:
        """Gancho de exportación de voces."""
        del ws, destino, kw
        return self._no_implementado("exportación", "voces", ref)

    def _importar_voces(self, ws: Any, ref: AssetRef, origen: Path, **kw: Any) -> Resultado:
        """Gancho de importación de voces."""
        del ws, origen, kw
        return self._no_implementado("importación", "voces", ref)

    # ------------------------------------------------------------------ construcción y validación

    def aportaciones(
        self,
        ws: Any,
        capas: Iterable[str] | Mapping[str, Any] | None = None,
        progreso: Callable[[Progreso], None] | None = None,
        cancel: CancelToken | None = None,
    ) -> Aportacion:
        """Lo que el objetivo aporta a una candidata. Vacío por defecto."""
        del ws, capas, progreso
        if cancel is not None:
            cancel.comprobar()
        return Aportacion()

    def reglas_validacion(self) -> list[Regla]:
        """Reglas de validación propias del objetivo. Vacío por defecto."""
        return []


def _borrar_capas(carpetas: Iterable[Path]) -> None:
    """Borra las carpetas de capa que dejó una importación fallida."""
    for carpeta in carpetas:
        shutil.rmtree(carpeta, ignore_errors=True)
