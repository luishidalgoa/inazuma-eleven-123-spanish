"""Registro de activos: escaneo perezoso del `archive.fa` base y caché por objetivo.

Capa `servicio`: solo importa `ie123kit.nucleo.*` y `ie123kit.servicio.*`. Los juegos
llegan SIEMPRE como parámetro (nunca se importa un paquete de juego desde aquí).

El escaneo es perezoso: importar este módulo no hace E/S ni abre ninguna ROM; todo
ocurre al llamar a `construir()` u `obtener()`.
"""

from __future__ import annotations

import tomllib
from collections.abc import Callable
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ie123kit.nucleo import util
from ie123kit.nucleo.contenedores.fa import FaArchive
from ie123kit.nucleo.juego import es_editable
from ie123kit.nucleo.tipos import AssetRef, Progreso, componer_id

if TYPE_CHECKING:  # pragma: no cover - solo para anotaciones
    from ie123kit.nucleo.tipos import CancelToken
    from ie123kit.servicio.proyecto import Workspace

__all__ = [
    "ESQUEMA",
    "EXTENSIONES",
    "Familia",
    "Registro",
    "cargar",
    "construir",
    "estado_de",
    "familias",
    "guardar",
    "obtener",
    "tipo_de_ruta",
]

ESQUEMA = 1

#: Extensión (en minúsculas) -> tipo de activo. Estos tipos NO son capacidades: la
#: traducción a `InfoObjetivo.capacidades` vive en `nucleo.juego.CAPACIDAD_POR_TIPO`.
EXTENSIONES: dict[str, str] = {
    ".arc": "grafico",
    ".ctpk": "grafico",
    ".qna": "grafico",
    ".tga": "grafico",
    ".png": "grafico",
    ".eve": "evento",
    ".mch": "evento",
    ".pkh": "evento",
    ".pkb": "evento",
    ".str": "texto",
    ".dat": "texto",
    ".txt": "texto",
    ".moflex": "cinematica",
    ".sad": "voz",
    ".swd": "voz",
    ".sed": "voz",
    ".cro": "literal_cro",
}
TIPO_POR_DEFECTO = "binario"

#: Cada cuántas entradas se comprueba la cancelación y se emite progreso.
PASO_PROGRESO = 256


def tipo_de_ruta(ruta: str) -> str:
    """Tipo de activo deducido por extensión (`binario` si no se reconoce)."""
    punto = ruta.rfind(".")
    if punto < 0:
        return TIPO_POR_DEFECTO
    return EXTENSIONES.get(ruta[punto:].lower(), TIPO_POR_DEFECTO)


@dataclass(frozen=True)
class Familia:
    """Grupo declarativo de activos de un objetivo (derivado de su `activos.toml`)."""

    tipo: str
    prefijo_romfs: str
    contenedores: tuple[str, ...]
    perfil_texto: str
    ambito: str
    contrapartida: str | None = None


def _activos_toml(juego: Any) -> dict:
    """Lee el `activos.toml` del paquete del juego (esquema 1, secciones opcionales)."""
    paquete = getattr(juego, "PAQUETE", None)
    if not paquete:
        return {}
    recurso = resources.files(paquete).joinpath("activos.toml")
    if not recurso.is_file():
        return {}
    return tomllib.loads(recurso.read_text(encoding="utf-8"))


