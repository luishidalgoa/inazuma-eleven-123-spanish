"""Objetivo completo de Inazuma Eleven 1: ganchos reales sobre las primitivas de ``nucleo``.

Reglas de la casa que este módulo hace cumplir y nunca relaja:

- ningún método lanza: todo sale como :class:`~ie123kit.nucleo.tipos.Resultado` con
  incidencias de código estable;
- ``simular=True`` (el defecto) no escribe ni un byte; con ``simular=False`` se escribe
  SIEMPRE una capa NUEVA en ``work/ie1/capas/<tema>/<linea>_<aaaammdd_hhmm>/``, jamás
  dentro de una candidata ya construida;
- todo lo que caiga bajo ``[romfs].solo_lectura`` (las fuentes) se rechaza con
  ``BLOQUEO_V20``: el perfil tipográfico v20 está bloqueado para toda la recopilación;
- no hay codificador WAV -> SADL: importar voces desde ``.wav`` es ``NOT_SUPPORTED``, y las
  voces J18/J19 no se instalan nunca (ver ``ie1/media/voces.py``).

Este paquete solo importa ``ie123kit.nucleo.*`` y sus propios submódulos. Las primitivas
pesadas (Pillow, CTPK, moflex) se importan dentro de cada método para que importar el
módulo no tenga efectos ni coste.
"""

from __future__ import annotations

import csv
import json
import re
from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ie123kit.nucleo.errores import CanceladoError
from ie123kit.nucleo.juego import Aportacion, JuegoBase, Regla, es_editable
from ie123kit.nucleo.tipos import (
    AssetRef,
    CancelToken,
    Incidencia,
    Progreso,
    Resultado,
    componer_id,
)

__all__ = ["CABECERA_TSV", "JuegoIE1"]

#: Columnas exactas del TSV de textos (acordadas con ``ie1.texto.eventos``).
CABECERA_TSV: tuple[str, ...] = ("id", "jp", "es_oficial", "traduccion", "max_px", "max_bytes", "estado")

#: Avance nominal del perfil v20 (``dialogue_lock.approved_layout``: advance=11, width=220).
_AVANCE_PX = 11

_BASE_ROMFS = ("shared", "base_3ds", "romfs")
_PACKS = {"eve": "events", "mch": "events_mch"}
_RX_VERSION = re.compile(r"(\d+)\s*$")
#: Tema de ``work/ie1/capas/<tema>/`` para cada línea de capa que generan estas acciones.
_TEMA_DE_LINEA = {"gui": "graficos", "eventos": "dialogo", "tablas": "nombres", "cro": "menus_cro",
                  "cinematicas": "media", "voces": "media"}


# --------------------------------------------------------------------------- utilidades


def _base_romfs(ws: Any) -> Path:
    """``work/shared/base_3ds/romfs`` del workspace (no se crea)."""
    return Path(ws.work).joinpath(*_BASE_ROMFS)


def _archive(ws: Any) -> Path:
    """``archive.fa`` de la base 3DS."""
    return _base_romfs(ws) / "archive.fa"


def _avance(progreso: Callable[[Progreso], None] | None, fase: str, actual: int, total: int, mensaje: str = "") -> None:
    if progreso is not None:
        progreso(Progreso(fase=fase, actual=actual, total=total, mensaje=mensaje))


def _comprobar(cancel: CancelToken | None) -> None:
    if cancel is not None:
        cancel.comprobar()


def _inc(codigo: str, mensaje: str, ref: AssetRef | None = None, *, severidad: str = "error",
         ubicacion: str | None = None, pista: str | None = None) -> Incidencia:
    return Incidencia(
        codigo=codigo,
        severidad=severidad,
        mensaje=mensaje,
        activo_id=None if ref is None else ref.id,
        ruta=None if ref is None else ref.ruta_romfs,
        ubicacion=ubicacion,
        pista=pista,
    )


def _fallo(codigo: str, mensaje: str, ref: AssetRef | None = None, **kw: Any) -> Resultado:
    return Resultado.fallo([_inc(codigo, mensaje, ref, **kw)])


def _de_excepcion(exc: Exception, ref: AssetRef | None) -> Resultado:
    """Cualquier error inesperado sale como Resultado (los ganchos no lanzan)."""
    return _fallo("NOT_SUPPORTED", f"{type(exc).__name__}: {exc}", ref)


def _marca() -> str:
    return datetime.now(tz=UTC).strftime("%Y%m%d_%H%M")


def _ancho_px(texto: str) -> int:
    """Ancho en píxeles de la línea más larga, con el avance nominal del perfil v20."""
    return max((len(linea) for linea in texto.replace("\f", "\n").split("\n")), default=0) * _AVANCE_PX


# --------------------------------------------------------------------------- el objetivo


