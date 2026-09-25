"""Traducción para la actualización oficial de la recopilación (v1.4.0, título 0004000E000BB800).

La actualización trae su propio ``.code`` y, en su RomFS (``rom2:`` para el juego), las cuatro CRO
recompiladas, ``static.crs``/``static.crr`` y algunas texturas nuevas. El juego actualizado carga las CRO
y esas texturas de ``rom2:`` y el resto (``archive.fa``…) de la RomFS base (``rom:``).

:func:`construir_actualizacion` produce los ficheros de la actualización traducidos:

- cada CRO: los parches de la candidata 1.0 relocalizados por contenido
  (:mod:`ie123kit.nucleo.ejecutable.relocalizar`), con las direcciones absolutas del code.bin que usen
  traducidas al ``.code`` de la actualización;
- cada fichero de datos de la actualización cuyo equivalente de la 1.0 (``data_iz2`` -> ``data_iz``)
  cambie la candidata: el de la candidata (el mismo recurso traducido);
- ``static.crs``/``static.crr`` no se tocan (la 1.0 traducida tampoco actualiza el ``.crr``).

Nada se escribe si algún parche no se relocaliza con seguridad, salvo ``permitir_parcial``.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path, PurePosixPath

from ie123kit.nucleo.contenedores.fa import FaArchiveMapeado
from ie123kit.nucleo.ejecutable.relocalizar import (
    literales_absolutos,
    mapear_direccion_absoluta,
    relocalizar,
    verificar_estructura,
    verificar_relocalizacion,
)
from ie123kit.nucleo.util import escribir_json, sha256_bytes

__all__ = ["TITULO_ACTUALIZACION", "TITULO_BASE", "construir_actualizacion", "equivalente_1_0"]

TITULO_BASE = "00040000000BB800"
TITULO_ACTUALIZACION = "0004000E000BB800"
_NO_DATOS = ("cro/", ".crr/")

Ruta = str | os.PathLike[str]
Progreso = Callable[[str, int, int], None]


def equivalente_1_0(ruta: str) -> str:
    """Ruta en el ``archive.fa`` de la 1.0 del fichero de datos ``ruta`` de la actualización."""
    return ruta.replace("/data_iz2/", "/data_iz/")


def _ficheros(raiz: Path) -> list[str]:
    return sorted(PurePosixPath(p.relative_to(raiz)).as_posix() for p in raiz.rglob("*") if p.is_file())


def construir_actualizacion(*, cro_base: Ruta, cro_candidata: Ruta, romfs_actualizacion: Ruta,
                            code_base: bytes, code_actualizacion: bytes, archive_base: Ruta,
                            archive_candidata: Ruta, destino: Ruta, permitir_parcial: bool = False,
                            progreso: Progreso | None = None) -> dict:
    """Escribe en ``destino/romfs`` los ficheros de la actualización traducidos y devuelve el informe.

    ``cro_base``: carpeta con las CRO 1.0 originales; ``cro_candidata``: las CRO 1.0 traducidas;
    ``romfs_actualizacion``: RomFS extraída de la actualización; ``code_*``: ``.code`` planos (1.0 y
    actualización); ``archive_*``: ``archive.fa`` original y de la candidata. También escribe
    ``destino/informe_actualizacion.json``.
    """
    romfs_u = Path(romfs_actualizacion)
    salida = Path(destino) / "romfs"
    informe: dict = {"titulo_base": TITULO_BASE, "titulo_actualizacion": TITULO_ACTUALIZACION,
                     "cro": {}, "absolutas": {}, "datos": {}, "sin_tocar": [], "escritos": [], "completo": True}

    # 1) Direcciones absolutas del code.bin que usan los parches ------------------------------------
    cros = sorted(p.name for p in (romfs_u / "cro").glob("*.cro"))
    entradas = {}
    for nombre in cros:
        entradas[nombre] = tuple((Path(d) / nombre).read_bytes() for d in (cro_base, cro_candidata))
        entradas[nombre] += ((romfs_u / "cro" / nombre).read_bytes(),)
    absolutas: dict[int, int] = {}
    for nombre, (b, c, _u) in entradas.items():
        for valor in sorted(set(literales_absolutos(b, c).values())):
            if valor in absolutas:
                continue
            res = mapear_direccion_absoluta(code_base, code_actualizacion, valor)
            informe["absolutas"][hex(valor)] = {**res, "direccion": hex(valor),
                                                "destino": hex(res["destino"]) if res["destino"] else None,
                                                "cro": nombre}
            if res["destino"] is not None:
                absolutas[valor] = res["destino"]

    # 2) CRO -------------------------------------------------------------------------------------------
    resultados = {}
    for i, (nombre, (b, c, u)) in enumerate(entradas.items()):
        if progreso:
            progreso(nombre, i, len(entradas))
        if b == c:
            informe["sin_tocar"].append(f"cro/{nombre}")
            continue
        r = relocalizar(b, c, u, absolutas=absolutas)
        problemas = verificar_estructura(u, r.datos, r.rangos) + verificar_relocalizacion(b, c, u, r)
        resultados[nombre] = r
        informe["cro"][nombre] = {
            "resumen": r.resumen(),
            "problemas": problemas,
            "fallidos": [p.a_dict() for p in r.fallidos],
            "sha256_actualizacion": sha256_bytes(u),
            "sha256_resultado": sha256_bytes(r.datos),
        }
        if r.fallidos or problemas:
            informe["completo"] = False

    # 3) Datos de la actualización (texturas…) ---------------------------------------------------------
    datos = {}
    with FaArchiveMapeado(archive_base) as fb, FaArchiveMapeado(archive_candidata) as fc:
        for rel in _ficheros(romfs_u):
            if rel.startswith(_NO_DATOS):
                if not rel.endswith(".cro"):
                    informe["sin_tocar"].append(rel)
                continue
            eq = equivalente_1_0(rel)
            if not fb.exists(eq) or not fc.exists(eq):
                informe["datos"][rel] = {"equivalente": eq, "estado": "sin_equivalente"}
                informe["completo"] = False
                continue
            original, traducido = fb.read(eq), fc.read(eq)
            if original == traducido:
                informe["sin_tocar"].append(rel)
                continue
            datos[rel] = traducido
            informe["datos"][rel] = {"equivalente": eq, "estado": "sustituido_por_el_de_la_candidata",
                                     "sha256_actualizacion": sha256_bytes((romfs_u / rel).read_bytes()),
                                     "sha256_resultado": sha256_bytes(traducido)}

    # 4) Escritura ---------------------------------------------------------------------------------------
    if informe["completo"] or permitir_parcial:
        for nombre, r in resultados.items():
            ruta = salida / "cro" / nombre
            ruta.parent.mkdir(parents=True, exist_ok=True)
            ruta.write_bytes(r.datos)
            informe["escritos"].append(f"cro/{nombre}")
        for rel, contenido in datos.items():
            ruta = salida / rel
            ruta.parent.mkdir(parents=True, exist_ok=True)
            ruta.write_bytes(contenido)
            informe["escritos"].append(rel)
    escribir_json(Path(destino) / "informe_actualizacion.json", informe)
    return informe
