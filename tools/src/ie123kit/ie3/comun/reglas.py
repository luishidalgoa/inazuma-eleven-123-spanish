"""Reglas y datos compartidos por las versiones de Inazuma Eleven 3.

`JuegoIE3` fija el patrón de los objetivos de IE3 (perfil de texto v20 bloqueado,
identidad leída de `activos.toml` y reglas de validación comunes) pero **no
implementa ninguna capacidad**: mientras `capacidades` esté vacío en el
`activos.toml` de la versión, exportar e importar devuelven `NOT_SUPPORTED`.
Las capacidades se abrirán cuando exista la extracción de esa versión; entonces
bastará con declararlas en `activos.toml` e implementar los ganchos
`_exportar_*`/`_importar_*` de `nucleo.juego.JuegoBase`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ie123kit.nucleo.juego import JuegoBase, Regla
from ie123kit.nucleo.tipos import AssetRef, CancelToken, Resultado

__all__ = ["CRO_PRINCIPAL", "JUEGO", "PREFIJOS_ROMFS", "REGLAS_COMUNES", "JuegoIE3"]

#: Identificador corto del juego al que pertenecen estas versiones.
JUEGO = "ie3"

#: Prefijos del archive.fa que se reparten las versiones de IE3 (sin auditar).
PREFIJOS_ROMFS = ("inazuma3/", "inazuma3_ogre/")

#: CRO principal compartida por las versiones de IE3.
CRO_PRINCIPAL = "cro/ina_main3ogre.cro"

#: Reglas de validación que declaran todos los objetivos de IE3.
REGLAS_COMUNES: tuple[Regla, ...] = (
    Regla(
        codigo="V20_BLOQUEADO",
        descripcion="La tipografía v20 está bloqueada para toda la recopilación.",
        ambito="texto",
    ),
    Regla(
        codigo="PENDIENTE_AUDITORIA",
        descripcion="El reparto de activos de IE3 está sin auditar: no hay extracción todavía.",
        ambito="objetivo",
    ),
)


class JuegoIE3(JuegoBase):
    """Base común de las versiones de IE3. Sin capacidades hasta que exista su extracción."""

    def _sin_extraccion(self, accion: str, ref: AssetRef) -> Resultado:
        """Respuesta uniforme mientras el objetivo no tiene capacidades declaradas."""
        return Resultado.no_soportado(
            f"{self.info().id}: todavía no hay extracción; no se puede {accion} "
            f"activos de tipo {ref.tipo!r}",
            activo_id=ref.id,
        )

    def exportar(
        self,
        ws: Any,
        ref: AssetRef,
        destino: Path,
        formato: str | None = None,
        progreso: Any = None,
        cancel: CancelToken | None = None,
    ) -> Resultado:
        """Exporta un activo; sin capacidades declaradas devuelve NOT_SUPPORTED."""
        if cancel is not None:
            cancel.comprobar()
        if not self.info().capacidades:
            return self._sin_extraccion("exportar", ref)
        return super().exportar(ws, ref, destino, formato=formato, progreso=progreso, cancel=cancel)

    def importar(
        self,
        ws: Any,
        ref: AssetRef,
        origen: Path,
        simular: bool = True,
        progreso: Any = None,
        cancel: CancelToken | None = None,
    ) -> Resultado:
        """Importa un activo; sin capacidades declaradas devuelve NOT_SUPPORTED."""
        if cancel is not None:
            cancel.comprobar()
        if not self.info().capacidades:
            return self._sin_extraccion("importar", ref)
        return super().importar(ws, ref, origen, simular=simular, progreso=progreso, cancel=cancel)

    def reglas_validacion(self) -> list[Regla]:
        """Reglas comunes a todas las versiones de IE3."""
        return list(REGLAS_COMUNES)