class JuegoIE1(JuegoBase):
    """Inazuma Eleven 1 (``inazuma1/`` del ``archive.fa``, ``cro/ina_main1.cro`` y sus voces)."""

    PAQUETE = "ie123kit.ie1"

    # ---------------------------------------------------------------- datos declarativos

    def _tabla(self, nombre: str) -> Mapping[str, Any]:
        valor = self.datos_activos().get(nombre, {})
        return valor if isinstance(valor, dict) else {}

    def _solo_lectura(self, ruta_romfs: str) -> bool:
        prefijos = tuple(self._tabla("romfs").get("solo_lectura", ()))
        return any(ruta_romfs.startswith(p) for p in prefijos)

    def _protegidos(self) -> frozenset[int]:
        return frozenset(int(x) for x in self._tabla("eventos").get("protegidos", ()))

    # ---------------------------------------------------------------- inventario

    def activos(
        self,
        ws: Any,
        tipo: str | None = None,
        filtro: Callable[[AssetRef], bool] | None = None,
    ) -> list[AssetRef]:
        """Activos de IE1 que NO viven dentro del ``archive.fa``.

        El contenido del contenedor lo escanea ``servicio.registro_activos`` y el servicio
        funde ambas listas por ``id``. Aquí salen la CRO suelta y los ``.SAD`` de voces.
        Sin ROM (CI) la lista es vacía: eso no es un error.
        """
        capacidades = self.info().capacidades
        base = _base_romfs(ws)
        refs: list[AssetRef] = []
        try:
            for rel in self._tabla("romfs").get("cros", ()):
                ruta = base / rel
                if ruta.is_file():
                    refs.append(self._ref(rel, "literal_cro", ruta.stat().st_size, capacidades))
            for prefijo in self._tabla("voces").get("prefijos", ()):
                carpeta = base / prefijo
                if not carpeta.is_dir():
                    continue
                for sad in sorted(carpeta.rglob("*")):
                    if sad.is_file() and sad.suffix.lower() == ".sad":
                        rel = prefijo + sad.relative_to(carpeta).as_posix()
                        refs.append(self._ref(rel, "voz", sad.stat().st_size, capacidades))
        except OSError:
            return []
        if tipo is not None:
            refs = [r for r in refs if r.tipo == tipo]
        if filtro is not None:
            refs = [r for r in refs if filtro(r)]
        return refs

    def _ref(self, ruta_romfs: str, tipo: str, tamano: int, capacidades: frozenset[str]) -> AssetRef:
        return AssetRef(
            id=componer_id("ie1", tipo, ruta_romfs),
            objetivo="ie1",
            tipo=tipo,
            ruta_romfs=ruta_romfs,
            cadena_contenedores=(),
            tamano=tamano,
            editable=es_editable(tipo, capacidades),
        )

    # ---------------------------------------------------------------- capas de salida

    def _siguiente_version(self, ws: Any) -> str:
        """``vNN`` de la próxima candidata; ``v1`` si aún no hay ninguna."""
        try:
            nombres = list(ws.listar_candidatas())
        except Exception:  # noqa: BLE001 - un workspace sintético puede no tener candidatas
            nombres = []
        numeros = [int(m.group(1)) for m in (_RX_VERSION.search(n) for n in nombres) if m]
        return f"v{(max(numeros) + 1) if numeros else 1}"

    def _preparar_capa(self, ws: Any, linea: str) -> Path:
        """Crea una capa NUEVA de ``work/ie1/capas/<tema>/<linea>_<marca>/`` con su ``capa.toml``.

        El tema sale de :data:`_TEMA_DE_LINEA` (docs/ARQUITECTURA.md); la versión (la próxima
        candidata) ya no va en la ruta sino en ``capa.toml``.
        """
        version = self._siguiente_version(ws)
        tema = _TEMA_DE_LINEA.get(linea, "graficos")
        try:
            capas = Path(ws.dirs("ie1").capas)
        except Exception:  # noqa: BLE001 - workspace sin dirs(): ruta canónica de la arquitectura
            capas = Path(ws.work) / "ie1" / "capas"
        # Siempre una carpeta NUEVA: dos importaciones en el mismo minuto no se mezclan (_2, _3…).
        nombre = f"{linea}_{_marca()}"
        destino = capas / tema / nombre
        sufijo = 1
        while destino.exists():
            sufijo += 1
            destino = capas / tema / f"{nombre}_{sufijo}"
        destino.mkdir(parents=True)
        meta = (
            "[capa]\n"
            'objetivo = "ie1"\n'
            f'tema = "{tema}"\n'
            f'version = "{version}"\n'
            f'linea = "{destino.name}"\n'
            'descripcion = "capa generada por ie123kit.ie1.acciones"\n'
        )
        (destino / "capa.toml").write_text(meta, encoding="utf-8")
        return self._capa_creada(destino)

    # ---------------------------------------------------------------- gráficos

    def _exportar_graficos(self, ws: Any, ref: AssetRef, destino: Path, **kw: Any) -> Resultado:
        """Vuelca a PNG RGBA cada CTPK del ``.arc``/``.lzs``, con sus rectángulos QNA."""
        progreso, cancel = kw.get("progreso"), kw.get("cancel")
        try:
            _comprobar(cancel)
            from ie123kit.nucleo.contenedores.fa import FaArchive
            from ie123kit.nucleo.graficos import qna as qna_mod
            from ie123kit.nucleo.graficos.texturas import iter_ctpk, load_texture

            arc = FaArchive(str(_archive(ws)))
            datos = arc.read(ref.ruta_romfs)
            texturas = list(iter_ctpk(datos))
            rectangulos: dict[str, list[tuple[int, int, int, int]]] = {}
            for _off, layout in qna_mod.qna_in_arc(datos):
                for nombre, caja in qna_mod.regions(layout.to_bytes()):
                    rectangulos.setdefault(nombre, []).append(caja)
            destino = Path(destino)
            destino.mkdir(parents=True, exist_ok=True)
            artefactos: list[str] = []
            total = len(texturas)
            for indice, textura in enumerate(texturas, 1):
                _comprobar(cancel)
                imagen = load_texture(arc, ref.ruta_romfs, textura.nombre)
                tallo = Path(textura.nombre).stem or f"tex{indice}"
                png = destino / f"{tallo}.png"
                imagen.save(png)
                meta = destino / f"{tallo}.qna.json"
                meta.write_text(
                    json.dumps(
                        {
                            "textura": textura.nombre,
                            "ancho": textura.ancho,
                            "alto": textura.alto,
                            "formato": textura.formato,
                            "rects": [list(c) for c in rectangulos.get(textura.nombre, [])],
                        },
                        ensure_ascii=False,
                        indent=2,
                    ),
                    encoding="utf-8",
                )
                artefactos += [str(png), str(meta)]
                _avance(progreso, "graficos", indice, total, textura.nombre)
            return Resultado.correcto({"texturas": [t.nombre for t in texturas]}, artefactos=tuple(artefactos))
        except CanceladoError:
            raise
        except Exception as exc:  # noqa: BLE001 - contrato: los ganchos no lanzan
            return _de_excepcion(exc, ref)

    def _importar_graficos(self, ws: Any, ref: AssetRef, origen: Path, **kw: Any) -> Resultado:
        """Sustituye texturas del ``.arc`` con los PNG de `origen` (V37: ``rewrap='raw'``)."""
        progreso, cancel = kw.get("progreso"), kw.get("cancel")
        simular = bool(kw.get("simular", True))
        if self._solo_lectura(ref.ruta_romfs):
            return _fallo("BLOQUEO_V20", f"{ref.ruta_romfs} es de solo lectura (perfil v20 bloqueado)", ref)
        try:
            _comprobar(cancel)
            from ie123kit.nucleo.contenedores.fa import FaArchive
            from ie123kit.nucleo.graficos.texturas import apply_plan, iter_ctpk, validate_plan

            origen = Path(origen)
            pngs = sorted(origen.glob("*.png")) if origen.is_dir() else [origen]
            if not pngs:
                return _fallo("NOT_SUPPORTED", f"no hay PNG que importar en {origen}", ref)
            arc = FaArchive(str(_archive(ws)))
            datos = arc.read(ref.ruta_romfs)
            por_tallo = {Path(t.nombre).stem: t for t in iter_ctpk(datos)}
            plan: dict[str, dict[str, Any]] = {ref.ruta_romfs: {}}
            incidencias: list[Incidencia] = []
            cambios: list[dict[str, Any]] = []
            sin_cambios: list[str] = []
            for indice, png in enumerate(pngs, 1):
                _comprobar(cancel)
                textura = por_tallo.get(png.stem)
                if textura is None:
                    incidencias.append(_inc("NOT_SUPPORTED", f"textura desconocida: {png.stem}", ref))
                    continue
                nueva = self._cargar_png(png, textura, ref, incidencias)
                if nueva is None:
                    continue
                # Solo se declara lo que de verdad cambia: `validate_plan` exige que TODA
                # textura declarada cambie, así que reimportar un PNG idéntico al exportado
                # (ida y vuelta sin tocar nada) no puede entrar en el plan.
                if self._misma_textura(textura, nueva):
                    sin_cambios.append(textura.nombre)
                    _avance(progreso, "graficos", indice, len(pngs), png.name)
                    continue
                plan[ref.ruta_romfs][textura.nombre] = _edicion(nueva)
                cambios.append({"textura": textura.nombre, "png": str(png)})
                _avance(progreso, "graficos", indice, len(pngs), png.name)
            if incidencias:
                return Resultado.fallo(incidencias)
            if simular:
                return Resultado.correcto({"simulado": True, "diff": cambios, "sin_cambios": sin_cambios})
            capa = self._preparar_capa(ws, "gui")
            apply_plan(arc, plan, capa / "extra", rewrap="raw")
            informe = validate_plan(arc, plan, capa / "extra")
            if not informe.ok:
                return Resultado.fallo([_inc("TAMANO_PNG", p, ref) for p in informe.problemas])
            return Resultado.correcto(
                {"simulado": False, "capa": str(capa), "diff": cambios, "sin_cambios": sin_cambios},
                artefactos=(str(capa),),
            )
        except CanceladoError:
            raise
        except Exception as exc:  # noqa: BLE001 - contrato: los ganchos no lanzan
            return _de_excepcion(exc, ref)

    def _misma_textura(self, textura: Any, imagen: Any) -> bool:
        """``True`` si `imagen` tiene exactamente los píxeles que ya lleva la textura.

        Se compara en RGBA decodificado, no en bytes del CTPK: es lo que decide si la
        importación tiene algo que sustituir (con los códecs de `nucleo.graficos.ctpk`,
        unos píxeles iguales vuelven a codificarse en el mismo blob).
        """
        from ie123kit.nucleo.graficos import ctpk

        try:
            actual = ctpk.decode(textura.blob).convert("RGBA")
        except Exception:  # noqa: BLE001 - si no se puede decodificar, que decida apply_plan
            return False
        return actual.tobytes() == imagen.convert("RGBA").tobytes()

    def _cargar_png(self, png: Path, textura: Any, ref: AssetRef, incidencias: list[Incidencia]) -> Any:
        from PIL import Image

        imagen = Image.open(png).convert("RGBA")
        if imagen.size != (textura.ancho, textura.alto):
            incidencias.append(
                _inc(
                    "TAMANO_PNG",
                    f"{png.name}: {imagen.size} != ({textura.ancho}, {textura.alto})",
                    ref,
                    ubicacion=textura.nombre,
                )
            )
            return None
        return imagen

    # ---------------------------------------------------------------- textos y eventos

    def _ambito(self, ref: AssetRef) -> str:
        """Ámbito de texto al que pertenece el activo: ``cro``, ``eventos`` o ``tablas``."""
        if ref.tipo == "literal_cro" or ref.ruta_romfs.endswith(".cro"):
            return "cro"
        if ref.tipo == "evento" or "/script/" in ref.ruta_romfs or ref.ruta_romfs.endswith((".pkh", ".pkb")):
            return "eventos"
        return "tablas"

    def _exportar_textos(self, ws: Any, ref: AssetRef, destino: Path, **kw: Any) -> Resultado:
        """Exporta el ámbito que corresponda al activo (TSV UTF-8 por defecto)."""
        ambito = self._ambito(ref)
        if ambito == "eventos":
            return self._exportar_eventos(ws, ref, destino, **kw)
        if ambito == "cro":
            return self._exportar_literales_cro(ws, ref, destino, **kw)
        return self._exportar_tablas(ws, ref, destino, **kw)

    def _importar_textos(self, ws: Any, ref: AssetRef, origen: Path, **kw: Any) -> Resultado:
        """Importa el ámbito que corresponda al activo."""
        ambito = self._ambito(ref)
        if ambito == "eventos":
            return self._importar_eventos(ws, ref, origen, **kw)
        if ambito == "cro":
            return self._importar_literales_cro(ws, ref, origen, **kw)
        return self._importar_tablas(ws, ref, origen, **kw)

    def _pack(self, ref: AssetRef) -> str:
        return "mch" if "mch" in Path(ref.ruta_romfs).name.lower() else "eve"

    def _exportar_eventos(self, ws: Any, ref: AssetRef, destino: Path, **kw: Any) -> Resultado:
        """Un TSV por evento (``<destino>/<pack>/<eid>.tsv``) vía ``ie1.texto.eventos``."""
        progreso, cancel = kw.get("progreso"), kw.get("cancel")
        formato = kw.get("formato") or "tsv"
        if formato not in {"tsv", "po"}:
            return _fallo("NOT_SUPPORTED", f"formato de textos desconocido: {formato!r}", ref)
        try:
            _comprobar(cancel)
            from ie123kit.ie1.texto import eventos as mod

            ids = [int(ref.subruta)] if (ref.subruta or "").isdigit() else None
            protegidos = self._protegidos()
            if ids and protegidos.intersection(ids):
                _avance(progreso, "eventos", 1, 1, "protegido")
            _avance(progreso, "eventos", 0, 1, "exportando")
            ficheros = mod.exportar(_archive(ws), Path(destino), pack=self._pack(ref), ids=ids)
            _avance(progreso, "eventos", 1, 1, f"{len(ficheros)} ficheros")
            return Resultado.correcto(
                {"formato": formato, "ficheros": len(ficheros)},
                artefactos=tuple(str(f) for f in ficheros),
            )
        except CanceladoError:
            raise
        except Exception as exc:  # noqa: BLE001 - contrato: los ganchos no lanzan
            return _de_excepcion(exc, ref)

    def _importar_eventos(self, ws: Any, ref: AssetRef, origen: Path, **kw: Any) -> Resultado:
        """Prepara los ``.ssd`` del pack a partir de los TSV traducidos, con las reglas de v20."""
        progreso, cancel = kw.get("progreso"), kw.get("cancel")
        simular = bool(kw.get("simular", True))
        if self._solo_lectura(ref.ruta_romfs):
            return _fallo("BLOQUEO_V20", f"{ref.ruta_romfs} es de solo lectura (perfil v20 bloqueado)", ref)
        try:
            _comprobar(cancel)
            origen = Path(origen)
            tsvs = sorted(origen.rglob("*.tsv")) if origen.is_dir() else [origen]
            protegidos = self._protegidos()
            incidencias: list[Incidencia] = []
            for tsv in tsvs:
                # La protección castiga EDITAR, no exportar: una ida y vuelta sin cambios
                # trae el TSV del evento protegido con la columna `traduccion` vacía y no
                # debe dar incidencia (si no, ningún roundtrip limpio sería posible).
                if tsv.stem.isdigit() and int(tsv.stem) in protegidos and self._tsv_traducido(tsv):
                    incidencias.append(
                        _inc(
                            "NOT_SUPPORTED",
                            f"evento protegido {tsv.stem}: está en [eventos].protegidos y no se edita",
                            ref,
                            ubicacion=tsv.stem,
                            pista="DONT_TOUCH del tutorial",
                        )
                    )
            for indice, tsv in enumerate(tsvs, 1):
                _comprobar(cancel)
                incidencias += self._revisar_tsv(tsv, ref)
                _avance(progreso, "eventos", indice, len(tsvs), tsv.name)
            if any(i.severidad == "error" for i in incidencias):
                return Resultado.fallo(incidencias)
            from ie123kit.ie1.texto import eventos as mod

            salida = None if simular else self._preparar_capa(ws, "eventos")
            informe = mod.importar(
                _archive(ws), origen, pack=self._pack(ref), simular=simular, salida=salida
            )
            incidencias += [
                _inc(str(d.get("codigo", "NOT_SUPPORTED")), str(d.get("mensaje", "")), ref,
                     ubicacion=d.get("ubicacion"))
                for d in informe.get("incidencias", ())
            ]
            if any(i.severidad == "error" for i in incidencias):
                return Resultado.fallo(incidencias)
            datos = {
                "simulado": simular,
                "eventos_preparados": informe.get("eventos_preparados", 0),
                "ficheros": list(informe.get("ficheros", ())),
            }
            if salida is not None:
                datos["capa"] = str(salida)
            return Resultado(ok=True, datos=datos, incidencias=tuple(incidencias))
        except CanceladoError:
            raise
        except Exception as exc:  # noqa: BLE001 - contrato: los ganchos no lanzan
            return _de_excepcion(exc, ref)

    # -- reglas de texto ------------------------------------------------

    def _tsv_traducido(self, tsv: Path) -> bool:
        """``True`` si el TSV trae alguna traducción escrita, es decir, si edita el evento.

        Un TSV recién exportado sale con ``traduccion`` vacía en todas las filas: eso NO
        es una edición. Un TSV ilegible se deja pasar aquí; ``_revisar_tsv`` lo reporta.
        """
        try:
            with tsv.open("r", encoding="utf-8", newline="") as fh:
                return any(
                    (fila.get("traduccion") or "").strip()
                    for fila in csv.DictReader(fh, delimiter="\t")
                )
        except OSError:
            return False

    def _revisar_tsv(self, tsv: Path, ref: AssetRef) -> list[Incidencia]:
        """Comprueba cabecera y reglas v20 de cada fila; nunca trunca en silencio."""
        incidencias: list[Incidencia] = []
        try:
            with tsv.open("r", encoding="utf-8", newline="") as fh:
                filas = list(csv.DictReader(fh, delimiter="\t"))
                cabecera = tuple(filas[0].keys()) if filas else CABECERA_TSV
        except OSError as exc:
            return [_inc("NOT_SUPPORTED", f"{tsv.name}: {exc}", ref)]
        if tuple(cabecera) != CABECERA_TSV:
            return [_inc("NOT_SUPPORTED", f"{tsv.name}: cabecera {cabecera} != {CABECERA_TSV}", ref)]
        for fila in filas:
            incidencias += self._revisar_fila(fila, tsv.name, ref)
        return incidencias

    def _revisar_fila(self, fila: Mapping[str, Any], fichero: str, ref: AssetRef) -> list[Incidencia]:
        texto = (fila.get("traduccion") or "").strip()
        ident = str(fila.get("id") or "")
        ubicacion = f"{fichero}:{ident}"
        if not texto:
            return []
        salida: list[Incidencia] = []
        jp = fila.get("jp") or ""
        if texto.count("%NF") != jp.count("%NF") or texto.endswith("%NF") or "%NF%NF" in texto:
            salida.append(_inc("NF_HUERFANO", f"%NF descolocado en {ident}", ref, ubicacion=ubicacion))
        maquetado = self._maquetar(texto, ref, ubicacion, salida)
        if maquetado is not None and maquetado.count("\f") != texto.count("\f"):
            salida.append(_inc("PAGINAS_DISTINTAS", f"el paginado \\f cambia en {ident}", ref, ubicacion=ubicacion))
        salida += self._revisar_limites(texto, maquetado, fila, ref, ubicacion)
        return salida

    def _maquetar(self, texto: str, ref: AssetRef, ubicacion: str, salida: list[Incidencia]) -> str | None:
        """Aplica el layout v20 aprobado; si el módulo bloqueado no está, avisa y sigue."""
        try:
            from ie123kit.nucleo.texto.tipografia_v20 import approved_layout

            return approved_layout(texto)
        except Exception as exc:  # noqa: BLE001 - sin las fuentes bloqueadas no se puede maquetar
            salida.append(
                _inc("HERRAMIENTA_AUSENTE", f"layout v20 no disponible: {exc}", ref,
                     severidad="aviso", ubicacion=ubicacion)
            )
            return None

    def _revisar_limites(self, texto: str, maquetado: str | None, fila: Mapping[str, Any],
                         ref: AssetRef, ubicacion: str) -> list[Incidencia]:
        salida: list[Incidencia] = []
        max_px = _entero(fila.get("max_px"))
        max_bytes = _entero(fila.get("max_bytes"))
        if max_px and _ancho_px(maquetado if maquetado is not None else texto) > max_px:
            salida.append(_inc("EXCEDE_PX", f"la línea excede {max_px} px", ref, ubicacion=ubicacion))
        codificado = self._codificar(texto, ref, ubicacion, salida)
        if max_bytes and codificado is not None and len(codificado) > max_bytes:
            salida.append(
                _inc("EXCEDE_BYTES", f"{len(codificado)} B > {max_bytes} B", ref, ubicacion=ubicacion)
            )
        return salida

    def _codificar(self, texto: str, ref: AssetRef, ubicacion: str, salida: list[Incidencia]) -> bytes | None:
        """Codifica con el transporte latino de ancho completo; el glifo que falta se declara."""
        try:
            from ie123kit.nucleo.texto.ancho_completo import encode_fullwidth

            return encode_fullwidth(texto)
        except UnicodeEncodeError as exc:
            salida.append(_inc("GLIFO_NO_SOPORTADO", f"{exc}", ref, ubicacion=ubicacion))
            return None
        except Exception as exc:  # noqa: BLE001 - módulo bloqueado ausente en el entorno
            salida.append(
                _inc("HERRAMIENTA_AUSENTE", f"codificador v20 no disponible: {exc}", ref,
                     severidad="aviso", ubicacion=ubicacion)
            )
            return None

    # -- tablas ---------------------------------------------------------

    def _exportar_tablas(self, ws: Any, ref: AssetRef, destino: Path, **kw: Any) -> Resultado:
        """Vuelca una tabla de registros fijos de 32 B (item.dat) a TSV UTF-8."""
        progreso, cancel = kw.get("progreso"), kw.get("cancel")
        try:
            _comprobar(cancel)
            from ie123kit.nucleo.contenedores.fa import FaArchive
            from ie123kit.nucleo.texto.ancho_completo import decode_fullwidth

            datos = FaArchive(str(_archive(ws))).read(ref.ruta_romfs)
            if len(datos) % 32:
                return _fallo("NOT_SUPPORTED", f"{ref.ruta_romfs}: no es una tabla de 32 B", ref)
            destino = Path(destino)
            destino.parent.mkdir(parents=True, exist_ok=True)
            total = len(datos) // 32
            with destino.open("w", encoding="utf-8", newline="") as fh:
                escritor = csv.writer(fh, delimiter="\t", lineterminator="\n")
                escritor.writerow(CABECERA_TSV)
                for indice in range(total):
                    _comprobar(cancel)
                    crudo = datos[indice * 32:indice * 32 + 19].split(b"\0")[0]
                    try:
                        jp = decode_fullwidth(crudo)
                    except Exception:  # noqa: BLE001 - un registro ilegible no aborta el volcado
                        jp = crudo.decode("shift_jis", "replace")
                    escritor.writerow([indice, jp, "", "", 0, 19, "original"])
                    _avance(progreso, "tablas", indice + 1, total, str(indice))
            return Resultado.correcto({"registros": total}, artefactos=(str(destino),))
        except CanceladoError:
            raise
        except Exception as exc:  # noqa: BLE001 - contrato: los ganchos no lanzan
            return _de_excepcion(exc, ref)

    def _importar_tablas(self, ws: Any, ref: AssetRef, origen: Path, **kw: Any) -> Resultado:
        """Escribe los nombres traducidos en la tabla (19 B por nombre, sin truncar)."""
        progreso, cancel = kw.get("progreso"), kw.get("cancel")
        simular = bool(kw.get("simular", True))
        if self._solo_lectura(ref.ruta_romfs):
            return _fallo("BLOQUEO_V20", f"{ref.ruta_romfs} es de solo lectura (perfil v20 bloqueado)", ref)
        try:
            _comprobar(cancel)
            from ie123kit.ie1.texto.tablas import write_field
            from ie123kit.nucleo.contenedores.fa import FaArchive

            origen = Path(origen)
            incidencias = self._revisar_tsv(origen, ref)
            if any(i.severidad == "error" for i in incidencias):
                return Resultado.fallo(incidencias)
            datos = bytearray(FaArchive(str(_archive(ws))).read(ref.ruta_romfs))
            with origen.open("r", encoding="utf-8", newline="") as fh:
                filas = [f for f in csv.DictReader(fh, delimiter="\t") if (f.get("traduccion") or "").strip()]
            for indice, fila in enumerate(filas, 1):
                _comprobar(cancel)
                posicion = _entero(fila.get("id")) * 32
                if posicion < 0 or posicion + 32 > len(datos):
                    incidencias.append(_inc("NOT_SUPPORTED", f"registro fuera de rango: {fila.get('id')}", ref))
                    continue
                try:
                    write_field(datos, posicion, 19, fila["traduccion"].strip())
                except ValueError as exc:
                    incidencias.append(_inc("EXCEDE_BYTES", f"{fila.get('id')}: {exc}", ref))
                _avance(progreso, "tablas", indice, len(filas), str(fila.get("id")))
            if any(i.severidad == "error" for i in incidencias):
                return Resultado.fallo(incidencias)
            if simular:
                return Resultado.correcto({"simulado": True, "registros": len(filas)}, incidencias=tuple(incidencias))
            capa = self._preparar_capa(ws, "tablas")
            salida = capa / "extra" / ref.ruta_romfs
            salida.parent.mkdir(parents=True, exist_ok=True)
            salida.write_bytes(bytes(datos))
            return Resultado(
                ok=True,
                datos={"simulado": False, "registros": len(filas), "capa": str(capa)},
                incidencias=tuple(incidencias),
                artefactos=(str(salida),),
            )
        except CanceladoError:
            raise
        except Exception as exc:  # noqa: BLE001 - contrato: los ganchos no lanzan
            return _de_excepcion(exc, ref)

    # ---------------------------------------------------------------- literales de la CRO

    def _cro(self, ws: Any, ref: AssetRef) -> Path:
        rel = ref.ruta_romfs if ref.ruta_romfs.endswith(".cro") else "cro/ina_main1.cro"
        return _base_romfs(ws) / rel

    def _exportar_literales_cro(self, ws: Any, ref: AssetRef, destino: Path, **kw: Any) -> Resultado:
        """Vuelca los segmentos de la CRO y una plantilla JSON de literales a rellenar."""
        progreso, cancel = kw.get("progreso"), kw.get("cancel")
        try:
            _comprobar(cancel)
            from ie123kit.nucleo.ejecutable.cro import Cro
            from ie123kit.nucleo.util import sha256_file

            ruta = self._cro(ws, ref)
            cro = Cro(ruta.read_bytes())
            _avance(progreso, "cro", 1, 2, ruta.name)
            destino = Path(destino)
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_text(
                json.dumps(
                    {
                        "cro": ref.ruta_romfs,
                        "sha256": sha256_file(ruta),
                        "segmentos": [
                            {"offset": s.offset, "tamano": s.tamano} if hasattr(s, "tamano")
                            else {"offset": getattr(s, "offset", 0)}
                            for s in cro.segments()
                        ],
                        "entries": [],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            _avance(progreso, "cro", 2, 2, "listo")
            return Resultado.correcto({"cro": ref.ruta_romfs}, artefactos=(str(destino),))
        except CanceladoError:
            raise
        except Exception as exc:  # noqa: BLE001 - contrato: los ganchos no lanzan
            return _de_excepcion(exc, ref)

    def _importar_literales_cro(self, ws: Any, ref: AssetRef, origen: Path, **kw: Any) -> Resultado:
        """Aplica los literales declarados (``entries``: offset, esperado, nuevo) con CroPatcher."""
        progreso, cancel = kw.get("progreso"), kw.get("cancel")
        simular = bool(kw.get("simular", True))
        try:
            _comprobar(cancel)
            from ie123kit.nucleo.ejecutable.cro import CroPatcher

            entradas = json.loads(Path(origen).read_text(encoding="utf-8")).get("entries", [])
            ruta = self._cro(ws, ref)
            parcheador = CroPatcher(ruta)
            incidencias: list[Incidencia] = []
            aplicados = 0
            for indice, entrada in enumerate(entradas, 1):
                _comprobar(cancel)
                offset = _entero(entrada.get("offset"))
                if offset <= 0 or offset >= len(parcheador.base):
                    incidencias.append(_inc("CRO_FUERA_DE_RANGO", f"offset 0x{offset:x}", ref))
                    continue
                try:
                    parcheador.literal(offset, entrada["esperado"], entrada.get("nuevo", ""))
                    aplicados += 1
                except Exception as exc:  # noqa: BLE001 - se traduce a incidencia, no aborta
                    incidencias.append(_inc("CRO_FUERA_DE_RANGO", f"0x{offset:x}: {exc}", ref))
                _avance(progreso, "cro", indice, len(entradas), f"0x{offset:x}")
            if any(i.severidad == "error" for i in incidencias):
                return Resultado.fallo(incidencias)
            if simular:
                return Resultado.correcto({"simulado": True, "literales": aplicados})
            capa = self._preparar_capa(ws, "cro")
            escrito = parcheador.save(capa)
            return Resultado.correcto(
                {"simulado": False, "literales": aplicados, "capa": str(capa)},
                artefactos=(str(escrito),),
            )
        except CanceladoError:
            raise
        except Exception as exc:  # noqa: BLE001 - contrato: los ganchos no lanzan
            return _de_excepcion(exc, ref)

    # ---------------------------------------------------------------- cinemáticas

    def _exportar_cinematicas(self, ws: Any, ref: AssetRef, destino: Path, **kw: Any) -> Resultado:
        """MOFLEX -> ``<id>.mp4`` + ``<id>.srt`` vía ``ie1.media.cinematicas``."""
        progreso, cancel = kw.get("progreso"), kw.get("cancel")
        try:
            _comprobar(cancel)
            from ie123kit.ie1.media import cinematicas as mod

            pelicula = self._pelicula(mod, ref)
            subtitulos = None
            if pelicula and pelicula.get("subtitulos_dat"):
                candidato = _base_romfs(ws) / str(pelicula["subtitulos_dat"])
                subtitulos = candidato if candidato.is_file() else None
            _avance(progreso, "cinematicas", 0, 1, ref.ruta_romfs)
            informe = mod.exportar(
                _base_romfs(ws) / ref.ruta_romfs, Path(destino), subtitulos=subtitulos, ws=ws
            )
            _avance(progreso, "cinematicas", 1, 1, "listo")
            return Resultado.correcto(dict(informe))
        except CanceladoError:
            raise
        except Exception as exc:  # noqa: BLE001 - contrato: los ganchos no lanzan
            return _de_excepcion(exc, ref)

    def _importar_cinematicas(self, ws: Any, ref: AssetRef, origen: Path, **kw: Any) -> Resultado:
        """MP4 (+SRT) -> MOFLEX, exigiendo que se conserve la disposición de rotación 0x16."""
        progreso, cancel = kw.get("progreso"), kw.get("cancel")
        simular = bool(kw.get("simular", True))
        try:
            _comprobar(cancel)
            from ie123kit.ie1.media import cinematicas as mod

            origen = Path(origen)
            srt = origen.with_suffix(".srt")
            _avance(progreso, "cinematicas", 0, 1, origen.name)
            destino = (
                _base_romfs(ws) / ref.ruta_romfs
                if simular
                else self._preparar_capa(ws, "cinematicas") / "romfs" / ref.ruta_romfs
            )
            if not simular:
                destino.parent.mkdir(parents=True, exist_ok=True)
            informe = mod.importar(
                origen, destino, srt=srt if srt.is_file() else None, simular=simular, ws=ws
            )
            _avance(progreso, "cinematicas", 1, 1, "listo")
            layout = informe.get("layout")
            if layout not in (0x16, "0x16"):
                return _fallo("LAYOUT_MOFLEX", f"disposición {layout!r} != 0x16", ref)
            datos = {"simulado": simular, **{k: v for k, v in informe.items() if k != "layout"}}
            datos["layout"] = layout if isinstance(layout, str) else f"0x{layout:02x}"
            return Resultado.correcto(datos)
        except CanceladoError:
            raise
        except Exception as exc:  # noqa: BLE001 - contrato: los ganchos no lanzan
            return _de_excepcion(exc, ref)

    def _pelicula(self, mod: Any, ref: AssetRef) -> dict[str, Any] | None:
        for pelicula in mod.peliculas():
            if pelicula.get("ruta_romfs") == ref.ruta_romfs or pelicula.get("id") == ref.subruta:
                return dict(pelicula)
        return None

    # ---------------------------------------------------------------- voces

    def _exportar_voces(self, ws: Any, ref: AssetRef, destino: Path, **kw: Any) -> Resultado:
        """SAD -> WAV (solo lectura del audio; no se reescribe ningún SADL)."""
        progreso, cancel = kw.get("progreso"), kw.get("cancel")
        try:
            _comprobar(cancel)
            from ie123kit.nucleo.media.audio import sad_a_wav

            _avance(progreso, "voces", 0, 1, ref.ruta_romfs)
            destino = Path(destino)
            destino.parent.mkdir(parents=True, exist_ok=True)
            informe = sad_a_wav(_base_romfs(ws) / ref.ruta_romfs, destino, ws=ws)
            _avance(progreso, "voces", 1, 1, "listo")
            return Resultado.correcto(dict(informe), artefactos=(str(destino),))
        except CanceladoError:
            raise
        except Exception as exc:  # noqa: BLE001 - contrato: los ganchos no lanzan
            return _de_excepcion(exc, ref)

    def _importar_voces(self, ws: Any, ref: AssetRef, origen: Path, **kw: Any) -> Resultado:
        """Solo acepta un ``.SAD`` validado: se copia entero, sin recortar, y se comprueba el sha256."""
        progreso, cancel = kw.get("progreso"), kw.get("cancel")
        simular = bool(kw.get("simular", True))
        origen = Path(origen)
        if origen.suffix.lower() != ".sad":
            return Resultado.no_soportado(
                "no hay codificador WAV -> SADL: aporta un .SAD europeo ya codificado",
                activo_id=ref.id,
            )
        try:
            _comprobar(cancel)
            import shutil

            from ie123kit.nucleo.media.audio import sha256, validar_sad

            _avance(progreso, "voces", 0, 1, origen.name)
            info = validar_sad(origen)
            if simular:
                _avance(progreso, "voces", 1, 1, "simulado")
                return Resultado.correcto({"simulado": True, "sha256": getattr(info, "sha256", None)})
            capa = self._preparar_capa(ws, "voces")
            destino = capa / "romfs" / ref.ruta_romfs
            destino.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(origen, destino)
            if sha256(destino) != sha256(origen):
                return _fallo("NOT_SUPPORTED", "la copia del SADL no coincide con el origen", ref)
            _avance(progreso, "voces", 1, 1, "copiado")
            return Resultado.correcto(
                {"simulado": False, "capa": str(capa), "sha256": sha256(destino)},
                artefactos=(str(destino),),
            )
        except CanceladoError:
            raise
        except Exception as exc:  # noqa: BLE001 - contrato: los ganchos no lanzan
            return _de_excepcion(exc, ref)

    # ---------------------------------------------------------------- aportaciones

    def aportaciones(
        self,
        ws: Any,
        capas: Iterable[str] | Mapping[str, Any] | None = None,
        progreso: Callable[[Progreso], None] | None = None,
        cancel: CancelToken | None = None,
    ) -> Aportacion:
        """Funde las capas de ``work/ie1/capas`` en entradas del archive, eventos y CRO suelta."""
        _comprobar(cancel)
        from ie123kit.nucleo.construir.capas import Capa

        aportacion = Aportacion()
        rutas = list(self._rutas_capas(ws, capas))
        for indice, ruta in enumerate(rutas, 1):
            _comprobar(cancel)
            capa = Capa(ruta, raiz=getattr(ws, "raiz", None))
            extra = capa.aqui / "extra"
            if extra.is_dir():
                for fichero in sorted(extra.rglob("*")):
                    if fichero.is_file():
                        aportacion.entradas_fa[fichero.relative_to(extra).as_posix()] = fichero
            for pack, carpeta in _PACKS.items():
                directorio = capa.aqui / carpeta
                if directorio.is_dir() and any(directorio.glob("*.ssd")):
                    aportacion.eventos[pack] = directorio
            # Todo lo de romfs/ de la capa (CRO, y también MOFLEX y SAD que escriben las importaciones
            # de cinemáticas y voces): lo que el constructor aún no sepa aplicar lo marca pendiente
            # el servicio, en vez de perderse aquí sin aviso.
            romfs = capa.aqui / "romfs"
            if romfs.is_dir():
                for fichero in sorted(romfs.rglob("*")):
                    if fichero.is_file():
                        aportacion.romfs_sueltos[fichero.relative_to(romfs).as_posix()] = fichero
            _avance(progreso, "aportaciones", indice, len(rutas), capa.aqui.name)
        return aportacion

    def _rutas_capas(self, ws: Any, capas: Iterable[str] | Mapping[str, Any] | None) -> list[Path]:
        """Rutas de capa a partir de rutas absolutas, nombres relativos o, sin argumento, todas."""
        try:
            raiz_capas = Path(ws.dirs("ie1").capas)
        except Exception:  # noqa: BLE001 - workspace sin dirs()
            raiz_capas = Path(ws.work) / "ie1" / "capas"
        if capas is None:
            from ie123kit.nucleo.construir.capas import listar_capas

            return listar_capas(raiz_capas)
        nombres = list(capas.keys()) if isinstance(capas, Mapping) else list(capas)
        rutas: list[Path] = []
        for nombre in nombres:
            ruta = Path(nombre)
            if not ruta.is_absolute():
                ruta = raiz_capas / nombre
            if ruta.is_dir():
                rutas.append(ruta)
        return rutas

    # ---------------------------------------------------------------- validación

    def reglas_validacion(self) -> list[Regla]:
        """Invariantes que comprueba ``ie123kit.ie1.verificar`` sobre una candidata."""
        return [
            Regla("ENTRADAS_IDENTICAS",
                  "toda entrada del archive.fa coincide con la base salvo las aportadas por capas",
                  "archive"),
            Regla("CRO_SOLO_LITERALES",
                  "la CRO solo difiere en los rangos de los literales declarados",
                  "cro"),
            Regla("FUENTES_INTACTAS",
                  "las fuentes de inazuma1/data_iz/font/ son idénticas a la base (bloqueo v20)",
                  "fuentes"),
            Regla("AUDIO_IDENTICO",
                  "cada SADL instalado es idéntico byte a byte a la fuente preparada",
                  "voces"),
            Regla("LAYOUT_MOFLEX",
                  "los MOFLEX conservan la disposición de rotación 0x16 y son decodificables",
                  "cinematicas"),
        ]


def _edicion(imagen: Any) -> Callable[[Any], Any]:
    """Función de plan que sustituye la textura por `imagen` (mismo tamaño, ya comprobado)."""

    def sustituir(_antes: Any) -> Any:
        return imagen

    sustituir.__name__ = "png_importado"
    return sustituir


def _entero(valor: Any) -> int:
    try:
        return int(str(valor).strip())
    except (TypeError, ValueError):
        return 0
