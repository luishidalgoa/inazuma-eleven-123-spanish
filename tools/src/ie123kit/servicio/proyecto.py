"""Workspace: raíz, configuración del proyecto y rutas de trabajo por objetivo.

Lee ``ie123.toml`` (versionado, sin rutas locales ni secretos) y
``ie123.local.toml`` (ignorado por git, con rutas de la máquina). La precedencia
es: flags de CLI > variables ``IE123_*`` > ie123.local.toml > ie123.toml >
valores por defecto.
"""

from __future__ import annotations

import os
import re
import shutil
import tomllib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ie123kit.nucleo import util
from ie123kit.nucleo.config.raiz import find_root
from ie123kit.nucleo.errores import ValidacionError
from ie123kit.nucleo.tipos import Incidencia, Resultado

__all__ = ["DirsObjetivo", "ManifiestoCandidata", "Workspace"]

# Nombre de las carpetas comunes de ie2/ie3 dentro de work/ (docs/ARQUITECTURA.md).
_COMUN_EN_WORK = "shared"

_VARIABLES = {
    "IE123_AZAHAR": ("azahar", "mods_dir"),
    "IE123_FUENTE_TTF": ("fuentes", "ttf_ui"),
    "IE123_HERRAMIENTAS": ("herramientas", "dir"),
}

_PATRON_DEFECTO = "probe_ie1_v{n}"


def _leer_toml(ruta: Path) -> dict[str, Any]:
    if not ruta.is_file():
        return {}
    with ruta.open("rb") as fh:
        return tomllib.load(fh)


def _valor_toml(valor: Any) -> str:
    """Literal TOML de un valor simple (cadena, ruta, bool, número o lista de esos)."""
    if isinstance(valor, bool):
        return "true" if valor else "false"
    if isinstance(valor, (int, float)):
        return str(valor)
    if isinstance(valor, (list, tuple)):
        return "[" + ", ".join(_valor_toml(v) for v in valor) + "]"
    texto = str(valor).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{texto}"'


def _volcar_toml(datos: Mapping[str, Any]) -> str:
    """Vuelca un TOML plano de secciones (`[seccion] clave = valor`).

    No hay `tomllib.dumps` en la biblioteca estándar y `ie123.local.toml` solo guarda
    rutas y ajustes simples: no se añade una dependencia por esto.
    """
    lineas = ["# Generado por `ie123 proyecto init`. Rutas de ESTA máquina; git lo ignora.",
              "# Nunca contenido extraído de una ROM (Norma 2): solo rutas.", ""]
    _volcar_tabla(datos, (), lineas)
    return "\n".join(lineas).rstrip("\n") + "\n"


def _volcar_tabla(datos: Mapping[str, Any], prefijo: tuple[str, ...], lineas: list[str]) -> None:
    """Vuelca una tabla TOML y, después, sus subtablas (`[a]`, `[a.b]`…)."""
    if prefijo:
        lineas.append("[" + ".".join(prefijo) + "]")
    for clave, valor in datos.items():
        if not isinstance(valor, dict):
            lineas.append(f"{clave} = {_valor_toml(valor)}")
    if prefijo:
        lineas.append("")
    for clave, valor in datos.items():
        if isinstance(valor, dict):
            _volcar_tabla(valor, (*prefijo, clave), lineas)


def _en(d: dict[str, Any], camino: tuple[str, ...]) -> Any:
    actual: Any = d
    for parte in camino:
        if not isinstance(actual, dict) or parte not in actual:
            return None
        actual = actual[parte]
    return actual


def _fijar(d: dict[str, Any], camino: tuple[str, ...], valor: Any) -> None:
    actual = d
    for parte in camino[:-1]:
        hijo = actual.get(parte)
        if not isinstance(hijo, dict):
            hijo = {}
            actual[parte] = hijo
        actual = hijo
    actual[camino[-1]] = valor


@dataclass(frozen=True)
class DirsObjetivo:
    """Carpetas de trabajo de un objetivo (juego o recopilación)."""

    raiz: Path
    capas: Path
    qa: Path
    exportaciones: Path
    registro: Path
    #: Histórico de capas antiguas que tocan el objetivo (hoy solo `juego_principal`).
    historico: Path = Path("historico.json")


