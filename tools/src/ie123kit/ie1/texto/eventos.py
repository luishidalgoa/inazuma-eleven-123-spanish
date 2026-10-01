"""Exportación e importación del texto de los eventos de IE1 (paquetes ``eve`` y ``mch``).

Formato de intercambio: un TSV UTF-8 por evento, ``<destino>/<pack>/<eid>.tsv``, con la
cabecera :data:`CABECERA_TSV`. Una fila por registro de texto visible (opcode ``0x301D``,
argumento 1), que es exactamente la selección del bloqueado ``tools/build_ie1_probe.py``.

Reinserción: nunca se escribe nada si alguna fila incumple una regla; las reglas se
devuelven como incidencias con código estable:

- ``NF_HUERFANO``      marcador ``%NF`` sin N caracteres detrás (docs/FURIGANA_LECCIONES.md #6).
- ``PAGINAS_DISTINTAS`` el número de páginas ``\\f`` no coincide con el original.
- ``EXCEDE_BYTES``     el cuerpo codificado pasa de ``LIMITE_TEXTO`` bytes del registro SSD.
- ``EXCEDE_PX``        alguna línea pasa del ancho de caja del layout v20.
- ``GLIFO_NO_SOPORTADO`` un carácter que la tipografía aprobada no sabe codificar.

Bloqueo tipográfico v20: el ajuste de líneas es ``nucleo.texto.tipografia_v20.approved_layout``
y la codificación ``nucleo.texto.ancho_completo.encode_fullwidth``. Aquí no hay ninguna tabla
propia ni se cambia caja, espaciado ni saltos.
"""

from __future__ import annotations

import csv
import re
from collections.abc import Iterable
from pathlib import Path

from ie123kit.ie1.texto import mch as reglas_mch
from ie123kit.nucleo.contenedores.fa import FaArchive
from ie123kit.nucleo.errores import ValidacionError
from ie123kit.nucleo.eventos.instrucciones import LIMITE_TEXTO, EventPack
from ie123kit.nucleo.texto import ancho_completo, tipografia_v20

__all__ = [
    "ANCHO_CAJA_PX",
    "ARGUMENTO_DIALOGO",
    "AVANCE_PX",
    "CABECERA_TSV",
    "OPCODE_DIALOGO",
    "exportar",
    "importar",
]

CABECERA_TSV: tuple[str, ...] = ("id", "jp", "es_oficial", "traduccion", "max_px", "max_bytes", "estado")

OPCODE_DIALOGO = reglas_mch.OPCODE_DIALOGO
ARGUMENTO_DIALOGO = reglas_mch.ARGUMENTO_DIALOGO

#: Caja y avance del perfil v20 (``dialogue_lock.approved_layout``: ancho 220, avance 11).
ANCHO_CAJA_PX = 220
AVANCE_PX = 11

_MARCADOR = re.compile(r"%([1-9])F")
_TOKEN = re.compile(r"\\[nf]|%[0-9]*[A-Za-z]")
_SALTO = "\\n"
_PAGINA = "\\f"


def _abrir(archive: Path, pack: str) -> EventPack:
    return EventPack.from_archive(FaArchive(str(Path(archive))), pack)


def _visibles(paquete: EventPack, eid: int) -> list[tuple[int, object]]:
    """``[(indice, TextRecord), ...]`` de los registros con texto en pantalla."""
    if paquete.pack == reglas_mch.PACK:
        tabla = paquete.instructions(eid)
        registros = paquete.records(eid)
        return [(i, registros[i]) for i in reglas_mch.registros_visibles(tabla, registros)]
    return paquete.find(eid, OPCODE_DIALOGO, ARGUMENTO_DIALOGO)


def _texto(registro) -> str:
    return registro.body.decode("shift_jis", "replace")


def _paginas(texto: str) -> int:
    return texto.count(_PAGINA) + 1


