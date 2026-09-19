"""Acciones del juego principal (el menú/selector de la recopilación).

Implementa `nucleo.juego.JuegoBase` para el objetivo `juego_principal`: gráficos de
`menu/*.arc`, textos de `message/jp/GameString.*`, literales de `cro/ina_menu.cro`,
las cinemáticas `movie/*.moflex`, la lectura del SMDH/banner del ExeFS (experimental)
y el bloqueo de solo lectura de `font/` (tipografía v20 de TODA la recopilación).

Reglas de capas: este módulo importa SOLO `ie123kit.nucleo.*`. Importarlo no tiene
efectos: no abre ROMs, no resuelve rutas ni lee ficheros.
"""

from __future__ import annotations

import csv
import re
from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

from PIL import Image

from ie123kit.nucleo.compresion import sszl
from ie123kit.nucleo.config.herramientas import HerramientaAusente
from ie123kit.nucleo.construir.capas import Capa
from ie123kit.nucleo.contenedores.fa import FaArchive
from ie123kit.nucleo.ejecutable import smdh as smdh_mod
from ie123kit.nucleo.ejecutable.cro import Cro, CroPatcher
from ie123kit.nucleo.errores import CanceladoError
from ie123kit.nucleo.fuentes.bcfnt import BCFNT
from ie123kit.nucleo.graficos import ctpk, texturas
from ie123kit.nucleo.graficos import qna as qna_mod
from ie123kit.nucleo.juego import Aportacion, JuegoBase, Regla
from ie123kit.nucleo.media import moflex
from ie123kit.nucleo.texto import ancho_completo, tipografia_v20
from ie123kit.nucleo.tipos import AssetRef, Incidencia, Progreso, Resultado, componer_id
from ie123kit.nucleo.util import escribir_json

__all__ = ["COLUMNAS_TSV", "OBJETIVO", "JuegoPrincipal"]

#: Identificador del objetivo (coincide con `[objetivo].id` de activos.toml).
OBJETIVO = "juego_principal"

#: Columnas exactas del TSV de textos (UTF-8, tabulador, sin comillas).
COLUMNAS_TSV: tuple[str, ...] = (
    "id",
    "jp",
    "es_oficial",
    "traduccion",
    "max_px",
    "max_bytes",
    "estado",
)

#: Ficheros del ExeFS que aparecen en el inventario (soporte EXPERIMENTAL, no editable).
_EXEFS = ("banner.bnr", "icon.icn")

#: Byte de disposición que deben llevar los descriptores de vídeo de los MOFLEX del menú.
ROTACION_ESPERADA = 0x16

#: Literales declarados por CRO: {ruta_romfs: ((inicio, fin), ...)}. Vacío mientras la
#: auditoría de `cro/ina_menu.cro` siga pendiente: cualquier offset da CRO_FUERA_DE_RANGO.
RANGOS_CRO: Mapping[str, tuple[tuple[int, int], ...]] = {"cro/ina_menu.cro": ()}

_RAIZ_BASE = ("shared", "base_3ds")
_CODIFICACION_CRO = "cp932"
_MARCA = "%Y%m%d_%H%M"
#: Tema de las capas que crea la edición desde la GUI (texturas del menú).
_TEMA_GUI = "graficos"


# --------------------------------------------------------------------------- utilidades


def _inc(codigo: str, mensaje: str, *, ref: AssetRef | None = None, ruta: str | None = None,
         severidad: str = "error", pista: str | None = None) -> Incidencia:
    """Incidencia con el activo y la ruta ya rellenados."""
    return Incidencia(
        codigo=codigo,
        severidad=severidad,
        mensaje=mensaje,
        activo_id=None if ref is None else ref.id,
        ruta=ruta if ruta is not None else (None if ref is None else ref.ruta_romfs),
        pista=pista,
    )


def _avisar(progreso: Callable[[Progreso], None] | None, fase: str, actual: int, total: int,
            mensaje: str = "") -> None:
    if progreso is not None:
        progreso(Progreso(fase=fase, actual=actual, total=total, mensaje=mensaje))


def _romfs(ws: Any) -> Path:
    """`work/shared/base_3ds/romfs` del espacio de trabajo dado."""
    return Path(ws.work).joinpath(*_RAIZ_BASE, "romfs")


def _exefs(ws: Any) -> Path:
    """`work/shared/base_3ds/exefs` del espacio de trabajo dado."""
    return Path(ws.work).joinpath(*_RAIZ_BASE, "exefs")


def _fa(ws: Any) -> Path:
    return _romfs(ws) / "archive.fa"


def _stem(ruta: str) -> str:
    return PurePosixPath(ruta).stem


class _SinBase(Exception):
    """La base extraída no está disponible (en CI no hay ROM: no es un error del código)."""


def _abrir_fa(ws: Any) -> FaArchive:
    ruta = _fa(ws)
    if not ruta.is_file():
        raise _SinBase(str(ruta))
    return FaArchive(ruta)


# --------------------------------------------------------------------------- el objetivo


