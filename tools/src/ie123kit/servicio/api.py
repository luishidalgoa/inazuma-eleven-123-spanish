"""Fachada sin cabeza del toolkit: la CLI y la futura GUI solo hablan con ``ServicioToolkit``.

Regla de capas: este módulo NO importa estáticamente ``ie123kit.juego_principal``/``ie1``/``ie2``/``ie3``.
El descubrimiento de juegos se hace con ``importlib.import_module`` sobre la tabla literal ``OBJETIVOS``.
Importar este módulo no tiene efectos: no lee ficheros ni resuelve la raíz del repositorio.
"""

from __future__ import annotations

import importlib
import inspect
import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ie123kit.nucleo.juego import InfoObjetivo, JuegoBase
from ie123kit.nucleo.tipos import API_VERSION, CancelToken, Incidencia, Progreso, Resultado

__all__ = [
    "API_VERSION",
    "MOTORES",
    "OBJETIVOS",
    "ServicioToolkit",
    "SolicitudConstruccion",
    "descubrir_juegos",
]

#: Objetivos con ``activos.toml`` hoy y el paquete que los implementa.
OBJETIVOS: dict[str, str] = {
    "juego_principal": "ie123kit.juego_principal",
    "ie1": "ie123kit.ie1",
    "ie2.tormenta_de_fuego": "ie123kit.ie2.tormenta_de_fuego",
    "ie2.ventisca_eterna": "ie123kit.ie2.ventisca_eterna",
    "ie3.rayo_celeste": "ie123kit.ie3.rayo_celeste",
    "ie3.fuego_explosivo": "ie123kit.ie3.fuego_explosivo",
    "ie3.amenaza_del_ogro": "ie123kit.ie3.amenaza_del_ogro",
}

#: Motores con entrada de fichero: ``(juego, motor) -> "módulo:función"`` (import dinámico, como OBJETIVOS).
#: Los motores son de un juego (sus límites y direcciones cambian); ``ie123 motor`` los expone.
MOTORES: dict[tuple[str, str], str] = {
    ("ie1", "paginar"): "ie123kit.ie1.texto.dialogo:paginar",
    ("ie2", "paginar"): "ie123kit.ie2.comun.motores:paginar",
    ("ie2", "teclado"): "ie123kit.ie2.comun.motores:teclado",
    ("ie2", "cro-ancho-dialogo"): "ie123kit.ie2.comun.motores:cro_ancho_dialogo",
    ("ie2", "voces"): "ie123kit.ie2.comun.motores:voces",
    ("ie2", "subtitulos"): "ie123kit.ie2.comun.motores:subtitulos",
}


def _juego_generico(paquete: str) -> JuegoBase:
    """Instancia mínima de JuegoBase para un paquete que aún no declara ``JUEGO`` (llega en F2.3)."""
    clase = type("JuegoGenerico", (JuegoBase,), {"PAQUETE": paquete, "__module__": __name__})
    return clase()


def _cargar_juego(paquete: str) -> JuegoBase | None:
    """Importa `paquete` y devuelve su JuegoBase; None si falta o está roto (nunca lanza).

    Un objetivo que no se carga no desaparece en silencio: `ServicioToolkit._juego` lo
    reporta como incidencia NOT_SUPPORTED en cuanto se pide.
    """
    try:
        modulo = importlib.import_module(paquete)
        declarado = getattr(modulo, "JUEGO", None)
        if declarado is None:
            return _juego_generico(paquete)
        return declarado() if isinstance(declarado, type) else declarado
    except Exception:
        return None


def descubrir_juegos(
    objetivos: dict[str, str] | None = None,
    *,
    extra: dict[str, JuegoBase] | None = None,
) -> dict[str, JuegoBase]:
    """Devuelve {id_objetivo: JuegoBase}. Un paquete ausente o roto se omite (nunca lanza)."""
    tabla = dict(OBJETIVOS if objetivos is None else objetivos)
    juegos: dict[str, JuegoBase] = {}
    for ident, paquete in tabla.items():
        juego = _cargar_juego(paquete)
        if juego is not None:
            juegos[ident] = juego
    for ident, juego in (extra or {}).items():
        juegos[ident] = juego
    return juegos


@dataclass(frozen=True)
class SolicitudConstruccion:
    """Petición de construcción de una candidata de TODA la recopilación."""

    base: str
    objetivos: tuple[str, ...]
    capas: tuple[str, ...]
    salida: str


def _incidencia(codigo: str, mensaje: str, **kw: Any) -> Incidencia:
    return Incidencia(codigo=codigo, severidad="error", mensaje=mensaje, **kw)


def _comprobar_bloqueo(bloqueo: Any, archive: Path, raiz: Path) -> Incidencia | None:
    """Ejecuta el bloqueo tipográfico v20 sobre la candidata; devuelve la incidencia si falla."""
    try:
        bloqueo.comprobar(archive, raiz)
    except Exception as exc:
        if getattr(exc, "codigo", "") in {"bloqueo_v20", "fuente_ausente", "candidata_ausente"}:
            return Incidencia("BLOQUEO_V20", "error", f"bloqueo tipográfico v20: {exc}", ruta=str(archive))
        return _incidencia("NOT_SUPPORTED", f"bloqueo v20: {exc}", ruta=str(archive))
    return None


def _cro_de_aportacion(aporte: Any) -> list[Path]:
    """CRO EXISTENTES que declara una aportación (admite una ruta suelta o una lista)."""
    valor = (aporte.get("cro") if isinstance(aporte, dict) else None) or []
    entradas = [valor] if isinstance(valor, (str, Path)) else list(valor)
    return [Path(c) for c in entradas if Path(c).is_file()]


#: Campos de ``nucleo.juego.Aportacion``; sirven para reconocerla sin importarla aquí.
_CAMPOS_APORTACION = ("entradas_fa", "eventos", "literales_cro", "romfs_sueltos")


def _es_cro_suelta(rel: Any) -> bool:
    """¿Esta ruta de ``romfs_sueltos`` es una CRO que el constructor sabe colocar?"""
    texto = str(rel).replace("\\", "/")
    return texto.startswith("cro/") and texto.endswith(".cro")


def _raiz_de_entradas_fa(entradas: Any) -> Path | None:
    """Raíz común de un ``entradas_fa`` que sea un árbol de ficheros ya volcado en disco.

    Una carpeta ``extra/`` cuyo árbol ES el de ``romfs`` se pasa entera al constructor. Si cada ``(ruta, path)`` cumple que
    ``path`` termina en ``ruta`` y todas comparten la misma raíz, esa raíz vale como ``extra``.
    Si no (bytes en memoria, o rutas que no comparten raíz), se devuelve None y el llamador las
    pasa como entradas sueltas (``entradas``) al constructor.
    """
    if not entradas:
        return None
    raices: set[str] = set()
    for rel, valor in entradas.items():
        if not isinstance(valor, Path):
            return None
        relativo = str(rel).replace("\\", "/").strip("/")
        absoluto = str(valor).replace("\\", "/")
        if not relativo or not absoluto.endswith("/" + relativo):
            return None
        raices.add(absoluto[: -(len(relativo) + 1)])
    if len(raices) != 1:
        return None
    return Path(next(iter(raices)))