@dataclass(frozen=True)
class Workspace:
    """Raíz del repositorio más la configuración fusionada del proyecto."""

    raiz: Path
    proyecto: dict[str, Any] = field(default_factory=dict)
    local: dict[str, Any] = field(default_factory=dict)

    # -- apertura ---------------------------------------------------------
    @classmethod
    def abrir(
        cls,
        raiz: str | os.PathLike[str] | None = None,
        *,
        entorno: dict[str, str] | None = None,
    ) -> Workspace:
        """Abre el workspace; ``entorno`` es inyectable para los tests."""
        entorno = dict(os.environ if entorno is None else entorno)
        base = Path(raiz).resolve() if raiz is not None else find_root()
        proyecto = _leer_toml(base / "ie123.toml")
        local = _leer_toml(base / "ie123.local.toml")
        for variable, camino in _VARIABLES.items():
            valor = entorno.get(variable)
            if valor:
                _fijar(local, camino, valor)
        return cls(raiz=base, proyecto=proyecto, local=local)

    # -- rutas base -------------------------------------------------------
    @property
    def work(self) -> Path:
        return self.raiz / "work"

    @property
    def translation(self) -> Path:
        return self.raiz / "translation"

    @property
    def candidatas(self) -> Path:
        return self.work / "shared" / "candidatas"

    @property
    def verificacion(self) -> Path:
        return self.work / "shared" / "verificacion"

    # -- objetivos --------------------------------------------------------
    def _raiz_objetivo(self, objetivo: str) -> Path:
        partes = objetivo.split(".")
        if len(partes) == 1:
            if partes[0] in {"juego_principal", "ie1"}:
                return self.work / partes[0]
        elif len(partes) == 2 and partes[0] in {"ie2", "ie3"} and partes[1]:
            sub = _COMUN_EN_WORK if partes[1] == "comun" else partes[1]
            return self.work / partes[0] / sub
        raise ValidacionError(
            "OBJETIVO_DESCONOCIDO",
            detalle=f"objetivo '{objetivo}'; válidos: juego_principal, ie1, ie2.<version>, ie3.<version>, ie2.comun, ie3.comun",
        )

    def dirs(self, objetivo: str) -> DirsObjetivo:
        """Carpetas del objetivo. No crea nada."""
        base = self._raiz_objetivo(objetivo)
        return DirsObjetivo(
            raiz=base,
            capas=base / "capas",
            qa=base / "qa",
            exportaciones=base / "exportaciones",
            registro=base / "registro.json",
            historico=base / "historico.json",
        )

    def preparar(self, objetivo: str) -> DirsObjetivo:
        """Crea capas/qa/exportaciones del objetivo (idempotente)."""
        d = self.dirs(objetivo)
        for carpeta in (d.capas, d.qa, d.exportaciones):
            carpeta.mkdir(parents=True, exist_ok=True)
        return d

    def dir_traduccion(self, objetivo: str) -> Path:
        """Carpeta de `translation/` del objetivo (`ie2.comun` -> `translation/ie2/shared`)."""
        partes = objetivo.split(".")
        if len(partes) == 2:
            sub = _COMUN_EN_WORK if partes[1] == "comun" else partes[1]
            return self.translation / partes[0] / sub
        return self.translation / objetivo

    def preparar_todo(self, objetivos: Iterable[str]) -> list[Path]:
        """Crea `work/<objetivo>/{capas,qa,exportaciones}` y `translation/<objetivo>/`.

        Idempotente: devuelve SOLO las carpetas que ha tenido que crear, para que
        `ServicioToolkit.init` pueda decir qué ha cambiado y qué ya estaba.
        """
        creadas: list[Path] = []
        for objetivo in objetivos:
            d = self.dirs(objetivo)
            for carpeta in (d.capas, d.qa, d.exportaciones, self.dir_traduccion(objetivo)):
                if not carpeta.is_dir():
                    creadas.append(carpeta)
                carpeta.mkdir(parents=True, exist_ok=True)
        return creadas

    # -- configuración local ----------------------------------------------
    @property
    def ruta_local(self) -> Path:
        """`ie123.local.toml`: rutas de la máquina, ignorado por git (nunca contenido de ROM)."""
        return self.raiz / "ie123.local.toml"

    def escribir_local(self, ajustes: Mapping[str, Mapping[str, Any]]) -> Path:
        """Fusiona `ajustes` en `ie123.local.toml` (sección -> clave -> valor) y lo reescribe.

        Solo se guardan RUTAS, jamás contenido extraído (Norma 2). Las claves que no
        aparecen en `ajustes` se conservan tal cual.
        """
        actual = _leer_toml(self.ruta_local)
        for seccion, valores in ajustes.items():
            destino = actual.get(seccion)
            if not isinstance(destino, dict):
                destino = {}
                actual[seccion] = destino
            for clave, valor in valores.items():
                if valor is not None:
                    destino[clave] = valor
        self.ruta_local.write_text(_volcar_toml(actual), encoding="utf-8")
        # El Workspace ya abierto tiene que ver lo que se acaba de escribir.
        for seccion, valores in actual.items():
            if not isinstance(valores, dict):
                continue
            previo = self.local.get(seccion)
            if not isinstance(previo, dict):
                previo = {}
                self.local[seccion] = previo
            previo.update(valores)
        return self.ruta_local

    def objetivos_habilitados(self) -> tuple[str, ...]:
        valor = _en(self.proyecto, ("objetivos", "habilitados"))
        if not isinstance(valor, list):
            return ()
        return tuple(str(v) for v in valor)

    # -- candidatas -------------------------------------------------------
    @property
    def patron_candidata(self) -> str:
        valor = self.ajuste("candidatas.patron", _PATRON_DEFECTO)
        return str(valor)

    def nombre_candidata(self, n: int) -> str:
        return self.patron_candidata.format(n=n)

    def candidata(self, nombre: str) -> Path:
        return self.candidatas / nombre

    def _regex_candidata(self) -> re.Pattern[str]:
        partes = self.patron_candidata.split("{n}")
        return re.compile("^" + r"(\d+)".join(re.escape(p) for p in partes) + "$")

    def listar_candidatas(self) -> list[str]:
        """Nombres de candidatas existentes, ordenados por su número (v9 antes que v67)."""
        carpeta = self.candidatas
        if not carpeta.is_dir():
            return []
        rx = self._regex_candidata()
        hallados: list[tuple[int, str]] = []
        for hijo in carpeta.iterdir():
            if not hijo.is_dir():
                continue
            m = rx.match(hijo.name)
            if m:
                hallados.append((int(m.group(1)), hijo.name))
        return [nombre for _, nombre in sorted(hallados)]

    def golden(self) -> tuple[str, ...]:
        valor = self.ajuste("candidatas.golden", ())
        if not isinstance(valor, (list, tuple)):
            return ()
        return tuple(str(v) for v in valor)

    def dir_manifiestos_golden(self) -> Path:
        rel = self.ajuste("golden.manifiestos", "tools/tests/compat/golden")
        return self.raiz / str(rel)

    # -- ajustes genéricos ------------------------------------------------
    def ajuste(self, ruta_punteada: str, defecto: Any = None) -> Any:
        """Devuelve un ajuste resolviendo local > proyecto > defecto."""
        camino = tuple(ruta_punteada.split("."))
        for origen in (self.local, self.proyecto):
            valor = _en(origen, camino)
            if valor is not None:
                return valor
        return defecto

    # -- diagnóstico ------------------------------------------------------
    def doctor(self) -> Resultado:
        """Comprueba el entorno local sin red y sin exigir ROM. Nunca lanza."""
        incidencias: list[Incidencia] = []
        datos: dict[str, Any] = {
            "raiz": str(self.raiz),
            "raiz_existe": self.raiz.is_dir(),
            "ie123_toml": (self.raiz / "ie123.toml").is_file(),
            "ie123_local_toml": (self.raiz / "ie123.local.toml").is_file(),
            "work": self.work.is_dir(),
            "objetivos_habilitados": list(self.objetivos_habilitados()),
            "herramientas": {},
        }
        herramientas = self.ajuste("herramientas", {}) or {}
        if isinstance(herramientas, dict):
            for nombre, valor in sorted(herramientas.items()):
                if not isinstance(valor, str):
                    continue
                encontrado = Path(valor).is_file() or shutil.which(valor) is not None
                datos["herramientas"][nombre] = encontrado
                if not encontrado:
                    incidencias.append(
                        Incidencia(
                            codigo="HERRAMIENTA_AUSENTE",
                            severidad="aviso",
                            mensaje=f"No se encuentra la herramienta '{nombre}' ({valor}).",
                            pista="Ajusta [herramientas] en ie123.local.toml o añádela al PATH.",
                        )
                    )
        return Resultado.correcto(datos=datos, incidencias=incidencias)


