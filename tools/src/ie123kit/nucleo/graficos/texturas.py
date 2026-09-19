"""Primitivas de texturas CTPK dentro de contenedores ARCV (.arc/.lzs de la interfaz).

Consolidan tres patrones del catálogo de auditoría:

- ``arcv_ctpk_iteration`` (33 ficheros): el bucle ``unwrap -> entries(raw) -> blob[:4] == b'CTPK'
  -> metadata(blob)[0] == nombre`` pasa a :func:`iter_ctpk`, :func:`texture_map`,
  :func:`find_texture` y :func:`load_texture`.
- ``texture_plan_replace`` (18 capas): la tubería de ``work/ie1/capas/graficos/graficos_nds/apply.py`` (antes v37)
  pasa a :func:`apply_plan`, sin globales de módulo y con la reenvoltura explícita
  (``rewrap='raw'`` por defecto, que es lo que hace V37).
- ``texture_layer_validate_clone`` (8 copias de validate.py): pasa a :func:`validate_plan`.

Todo son funciones puras: no hay estado de módulo, ni print, ni efectos al importar.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from PIL import Image

from ie123kit.nucleo.compresion import sszl
from ie123kit.nucleo.contenedores import arcv
from ie123kit.nucleo.contenedores.fa import FaArchive
from ie123kit.nucleo.errores import ValidacionError
from ie123kit.nucleo.graficos import ctpk
from ie123kit.nucleo.graficos.imagen import (
    drop_shadow,
    fit_into,
    paste_centered,
    preview_pair,
)
from ie123kit.nucleo.util import escribir_json, sha256_file

__all__ = [
    "Ctpk",
    "InformeValidacion",
    "apply_plan",
    "drop_shadow",
    "find_texture",
    "fit_into",
    "iter_ctpk",
    "load_texture",
    "paste_centered",
    "preview_pair",
    "texture_map",
    "validate_plan",
]

#: Una función de plan: recibe la textura decodificada en RGBA y devuelve la nueva.
Edicion = Callable[[Image.Image], Image.Image]
#: Plan de sustitución: ruta dentro del contenedor -> {nombre de textura: edición}.
Plan = dict[str, dict[str, Edicion]]


@dataclass(frozen=True)
class Ctpk:
    """Una textura CTPK localizada dentro de un ARCV ya desenvuelto."""

    nombre: str
    offset: int
    tamano: int
    ancho: int
    alto: int
    formato: int
    blob: bytes


@dataclass(frozen=True)
class InformeValidacion:
    """Resultado de :func:`validate_plan`."""

    ok: bool
    problemas: list[str] = field(default_factory=list)
    cambiadas: list[str] = field(default_factory=list)
    declaradas: list[str] = field(default_factory=list)


def _abrir(base: str | os.PathLike[str] | FaArchive) -> FaArchive:
    return base if isinstance(base, FaArchive) else FaArchive(str(base))


def iter_ctpk(data: bytes) -> Iterator[Ctpk]:
    """Recorre las texturas CTPK de un .arc (desenvuelve SSZL y salta QNA y demás entradas)."""
    raw = sszl.unwrap(bytes(data))
    for off, tamano, _crc in arcv.entries(raw):
        blob = bytes(raw[off:off + tamano])
        if blob[:4] != b"CTPK":
            continue
        nombre, ancho, alto, formato, _off, _size = ctpk.metadata(blob)
        yield Ctpk(nombre=nombre, offset=off, tamano=tamano, ancho=ancho, alto=alto,
                   formato=formato, blob=blob)


def texture_map(data: bytes) -> dict[str, tuple[int, int]]:
    """Nombre de textura -> (offset dentro del ARCV desenvuelto, tamaño)."""
    return {t.nombre: (t.offset, t.tamano) for t in iter_ctpk(data)}


def find_texture(data: bytes, nombre: str) -> Ctpk:
    """Devuelve la textura `nombre`; KeyError enumerando las disponibles si no está."""
    disponibles = []
    for textura in iter_ctpk(data):
        if textura.nombre == nombre:
            return textura
        disponibles.append(textura.nombre)
    raise KeyError(f"textura ausente: {nombre}; disponibles: {', '.join(disponibles) or '(ninguna)'}")


def load_texture(arc: FaArchive, ruta_arc: str, nombre: str) -> Image.Image:
    """Decodifica en RGBA la textura `nombre` del .arc `ruta_arc` del contenedor `arc`."""
    return ctpk.decode(find_texture(arc.read(ruta_arc), nombre).blob).convert("RGBA")


def _sustituir(ruta_arc: str, blob: bytes, tamano: int, edicion: Edicion) -> tuple[bytes, Image.Image]:
    """Comprueba el códec, aplica `edicion` y devuelve (blob nuevo, imagen original en RGBA)."""
    imagen = ctpk.decode(blob)
    if ctpk.encode(blob, imagen) != blob:
        raise ValidacionError("codec_sin_ida_y_vuelta", ruta_arc, ctpk.metadata(blob)[0])
    antes = imagen.convert("RGBA")
    nueva = edicion(antes.copy())
    reemplazo = ctpk.encode(blob, nueva)
    nombre = ctpk.metadata(blob)[0]
    if len(reemplazo) != tamano:
        raise ValidacionError("tamano_distinto", ruta_arc, f"{nombre}: {len(reemplazo)} != {tamano}")
    if ctpk.metadata(reemplazo) != ctpk.metadata(blob):
        raise ValidacionError("metadata_distinta", ruta_arc, nombre)
    if ctpk.encode(reemplazo, ctpk.decode(reemplazo)) != reemplazo:
        raise ValidacionError("codec_sin_ida_y_vuelta_tras_editar", ruta_arc, nombre)
    return reemplazo, antes


def apply_plan(
    base: str | os.PathLike[str] | FaArchive,
    plan: Plan,
    salida: str | os.PathLike[str],
    *,
    previews: str | os.PathLike[str] | None = None,
    rewrap: str = "raw",
    report: str | os.PathLike[str] | None = None,
) -> list[dict]:
    """Aplica `plan` sobre `base` y escribe los .arc resultantes en `salida/<ruta_arc>`.

    Reproduce la tubería de ``work/ie1/capas/graficos/graficos_nds/apply.py`` (antes v37): desenvuelve el .arc,
    comprueba que el códec hace ida y vuelta ANTES de editar, llama a la función del plan,
    reencodea, exige el mismo tamaño y los mismos metadatos, vuelve a comprobar la ida y vuelta
    sobre el reemplazo, exige que la tabla ARCV no cambie y falla si alguna textura declarada no
    aparece en el contenedor.

    `rewrap` es explícito porque las capas no coinciden: V37 escribe ARCV en crudo (``'raw'``,
    el defecto) y v64/v65/v67 reenvuelven en SSZL (``'keep'`` o ``'sszl'``).

    Devuelve el registro por textura y, con `report`, lo escribe como JSON UTF-8.
    """
    arc = _abrir(base)
    salida = Path(salida)
    informe: list[dict] = []
    for ruta_arc, texturas in plan.items():
        datos = arc.read(ruta_arc)
        raw = sszl.unwrap(datos)
        resultado = bytearray(raw)
        vistos: set[str] = set()
        for off, tamano, _crc in arcv.entries(raw):
            blob = bytes(raw[off:off + tamano])
            if blob[:4] != b"CTPK":
                continue
            nombre = ctpk.metadata(blob)[0]
            if nombre not in texturas:
                continue
            vistos.add(nombre)
            edicion = texturas[nombre]
            reemplazo, antes = _sustituir(ruta_arc, blob, tamano, edicion)
            resultado[off:off + tamano] = reemplazo
            if previews is not None:
                carpeta = Path(previews)
                carpeta.mkdir(parents=True, exist_ok=True)
                par = preview_pair(antes, ctpk.decode(reemplazo).convert("RGBA"))
                par.convert("RGB").save(carpeta / (PurePosixPath(nombre).stem + ".png"))
            informe.append({"archivo": ruta_arc, "textura": nombre,
                            "cambio": getattr(edicion, "__name__", type(edicion).__name__)})
        faltan = sorted(set(texturas) - vistos)
        if faltan:
            raise ValidacionError("texturas_no_encontradas", ruta_arc, ", ".join(faltan))
        final = bytes(resultado)
        if arcv.entries(final) != arcv.entries(raw):
            raise ValidacionError("tabla_arcv_alterada", ruta_arc)
        destino = salida / ruta_arc
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(sszl.reenvolver_como(datos, final, rewrap))
    if report is not None:
        ruta_base = Path(arc.ruta)
        escribir_json(report, {"base": str(ruta_base), "base_sha256": sha256_file(ruta_base),
                               "texturas": informe, "runtime_verified": False})
    return informe


def _revisar_arc(
    arc: FaArchive,
    ruta_arc: str,
    texturas: dict[str, Edicion],
    fichero: Path,
    allow: Callable[[str, bytes, bytes], bool] | None,
    problemas: list[str],
    cambiadas: list[str],
) -> None:
    if not fichero.is_file():
        problemas.append(f"{ruta_arc}: falta el .arc en extra/")
        return
    try:
        original = sszl.unwrap(arc.read(ruta_arc))
    except KeyError as exc:
        problemas.append(f"{ruta_arc}: no está en la base ({exc})")
        return
    nuevo = sszl.unwrap(fichero.read_bytes())
    try:
        tabla = arcv.entries(original)
        if arcv.entries(nuevo) != tabla:
            problemas.append(f"{ruta_arc}: la tabla ARCV ha cambiado")
            return
    except ValueError as exc:
        problemas.append(f"{ruta_arc}: ARCV ilegible ({exc})")
        return
    vistas: set[str] = set()
    for off, tamano, _crc in tabla:
        viejo = bytes(original[off:off + tamano])
        nueva = bytes(nuevo[off:off + tamano])
        if viejo[:4] != b"CTPK":
            if viejo != nueva and not (allow and allow(f"{ruta_arc}#{off}", viejo, nueva)):
                problemas.append(f"{ruta_arc}: entrada no CTPK modificada en {off}")
            continue
        nombre = ctpk.metadata(viejo)[0]
        cambio = viejo != nueva
        if cambio:
            cambiadas.append(f"{ruta_arc}::{nombre}")
        if nombre not in texturas:
            if cambio and not (allow and allow(nombre, viejo, nueva)):
                problemas.append(f"{ruta_arc}: textura no declarada modificada: {nombre}")
            continue
        vistas.add(nombre)
        if not cambio:
            problemas.append(f"{ruta_arc}: textura declarada sin cambios: {nombre}")
        elif ctpk.metadata(nueva) != ctpk.metadata(viejo):
            problemas.append(f"{ruta_arc}: metadatos distintos en {nombre}")
        elif ctpk.encode(nueva, ctpk.decode(nueva)) != nueva:
            problemas.append(f"{ruta_arc}: el códec no hace ida y vuelta en {nombre}")
    for nombre in sorted(set(texturas) - vistas):
        problemas.append(f"{ruta_arc}: textura declarada ausente: {nombre}")


def validate_plan(
    base: str | os.PathLike[str] | FaArchive,
    plan: Plan,
    extra_dir: str | os.PathLike[str],
    *,
    allow: Callable[[str, bytes, bytes], bool] | None = None,
) -> InformeValidacion:
    """Comprueba que `extra_dir` contiene exactamente los cambios que declara `plan`.

    Sustituye a los ocho validate.py copiados de V37. Marca como problema un .arc que falte,
    una tabla ARCV alterada, una textura declarada que no cambie o no aparezca, y cualquier
    textura NO declarada que sí haya cambiado, salvo que `allow(nombre, viejo, nuevo)` la
    acepte (así v43 admitía su excepción de QNA).
    """
    arc = _abrir(base)
    extra = Path(extra_dir)
    problemas: list[str] = []
    cambiadas: list[str] = []
    declaradas: list[str] = []
    for ruta_arc, texturas in plan.items():
        declaradas += [f"{ruta_arc}::{nombre}" for nombre in texturas]
        _revisar_arc(arc, ruta_arc, texturas, extra / ruta_arc, allow, problemas, cambiadas)
    return InformeValidacion(ok=not problemas, problemas=problemas,
                             cambiadas=cambiadas, declaradas=declaradas)