class JuegoPrincipal(JuegoBase):
    """Objetivo `juego_principal`: el menú de la recopilación."""

    PAQUETE = "ie123kit.juego_principal"

    # -- datos declarativos ------------------------------------------------

    def _seccion(self, nombre: str) -> dict[str, Any]:
        valor = self.datos_activos().get(nombre, {})
        return valor if isinstance(valor, dict) else {}

    def _solo_lectura(self) -> tuple[str, ...]:
        return tuple(self._seccion("romfs").get("solo_lectura", ()))

    def _sueltos(self) -> tuple[str, ...]:
        return tuple(self._seccion("romfs").get("sueltos", ()))

    def _cinematicas(self) -> tuple[str, ...]:
        return tuple(self._seccion("cinematicas").get("rutas", ()))

    def _exefs_ficheros(self) -> tuple[str, ...]:
        return tuple(self._seccion("exefs").get("ficheros", _EXEFS))

    def _exefs_experimental(self) -> bool:
        return bool(self._seccion("exefs").get("experimental", True))

    def _bloqueada(self, ruta: str) -> bool:
        return any(ruta.startswith(prefijo) for prefijo in self._solo_lectura())

    # -- inventario --------------------------------------------------------

    def activos(
        self,
        ws: Any,
        tipo: str | None = None,
        filtro: Callable[[AssetRef], bool] | None = None,
    ) -> list[AssetRef]:
        """Activos que NO viven dentro del `archive.fa` (la CRO suelta y el ExeFS).

        El escaneo del contenedor lo hace `servicio.registro_activos`; el servicio funde
        ambas listas por `id`. Sin ROM devuelve lista vacía: en CI eso NO es un error.
        """
        salida: list[AssetRef] = []
        romfs = _romfs(ws)
        for ruta in self._sueltos():
            fichero = romfs / ruta
            if not fichero.is_file():
                continue
            salida.append(
                AssetRef(
                    id=componer_id(OBJETIVO, "literal_cro", ruta),
                    objetivo=OBJETIVO,
                    tipo="literal_cro",
                    ruta_romfs=ruta,
                    tamano=fichero.stat().st_size,
                    editable="literales_cro" in self.info().capacidades,
                )
            )
        exefs = _exefs(ws)
        for nombre in self._exefs_ficheros():
            fichero = exefs / nombre
            if not fichero.is_file():
                continue
            salida.append(
                AssetRef(
                    id=componer_id(OBJETIVO, "ejecutable", nombre),
                    objetivo=OBJETIVO,
                    tipo="ejecutable",
                    ruta_romfs=nombre,
                    tamano=fichero.stat().st_size,
                    editable=False,
                )
            )
        if tipo is not None:
            salida = [r for r in salida if r.tipo == tipo]
        if filtro is not None:
            salida = [r for r in salida if filtro(r)]
        return salida

    # -- despacho ----------------------------------------------------------

    def exportar(self, ws: Any, ref: AssetRef, destino: Path, formato: str | None = None,
                 progreso: Callable[[Progreso], None] | None = None, cancel: Any = None) -> Resultado:
        """Exporta un activo; intercepta el ExeFS y las fuentes antes del despacho normal."""
        if cancel is not None:
            cancel.comprobar()
        try:
            if ref.tipo == "ejecutable":
                return self._exportar_ejecutable(ws, ref, Path(destino))
            if self._bloqueada(ref.ruta_romfs):
                return self._exportar_fuente(ws, ref, Path(destino))
        except CanceladoError:
            raise
        except _SinBase as exc:
            return self._sin_base(ref, exc)
        except Exception as exc:  # noqa: BLE001 - el contrato es que nunca lanza
            return Resultado.fallo([_inc("NOT_SUPPORTED", f"exportación fallida: {exc}", ref=ref)])
        return super().exportar(ws, ref, Path(destino), formato=formato, progreso=progreso, cancel=cancel)

    def importar(self, ws: Any, ref: AssetRef, origen: Path, simular: bool = True,
                 progreso: Callable[[Progreso], None] | None = None, cancel: Any = None) -> Resultado:
        """Importa un activo; el bloqueo v20 y el ExeFS experimental cortan antes del despacho."""
        if cancel is not None:
            cancel.comprobar()
        if self._bloqueada(ref.ruta_romfs):
            return Resultado.fallo(
                [
                    _inc(
                        "BLOQUEO_V20",
                        f"{ref.ruta_romfs}: prefijo de solo lectura; la tipografía v20 está bloqueada",
                        ref=ref,
                        pista="Requiere una petición explícita del usuario sobre la tipografía (AGENTS.md).",
                    )
                ]
            )
        if ref.tipo == "ejecutable":
            return Resultado.fallo(
                [
                    _inc(
                        "NOT_SUPPORTED",
                        f"{ref.ruta_romfs}: el soporte de ExeFS (SMDH/banner/icono) sigue siendo experimental",
                        ref=ref,
                    )
                ]
            )
        return super().importar(ws, ref, Path(origen), simular=simular, progreso=progreso, cancel=cancel)

    # -- ExeFS y fuentes ---------------------------------------------------

    def _sin_base(self, ref: AssetRef, exc: Exception) -> Resultado:
        return Resultado.fallo(
            [
                _inc(
                    "NOT_SUPPORTED",
                    f"no hay base extraída ({exc}); el toolkit no distribuye ROMs",
                    ref=ref,
                    pista="Extrae la ROM en work/shared/base_3ds/ (Norma 2: nunca se versiona).",
                )
            ]
        )

    def _exportar_ejecutable(self, ws: Any, ref: AssetRef, destino: Path) -> Resultado:
        """Vuelca a JSON los títulos del SMDH/banner del ExeFS (EXPERIMENTAL, solo lectura)."""
        fichero = _exefs(ws) / ref.ruta_romfs
        if not fichero.is_file():
            raise _SinBase(str(fichero))
        datos = fichero.read_bytes()
        titulos = _titulos_smdh(datos)
        if titulos is None:
            return Resultado.fallo(
                [_inc("NOT_SUPPORTED", f"{ref.ruta_romfs}: no contiene una cabecera SMDH legible", ref=ref)]
            )
        salida = destino if destino.suffix == ".json" else destino / f"{_stem(ref.ruta_romfs)}.smdh.json"
        salida.parent.mkdir(parents=True, exist_ok=True)
        escribir_json(salida, {"fichero": ref.ruta_romfs, "experimental": self._exefs_experimental(),
                               "titulos": titulos})
        return Resultado.correcto(
            datos={"titulos": titulos, "experimental": self._exefs_experimental()},
            artefactos=(str(salida),),
        )

    def _exportar_fuente(self, ws: Any, ref: AssetRef, destino: Path) -> Resultado:
        """Lee una .bcfnt bloqueada y vuelca sus métricas (la escritura está prohibida)."""
        arc = _abrir_fa(ws)
        if not ref.ruta_romfs.lower().endswith(".bcfnt"):
            return Resultado.fallo(
                [_inc("NOT_SUPPORTED", f"{ref.ruta_romfs}: solo se leen fuentes .bcfnt", ref=ref)]
            )
        fuente = BCFNT(arc.read(ref.ruta_romfs))
        salida = destino if destino.suffix == ".json" else destino / f"{_stem(ref.ruta_romfs)}.bcfnt.json"
        salida.parent.mkdir(parents=True, exist_ok=True)
        info = {"fichero": ref.ruta_romfs, "solo_lectura": True, "tglp": fuente.tglp()}
        escribir_json(salida, info)
        return Resultado.correcto(datos=info, artefactos=(str(salida),))

    # -- gráficos ----------------------------------------------------------

    def _exportar_graficos(self, ws: Any, ref: AssetRef, destino: Path, **kw: Any) -> Resultado:
        """Vuelca cada CTPK del .arc como PNG RGBA más su `<tex>.qna.json`."""
        progreso = kw.get("progreso")
        cancel = kw.get("cancel")
        try:
            arc = _abrir_fa(ws)
            datos = arc.read(ref.ruta_romfs)
            crudo = sszl.unwrap(datos)
            lista = list(texturas.iter_ctpk(crudo))
            rects = _rects_qna(datos)
            carpeta = Path(destino) / _stem(ref.ruta_romfs)
            carpeta.mkdir(parents=True, exist_ok=True)
            artefactos: list[str] = []
            total = len(lista)
            for indice, textura in enumerate(lista, start=1):
                if cancel is not None:
                    cancel.comprobar()
                imagen = texturas.load_texture(arc, ref.ruta_romfs, textura.nombre)
                png = carpeta / f"{PurePosixPath(textura.nombre).stem}.png"
                imagen.save(png)
                meta = carpeta / f"{PurePosixPath(textura.nombre).stem}.qna.json"
                escribir_json(
                    meta,
                    {
                        "arc": ref.ruta_romfs,
                        "textura": textura.nombre,
                        "ancho": textura.ancho,
                        "alto": textura.alto,
                        "formato": textura.formato,
                        "tamano": textura.tamano,
                        "rects": [list(caja) for nombre, caja in rects if nombre == textura.nombre],
                    },
                )
                artefactos += [str(png), str(meta)]
                _avisar(progreso, "exportar_graficos", indice, total, textura.nombre)
            return Resultado.correcto(datos={"texturas": [t.nombre for t in lista]},
                                      artefactos=tuple(artefactos))
        except CanceladoError:
            raise
        except _SinBase as exc:
            return self._sin_base(ref, exc)
        except KeyError as exc:
            return Resultado.fallo([_inc("NOT_SUPPORTED", f"{ref.ruta_romfs}: no está en la base ({exc})", ref=ref)])
        except Exception as exc:  # noqa: BLE001 - todo fallo sale como Resultado
            return Resultado.fallo([_inc("NOT_SUPPORTED", f"{ref.ruta_romfs}: {exc}", ref=ref)])

    def _importar_graficos(self, ws: Any, ref: AssetRef, origen: Path, **kw: Any) -> Resultado:
        """Sustituye texturas del .arc con los PNG de `origen` (mismo tamaño exacto)."""
        simular = bool(kw.get("simular", True))
        progreso = kw.get("progreso")
        cancel = kw.get("cancel")
        try:
            arc = _abrir_fa(ws)
            crudo = sszl.unwrap(arc.read(ref.ruta_romfs))
            por_nombre = {t.nombre: t for t in texturas.iter_ctpk(crudo)}
            plan, incidencias, cambios, sin_cambios = _plan_desde_png(ref, Path(origen), por_nombre)
            if incidencias:
                return Resultado.fallo(incidencias)
            if not plan and not sin_cambios:
                return Resultado.fallo(
                    [_inc("TAMANO_PNG", f"{ref.ruta_romfs}: no hay ningún PNG que corresponda a una textura",
                          ref=ref)]
                )
            if cancel is not None:
                cancel.comprobar()
            _avisar(progreso, "importar_graficos", 1, 2, "plan")
            if simular:
                return Resultado.correcto(datos={"simulado": True, "cambios": cambios,
                                                 "sin_cambios": sin_cambios})
            capa = self._nueva_capa(ws)
            informe = texturas.apply_plan(arc, {ref.ruta_romfs: plan}, capa.aqui / "extra", rewrap="raw")
            revision = texturas.validate_plan(arc, {ref.ruta_romfs: plan}, capa.aqui / "extra")
            _avisar(progreso, "importar_graficos", 2, 2, "capa")
            if not revision.ok:
                return Resultado.fallo(
                    [_inc("RECT_QNA", f"{ref.ruta_romfs}: {p}", ref=ref) for p in revision.problemas]
                )
            return Resultado.correcto(
                datos={"simulado": False, "cambios": cambios, "sin_cambios": sin_cambios,
                       "informe": informe, "capa": str(capa.aqui)},
                artefactos=(str(capa.aqui / "extra" / ref.ruta_romfs),),
            )
        except CanceladoError:
            raise
        except _SinBase as exc:
            return self._sin_base(ref, exc)
        except Exception as exc:  # noqa: BLE001 - todo fallo sale como Resultado
            return Resultado.fallo([_inc("TAMANO_PNG", f"{ref.ruta_romfs}: {exc}", ref=ref)])

    # -- textos ------------------------------------------------------------

    def _exportar_textos(self, ws: Any, ref: AssetRef, destino: Path, **kw: Any) -> Resultado:
        """Vuelca las cadenas del recurso a TSV UTF-8 (o PO con `formato='po'`)."""
        formato = kw.get("formato") or "tsv"
        cancel = kw.get("cancel")
        try:
            arc = _abrir_fa(ws)
            blob = arc.read(ref.ruta_romfs)
            if cancel is not None:
                cancel.comprobar()
            filas = [
                {
                    "id": componer_id(OBJETIVO, ref.tipo, ref.ruta_romfs, f"0x{offset:x}"),
                    "jp": texto,
                    "es_oficial": "",
                    "traduccion": "",
                    "max_px": "",
                    "max_bytes": str(largo),
                    "estado": "original",
                }
                for offset, largo, texto in _cadenas(blob)
            ]
            salida = _escribir_textos(Path(destino), ref, filas, formato)
            return Resultado.correcto(datos={"cadenas": len(filas), "formato": formato},
                                      artefactos=(str(salida),))
        except CanceladoError:
            raise
        except _SinBase as exc:
            return self._sin_base(ref, exc)
        except KeyError as exc:
            return Resultado.fallo([_inc("NOT_SUPPORTED", f"{ref.ruta_romfs}: no está en la base ({exc})", ref=ref)])
        except Exception as exc:  # noqa: BLE001 - todo fallo sale como Resultado
            return Resultado.fallo([_inc("NOT_SUPPORTED", f"{ref.ruta_romfs}: {exc}", ref=ref)])

    def _importar_textos(self, ws: Any, ref: AssetRef, origen: Path, **kw: Any) -> Resultado:
        """Reinserta el TSV en el recurso, respetando el hueco de cada cadena."""
        simular = bool(kw.get("simular", True))
        cancel = kw.get("cancel")
        try:
            arc = _abrir_fa(ws)
            blob = bytearray(arc.read(ref.ruta_romfs))
            filas, incidencias = _leer_tsv(Path(origen), ref)
            if incidencias:
                return Resultado.fallo(incidencias)
            huecos = {f"0x{offset:x}": (offset, largo) for offset, largo, _ in _cadenas(bytes(blob))}
            cambios: list[dict[str, Any]] = []
            problemas: list[Incidencia] = []
            for fila in filas:
                if cancel is not None:
                    cancel.comprobar()
                traduccion = fila.get("traduccion", "").strip()
                if not traduccion:
                    continue
                clave = (fila.get("id", "").rpartition("#")[2]) or ""
                sitio = huecos.get(clave)
                if sitio is None:
                    problemas.append(_inc("NF_HUERFANO", f"{ref.ruta_romfs}: cadena sin sitio ({clave})", ref=ref))
                    continue
                codificado, incidencia = _codificar(traduccion, ref)
                if incidencia is not None:
                    problemas.append(incidencia)
                    continue
                offset, largo = sitio
                if len(codificado) > largo:
                    problemas.append(
                        _inc("EXCEDE_BYTES", f"{ref.ruta_romfs}#{clave}: {len(codificado)} B > {largo} B", ref=ref)
                    )
                    continue
                blob[offset:offset + largo] = codificado + bytes(largo - len(codificado))
                cambios.append({"offset": offset, "bytes": len(codificado), "texto": traduccion})
            if problemas:
                return Resultado.fallo(problemas)
            if simular:
                return Resultado.correcto(datos={"simulado": True, "cambios": cambios})
            capa = self._nueva_capa(ws)
            destino = capa.extra(ref.ruta_romfs)
            destino.write_bytes(bytes(blob))
            return Resultado.correcto(
                datos={"simulado": False, "cambios": cambios, "capa": str(capa.aqui)},
                artefactos=(str(destino),),
            )
        except CanceladoError:
            raise
        except _SinBase as exc:
            return self._sin_base(ref, exc)
        except Exception as exc:  # noqa: BLE001 - todo fallo sale como Resultado
            return Resultado.fallo([_inc("NOT_SUPPORTED", f"{ref.ruta_romfs}: {exc}", ref=ref)])

    # -- literales de la CRO ----------------------------------------------

    def _rangos(self, ruta: str) -> tuple[tuple[int, int], ...]:
        return tuple(RANGOS_CRO.get(ruta, ()))

    def _exportar_literales_cro(self, ws: Any, ref: AssetRef, destino: Path, **kw: Any) -> Resultado:
        """Vuelca a TSV los literales de los rangos DECLARADOS de la CRO."""
        formato = kw.get("formato") or "tsv"
        try:
            fichero = _romfs(ws) / ref.ruta_romfs
            if not fichero.is_file():
                raise _SinBase(str(fichero))
            cro = Cro(fichero.read_bytes())
            filas = []
            for inicio, fin in self._rangos(ref.ruta_romfs):
                for offset, largo, texto in _cadenas(cro.to_bytes()[inicio:fin], base=inicio):
                    filas.append(
                        {
                            "id": componer_id(OBJETIVO, ref.tipo, ref.ruta_romfs, f"0x{offset:x}"),
                            "jp": texto,
                            "es_oficial": "",
                            "traduccion": "",
                            "max_px": "",
                            "max_bytes": str(largo),
                            "estado": "original",
                        }
                    )
            salida = _escribir_textos(Path(destino), ref, filas, formato)
            return Resultado.correcto(
                datos={"literales": len(filas), "rangos": [list(r) for r in self._rangos(ref.ruta_romfs)]},
                artefactos=(str(salida),),
                incidencias=()
                if self._rangos(ref.ruta_romfs)
                else (
                    _inc("CRO_FUERA_DE_RANGO",
                         f"{ref.ruta_romfs}: no hay rangos declarados todavía (auditoría pendiente)",
                         ref=ref, severidad="aviso"),
                ),
            )
        except CanceladoError:
            raise
        except _SinBase as exc:
            return self._sin_base(ref, exc)
        except Exception as exc:  # noqa: BLE001 - todo fallo sale como Resultado
            return Resultado.fallo([_inc("NOT_SUPPORTED", f"{ref.ruta_romfs}: {exc}", ref=ref)])

    def _importar_literales_cro(self, ws: Any, ref: AssetRef, origen: Path, **kw: Any) -> Resultado:
        """Parchea literales de la CRO; fuera de un rango declarado no se toca nada."""
        simular = bool(kw.get("simular", True))
        cancel = kw.get("cancel")
        try:
            fichero = _romfs(ws) / ref.ruta_romfs
            if not fichero.is_file():
                raise _SinBase(str(fichero))
            filas, incidencias = _leer_tsv(Path(origen), ref)
            if incidencias:
                return Resultado.fallo(incidencias)
            rangos = self._rangos(ref.ruta_romfs)
            parcheador = CroPatcher(fichero)
            cambios: list[dict[str, Any]] = []
            problemas: list[Incidencia] = []
            for fila in filas:
                if cancel is not None:
                    cancel.comprobar()
                traduccion = fila.get("traduccion", "").strip()
                if not traduccion:
                    continue
                clave = fila.get("id", "").rpartition("#")[2]
                offset = _offset(clave)
                if offset is None or not any(ini <= offset < fin for ini, fin in rangos):
                    problemas.append(
                        _inc("CRO_FUERA_DE_RANGO",
                             f"{ref.ruta_romfs}: offset {clave!r} fuera de los rangos declarados", ref=ref)
                    )
                    continue
                _codificado, incidencia = _codificar(traduccion, ref)
                if incidencia is not None:
                    problemas.append(incidencia)
                    continue
                try:
                    parcheador.literal(offset, fila.get("jp", ""), traduccion)
                except Exception as exc:  # noqa: BLE001 - todo fallo sale como Resultado
                    problemas.append(_inc("EXCEDE_BYTES", f"{ref.ruta_romfs}@{clave}: {exc}", ref=ref))
                    continue
                cambios.append({"offset": offset, "texto": traduccion})
            if problemas:
                return Resultado.fallo(problemas)
            if simular:
                return Resultado.correcto(datos={"simulado": True, "cambios": cambios})
            capa = self._nueva_capa(ws)
            salida = parcheador.save(capa.aqui)
            return Resultado.correcto(
                datos={"simulado": False, "cambios": cambios, "capa": str(capa.aqui)},
                artefactos=(str(salida),),
            )
        except CanceladoError:
            raise
        except _SinBase as exc:
            return self._sin_base(ref, exc)
        except Exception as exc:  # noqa: BLE001 - todo fallo sale como Resultado
            return Resultado.fallo([_inc("NOT_SUPPORTED", f"{ref.ruta_romfs}: {exc}", ref=ref)])

    # -- cinemáticas -------------------------------------------------------

    def _ruta_moflex(self, ws: Any, ref: AssetRef) -> Path:
        """Ruta local del MOFLEX; primero la base suelta, si no la entrada del archive."""
        suelto = _romfs(ws) / ref.ruta_romfs
        if suelto.is_file():
            return suelto
        raise _SinBase(str(suelto))

    def _exportar_cinematicas(self, ws: Any, ref: AssetRef, destino: Path, **kw: Any) -> Resultado:
        """Comprueba la rotación 0x16 y saca un MP4 con `nucleo.media.moflex`."""
        try:
            if ref.ruta_romfs not in self._cinematicas():
                return Resultado.fallo(
                    [_inc("NOT_SUPPORTED", f"{ref.ruta_romfs}: no es una cinemática declarada", ref=ref)]
                )
            fuente = self._ruta_moflex(ws, ref)
            fallo = _revisar_rotacion(fuente, ref)
            if fallo is not None:
                return Resultado.fallo([fallo])
            exportar_mp4 = getattr(moflex, "exportar_mp4", None)
            if exportar_mp4 is None:
                return Resultado.fallo(
                    [_inc("NOT_SUPPORTED", "nucleo.media.moflex.exportar_mp4 no está disponible", ref=ref)]
                )
            salida = Path(destino) if Path(destino).suffix == ".mp4" else Path(destino) / f"{_stem(ref.ruta_romfs)}.mp4"
            salida.parent.mkdir(parents=True, exist_ok=True)
            datos = exportar_mp4(fuente, salida, ws=ws)
            return Resultado.correcto(datos=dict(datos or {}), artefactos=(str(salida),))
        except CanceladoError:
            raise
        except HerramientaAusente as exc:
            return Resultado.fallo([_inc("HERRAMIENTA_AUSENTE", str(exc), ref=ref)])
        except _SinBase as exc:
            return self._sin_base(ref, exc)
        except Exception as exc:  # noqa: BLE001 - todo fallo sale como Resultado
            return Resultado.fallo([_inc("NOT_SUPPORTED", f"{ref.ruta_romfs}: {exc}", ref=ref)])

    def _importar_cinematicas(self, ws: Any, ref: AssetRef, origen: Path, **kw: Any) -> Resultado:
        """Coloca un MOFLEX ya codificado en una capa nueva (rotación 0x16 obligatoria)."""
        simular = bool(kw.get("simular", True))
        try:
            if ref.ruta_romfs not in self._cinematicas():
                return Resultado.fallo(
                    [_inc("NOT_SUPPORTED", f"{ref.ruta_romfs}: no es una cinemática declarada", ref=ref)]
                )
            fuente = Path(origen)
            if not fuente.is_file() or fuente.suffix.lower() != ".moflex":
                return Resultado.fallo(
                    [_inc("NOT_SUPPORTED", f"{fuente}: se esperaba un .moflex ya codificado", ref=ref)]
                )
            fallo = _revisar_rotacion(fuente, ref)
            if fallo is not None:
                return Resultado.fallo([fallo])
            if simular:
                return Resultado.correcto(
                    datos={"simulado": True, "cambios": [{"ruta": ref.ruta_romfs, "bytes": fuente.stat().st_size}]}
                )
            capa = self._nueva_capa(ws)
            destino = capa.extra(ref.ruta_romfs)
            destino.write_bytes(fuente.read_bytes())
            return Resultado.correcto(
                datos={"simulado": False, "capa": str(capa.aqui)}, artefactos=(str(destino),)
            )
        except CanceladoError:
            raise
        except Exception as exc:  # noqa: BLE001 - todo fallo sale como Resultado
            return Resultado.fallo([_inc("LAYOUT_MOFLEX", f"{ref.ruta_romfs}: {exc}", ref=ref)])

    # -- capas y construcción ---------------------------------------------

    def _dir_capas(self, ws: Any) -> Path:
        """`work/juego_principal/capas`."""
        return Path(ws.work) / OBJETIVO / "capas"

    def _version_capa(self, ws: Any) -> str:
        """`vNN` de la capa nueva: la candidata siguiente a la última conocida (como IE1), si no `v1`."""
        try:
            candidatas = list(ws.listar_candidatas())
        except Exception:  # noqa: BLE001 - un workspace sin candidatas no es un error
            candidatas = []
        numeros = [int(m.group(1)) for m in (re.search(r"(\d+)$", c) for c in candidatas) if m]
        existentes = []
        carpeta = self._dir_capas(ws)
        if carpeta.is_dir():
            existentes = [int(m.group(1)) for m in (re.fullmatch(r"v(\d+)", h.name) for h in carpeta.iterdir()) if m]
        todos = numeros + existentes
        return f"v{max(todos) + 1}" if todos else "v1"

    def _nueva_capa(self, ws: Any) -> Capa:
        """Crea `work/juego_principal/capas/graficos/gui_<aaaammdd_hhmm>/` con su capa.toml.

        Disposición por tema (docs/ARQUITECTURA.md): la versión va en capa.toml, no en la ruta.
        """
        version = self._version_capa(ws)
        nombre = f"gui_{datetime.now(UTC).strftime(_MARCA)}"
        carpeta = self._dir_capas(ws) / _TEMA_GUI / nombre
        sufijo = 1
        while carpeta.exists():
            sufijo += 1
            carpeta = self._dir_capas(ws) / _TEMA_GUI / f"{nombre}_{sufijo}"
        carpeta.mkdir(parents=True)
        (carpeta / "capa.toml").write_text(
            "[capa]\n"
            f'objetivo = "{OBJETIVO}"\n'
            f'tema = "{_TEMA_GUI}"\n'
            f'version = "{version}"\n'
            f'linea = "{carpeta.name}"\n'
            'descripcion = "capa creada por ie123kit.juego_principal"\n',
            encoding="utf-8",
        )
        return Capa(self._capa_creada(carpeta), raiz=ws.raiz)

    def aportaciones(self, ws: Any, capas: Iterable[str] | Mapping[str, Any] | None = None,
                     progreso: Callable[[Progreso], None] | None = None,
                     cancel: Any = None) -> Aportacion:
        """Funde las capas de `work/juego_principal/capas/` en una aportación."""
        if cancel is not None:
            cancel.comprobar()
        entradas: dict[str, bytes | Path] = {}
        sueltos: dict[str, Path] = {}
        carpetas = _carpetas_capa(self._dir_capas(ws), capas)
        for indice, carpeta in enumerate(carpetas, start=1):
            if cancel is not None:
                cancel.comprobar()
            capa = Capa(carpeta, raiz=ws.raiz)
            extra = capa.aqui / "extra"
            if extra.is_dir():
                for fichero in sorted(extra.rglob("*")):
                    if fichero.is_file():
                        entradas[fichero.relative_to(extra).as_posix()] = fichero
            cro_dir = capa.aqui / "romfs" / "cro"
            if cro_dir.is_dir():
                for fichero in sorted(cro_dir.glob("*.cro")):
                    sueltos[f"cro/{fichero.name}"] = fichero
            _avisar(progreso, "aportaciones", indice, len(carpetas), capa.aqui.name)
        return Aportacion(entradas_fa=entradas, eventos={}, literales_cro={}, romfs_sueltos=sueltos)

    # -- validación --------------------------------------------------------

    def reglas_validacion(self) -> list[Regla]:
        """Invariantes del menú de la recopilación."""
        return [
            Regla("BLOQUEO_V20", "Las fuentes .bcfnt de font/ se quedan intactas (bloqueo v20).", "fuentes"),
            Regla("CRO_FUERA_DE_RANGO", "cro/ina_menu.cro solo cambia en los literales declarados.", "literales_cro"),
            Regla("LAYOUT_MOFLEX", "Los MOFLEX del menú conservan la disposición de rotación 0x16.", "cinematicas"),
            Regla("NOT_SUPPORTED", "El ExeFS (SMDH/banner/icono) es experimental: solo lectura.", "ejecutable"),
        ]