@dataclass(frozen=True)
class ManifiestoCandidata:
    """Manifiesto de una candidata (``<candidata>/manifest.json``)."""

    nombre: str
    base: str
    base_sha256: str
    capas: tuple[dict[str, str], ...] = ()
    salidas: dict[str, str] = field(default_factory=dict)
    objetivos: tuple[str, ...] = ()
    generado_en: str = ""

    ESQUEMA = 1

    def to_json(self) -> dict[str, Any]:
        return {
            "esquema": self.ESQUEMA,
            "nombre": self.nombre,
            "base": self.base,
            "base_sha256": self.base_sha256,
            "capas": [{"ruta": str(c["ruta"]), "sha256": str(c["sha256"])} for c in self.capas],
            "salidas": {str(k): str(v) for k, v in self.salidas.items()},
            "objetivos": list(self.objetivos),
            # Solo una persona marca esto a true tras la QA en emulador
            # (docs/PROTOCOLO_QA_IE1.md): ningún proceso automático puede hacerlo.
            "runtime_verified": False,
            "generado_en": self.generado_en or util.ahora_iso(),
        }

    @classmethod
    def desde_json(cls, d: dict[str, Any]) -> ManifiestoCandidata:
        capas = tuple(
            {"ruta": str(c.get("ruta", "")), "sha256": str(c.get("sha256", ""))} for c in d.get("capas", []) or []
        )
        return cls(
            nombre=str(d.get("nombre", "")),
            base=str(d.get("base", "")),
            base_sha256=str(d.get("base_sha256", "")),
            capas=capas,
            salidas={str(k): str(v) for k, v in (d.get("salidas") or {}).items()},
            objetivos=tuple(str(o) for o in (d.get("objetivos") or [])),
            generado_en=str(d.get("generado_en", "")),
        )

    @classmethod
    def leer(cls, ruta: str | os.PathLike[str]) -> ManifiestoCandidata:
        p = Path(ruta)
        if p.is_dir():
            p = p / "manifest.json"
        return cls.desde_json(util.leer_json(p))

    def escribir(self, ruta: str | os.PathLike[str]) -> Path:
        p = Path(ruta)
        if p.suffix != ".json":
            p = p / "manifest.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        util.escribir_json(p, self.to_json())
        return p
