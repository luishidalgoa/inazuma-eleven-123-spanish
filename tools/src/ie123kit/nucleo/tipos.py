"""Tipos del contrato de ie123kit: lo que viaja entre el núcleo, el servicio y la CLI/GUI.

Todas las dataclases son congeladas y se serializan con `to_json()`; los campos
opcionales con valor None se omiten y las tuplas salen como listas.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any

from ie123kit import API_VERSION
from ie123kit.nucleo.errores import CanceladoError

__all__ = [
    "API_VERSION",
    "CODIGOS",
    "CONTENEDORES",
    "ESTADOS",
    "ORIGENES",
    "SEVERIDADES",
    "AssetRef",
    "CancelToken",
    "Incidencia",
    "Progreso",
    "Rect",
    "Resultado",
    "componer_id",
    "partir_id",
]

CODIGOS: frozenset[str] = frozenset(
    {
        "TAMANO_PNG",
        "RECT_QNA",
        "GLIFO_NO_SOPORTADO",
        "EXCEDE_PX",
        "EXCEDE_BYTES",
        "BLOQUEO_V20",
        "NF_HUERFANO",
        "PAGINAS_DISTINTAS",
        "CRO_FUERA_DE_RANGO",
        "LAYOUT_MOFLEX",
        "HERRAMIENTA_AUSENTE",
        "NOT_SUPPORTED",
        "CONTENIDO_EN_GIT",
        "GATE_FALLIDO",
    }
)

SEVERIDADES: tuple[str, ...] = ("error", "aviso", "info")
ESTADOS: tuple[str, ...] = ("original", "editado", "traducido", "construido")
ORIGENES: tuple[str, ...] = ("3ds_jp", "3ds_eu", "nds_es", "manual")
CONTENEDORES: tuple[str, ...] = ("fa", "sszl", "arcv", "ctpk")


def _exigir(valor: str, permitidos: tuple[str, ...] | frozenset[str], campo: str) -> None:
    """Lanza ValueError si `valor` no pertenece al vocabulario cerrado `permitidos`."""
    if valor not in permitidos:
        raise ValueError(f"{campo} inválido: {valor!r}; permitidos: {sorted(permitidos)}")


@dataclass(frozen=True, slots=True)
class Rect:
    """Rectángulo de una zona editable de una imagen."""

    x0: int
    y0: int
    x1: int
    y1: int
    parte: str

    def to_json(self) -> dict[str, Any]:
        """Forma JSON del rectángulo."""
        return {"x0": self.x0, "y0": self.y0, "x1": self.x1, "y1": self.y1, "parte": self.parte}


@dataclass(frozen=True, slots=True)
class Incidencia:
    """Hallazgo de una operación o de una validación, con código estable."""

    codigo: str
    severidad: str = "error"
    mensaje: str = ""
    activo_id: str | None = None
    ruta: str | None = None
    ubicacion: str | None = None
    pista: str | None = None

    def __post_init__(self) -> None:
        _exigir(self.codigo, CODIGOS, "codigo")
        _exigir(self.severidad, SEVERIDADES, "severidad")

    def to_json(self) -> dict[str, Any]:
        """Forma JSON; omite los campos opcionales sin valor."""
        datos: dict[str, Any] = {
            "codigo": self.codigo,
            "severidad": self.severidad,
            "mensaje": self.mensaje,
        }
        for nombre in ("activo_id", "ruta", "ubicacion", "pista"):
            valor = getattr(self, nombre)
            if valor is not None:
                datos[nombre] = valor
        return datos


def componer_id(objetivo: str, tipo: str, ruta_romfs: str, subruta: str | None = None) -> str:
    """Identificador estable de un activo: `objetivo:tipo:ruta_romfs[#subruta]`."""
    base = f"{objetivo}:{tipo}:{ruta_romfs}"
    return f"{base}#{subruta}" if subruta else base


def partir_id(identificador: str) -> tuple[str, str, str, str | None]:
    """Inverso de `componer_id`: (objetivo, tipo, ruta_romfs, subruta)."""
    objetivo, sep1, resto = identificador.partition(":")
    tipo, sep2, cola = resto.partition(":")
    if not sep1 or not sep2 or not objetivo or not tipo or not cola:
        raise ValueError(f"identificador de activo inválido: {identificador!r}")
    ruta_romfs, sep3, subruta = cola.partition("#")
    return objetivo, tipo, ruta_romfs, (subruta if sep3 else None)


@dataclass(frozen=True, slots=True)
class AssetRef:
    """Referencia a un activo del juego; nunca lleva contenido extraído (Norma 2)."""

    id: str
    objetivo: str
    tipo: str
    ruta_romfs: str
    cadena_contenedores: tuple[str, ...] = ()
    subruta: str | None = None
    rects: tuple[Rect, ...] | None = None
    tamano: int = 0
    editable: bool = False
    estado: str = "original"
    origen: str = "3ds_jp"
    vista_previa: str | None = None
    sha256: str | None = None

    def __post_init__(self) -> None:
        _exigir(self.estado, ESTADOS, "estado")
        _exigir(self.origen, ORIGENES, "origen")
        for contenedor in self.cadena_contenedores:
            _exigir(contenedor, CONTENEDORES, "contenedor")
        esperado = componer_id(self.objetivo, self.tipo, self.ruta_romfs, self.subruta)
        if self.id != esperado:
            raise ValueError(f"id incoherente: {self.id!r}; se esperaba {esperado!r}")

    def to_json(self) -> dict[str, Any]:
        """Forma JSON; omite los campos opcionales sin valor."""
        datos: dict[str, Any] = {
            "id": self.id,
            "objetivo": self.objetivo,
            "tipo": self.tipo,
            "ruta_romfs": self.ruta_romfs,
            "cadena_contenedores": list(self.cadena_contenedores),
            "tamano": self.tamano,
            "editable": self.editable,
            "estado": self.estado,
            "origen": self.origen,
        }
        if self.subruta is not None:
            datos["subruta"] = self.subruta
        if self.rects is not None:
            datos["rects"] = [r.to_json() for r in self.rects]
        if self.vista_previa is not None:
            datos["vista_previa"] = self.vista_previa
        if self.sha256 is not None:
            datos["sha256"] = self.sha256
        return datos


@dataclass(frozen=True, slots=True)
class Resultado:
    """Salida uniforme de toda operación del toolkit."""

    ok: bool
    datos: dict[str, Any] = field(default_factory=dict)
    incidencias: tuple[Incidencia, ...] = ()
    artefactos: tuple[str, ...] = ()
    duracion_s: float = 0.0
    api_version: str = API_VERSION

    @classmethod
    def correcto(cls, datos: dict[str, Any] | None = None, **kw: Any) -> Resultado:
        """Resultado satisfactorio."""
        return cls(ok=True, datos=dict(datos or {}), **kw)

    @classmethod
    def fallo(cls, incidencias: tuple[Incidencia, ...] | list[Incidencia], **kw: Any) -> Resultado:
        """Resultado fallido con las incidencias dadas."""
        return cls(ok=False, incidencias=tuple(incidencias), **kw)

    @classmethod
    def no_soportado(cls, mensaje: str, activo_id: str | None = None, **kw: Any) -> Resultado:
        """Operación aún no implementada o no aplicable a este objetivo."""
        return cls.fallo([Incidencia("NOT_SUPPORTED", "error", mensaje, activo_id=activo_id)], **kw)

    def to_json(self) -> dict[str, Any]:
        """Forma JSON del resultado."""
        return {
            "ok": self.ok,
            "datos": self.datos,
            "incidencias": [i.to_json() for i in self.incidencias],
            "artefactos": list(self.artefactos),
            "duracion_s": self.duracion_s,
            "api_version": self.api_version,
        }


@dataclass(frozen=True, slots=True)
class Progreso:
    """Avance de una fase de un trabajo."""

    fase: str
    actual: int
    total: int
    mensaje: str = ""

    def __post_init__(self) -> None:
        if self.actual < 0:
            raise ValueError(f"actual negativo: {self.actual}")
        if self.total < 0:
            raise ValueError(f"total negativo: {self.total}")
        if self.total > 0 and self.actual > self.total:
            raise ValueError(f"actual ({self.actual}) mayor que total ({self.total})")

    def to_json(self) -> dict[str, Any]:
        """Forma JSON del progreso."""
        return {"fase": self.fase, "actual": self.actual, "total": self.total, "mensaje": self.mensaje}


class CancelToken:
    """Testigo de cancelación seguro entre hilos."""

    __slots__ = ("_evento",)

    def __init__(self) -> None:
        self._evento = threading.Event()

    def cancelar(self) -> None:
        """Marca el trabajo como cancelado."""
        self._evento.set()

    @property
    def cancelado(self) -> bool:
        """True si ya se ha pedido la cancelación."""
        return self._evento.is_set()

    def comprobar(self) -> None:
        """Lanza `CanceladoError` si se ha pedido la cancelación."""
        if self._evento.is_set():
            raise CanceladoError("El trabajo se ha cancelado")

    def to_json(self) -> dict[str, Any]:
        """Forma JSON del testigo."""
        return {"cancelado": self.cancelado}