# --------------------------------------------------------------------------- auxiliares


def _titulos_smdh(datos: bytes) -> dict[str, str] | None:
    """Títulos por slot de idioma de un SMDH; None si no lleva la cabecera."""
    if datos[:4] != smdh_mod.SMDH_MAGIC:
        return None
    salida: dict[str, str] = {}
    for slot in range(12):
        inicio = smdh_mod.TITLE_TABLE_OFFSET + slot * smdh_mod.TITLE_SLOT_SIZE
        fin = inicio + smdh_mod.TITLE_SLOT_SIZE
        if fin > len(datos):
            break
        texto = datos[inicio:fin].decode("utf-16le", "replace").split("\0")[0].strip()
        if texto:
            salida[str(slot)] = texto
    return salida


def _rects_qna(datos: bytes) -> list[tuple[str, tuple[int, ...]]]:
    """Rectángulos declarados por los maquetados QNA del .arc (vacío si no hay ninguno)."""
    salida: list[tuple[str, tuple[int, ...]]] = []
    try:
        for _offset, layout in qna_mod.qna_in_arc(datos):
            salida.extend(qna_mod.regions(layout.to_bytes()))
    except Exception:  # noqa: BLE001 - un .arc sin QNA legible no aporta rectángulos
        return salida
    return salida