def _aportacion_a_dict(ident: str, valor: Any) -> tuple[Any, list[str]]:
    """Traduce la ``Aportacion`` de un objetivo a la forma que entiende el constructor.

    El servicio recibe ``nucleo.juego.Aportacion`` (entradas_fa/eventos/literales_cro/
    romfs_sueltos) y ``nucleo.construir.candidata`` espera ``{objetivo, extra, eventos, cro}``:
    sin traducción, construir con ``--objetivos`` muere en ``_normalizar_aportaciones``.
    Devuelve también los campos que el constructor NO sabe aplicar todavía, para decirlos en vez
    de tirarlos. Lo que no sea ni un dict ni una ``Aportacion`` se pasa tal cual: que lo rechace
    el constructor con su propio error, sin que el servicio lo interprete.
    """
    if isinstance(valor, dict):
        return {**valor, "objetivo": valor.get("objetivo") or ident}, []
    if not all(hasattr(valor, campo) for campo in _CAMPOS_APORTACION):
        return valor, []
    romfs = dict(getattr(valor, "romfs_sueltos", None) or {})
    pendientes = []
    entradas_fa = dict(getattr(valor, "entradas_fa", None) or {})
    extra = _raiz_de_entradas_fa(entradas_fa)
    # Sin raíz común (varias capas fundidas, o bytes en memoria) se pasan como entradas sueltas:
    # el constructor las aplica tras el extra/ de esta aportación (F2.5).
    entradas = {} if extra is not None else entradas_fa
    if getattr(valor, "literales_cro", None):
        pendientes.append("literales_cro")
    if any(not _es_cro_suelta(rel) for rel in romfs):
        pendientes.append("romfs_sueltos que no son cro/*.cro")
    aporte = {
        "objetivo": ident,
        "extra": extra,
        "eventos": dict(getattr(valor, "eventos", None) or {}),
        "cro": [ruta for rel, ruta in sorted(romfs.items()) if _es_cro_suelta(rel)],
    }
    if entradas:
        aporte["entradas"] = entradas
    return aporte, pendientes


#: Rutas del `activos.toml` de `juego_principal` que delatan una capa del menú.
_RUTAS_MENU: tuple[str, ...] = ("menu/", "movie/", "message/", "import/", "patchscript/", "cro/ina_menu.cro")
#: Ficheros del ExeFS que pertenecen al juego principal.
_EXEFS_MENU: tuple[str, ...] = ("banner.bnr", "icon.icn")
#: Ficheros que identifican una carpeta de `work/` como capa y que se leen buscando esas rutas.
_FICHEROS_DE_CAPA: tuple[str, ...] = ("apply.py", "capa.toml", "report.json", "ownership.json")
#: Capas conocidas del menú que NO dejan rastro de rutas (producen imágenes que coloca otra
#: capa). Se listan a mano para que el histórico sea reproducible y no dependa de un grep.
_CAPAS_MENU_CONOCIDAS: tuple[str, ...] = ("graficos/pantalla_inicio", "historial/graficos/v54_pantalla_inicio",
                                          "v54/pantalla_inicio")
#: Tope de motivos anotados por capa: el histórico es un índice, no un inventario.
_MAX_MOTIVOS = 12


def _ahora() -> str:
    from ie123kit.nucleo import util

    return util.ahora_iso()


def _relativa(raiz: Path, ruta: Path) -> str:
    """Ruta relativa a la raíz en formato POSIX; absoluta si cae fuera."""
    try:
        return ruta.relative_to(raiz).as_posix()
    except ValueError:
        return ruta.as_posix()


def _es_ruta_del_menu(rel: str) -> bool:
    return rel.startswith(_RUTAS_MENU) or rel.rpartition("/")[2] in _EXEFS_MENU


def _motivos_de_menu(capa: Path) -> list[str]:
    """Por qué esta capa toca el juego principal (lista vacía si no lo toca)."""
    motivos: list[str] = []
    extra = capa / "extra"
    if extra.is_dir():
        for fichero in sorted(extra.rglob("*")):
            if len(motivos) >= _MAX_MOTIVOS:
                break
            if not fichero.is_file():
                continue
            rel = fichero.relative_to(extra).as_posix()
            if _es_ruta_del_menu(rel):
                motivos.append(f"extra/{rel}")
    for nombre in _FICHEROS_DE_CAPA:
        fichero = capa / nombre
        if not fichero.is_file():
            continue
        try:
            texto = fichero.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for aguja in (*_RUTAS_MENU, *_EXEFS_MENU):
            if aguja in texto and len(motivos) < _MAX_MOTIVOS:
                motivos.append(f"{nombre}: {aguja}")
    return list(dict.fromkeys(motivos))


def _es_capa(carpeta: Path) -> bool:
    return (carpeta / "extra").is_dir() or any((carpeta / n).is_file() for n in _FICHEROS_DE_CAPA)


def _capas_del_menu(dir_capas: Path) -> list[tuple[Path, list[str]]]:
    """Capas de `work/ie1/capas` que tocan el juego principal, ordenadas.

    Recorre `<tema>/<linea>`, la antigua `<vNN>/<linea>` y `historial/<tema>/vNN_<linea>`
    (ver ``nucleo.construir.capas.listar_capas``), además de cada carpeta de primer nivel.
    """
    from ie123kit.nucleo.construir.capas import HISTORIAL, listar_capas

    if not dir_capas.is_dir():
        return []
    grupos = [p for p in dir_capas.iterdir() if p.is_dir() and p.name != HISTORIAL]
    candidatas = sorted([*grupos, *listar_capas(dir_capas, historial=True)])
    salida: list[tuple[Path, list[str]]] = []
    for carpeta in candidatas:
        rel = carpeta.relative_to(dir_capas).as_posix()
        conocida = rel in _CAPAS_MENU_CONOCIDAS
        if not conocida and not _es_capa(carpeta):
            continue
        motivos = _motivos_de_menu(carpeta)
        if conocida:
            motivos.append("capa conocida del menú (declarada en _CAPAS_MENU_CONOCIDAS)")
        if motivos:
            salida.append((carpeta, motivos))
    return salida


def _capa_vacia(aporte: dict[str, Any]) -> bool:
    """¿La capa no aporta nada? (ni ficheros del archive, ni ``.ssd`` preparados, ni CRO).

    Una capa que se pide y no aporta nada casi siempre es una ruta equivocada o un ``apply.py``
    sin ejecutar: se dice, en vez de entregar una candidata idéntica a la base como si valiera.
    """
    extra = aporte.get("extra")
    if extra is not None and any(p.is_file() for p in Path(extra).rglob("*")):
        return False
    for carpeta in (aporte.get("eventos") or {}).values():
        if carpeta is not None and any(Path(carpeta).glob("*.ssd")):
            return False
    return not _cro_de_aportacion(aporte)