def _lineas(texto: str) -> list[str]:
    salida: list[str] = []
    for pagina in texto.split(_PAGINA):
        salida.extend(pagina.split(_SALTO))
    return salida


def _ancho_px(linea: str) -> int:
    return AVANCE_PX * len(_TOKEN.sub("", linea))


def _huerfanos(texto: str) -> bool:
    """``True`` si algún ``%NF`` no tiene N caracteres visibles detrás en su página."""
    for pagina in texto.split(_PAGINA):
        for linea in pagina.split(_SALTO):
            for coincidencia in _MARCADOR.finditer(linea):
                pedidos = int(coincidencia.group(1))
                resto = _TOKEN.sub("", linea[coincidencia.end():])
                if len(resto) < pedidos:
                    return True
    return False


def _fila(indice: int, jp: str) -> dict[str, str]:
    return {
        "id": str(indice),
        "jp": jp,
        "es_oficial": "",
        "traduccion": "",
        "max_px": str(ANCHO_CAJA_PX),
        "max_bytes": str(LIMITE_TEXTO),
        "estado": "pendiente",
    }


def exportar(archive: Path, destino: Path, *, pack: str = "eve", ids: Iterable[int] | None = None) -> list[Path]:
    """Escribe ``<destino>/<pack>/<eid>.tsv`` por evento y devuelve las rutas escritas."""
    paquete = _abrir(archive, pack)
    conocidos = [eid for eid, _o, _s in paquete.index]
    elegidos = sorted(conocidos) if ids is None else sorted({int(e) for e in ids})
    desconocidos = [e for e in elegidos if e not in set(conocidos)]
    if desconocidos:
        raise ValidacionError("evento_desconocido", detalle=", ".join(str(e) for e in desconocidos))
    carpeta = Path(destino) / pack
    carpeta.mkdir(parents=True, exist_ok=True)
    escritos: list[Path] = []
    for eid in elegidos:
        filas = [_fila(i, _texto(registro)) for i, registro in _visibles(paquete, eid)]
        if not filas:
            continue
        ruta = carpeta / f"{eid}.tsv"
        with ruta.open("w", encoding="utf-8", newline="") as fh:
            escritor = csv.DictWriter(fh, fieldnames=list(CABECERA_TSV), delimiter="\t",
                                      lineterminator="\n", quoting=csv.QUOTE_NONE, escapechar=None)
            escritor.writeheader()
            escritor.writerows(filas)
        escritos.append(ruta)
    return escritos


def _incidencia(codigo: str, mensaje: str, ubicacion: str) -> dict[str, str]:
    return {"codigo": codigo, "mensaje": mensaje, "ubicacion": ubicacion}


def _cuerpo(traduccion: str, jp: str, ubicacion: str, incidencias: list[dict[str, str]]) -> bytes | None:
    """Aplica el layout v20 y la codificación; acumula incidencias y devuelve el cuerpo."""
    if _huerfanos(traduccion):
        incidencias.append(_incidencia("NF_HUERFANO", "marcador %NF sin caracteres detrás", ubicacion))
        return None
    try:
        formateado = tipografia_v20.approved_layout(traduccion)
    except ValueError as exc:
        incidencias.append(_incidencia("EXCEDE_PX", str(exc), ubicacion))
        return None
    if _paginas(formateado) != _paginas(jp):
        incidencias.append(_incidencia(
            "PAGINAS_DISTINTAS",
            f"{_paginas(formateado)} páginas frente a {_paginas(jp)} del original",
            ubicacion,
        ))
        return None
    anchos = [_ancho_px(linea) for linea in _lineas(formateado)]
    if anchos and max(anchos) > ANCHO_CAJA_PX:
        incidencias.append(_incidencia("EXCEDE_PX", f"{max(anchos)} px > {ANCHO_CAJA_PX} px", ubicacion))
        return None
    try:
        cuerpo = ancho_completo.encode_fullwidth(formateado)
    except UnicodeEncodeError as exc:
        incidencias.append(_incidencia("GLIFO_NO_SOPORTADO", str(exc), ubicacion))
        return None
    if len(cuerpo) > LIMITE_TEXTO:
        incidencias.append(_incidencia("EXCEDE_BYTES", f"{len(cuerpo)} bytes > {LIMITE_TEXTO}", ubicacion))
        return None
    return cuerpo