def _sin_tocar(textura: Any, imagen: Image.Image) -> bool:
    """``True`` si `imagen` trae exactamente los píxeles que la textura ya tiene.

    Se compara en RGBA decodificado. Reimportar el PNG que acaba de salir de `exportar`
    no es una edición y NO puede entrar en el plan: `validate_plan` exige que toda
    textura declarada cambie y, si no, la da por problema.
    """
    try:
        actual = ctpk.decode(textura.blob).convert("RGBA")
    except Exception:  # noqa: BLE001 - si no se decodifica, que lo decida apply_plan
        return False
    return actual.tobytes() == imagen.tobytes()


def _plan_desde_png(ref: AssetRef, origen: Path, por_nombre: dict[str, Any]
                    ) -> tuple[dict[str, Any], list[Incidencia], list[dict[str, Any]], list[str]]:
    """Plan de sustitución a partir de los PNG de `origen`, comprobando el tamaño exacto.

    Devuelve ``(plan, incidencias, cambios, sin_cambios)``; `sin_cambios` son las texturas
    reconocidas cuyo PNG es idéntico al original, que quedan FUERA del plan.
    """
    plan: dict[str, Any] = {}
    incidencias: list[Incidencia] = []
    cambios: list[dict[str, Any]] = []
    sin_cambios: list[str] = []
    carpeta = origen if origen.is_dir() else origen.parent
    pngs = sorted(carpeta.glob("*.png")) if carpeta.is_dir() else []
    if origen.is_file() and origen.suffix.lower() == ".png":
        pngs = [origen]
    for png in pngs:
        nombre = _nombre_textura(png.stem, por_nombre)
        if nombre is None:
            continue
        textura = por_nombre[nombre]
        with Image.open(png) as imagen:
            ancho, alto = imagen.size
            copia = imagen.convert("RGBA")
        if (ancho, alto) != (textura.ancho, textura.alto):
            incidencias.append(
                _inc("TAMANO_PNG",
                     f"{ref.ruta_romfs}::{nombre}: {ancho}x{alto} != {textura.ancho}x{textura.alto}", ref=ref)
            )
            continue
        if _sin_tocar(textura, copia):
            sin_cambios.append(nombre)
            continue
        plan[nombre] = _edicion(copia)
        cambios.append({"textura": nombre, "ancho": ancho, "alto": alto, "png": str(png)})
    return plan, incidencias, cambios, sin_cambios