def familias(juego: Any) -> list[Familia]:
    """Familias declaradas por el objetivo.

    Si el `activos.toml` trae una tabla `[[familias]]` se usa tal cual. Con el esquema
    mínimo de hoy se derivan del producto de `[romfs].prefijos_fa` (+ `solo_lectura`)
    por los tipos conocidos; no se inventan claves nuevas en los .toml.
    """
    datos = _activos_toml(juego)
    objetivo = datos.get("objetivo", {})
    perfil = objetivo.get("perfil_texto", "")
    declaradas = datos.get("familias")
    if declaradas:
        return [
            Familia(
                tipo=str(f.get("tipo", TIPO_POR_DEFECTO)),
                prefijo_romfs=str(f.get("prefijo_romfs", "")),
                contenedores=tuple(f.get("contenedores", ("fa",))),
                perfil_texto=str(f.get("perfil_texto", perfil)),
                ambito=str(f.get("ambito", "editable")),
                contrapartida=f.get("contrapartida"),
            )
            for f in declaradas
        ]
    romfs = datos.get("romfs", {})
    solo_lectura = tuple(romfs.get("solo_lectura", ()))
    prefijos = list(romfs.get("prefijos_fa", ())) + list(solo_lectura)
    tipos = sorted(set(EXTENSIONES.values()) | {TIPO_POR_DEFECTO})
    salida: list[Familia] = []
    for prefijo in prefijos:
        ambito = "solo_lectura" if prefijo in solo_lectura else "editable"
        for tipo in tipos:
            salida.append(
                Familia(
                    tipo=tipo,
                    prefijo_romfs=prefijo,
                    contenedores=("fa",),
                    perfil_texto=perfil,
                    ambito=ambito,
                )
            )
    return salida


@dataclass(frozen=True)
class Registro:
    """Inventario de activos de un objetivo para una base concreta."""

    objetivo: str
    base_sha256: str
    generado_en: str
    activos: tuple[AssetRef, ...] = ()

    def to_json(self) -> dict:
        return {
            "esquema": ESQUEMA,
            "objetivo": self.objetivo,
            "base_sha256": self.base_sha256,
            "generado_en": self.generado_en,
            "activos": [a.to_json() for a in self.activos],
        }

    @classmethod
    def desde_json(cls, d: dict) -> Registro:
        return cls(
            objetivo=str(d["objetivo"]),
            base_sha256=str(d.get("base_sha256", "")),
            generado_en=str(d.get("generado_en", "")),
            activos=tuple(_assetref_desde_json(a) for a in d.get("activos", ())),
        )


def _assetref_desde_json(d: dict) -> AssetRef:
    campos = dict(d)
    if "cadena_contenedores" in campos:
        campos["cadena_contenedores"] = tuple(campos["cadena_contenedores"])
    return AssetRef(**campos)


def _info(juego: Any):
    return juego.info()


def _prefijos(juego: Any) -> tuple[str, ...]:
    return tuple(getattr(_info(juego), "prefijos_romfs", ()) or ())


def _prefijos_solo_lectura(juego: Any) -> tuple[str, ...]:
    """Prefijos de `[romfs].solo_lectura` del `activos.toml` del objetivo.

    `InfoObjetivo.prefijos_romfs` solo trae `prefijos_fa`, así que sin esto las fuentes
    bloqueadas por el perfil v20 (`font/`, `inazuma1/data_iz/font/`) NO aparecían en el
    inventario: ni siquiera como solo lectura. Aparecer marcadas es la diferencia entre
    «no se puede tocar» y «no existe».
    """
    romfs = _activos_toml(juego).get("romfs", {})
    if not isinstance(romfs, dict):
        return ()
    return tuple(str(p) for p in (romfs.get("solo_lectura") or ()))


def _capacidades(juego: Any) -> frozenset[str]:
    return frozenset(getattr(_info(juego), "capacidades", ()) or ())


def ruta_base_por_defecto(ws: Workspace | Any) -> Path:
    """`work/shared/base_3ds/romfs/archive.fa` del espacio de trabajo dado."""
    return Path(ws.work) / "shared" / "base_3ds" / "romfs" / "archive.fa"


def _emitir(progreso: Callable[[Progreso], None] | None, actual: int, total: int, fase: str) -> None:
    if progreso is None:
        return
    progreso(Progreso(fase=fase, actual=actual, total=total))