def _leer_tsv(ruta: Path, incidencias: list[dict[str, str]]) -> list[dict[str, str]]:
    with ruta.open("r", encoding="utf-8", newline="") as fh:
        lector = csv.DictReader(fh, delimiter="\t", quoting=csv.QUOTE_NONE)
        if tuple(lector.fieldnames or ()) != CABECERA_TSV:
            incidencias.append(_incidencia("CABECERA_TSV", "cabecera inesperada", str(ruta)))
            return []
        return [dict(fila) for fila in lector]


def importar(archive: Path, origen: Path, *, pack: str = "eve", simular: bool = True,
             salida: Path | None = None) -> dict:
    """Prepara los ``.ssd`` de los TSV de ``<origen>/<pack>``.

    Con ``simular`` no se escribe nada. Sin él se escriben en ``<salida>/events`` (pack
    ``eve``) o ``<salida>/events_mch`` (pack ``mch``) con ``EventPack.stage``, que aplica
    las comprobaciones de identidad de ``build_ui_revision.rebuild_events``.
    """
    carpeta = Path(origen) / pack
    incidencias: list[dict[str, str]] = []
    cambios: dict[int, dict[int, bytes]] = {}
    paquete = _abrir(archive, pack)
    conocidos = {eid for eid, _o, _s in paquete.index}
    for ruta in sorted(carpeta.glob("*.tsv")) if carpeta.is_dir() else []:
        try:
            eid = int(ruta.stem)
        except ValueError:
            incidencias.append(_incidencia("NOMBRE_TSV", "el nombre no es un id de evento", str(ruta)))
            continue
        if eid not in conocidos:
            incidencias.append(_incidencia("EVENTO_DESCONOCIDO", f"{eid} no está en {pack}.pkh", str(ruta)))
            continue
        if pack == reglas_mch.PACK and not reglas_mch.evento_editable(eid):
            incidencias.append(_incidencia("EVENTO_PROTEGIDO", f"{eid} fuera de los rangos de mch", str(ruta)))
            continue
        registros = dict(_visibles(paquete, eid))
        del_evento: dict[int, bytes] = {}
        for fila in _leer_tsv(ruta, incidencias):
            indice_bruto = (fila.get("id") or "").strip()
            ubicacion = f"{ruta}:{indice_bruto}"
            try:
                indice = int(indice_bruto)
            except ValueError:
                incidencias.append(_incidencia("INDICE_INVALIDO", "id de fila no numérico", ubicacion))
                continue
            if indice not in registros:
                incidencias.append(_incidencia("INDICE_DESCONOCIDO", "el registro no lleva texto visible", ubicacion))
                continue
            traduccion = (fila.get("traduccion") or "").strip()
            if not traduccion:
                continue
            jp = _texto(registros[indice])
            cuerpo = _cuerpo(traduccion, jp, ubicacion, incidencias)
            if cuerpo is None or cuerpo == registros[indice].body:
                continue
            del_evento[indice] = cuerpo
        if del_evento:
            cambios[eid] = del_evento

    ficheros: list[str] = []
    if incidencias:
        cambios = {}
    elif cambios and not simular:
        if salida is None:
            raise ValidacionError("SALIDA_REQUERIDA", detalle="importar(simular=False) necesita 'salida'")
        destino = Path(salida) / ("events" if pack != reglas_mch.PACK else "events_mch")
        informe = paquete.stage(cambios, destino)
        ficheros = [evento["ruta"] for evento in informe["eventos"]]
    return {"eventos_preparados": len(cambios), "incidencias": incidencias, "ficheros": ficheros}