def _nombre_textura(stem: str, por_nombre: dict[str, Any]) -> str | None:
    for nombre in por_nombre:
        if PurePosixPath(nombre).stem == stem or nombre == stem:
            return nombre
    return None


def _edicion(nueva: Image.Image) -> Callable[[Image.Image], Image.Image]:
    """Función de plan que sustituye la textura por `nueva` (mismo tamaño)."""

    def sustituir(antes: Image.Image) -> Image.Image:
        del antes
        return nueva

    sustituir.__name__ = "sustituir_png"
    return sustituir


def _cadenas(blob: bytes, base: int = 0) -> list[tuple[int, int, str]]:
    """Cadenas terminadas en NUL del blob: `(offset, bytes disponibles, texto)`."""
    salida: list[tuple[int, int, str]] = []
    inicio = 0
    datos = bytes(blob)
    for pos, byte in enumerate(datos):
        if byte != 0:
            continue
        crudo = datos[inicio:pos]
        if len(crudo) >= 2 and _legible(crudo):
            salida.append((base + inicio, len(crudo), _decodificar(crudo)))
        inicio = pos + 1
    return salida


def _legible(crudo: bytes) -> bool:
    return all(b >= 0x20 or b in (0x09, 0x0A) for b in crudo)


def _decodificar(crudo: bytes) -> str:
    """Texto de una cadena de la ROM; el ancho completo pasa por `nucleo.texto`."""
    try:
        return ancho_completo.decode_fullwidth(crudo)
    except Exception:  # noqa: BLE001 - texto ilegible: se cae a cp932
        return crudo.decode(_CODIFICACION_CRO, "replace")