def construir(
    ws: Workspace | Any,
    juego: Any,
    *,
    base: Path | str | None = None,
    escaneo: bool = True,
    progreso: Callable[[Progreso], None] | None = None,
    cancel: CancelToken | None = None,
) -> Registro:
    """Escanea el `archive.fa` base y devuelve el Registro del objetivo.

    Si la base no existe devuelve un Registro vacío con `base_sha256=''` (en CI no
    hay ROM y eso NO es un error).
    """
    if cancel is not None:
        cancel.comprobar()
    objetivo = _info(juego).id
    ruta = Path(base) if base is not None else ruta_base_por_defecto(ws)
    if not ruta.is_file():
        return Registro(objetivo=objetivo, base_sha256="", generado_en=util.ahora_iso(), activos=())
    sha_base = util.sha256_file(ruta)
    if not escaneo:
        return Registro(objetivo=objetivo, base_sha256=sha_base, generado_en=util.ahora_iso(), activos=())

    prefijos = _prefijos(juego)
    solo_lectura = _prefijos_solo_lectura(juego)
    todos = (*prefijos, *solo_lectura)
    capacidades = _capacidades(juego)
    arc = FaArchive(str(ruta))
    entradas: list[tuple[str, int, int]] = list(arc.entries)
    total = len(entradas)
    activos: list[AssetRef] = []
    for i, (ruta_romfs, offset, tamano) in enumerate(entradas):
        if cancel is not None and i % PASO_PROGRESO == 0:
            cancel.comprobar()
        if i % PASO_PROGRESO == 0:
            _emitir(progreso, i, total, "escaneando archive.fa")
        if not any(ruta_romfs.startswith(p) for p in todos):
            continue
        tipo = tipo_de_ruta(ruta_romfs)
        # `solo_lectura` manda sobre las capacidades declaradas: un activo bajo uno de esos
        # prefijos NUNCA es editable, aunque el objetivo declare la capacidad de su tipo.
        bloqueado = any(ruta_romfs.startswith(p) for p in solo_lectura)
        activos.append(
            AssetRef(
                id=componer_id(objetivo, tipo, ruta_romfs),
                objetivo=objetivo,
                tipo=tipo,
                ruta_romfs=ruta_romfs,
                cadena_contenedores=("fa",),
                tamano=tamano,
                editable=False if bloqueado else es_editable(tipo, capacidades),
                estado="original",
                origen="3ds_jp",
                sha256=util.sha256_bytes(arc.file_bytes(offset, tamano)),
            )
        )
    _emitir(progreso, total, total, "escaneando archive.fa")
    return Registro(
        objetivo=objetivo,
        base_sha256=sha_base,
        generado_en=util.ahora_iso(),
        activos=tuple(activos),
    )


def guardar(ws: Workspace | Any, registro: Registro) -> Path:
    """Escribe la caché del registro en `ws.dirs(objetivo).registro`."""
    destino = Path(ws.dirs(registro.objetivo).registro)
    destino.parent.mkdir(parents=True, exist_ok=True)
    util.escribir_json(destino, registro.to_json())
    return destino


def cargar(ws: Workspace | Any, objetivo: str) -> Registro | None:
    """Lee la caché del registro; None si no existe o el JSON no es válido."""
    ruta = Path(ws.dirs(objetivo).registro)
    if not ruta.is_file():
        return None
    try:
        datos = util.leer_json(ruta)
        return Registro.desde_json(datos)
    except (OSError, ValueError, TypeError, KeyError):
        return None


def obtener(
    ws: Workspace | Any,
    juego: Any,
    *,
    base: Path | str | None = None,
    refrescar: bool = False,
    progreso: Callable[[Progreso], None] | None = None,
    cancel: CancelToken | None = None,
) -> Registro:
    """Devuelve el registro desde la caché si sigue siendo válida; si no, lo reconstruye."""
    objetivo = _info(juego).id
    ruta = Path(base) if base is not None else ruta_base_por_defecto(ws)
    sha_actual = util.sha256_file(ruta) if ruta.is_file() else ""
    if not refrescar:
        cache = cargar(ws, objetivo)
        if cache is not None and cache.base_sha256 == sha_actual:
            return cache
    registro = construir(ws, juego, base=ruta, progreso=progreso, cancel=cancel)
    guardar(ws, registro)
    return registro


def estado_de(ref: AssetRef, *, sha_candidata: str | None = None) -> str:
    """Estado mínimo de un activo.

    Por ahora siempre 'original', salvo que se pase el sha de la última candidata:
    si difiere del de la base, el activo está 'construido'. La comparación completa
    con la candidata (capas, traducido/editado) llega en F2.2/F2.3.
    """
    if sha_candidata is not None and sha_candidata != ref.sha256:
        return "construido"
    return "original"