def _parametros_ausentes(funcion: Any, nombres: Any) -> list[str]:
    """Nombres de ``nombres`` que ``funcion`` NO acepta como parámetro.

    Sirve para detectar una incompatibilidad de FIRMA sin capturar ``TypeError`` alrededor de la
    llamada: ese ``except`` también atraparía los ``TypeError`` internos de la función y llevaría
    a reintentar con menos argumentos, tapando el fallo. Una función con ``**kwargs`` se da por
    compatible y una que no se puede inspeccionar no se declara incompatible.
    """
    try:
        parametros = inspect.signature(funcion).parameters
    except (TypeError, ValueError):
        return []
    if any(p.kind is inspect.Parameter.VAR_KEYWORD for p in parametros.values()):
        return []
    return [n for n in nombres if n not in parametros]


def _localizar_xdelta() -> Any:
    """Ruta de xdelta3; None si el localizador aún no existe y False si no se encuentra."""
    try:
        from ie123kit.nucleo.config import herramientas
    except ImportError:
        return None
    try:
        return herramientas.localizar("xdelta3") or False
    except Exception:
        return False


class ServicioToolkit:
    """Fachada síncrona. Todos los métodos devuelven ``Resultado`` y admiten ``progreso``/``cancel``."""

    API_VERSION = API_VERSION

    def __init__(self, ws: Any, *, juegos: dict[str, JuegoBase] | None = None, trabajos: Any = None) -> None:
        self.ws = ws
        self.juegos: dict[str, JuegoBase] = juegos if juegos is not None else descubrir_juegos()
        self._trabajos = trabajos

    @classmethod
    def abrir(cls, raiz: str | Path | None = None, **kw: Any) -> ServicioToolkit:
        from ie123kit.servicio.proyecto import Workspace

        return cls(Workspace.abrir(raiz), **kw)

    # -- utilidades internas ------------------------------------------------

    @property
    def trabajos(self) -> Any:
        if self._trabajos is None:
            from ie123kit.servicio.trabajos import Trabajos

            self._trabajos = Trabajos()
        return self._trabajos

    @staticmethod
    def _cronometrar(inicio: float, resultado: Resultado) -> Resultado:
        try:
            object.__setattr__(resultado, "duracion_s", round(time.perf_counter() - inicio, 6))
        except (AttributeError, TypeError):  # no es una dataclass con ese campo
            pass
        return resultado

    def _juego(self, objetivo: str) -> JuegoBase | Resultado:
        juego = self.juegos.get(objetivo)
        if juego is None:
            validos = ", ".join(sorted(self.juegos)) or "(ninguno)"
            return Resultado.fallo(
                [_incidencia("NOT_SUPPORTED", f"Objetivo desconocido: {objetivo!r}. Objetivos válidos: {validos}.")]
            )
        return juego

    def _del_registro(self, juego: JuegoBase, *, progreso: Any = None,
                      cancel: CancelToken | None = None) -> list[Any]:
        """Activos escaneados del `archive.fa` base; lista vacía si no se puede escanear.

        Sin ROM (la CI) o con el escaneo cancelado no hay registro, y eso NO es un error:
        lo que aporte el juego por su cuenta se sigue devolviendo.
        """
        try:
            from ie123kit.servicio import registro_activos

            return list(registro_activos.obtener(self.ws, juego, progreso=progreso, cancel=cancel).activos)
        except Exception:
            return []

    def _refs(self, juego: JuegoBase, *, progreso: Any = None, cancel: CancelToken | None = None) -> list[Any]:
        """Activos del objetivo: los del `archive.fa` MÁS los que aporta el propio juego.

        Son dos conjuntos complementarios, no dos formas de obtener el mismo: el registro
        escanea el `archive.fa` y el juego aporta lo que vive FUERA de él (`cro/*.cro`, los
        `.SAD` sueltos, `banner.bnr`/`icon.icn` del ExeFS). Coger solo uno dejaba la mitad
        del inventario invisible. Se deduplica por `AssetRef.id` y manda el registro.
        """
        refs: list[Any] = self._del_registro(juego, progreso=progreso, cancel=cancel)
        try:
            salida = juego.activos(self.ws)
            propios = list(salida.datos.get("activos", ())) if isinstance(salida, Resultado) else list(salida)
        except Exception:
            propios = []
        vistos = {getattr(r, "id", None) for r in refs}
        for ref in propios:
            ident = getattr(ref, "id", None)
            if ident is not None and ident in vistos:
                continue
            vistos.add(ident)
            refs.append(ref)
        return refs

    def _resolver(self, juego: JuegoBase, ident: Any) -> Any | None:
        """Convierte un id de activo en su AssetRef; devuelve None si no existe."""
        if not isinstance(ident, str):
            return ident
        for ref in self._refs(juego):
            if getattr(ref, "id", None) == ident:
                return ref
        return None

    # -- órdenes de proyecto ------------------------------------------------

    def init(self, rom_3ds: str | Path | None = None, roms: dict[str, Any] | None = None, *,
             simular: bool = False,
             progreso: Callable[[Progreso], None] | None = None,
             cancel: CancelToken | None = None) -> Resultado:
        """Prepara `work/<objetivo>/` y `translation/<objetivo>/` de los SIETE objetivos.

        `juego_principal` es un ámbito de primera clase como `shared`, `ie1`, `ie2` e `ie3`:
        su `work/juego_principal/` se crea aquí, no a mano. Las rutas de ROM que se pasen se
        anotan en `ie123.local.toml` (ignorado por git); nunca se copia contenido (Norma 2).
        Idempotente: repetirlo no cambia nada y `datos["creadas"]` sale vacío.
        """
        t0 = time.perf_counter()
        try:
            objetivos = sorted(OBJETIVOS)
            if progreso is not None:
                progreso(Progreso("init", 0, 2, "carpetas"))
            if simular:
                creadas = [
                    c for objetivo in objetivos
                    for c in self._carpetas_de(objetivo) if not Path(c).is_dir()
                ]
            else:
                creadas = [Path(c) for c in self.ws.preparar_todo(objetivos)]

            rutas: dict[str, str] = {}
            if rom_3ds:
                rutas["3ds_jp"] = str(rom_3ds)
            for nombre, ruta in (roms or {}).items():
                if ruta:
                    rutas[str(nombre)] = str(ruta)
            if progreso is not None:
                progreso(Progreso("init", 1, 2, "ie123.local.toml"))
            local = self.ws.escribir_local({"roms": rutas}) if rutas and not simular else None

            datos = {
                "objetivos": objetivos,
                "creadas": [str(c) for c in creadas],
                "roms": rutas,
                "ie123_local_toml": str(local) if local is not None else "",
                "simulado": bool(simular),
            }
            artefactos = tuple(str(c) for c in creadas) + ((str(local),) if local is not None else ())
            if progreso is not None:
                progreso(Progreso("init", 2, 2, "hecho"))
            return self._cronometrar(t0, Resultado.correcto(datos=datos, artefactos=artefactos))
        except Exception as exc:
            return self._cronometrar(t0, Resultado.fallo([_incidencia("NOT_SUPPORTED", f"init: {exc}")]))

    def _carpetas_de(self, objetivo: str) -> tuple[Path, ...]:
        """Carpetas que `init` crearía para ese objetivo (sin crearlas)."""
        d = self.ws.dirs(objetivo)
        return (Path(d.capas), Path(d.qa), Path(d.exportaciones), Path(self.ws.dir_traduccion(objetivo)))

    def migrar_juego_principal(self, simular: bool = True, *,
                               progreso: Callable[[Progreso], None] | None = None,
                               cancel: CancelToken | None = None) -> Resultado:
        """Índice `work/juego_principal/historico.json` de las capas de `work/ie1/capas` que tocan el menú.

        NO MUEVE NADA: esas capas calculan la raíz del repo subiendo niveles desde su propio fichero
        y algunas se importan por `importlib` desde su sitio actual (la V37); moverlas las rompe en
        silencio. El histórico es un índice que APUNTA a donde siguen estando.

        Con ``simular=True`` (por defecto) no se escribe nada: el documento va en ``datos``. Con
        ``simular=False`` se escribe el índice y se avisa de que las capas no se mueven.
        """
        t0 = time.perf_counter()
        try:
            if cancel is not None:
                cancel.comprobar()
            capas = _capas_del_menu(Path(self.ws.dirs("ie1").capas))
            if progreso is not None:
                progreso(Progreso("migrar_juego_principal", len(capas), len(capas) or 1, "detectadas"))
            destino = Path(self.ws.dirs("juego_principal").historico)
            documento = {
                "esquema": 1,
                "objetivo": "juego_principal",
                "generado_en": _ahora(),
                "origen": "work/ie1/capas",
                "movidas": False,
                "nota": ("Índice de solo lectura: las capas SIGUEN en work/ie1/capas. No se mueven "
                         "porque sus rutas relativas y sus importlib dependen de su sitio actual."),
                "capas": [
                    {"ruta": _relativa(self.ws.raiz, ruta), "motivos": motivos}
                    for ruta, motivos in capas
                ],
            }
            datos = {"historico": str(destino), "capas": documento["capas"], "movidas": False,
                     "simulado": bool(simular), "escrito": not simular}
            if simular:
                datos["documento"] = documento
                return self._cronometrar(t0, Resultado.correcto(datos=datos))
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_text(json.dumps(documento, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            aviso = Incidencia("NOT_SUPPORTED", "aviso",
                               "migrar-juego-principal: las capas no se mueven (sus rutas relativas e "
                               "importlib dependen de su sitio actual); solo se escribe el índice",
                               ruta=str(destino))
            return self._cronometrar(t0, Resultado.correcto(datos=datos, artefactos=(str(destino),),
                                                            incidencias=(aviso,)))
        except Exception as exc:
            return self._cronometrar(
                t0, Resultado.fallo([_incidencia("NOT_SUPPORTED", f"migrar-juego-principal: {exc}")])
            )

    def objetivos(self, *, progreso: Callable[[Progreso], None] | None = None,
                  cancel: CancelToken | None = None) -> Resultado:
        t0 = time.perf_counter()
        infos: list[dict[str, Any]] = []
        incidencias: list[Incidencia] = []
        for ident, juego in self.juegos.items():
            try:
                info = juego.info()
                infos.append(info.to_json() if isinstance(info, InfoObjetivo) else info)
            except Exception as exc:
                incidencias.append(_incidencia("NOT_SUPPORTED", f"{ident}: no se puede leer info(): {exc}"))
        res = Resultado.correcto(datos={"objetivos": infos}, incidencias=incidencias) if not incidencias or infos \
            else Resultado.fallo(incidencias)
        return self._cronometrar(t0, res)

    def activos(self, objetivo: str, tipo: str | None = None, filtro: str | None = None, *,
                progreso: Callable[[Progreso], None] | None = None,
                cancel: CancelToken | None = None) -> Resultado:
        t0 = time.perf_counter()
        juego = self._juego(objetivo)
        if isinstance(juego, Resultado):
            return self._cronometrar(t0, juego)
        try:
            refs = self._refs(juego, progreso=progreso, cancel=cancel)
        except Exception as exc:
            return self._cronometrar(t0, Resultado.fallo([_incidencia("NOT_SUPPORTED", f"{objetivo}: {exc}")]))
        if tipo is not None:
            refs = [r for r in refs if getattr(r, "tipo", None) == tipo]
        if filtro is not None:
            refs = [r for r in refs if filtro in getattr(r, "id", "")]
        return self._cronometrar(t0, Resultado.correcto(datos={"activos": [r.to_json() for r in refs]}))

    def exportar(self, objetivo: str, ids: list[str] | tuple[str, ...] | str, destino: str | Path, *,
                 formato: str | None = None,
                 progreso: Callable[[Progreso], None] | None = None,
                 cancel: CancelToken | None = None) -> Resultado:
        t0 = time.perf_counter()
        juego = self._juego(objetivo)
        if isinstance(juego, Resultado):
            return self._cronometrar(t0, juego)
        lista = [ids] if isinstance(ids, str) else list(ids)
        artefactos: list[str] = []
        incidencias: list[Incidencia] = []
        for ident in lista:
            ref = self._resolver(juego, ident)
            if ref is None:
                incidencias.append(_incidencia("NOT_SUPPORTED", f"{objetivo}: activo desconocido {ident!r}",
                                               activo_id=str(ident)))
                return self._cronometrar(t0, Resultado.fallo(incidencias, artefactos=tuple(artefactos)))
            try:
                res = juego.exportar(self.ws, ref, Path(destino), formato=formato, progreso=progreso, cancel=cancel)
            except Exception as exc:
                incidencias.append(_incidencia("NOT_SUPPORTED", f"{objetivo}:{ident}: {exc}", activo_id=str(ident)))
                return self._cronometrar(t0, Resultado.fallo(incidencias, artefactos=tuple(artefactos)))
            incidencias.extend(res.incidencias)
            artefactos.extend(str(a) for a in res.artefactos)
            if not res.ok:
                return self._cronometrar(t0, Resultado.fallo(incidencias, artefactos=tuple(artefactos)))
        return self._cronometrar(
            t0,
            Resultado.correcto(datos={"exportados": [str(i) for i in lista]},
                               incidencias=tuple(incidencias), artefactos=tuple(artefactos)),
        )

    def importar(self, objetivo: str, id: str, fichero: str | Path, simular: bool = True, *,
                 progreso: Callable[[Progreso], None] | None = None,
                 cancel: CancelToken | None = None) -> Resultado:
        t0 = time.perf_counter()
        juego = self._juego(objetivo)
        if isinstance(juego, Resultado):
            return self._cronometrar(t0, juego)
        ref = self._resolver(juego, id)
        if ref is None:
            return self._cronometrar(
                t0, Resultado.fallo([_incidencia("NOT_SUPPORTED", f"{objetivo}: activo desconocido {id!r}",
                                                 activo_id=str(id))])
            )
        try:
            res = juego.importar(self.ws, ref, Path(fichero), simular=simular, progreso=progreso, cancel=cancel)
        except Exception as exc:
            return self._cronometrar(
                t0, Resultado.fallo([_incidencia("NOT_SUPPORTED", f"{objetivo}:{id}: {exc}", activo_id=str(id))])
            )
        return self._cronometrar(t0, res)

    # -- construcción, verificación, instalación y parche --------------------

    def _ruta_candidata(self, nombre: str | Path) -> Path:
        """Ruta de una candidata: se admite un nombre (``probe_ie1_v67``) o una ruta explícita."""
        texto = str(nombre)
        p = Path(texto)
        if p.is_absolute() or "/" in texto or "\\" in texto:
            return (p if p.is_absolute() else self.ws.raiz / p).resolve()
        return Path(self.ws.candidata(texto)).resolve()

    def _ruta_capa(self, capa: str | Path) -> Path:
        p = Path(capa)
        return (p if p.is_absolute() else self.ws.raiz / p).resolve()

    def _aportaciones(self, objetivos: tuple[str, ...], capas: list[Path]) -> dict[str, Any] | Resultado:
        """Aportaciones declaradas por cada objetivo; un objetivo que no las implemente se omite."""
        salida: dict[str, Any] = {}
        for ident in objetivos:
            juego = self._juego(ident)
            if isinstance(juego, Resultado):
                return juego
            aporta = getattr(juego, "aportaciones", None)
            if aporta is None:
                continue
            try:
                valor = aporta(self.ws, tuple(capas))
            except NotImplementedError:
                continue
            except Exception as exc:
                return Resultado.fallo([_incidencia("NOT_SUPPORTED", f"aportaciones de {ident}: {exc}")])
            if valor is not None:
                salida[ident] = valor
        return salida

    def construir(self, solicitud: SolicitudConstruccion, *,
                  progreso: Callable[[Progreso], None] | None = None,
                  cancel: CancelToken | None = None) -> Resultado:
        """Construye la candidata de TODA la recopilación; el bloqueo v20 se comprueba siempre."""
        t0 = time.perf_counter()
        try:
            from ie123kit.nucleo.construir import candidata as constructor
            from ie123kit.nucleo.construir.capas import Capa
            from ie123kit.nucleo.validar import bloqueo
        except ImportError as exc:
            return self._cronometrar(t0, Resultado.no_soportado(f"construir: falta el núcleo ({exc})"))

        dir_base = self._ruta_candidata(solicitud.base)
        base = dir_base / "archive.fa" if dir_base.is_dir() else dir_base
        if not base.is_file():
            return self._cronometrar(
                t0, Resultado.no_soportado(f"construir: no existe la candidata base {solicitud.base!r} ({base})")
            )
        dir_salida = self._ruta_candidata(solicitud.salida)
        salida = dir_salida / "archive.fa"
        if salida.exists():
            return self._cronometrar(
                t0, Resultado.no_soportado(f"construir: la candidata de salida ya existe ({dir_salida})")
            )
        capas = [self._ruta_capa(c) for c in solicitud.capas]
        faltan = [str(c) for c in capas if not c.is_dir()]
        if faltan:
            return self._cronometrar(t0, Resultado.no_soportado(f"construir: capas inexistentes: {', '.join(faltan)}"))

        aportaciones = self._aportaciones(solicitud.objetivos, capas)
        if isinstance(aportaciones, Resultado):
            return self._cronometrar(t0, aportaciones)

        # Plan de capas: CADA capa aporta todo lo suyo (extra/, events/, events_mch/ y sus
        # romfs/cro/*.cro), en el orden en que se han pedido y con la regla «la última gana».
        # Antes solo la primera hacía de `ui` y de las demás se cogía `extra/`: sus CRO y sus
        # eventos se tiraban sin incidencia, y la candidata incompleta se daba por buena.
        aportes: list[dict[str, Any]] = []
        for capa in capas:
            aporte = Capa(capa, raiz=self.ws.raiz).aportacion()
            if _capa_vacia(aporte):
                return self._cronometrar(t0, Resultado.no_soportado(
                    f"construir: la capa {capa} no aporta nada (se esperaba extra/ con ficheros, "
                    "events/, events_mch/ o romfs/cro/*.cro); ¿falta ejecutar su apply.py?"
                ))
            aportes.append(aporte)
        for ident, valor in aportaciones.items():
            aporte, pendientes = _aportacion_a_dict(ident, valor)
            if pendientes:
                return self._cronometrar(t0, Resultado.no_soportado(
                    f"construir: la aportación de {ident} usa {', '.join(pendientes)}, que el "
                    "constructor todavía no sabe aplicar; no se entrega una candidata a medias"
                ))
            aportes.append(aporte)

        # Lo que la base ya llevaba y ninguna capa rehace se arrastra tal cual: si no, una capa
        # que solo toca ina_main1 dejaría la candidata sin ina_menu/ina_main2/ina_main3ogre.
        declaradas = {p.name for a in aportes for p in _cro_de_aportacion(a)}
        carpeta_base = base.parent / "romfs/cro"
        cro = [p for p in sorted(carpeta_base.glob("*.cro")) if p.name not in declaradas] \
            if carpeta_base.is_dir() else []

        if progreso is not None:
            progreso(Progreso("construir", 0, 2, str(dir_salida)))
        kw: dict[str, Any] = {"ui": None, "capas": None, "cro": cro or None,
                              "aportaciones": aportes, "rehusar_sobrescribir": True}
        # La incompatibilidad de firma se detecta INSPECCIONANDO la signatura, nunca capturando
        # TypeError: un `except TypeError` alrededor de la llamada también atraparía los errores
        # internos del constructor (p.ej. una aportación mal formada o un reempaquetado roto) y
        # reintentaría sin aportaciones, entregando una candidata incompleta como si fuera buena.
        faltan_parametros = _parametros_ausentes(constructor.construir, kw)
        if faltan_parametros:
            return self._cronometrar(
                t0,
                Resultado.no_soportado(
                    "construir: el núcleo instalado no admite "
                    f"{', '.join(sorted(faltan_parametros))}; actualiza ie123kit"
                ),
            )
        try:
            informe = constructor.construir(base, salida, **kw)
        except Exception as exc:
            return self._cronometrar(t0, Resultado.fallo([_incidencia("NOT_SUPPORTED", f"construir: {exc}")]))

        if progreso is not None:
            progreso(Progreso("bloqueo_v20", 1, 2, str(salida)))
        fallo = _comprobar_bloqueo(bloqueo, salida, self.ws.raiz)
        if fallo is not None:
            return self._cronometrar(t0, Resultado.fallo([fallo], artefactos=(str(salida),)))

        informe = dict(informe or {})
        build_json = salida.with_suffix(".build.json")
        # Las CRO entregadas son TODAS las de la candidata, no solo ina_main1: si una capa trae
        # ina_menu o ina_main2, tiene que verse en los artefactos que se instalan.
        cros = [c.get("destino") for c in (informe.get("cros") or []) if isinstance(c, dict) and c.get("destino")]
        if not cros and informe.get("cro"):
            cros = [informe["cro"]]
        datos = {
            "archive": str(salida),
            "archive_sha256": str(informe.get("archive_sha256", "")),
            "cro": informe.get("cro"),
            "cros": [str(c) for c in cros],
            "build_json": str(build_json),
            "candidata": dir_salida.name,
            "informe": informe,
        }
        artefactos = tuple(str(a) for a in (salida, build_json, *cros) if a)
        if progreso is not None:
            progreso(Progreso("construir", 2, 2, "hecha"))
        return self._cronometrar(t0, Resultado.correcto(datos=datos, artefactos=artefactos))

    def verificar(self, candidata: str, golden: bool | str | None = None, *,
                  progreso: Callable[[Progreso], None] | None = None,
                  cancel: CancelToken | None = None) -> Resultado:
        """Verifica una candidata construida. El bloqueo v20 se ejecuta siempre, nunca es opcional."""
        t0 = time.perf_counter()
        try:
            from ie123kit.nucleo.validar import bloqueo
            from ie123kit.nucleo.validar import candidata as validador
        except ImportError as exc:
            return self._cronometrar(t0, Resultado.no_soportado(f"verificar: falta el núcleo ({exc})"))

        dir_cand = self._ruta_candidata(candidata)
        archive = dir_cand / "archive.fa" if dir_cand.is_dir() else dir_cand
        if not archive.is_file():
            return self._cronometrar(
                t0, Resultado.no_soportado(f"verificar: no existe la candidata {candidata!r} ({archive})")
            )

        incidencias: list[Incidencia] = []
        fallo = _comprobar_bloqueo(bloqueo, archive, self.ws.raiz)
        if fallo is not None:
            return self._cronometrar(t0, Resultado.fallo([fallo]))

        datos: dict[str, Any] = {"candidata": dir_cand.name, "archive": str(archive), "bloqueo_v20": "ok"}
        try:
            datos["archive_sha256"] = validador.sha256_fichero(archive)
        except Exception as exc:
            return self._cronometrar(t0, Resultado.fallo([_incidencia("NOT_SUPPORTED", f"verificar: {exc}")]))

        build_json = archive.with_suffix(".build.json")
        if build_json.is_file():
            try:
                informe = json.loads(build_json.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                informe = {}
                incidencias.append(Incidencia("NOT_SUPPORTED", "aviso", f"{build_json.name} ilegible: {exc}"))
            esperado = str(informe.get("archive_sha256", "")) if isinstance(informe, dict) else ""
            datos["archive_sha256_esperado"] = esperado
            if esperado and esperado != datos["archive_sha256"]:
                return self._cronometrar(
                    t0,
                    Resultado.fallo(
                        [_incidencia("NOT_SUPPORTED",
                                     f"verificar: el archive.fa no coincide con {build_json.name} "
                                     f"({datos['archive_sha256']} != {esperado})", ruta=str(archive))]
                    ),
                )

        if golden:
            try:
                from ie123kit.nucleo.compat.golden import comprobar_grupo

                total, malos = comprobar_grupo("candidatas.sha256", self.ws.raiz)
            except Exception as exc:
                return self._cronometrar(t0, Resultado.fallo([_incidencia("NOT_SUPPORTED", f"golden: {exc}")]))
            datos["golden"] = {"total": total, "malos": list(malos)}
            incidencias.extend(_incidencia("NOT_SUPPORTED", f"golden: {malo}") for malo in malos)
            if malos:
                return self._cronometrar(t0, Resultado.fallo(incidencias))

        return self._cronometrar(t0, Resultado.correcto(datos=datos, incidencias=tuple(incidencias)))

    def instalar(self, candidata: str, emulador: str = "azahar", lanzar: bool = False, *,
                 progreso: Callable[[Progreso], None] | None = None,
                 cancel: CancelToken | None = None) -> Resultado:
        """Instala la candidata en el emulador (hoy solo Azahar, LayeredFS)."""
        t0 = time.perf_counter()
        if emulador != "azahar":
            return self._cronometrar(t0, Resultado.no_soportado(f"instalar: emulador no soportado: {emulador!r}"))
        try:
            from ie123kit.nucleo.construir import instalar as instalador
        except ImportError as exc:
            return self._cronometrar(t0, Resultado.no_soportado(f"instalar: falta el núcleo ({exc})"))

        dir_cand = self._ruta_candidata(candidata)
        if not (dir_cand / "archive.fa").is_file() and not dir_cand.is_file():
            return self._cronometrar(
                t0, Resultado.no_soportado(f"instalar: no existe la candidata {candidata!r} ({dir_cand})")
            )
        # La carpeta de mods sale de la configuración ([azahar] mods_dir o IE123_AZAHAR); antes se
        # llamaba con `lanzar`/`ws`, que el núcleo no admite, y el TypeError hacía caer siempre en la
        # carpeta por defecto del sistema aunque el proyecto configurase otra (F2.5).
        kw: dict[str, Any] = {}
        mods = self.ws.ajuste("azahar.mods_dir")
        if mods:
            kw["raiz_mods"] = Path(str(mods))
        incidencias: list[Incidencia] = []
        if lanzar:
            incidencias.append(Incidencia("NOT_SUPPORTED", "aviso",
                                          "instalar: lanzar el emulador no está soportado; ábrelo a mano"))
        try:
            salida = instalador.azahar(dir_cand, **kw)
        except Exception as exc:
            return self._cronometrar(t0, Resultado.fallo([_incidencia("NOT_SUPPORTED", f"instalar: {exc}")]))
        if isinstance(salida, Resultado):
            return self._cronometrar(t0, salida)
        datos = dict(salida) if isinstance(salida, dict) else {"destino": str(salida)}
        datos.setdefault("candidata", dir_cand.name)
        datos.setdefault("emulador", emulador)
        return self._cronometrar(t0, Resultado.correcto(datos=datos, incidencias=tuple(incidencias)))

    def parche(self, rom_base: str | Path, rom_parcheada: str | Path, salida: str | Path, *,
               progreso: Callable[[Progreso], None] | None = None,
               cancel: CancelToken | None = None) -> Resultado:
        """Genera el .xdelta entre la ROM base y la parcheada (único entregable distribuible)."""
        t0 = time.perf_counter()
        try:
            from ie123kit.nucleo.construir import parche as generador
        except ImportError as exc:
            return self._cronometrar(t0, Resultado.no_soportado(f"parche: falta el núcleo ({exc})"))

        base, parcheada, destino = Path(rom_base), Path(rom_parcheada), Path(salida)
        for rotulo, ruta in (("ROM base", base), ("ROM parcheada", parcheada)):
            if not ruta.is_file():
                return self._cronometrar(t0, Resultado.no_soportado(f"parche: no existe la {rotulo} ({ruta})"))
        if _localizar_xdelta() is False:
            return self._cronometrar(
                t0,
                Resultado.fallo([Incidencia("HERRAMIENTA_AUSENTE", "error", "No se encuentra xdelta3.",
                                            pista="Ajusta [herramientas] en ie123.local.toml o añádela al PATH.")]),
            )
        if progreso is not None:
            progreso(Progreso("parche", 0, 1, str(destino)))
        try:
            resultado = generador.xdelta(base, parcheada, destino)
        except Exception as exc:
            return self._cronometrar(t0, Resultado.fallo([_incidencia("NOT_SUPPORTED", f"parche: {exc}")]))
        if isinstance(resultado, Resultado):
            return self._cronometrar(t0, resultado)
        datos = dict(resultado) if isinstance(resultado, dict) else {"parche": str(resultado)}
        datos.setdefault("parche", str(destino))
        if progreso is not None:
            progreso(Progreso("parche", 1, 1, "hecho"))
        return self._cronometrar(t0, Resultado.correcto(datos=datos, artefactos=(str(destino),)))

    def limpiar(self, borrar: bool = False, *,
                progreso: Callable[[Progreso], None] | None = None,
                cancel: CancelToken | None = None) -> Resultado:
        t0 = time.perf_counter()
        try:
            from ie123kit.nucleo.construir import limpieza

            objetivos = [str(p) for p in limpieza.objetivos()]
            if borrar and hasattr(limpieza, "borrar"):
                limpieza.borrar()
            datos = {"objetivos": objetivos, "borrado": bool(borrar)}
            return self._cronometrar(t0, Resultado.correcto(datos=datos))
        except Exception as exc:
            return self._cronometrar(t0, Resultado.fallo([_incidencia("NOT_SUPPORTED", f"limpiar: {exc}")]))

    def doctor(self, *, progreso: Callable[[Progreso], None] | None = None,
               cancel: CancelToken | None = None) -> Resultado:
        t0 = time.perf_counter()
        try:
            salida = self.ws.doctor()
        except Exception as exc:
            return self._cronometrar(t0, Resultado.fallo([_incidencia("NOT_SUPPORTED", f"doctor: {exc}")]))
        if isinstance(salida, Resultado):
            datos = dict(salida.datos or {})
            datos["api_version"] = API_VERSION
            entorno, extra = self._entorno()
            datos.update(entorno)
            incidencias = [*salida.incidencias, *extra]
            ok = salida.ok and not any(i.severidad == "error" for i in extra)
            return self._cronometrar(
                t0, Resultado.correcto(datos=datos, incidencias=incidencias)
                if ok else Resultado.fallo(incidencias, datos=datos)
            )
        datos = dict(salida) if isinstance(salida, dict) else {"doctor": salida}
        datos["api_version"] = API_VERSION
        return self._cronometrar(t0, Resultado.correcto(datos=datos))

    def _entorno(self) -> tuple[dict[str, Any], list[Incidencia]]:
        """Comprobaciones de `ie123 doctor` que no dependen del Workspace (F2.4)."""
        import shutil
        import sys

        datos: dict[str, Any] = {"python": sys.version.split()[0]}
        incidencias: list[Incidencia] = []
        dependencias: dict[str, bool] = {}
        for modulo, obligatoria in (("PIL", True), ("numpy", True), ("capstone", True), ("scipy", False),
                                    ("cv2", False)):
            try:
                importlib.import_module(modulo)
                dependencias[modulo] = True
            except Exception:
                dependencias[modulo] = False
                incidencias.append(Incidencia("NOT_SUPPORTED", "error" if obligatoria else "aviso",
                                              f"Falta el módulo de Python {modulo!r}.",
                                              pista='python -m pip install -e "tools[dev,graficos]"'))
        datos["dependencias"] = dependencias
        try:
            from ie123kit.nucleo.config import herramientas as H

            externas = {}
            for nombre in H.HERRAMIENTAS:
                ruta = H.localizar(nombre, ws=self.ws)
                externas[nombre] = str(ruta) if ruta else None
                if ruta is None:
                    incidencias.append(Incidencia("HERRAMIENTA_AUSENTE", "aviso", f"No se encuentra {nombre}.",
                                                  pista="tools/bin, [herramientas] de ie123.local.toml o el PATH."))
            datos["herramientas_externas"] = externas
        except Exception as exc:
            incidencias.append(Incidencia("NOT_SUPPORTED", "aviso", f"herramientas: {exc}"))
        if (self.ws.raiz / "tools" / "dialogue_lock.py").is_file():
            try:
                import contextlib
                import io

                from ie123kit.nucleo.compat import guardia

                with contextlib.redirect_stdout(io.StringIO()):
                    codigo = guardia.comprobar_bloqueados(self.ws.raiz)
                datos["bloqueados"] = codigo == 0
                if codigo:
                    incidencias.append(Incidencia("BLOQUEO_V20", "error",
                                                  "Los ficheros congelados v20 no coinciden byte a byte.",
                                                  pista="python -m ie123kit.nucleo.compat.guardia bloqueados"))
            except Exception as exc:
                incidencias.append(Incidencia("NOT_SUPPORTED", "aviso", f"bloqueados: {exc}"))
        roms = {**(self.ws.proyecto.get("roms") or {}), **(self.ws.local.get("roms") or {})}
        datos["roms"] = {k: (Path(v) if Path(v).is_absolute() else self.ws.raiz / v).is_file()
                         for k, v in roms.items() if isinstance(v, str)}
        for clave, existe in datos["roms"].items():
            if not existe:
                incidencias.append(Incidencia("NOT_SUPPORTED", "aviso", f"ROM {clave} configurada pero ausente."))
        try:
            libre = shutil.disk_usage(self.ws.raiz).free
            datos["espacio_libre_gb"] = round(libre / 2**30, 1)
            if libre < 4 * 2**30:
                incidencias.append(Incidencia("NOT_SUPPORTED", "aviso", "Menos de 4 GB libres para construir."))
        except OSError:
            pass
        return datos, incidencias

    # -- órdenes de F2.4 (#50) ---------------------------------------------

    def extraer(self, tipo: str, rom: str | Path | None = None, salida: str | Path | None = None, *,
                progreso: Callable[[Progreso], None] | None = None,
                cancel: CancelToken | None = None) -> Resultado:
        """Extrae una ROM a ``work/``: ``romfs`` (3DS con 3dstool) o ``nds`` (Python puro).

        Sin ``rom``, ``romfs`` usa ``[roms] 3ds_jp`` de la configuración (``ie123 proyecto init``) o la
        ruta por defecto de ``extract_romfs.ps1``; sin ``salida``, ``work/shared/base_3ds``. ``nds``
        exige las dos rutas. Nunca escribe fuera de ``salida``.
        """
        t0 = time.perf_counter()
        try:
            from ie123kit.nucleo.construir import extraer as extractor
        except ImportError as exc:
            return self._cronometrar(t0, Resultado.no_soportado(f"extraer: falta el núcleo ({exc})"))
        if tipo not in ("romfs", "nds"):
            return self._cronometrar(t0, Resultado.no_soportado(f"extraer: tipo desconocido {tipo!r} (romfs|nds)"))
        if rom is None and tipo == "romfs":
            rom = self._rom_configurada("3ds_jp")
        if rom is None:
            return self._cronometrar(t0, Resultado.no_soportado(f"extraer {tipo}: falta --rom"))
        if salida is None:
            if tipo == "nds":
                return self._cronometrar(t0, Resultado.no_soportado("extraer nds: falta --salida"))
            salida = self.ws.raiz / "work" / "shared" / "base_3ds"
        rom, salida = Path(rom), Path(salida)
        if not salida.is_absolute():
            salida = self.ws.raiz / salida
        if not rom.is_absolute() and not rom.is_file():
            rom = self.ws.raiz / rom
        ocupada = (salida / "romfs").exists() if tipo == "romfs" else (salida.is_dir() and any(salida.iterdir()))
        if ocupada:
            return self._cronometrar(t0, Resultado.fallo([_incidencia(
                "NOT_SUPPORTED", f"extraer {tipo}: la salida ya tiene una extracción ({salida})",
                pista="No se sobrescribe: bórrala o elige otra --salida.")]))
        try:
            datos = extractor.romfs_3ds(rom, salida, ws=self.ws) if tipo == "romfs" else extractor.nds(rom, salida)
        except Exception as exc:
            codigo = "HERRAMIENTA_AUSENTE" if getattr(exc, "codigo", "") == "HERRAMIENTA_AUSENTE" else "NOT_SUPPORTED"
            return self._cronometrar(t0, Resultado.fallo([_incidencia(codigo, f"extraer {tipo}: {exc}")]))
        return self._cronometrar(t0, Resultado.correcto(datos=datos, artefactos=(str(salida),)))

    def _rom_configurada(self, clave: str) -> Path | None:
        """``[roms] <clave>`` de ie123.local.toml/ie123.toml; si no, la ruta de siempre si existe."""
        roms = {**(self.ws.proyecto.get("roms") or {}), **(self.ws.local.get("roms") or {})}
        valor = roms.get(clave)
        if isinstance(valor, dict):
            valor = valor.get("ruta")
        if isinstance(valor, str) and valor:
            return Path(valor)
        for nombre in ("Inazuma Eleven 1-2-3!! - Endou Mamoru Densetsu (2012) (Japan).3ds",
                       "Inazuma Eleven 1-2-3 - Endou Mamoru Densetsu.3ds"):
            defecto = self.ws.raiz / "Roms" / "shared" / nombre
            if defecto.is_file():
                return defecto
        return None

    def compat(self, golden: bool = False, *, progreso: Callable[[Progreso], None] | None = None,
               cancel: CancelToken | None = None) -> Resultado:
        """Gates de la migración (``nucleo.compat.gates``). Un gate conocido (#80) no cuenta como fallo."""
        t0 = time.perf_counter()
        try:
            from ie123kit.nucleo.compat import gates
        except ImportError as exc:
            return self._cronometrar(t0, Resultado.no_soportado(f"compat: falta el núcleo ({exc})"))
        lista = gates.comprobar(self.ws.raiz, golden=golden)
        incidencias = []
        for g in lista:
            if g["ok"]:
                continue
            if g["conocido"]:
                incidencias.append(Incidencia("BLOQUEO_V20", "aviso",
                                              f"{g['gate']}: fallo conocido, pendiente de decisión (#80): "
                                              f"{g['detalle']}"))
            else:
                codigo = "BLOQUEO_V20" if g["gate"] == "bloqueados" else "GATE_FALLIDO"
                incidencias.append(_incidencia(codigo, f"{g['gate']}: {g['detalle']}"))
        datos = {"golden": golden, "gates": lista}
        if any(i.severidad == "error" for i in incidencias):
            return self._cronometrar(t0, Resultado.fallo(incidencias, datos=datos))
        return self._cronometrar(t0, Resultado.correcto(datos=datos, incidencias=tuple(incidencias)))

    def registro(self, sesion: str | None = None, logdir: str | Path | None = None, forzar: bool = False, *,
                 progreso: Callable[[Progreso], None] | None = None,
                 cancel: CancelToken | None = None) -> Resultado:
        """Cosecha el log de Azahar en ``logs/runtime_errors.json`` (antes ``harvest_log.py``)."""
        t0 = time.perf_counter()
        try:
            from ie123kit.nucleo.construir import registro_azahar

            logs = self.ws.raiz / "logs"
            datos = registro_azahar.cosechar(sesion=sesion, logdir=str(logdir) if logdir else None, forzar=forzar,
                                             registro=str(logs / "runtime_errors.json"),
                                             informe_md=str(logs / "INFORME_ERRORES.md"))
        except Exception as exc:
            return self._cronometrar(t0, Resultado.fallo([_incidencia("NOT_SUPPORTED", f"registro: {exc}")]))
        artefactos = (datos["registro"], datos["informe"]) if datos["procesados"] else ()
        return self._cronometrar(t0, Resultado.correcto(datos=datos, artefactos=artefactos))

    def equivalencias(self, *, progreso: Callable[[Progreso], None] | None = None,
                      cancel: CancelToken | None = None) -> Resultado:
        """Orden ``ie123`` que sustituye a cada script u orden antigua (``servicio.equivalencias``)."""
        t0 = time.perf_counter()
        from ie123kit.servicio.equivalencias import EQUIVALENCIAS

        tabla = [{"antigua": k, "nueva": v, "nota": n} for k, (v, n) in EQUIVALENCIAS.items()]
        return self._cronometrar(t0, Resultado.correcto(datos={"equivalencias": tabla}))

    def motores(self, *, progreso: Callable[[Progreso], None] | None = None,
                cancel: CancelToken | None = None) -> Resultado:
        """Motores con entrada de fichero disponibles, por juego."""
        t0 = time.perf_counter()
        tabla: dict[str, list[str]] = {}
        for juego, nombre in MOTORES:
            tabla.setdefault(juego, []).append(nombre)
        return self._cronometrar(t0, Resultado.correcto(datos={"motores": tabla}))

    def motor(self, juego: str, nombre: str, parametros: dict[str, Any] | None = None, *,
              progreso: Callable[[Progreso], None] | None = None,
              cancel: CancelToken | None = None) -> Resultado:
        """Ejecuta el motor ``nombre`` de ``juego`` con ``parametros`` (rutas y opciones)."""
        t0 = time.perf_counter()
        destino = MOTORES.get((juego, nombre))
        if destino is None:
            validos = ", ".join(f"{j}:{n}" for j, n in sorted(MOTORES))
            return self._cronometrar(
                t0, Resultado.no_soportado(f"motor desconocido {juego}:{nombre}. Válidos: {validos}"))
        modulo, _, funcion = destino.partition(":")
        try:
            salida = getattr(importlib.import_module(modulo), funcion)(**(parametros or {}))
        except FileExistsError as exc:
            return self._cronometrar(t0, Resultado.fallo([_incidencia("NOT_SUPPORTED", f"{nombre}: {exc}",
                                                                      pista="La salida no se sobrescribe.")]))
        except Exception as exc:
            return self._cronometrar(t0, Resultado.fallo([_incidencia("NOT_SUPPORTED", f"{nombre}: {exc}")]))
        salida = dict(salida)
        artefactos = tuple(salida.pop("artefactos", ()))
        datos = json.loads(json.dumps(salida, ensure_ascii=False, default=str))
        return self._cronometrar(t0, Resultado.correcto(datos=datos, artefactos=artefactos))

    # -- trabajos -----------------------------------------------------------

    def enviar_trabajo(self, nombre_metodo: str, **kw: Any) -> Resultado:
        """Lanza un método de la fachada en un hilo de ``Trabajos`` y devuelve su id."""
        t0 = time.perf_counter()
        metodo = getattr(self, nombre_metodo, None)
        if not callable(metodo) or nombre_metodo.startswith("_"):
            return self._cronometrar(
                t0, Resultado.fallo([_incidencia("NOT_SUPPORTED", f"Método desconocido: {nombre_metodo!r}")])
            )
        try:
            ident = self.trabajos.enviar(metodo, **kw)
        except Exception as exc:
            return self._cronometrar(t0, Resultado.fallo([_incidencia("NOT_SUPPORTED", f"enviar_trabajo: {exc}")]))
        return self._cronometrar(t0, Resultado.correcto(datos={"trabajo": ident}))