def _codificar(texto: str, ref: AssetRef) -> tuple[bytes, Incidencia | None]:
    """Codifica con el layout aprobado v20; GLIFO_NO_SOPORTADO si algún carácter no cabe."""
    aprobado = tipografia_v20.approved_layout(texto)
    try:
        return aprobado.encode(_CODIFICACION_CRO), None
    except UnicodeEncodeError as exc:
        return b"", _inc("GLIFO_NO_SOPORTADO", f"{texto!r}: {exc}", ref=ref)


def _offset(clave: str) -> int | None:
    try:
        return int(clave, 16) if clave.startswith("0x") else int(clave)
    except ValueError:
        return None


def _escribir_textos(destino: Path, ref: AssetRef, filas: list[dict[str, str]], formato: str) -> Path:
    """Escribe las filas como TSV UTF-8 (o PO si se pide explícitamente)."""
    if destino.suffix in (".tsv", ".po"):
        salida = destino
    else:
        salida = destino / f"{_stem(ref.ruta_romfs)}.{'po' if formato == 'po' else 'tsv'}"
    salida.parent.mkdir(parents=True, exist_ok=True)
    if formato == "po":
        lineas = ['msgid ""', 'msgstr ""', '"Content-Type: text/plain; charset=UTF-8\\n"', ""]
        for fila in filas:
            lineas += [f"#: {fila['id']}", f'msgid "{_escapar(fila["jp"])}"',
                       f'msgstr "{_escapar(fila["traduccion"])}"', ""]
        salida.write_text("\n".join(lineas), encoding="utf-8")
        return salida
    with salida.open("w", encoding="utf-8", newline="") as fh:
        escritor = csv.DictWriter(fh, fieldnames=list(COLUMNAS_TSV), delimiter="\t",
                                  lineterminator="\n", quoting=csv.QUOTE_NONE, escapechar="\\")
        escritor.writeheader()
        for fila in filas:
            escritor.writerow({c: fila.get(c, "") for c in COLUMNAS_TSV})
    return salida


def _escapar(texto: str) -> str:
    return texto.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _leer_tsv(origen: Path, ref: AssetRef) -> tuple[list[dict[str, str]], list[Incidencia]]:
    """Lee el TSV y comprueba que las columnas son exactamente `COLUMNAS_TSV`."""
    if not origen.is_file():
        return [], [_inc("NOT_SUPPORTED", f"{origen}: no existe el fichero de textos", ref=ref)]
    with origen.open("r", encoding="utf-8", newline="") as fh:
        lector = csv.DictReader(fh, delimiter="\t", quoting=csv.QUOTE_NONE, escapechar="\\")
        cabecera = tuple(lector.fieldnames or ())
        if cabecera != COLUMNAS_TSV:
            return [], [
                _inc("NOT_SUPPORTED",
                     f"{origen}: columnas {cabecera} != {COLUMNAS_TSV}", ref=ref)
            ]
        return [{k: (v or "") for k, v in fila.items()} for fila in lector], []


def _revisar_rotacion(fichero: Path, ref: AssetRef) -> Incidencia | None:
    """Comprueba que todos los descriptores de vídeo llevan la disposición 0x16."""
    valores = moflex.disposicion_rotacion(fichero)
    malos = [v for v in valores if v != ROTACION_ESPERADA]
    if not valores:
        return _inc("LAYOUT_MOFLEX", f"{fichero.name}: sin descriptores de vídeo legibles", ref=ref)
    if malos:
        return _inc(
            "LAYOUT_MOFLEX",
            f"{fichero.name}: disposición {[hex(v) for v in malos]} != 0x{ROTACION_ESPERADA:02x}",
            ref=ref,
        )
    return None


def _carpetas_capa(raiz: Path, capas: Iterable[str] | Mapping[str, Any] | None) -> list[Path]:
    """Carpetas de capa bajo `work/juego_principal/capas/<tema>/<linea>/` (o la antigua `<vNN>/<linea>/`).

    `historial/` no cuenta. Una capa se pide por su nombre o por `<tema>/<linea>`.
    """
    from ie123kit.nucleo.construir.capas import listar_capas

    nombres = set(capas) if capas is not None else None
    return [c for c in listar_capas(raiz)
            if nombres is None or c.name in nombres or f"{c.parent.name}/{c.name}" in nombres]
