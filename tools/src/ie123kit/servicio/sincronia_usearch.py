"""Hook de nombres: ``usearch.dat`` sincronizado con el ``unitbase.dat`` final de IE1, IE2 e IE3.

Punto de enganche ÚNICO de los tres juegos. ``usearch.dat`` es un dato derivado del nombre actual de ``unitbase.dat``
(lo que usan la búsqueda por nombre de Ojear/Fichar en IE1/IE2 y las listas del Registro/Álbum en IE3), así que se
regenera como ÚLTIMO paso de la construcción, sin importar qué capa tocó unitbase. Piezas:

* :func:`sincronizar` / :func:`verificar`: funciones sobre un ``leer(ruta) -> bytes`` (un archive.fa, un directorio…).
  La transformación de IE1/IE2 vive en :mod:`ie123kit.nucleo.registros.usearch` (latín de ancho completo en ``+0x10``,
  ``+0x00`` kana y flags intactos); la de IE3 en :mod:`ie123kit.ie3.comun.usearch_sincronia` (se carga por nombre:
  servicio no importa los juegos).
* :func:`paso_final` -> :class:`PasoUsearch`: paso de build para ``candidata.construir(pasos_finales=…)``.
  ``ServicioToolkit.construir`` y ``candidata.construir`` (por defecto, también su ``__main__``) lo ejecutan SIEMPRE
  (salvo los opt-outs nombrados ``omitir_sincronia_usearch`` / ``sincronia_usearch=False`` / ``--sin-sincronia-usearch``,
  solo para tests y para reproducir hashes anteriores al hook). Resuelve el decodificador de bigramas ANTES de copiar la base (``preparar``) y falla con ``ValidacionError``
  si tras escribir sigue habiendo desincronía.
* :func:`verificar_archive`: lo que usan ``ServicioToolkit.verificar`` (falla con ``USEARCH_DESINCRONIZADO``) e
  ``instalar`` (se niega).
* El registro de capas de ``work/`` (qué protege y qué no) está en :mod:`ie123kit.servicio.capas_nombres`.

Orden de uso en la cadena imperativa de ``apply.py`` sobre una COPIA (docs/HARNESS.md §4): capas de nombres ->
``python -m ie123kit.servicio.sincronia_usearch cerrar <copia>`` (sincroniza los tres juegos y verifica; código 1 =
no copiar ni instalar) -> instalar. Importar este módulo no tiene efectos.
"""
from __future__ import annotations

import hashlib
import importlib
import json
from collections.abc import Callable, Iterable
from pathlib import Path

from ie123kit.nucleo.contenedores.fa_flujo import FaFlujo, comparar_archives, reemplazar_en_disco
from ie123kit.nucleo.errores import ValidacionError
from ie123kit.nucleo.registros import usearch as engine
from ie123kit.servicio.capas_nombres import CAPAS_NOMBRES_JUGADOR, CAPAS_SIN_NOMBRES_DE_JUGADOR

__all__ = [
    "CAPAS_NOMBRES_JUGADOR",
    "CAPAS_SIN_NOMBRES_DE_JUGADOR",
    "JUEGOS",
    "REGISTROS_BIGRAMAS",
    "PasoUsearch",
    "cargar_decodificador",
    "ejecutar_capa",
    "exigir_sincronia",
    "necesita_decodificador",
    "paso_final",
    "sincronizar",
    "verificar",
    "verificar_archive",
]

#: juego -> pasos (un paso = un par usearch/unitbase del archive.fa)
JUEGOS: dict[str, tuple[str, ...]] = {
    "ie1": ("ie1",),
    "ie2": ("ie2",),
    "ie3": ("ie3.inazuma3", "ie3.inazuma3_ogre", "ie3.ex_binder"),
}
_MODULO_IE3 = "ie123kit.ie3.comun.usearch_sincronia"

#: registros de bigramas de FONT12 (par de letras -> kanji reasignado), por prioridad; el primero que define un
#: código gana. Son el mismo registro compartido en sus versiones sucesivas: el de IE3 (3047) contiene al de IE2.
#: Rutas relativas a la raíz del proyecto; ``work/`` no viaja a CI (ver ``cargar_decodificador``).
REGISTROS_BIGRAMAS: tuple[str, ...] = (
    "work/ie3/shared/capas/nombres/nombres_cortos_bigramas/registro.json",
    "work/ie2/shared/capas/nombres/nombres_compactos/registro.json",
)

Leer = Callable[[str], bytes]


def cargar_decodificador(raiz=None) -> engine.Decodificador:
    """Decodificador de bigramas con los registros de ``work/`` (lee ficheros: no se llama al importar).

    ``raiz`` es la raíz del proyecto (por defecto la que localiza ``find_root``). Sin los ficheros (CI, o un clon sin
    ``work/``) lanza ``ValidacionError("USEARCH_SIN_DECODIFICADOR")`` con la ruta que falta y qué hacer.
    """
    if raiz is None:
        from ie123kit.nucleo.config.raiz import find_root

        raiz = find_root()
    registros = []
    for relativa in REGISTROS_BIGRAMAS:
        ruta = Path(raiz) / relativa
        if not ruta.is_file():
            raise ValidacionError(
                "USEARCH_SIN_DECODIFICADOR",
                ruta=ruta,
                detalle="falta el registro de bigramas que decodifica los nombres de IE1/IE2 (vive en work/, que no "
                        "está en git ni en CI): restaura work/ o construye sin los pares usearch de IE1/IE2",
            )
        registros.append(json.loads(ruta.read_text(encoding="utf-8")))
    return engine.Decodificador(registros)


def _existe(leer: Leer, ruta: str) -> bool:
    try:
        leer(ruta)
    except KeyError:
        return False
    return True


def _esquema(juego: str, paso: str):
    return _ie3().ESQUEMAS[paso] if juego == "ie3" else engine.ESQUEMAS[juego]


def _pasos(juegos: Iterable[str]) -> list[tuple[str, str]]:
    salida = []
    for juego in juegos:
        if juego not in JUEGOS:
            raise ValueError(f"juego desconocido: {juego!r} ({', '.join(JUEGOS)})")
        salida += [(juego, paso) for paso in JUEGOS[juego]]
    return salida


def _ie3():
    return importlib.import_module(_MODULO_IE3)


def _par_presente(leer: Leer, esquema) -> bool:
    return _existe(leer, esquema.ruta_usearch) and _existe(leer, esquema.ruta_unitbase)


def necesita_decodificador(leer: Leer, juegos: Iterable[str] = ("ie1", "ie2", "ie3")) -> bool:
    """¿Contiene el archive un par usearch/unitbase de IE1 o IE2 (los únicos que decodifican bigramas)?"""
    return any(
        _par_presente(leer, _esquema(juego, paso)) for juego, paso in _pasos(juegos) if juego in ("ie1", "ie2")
    )


def _exigir_decodificador(juego: str, decodificador) -> None:
    if decodificador is None:
        raise ValidacionError("USEARCH_SIN_DECODIFICADOR", detalle=f"{juego} necesita el decodificador de bigramas")


def sincronizar(
    leer: Leer, juegos: Iterable[str] = ("ie1", "ie2", "ie3"), *, decodificador: engine.Decodificador | None = None,
    ejemplos: int = 0, leer_base: Leer | None = None,
) -> tuple[dict[str, bytes], dict]:
    """(``{ruta: usearch nuevo}`` solo con lo que cambia, informe por paso).

    ``leer_base`` lee de la BASE de la construcción (si se conoce); IE3 la usa para distinguir un renombrado de unitbase
    del recorte legítimo de ``nombres_cortos_6`` (``ie3.comun.usearch_sincronia``). Un ``KeyError`` = sin base.
    """
    cambios: dict[str, bytes] = {}
    informe: dict[str, dict] = {}
    for juego, paso in _pasos(juegos):
        esquema = _esquema(juego, paso)
        if not _par_presente(leer, esquema):
            informe[paso] = {"omitido": "el archive no contiene el par usearch/unitbase"}
            continue
        usearch, unitbase = leer(esquema.ruta_usearch), leer(esquema.ruta_unitbase)
        if juego == "ie3":
            base_unitbase = None
            if leer_base is not None:
                try:
                    base_unitbase = leer_base(esquema.ruta_unitbase)
                except KeyError:
                    base_unitbase = None
            nuevo, inf = _ie3().sincronizar(esquema, usearch, unitbase, ejemplos=ejemplos, base_unitbase=base_unitbase)
        else:
            _exigir_decodificador(juego, decodificador)
            nuevo, inf = engine.sincronizar(esquema, usearch, unitbase, decodificador, ejemplos=ejemplos)
        informe[paso] = {"usearch": esquema.ruta_usearch, "unitbase": esquema.ruta_unitbase, **inf.a_json()}
        if nuevo != usearch:
            cambios[esquema.ruta_usearch] = nuevo
    return cambios, informe


def verificar(
    leer: Leer, juegos: Iterable[str] = ("ie1", "ie2", "ie3"), *, decodificador: engine.Decodificador | None = None,
    sustituciones: dict[str, bytes] | None = None,
) -> dict:
    """Hallazgos de sincronía de cada paso. ``ok`` es False si hay algún error (los avisos no cuentan).

    ``sustituciones`` permite comprobar un usearch recién calculado sin escribirlo (ruta -> bytes).
    """
    sustituciones = sustituciones or {}

    def leer_sust(ruta: str) -> bytes:
        return sustituciones[ruta] if ruta in sustituciones else leer(ruta)

    errores: list[str] = []
    avisos: list[str] = []
    por_paso: dict[str, dict] = {}
    for juego, paso in _pasos(juegos):
        esquema = _esquema(juego, paso)
        if not _par_presente(leer, esquema):
            por_paso[paso] = {"omitido": "el archive no contiene el par usearch/unitbase"}
            continue
        usearch, unitbase = leer_sust(esquema.ruta_usearch), leer(esquema.ruta_unitbase)
        if juego == "ie3":
            hallazgos = _ie3().verificar(esquema, usearch, unitbase)
        else:
            _exigir_decodificador(juego, decodificador)
            scout = leer(esquema.ruta_scout) if esquema.ruta_scout and _existe(leer, esquema.ruta_scout) else None
            hallazgos = engine.verificar(esquema, usearch, unitbase, decodificador, scout)
        cuenta: dict[str, int] = {}
        for h in hallazgos:
            clave = f"{h.gravedad}:{h.codigo}"
            cuenta[clave] = cuenta.get(clave, 0) + 1
            destino = errores if h.gravedad == "error" else avisos
            if sum(1 for x in destino if x.startswith(f"{paso}: {h.codigo}")) < 5:
                destino.append(f"{paso}: {h.codigo}: {h.mensaje}")
        por_paso[paso] = {"hallazgos": cuenta}
    return {"ok": not errores, "errores": errores, "avisos": avisos, "por_paso": por_paso}


def exigir_sincronia(informe: dict) -> None:
    """Falla si ``verificar`` encontró desincronía (nombres de unitbase sin reflejar en usearch)."""
    if not informe["ok"]:
        raise ValidacionError("USEARCH_DESINCRONIZADO", detalle="; ".join(informe["errores"][:5]))


def verificar_archive(
    archive, *, raiz=None, decodificador: engine.Decodificador | None = None,
    juegos: Iterable[str] = ("ie1", "ie2", "ie3"),
) -> dict:
    """``verificar`` sobre un ``archive.fa`` en disco; nunca lanza por un decodificador ausente.

    Si el archive trae un par de IE1/IE2 y no hay decodificador (CI, sin ``work/``), devuelve ``ok: False`` con el
    error explícito ``USEARCH_SIN_DECODIFICADOR`` (no se puede dar por sincronizado lo que no se ha podido comprobar).
    Un archive sin ningún par usearch/unitbase da ``ok: True`` con todos los pasos «omitido».
    """
    juegos = tuple(juegos)
    with FaFlujo(archive) as fa:
        if decodificador is None and necesita_decodificador(fa.leer, juegos):
            try:
                decodificador = cargar_decodificador(raiz)
            except ValidacionError as exc:
                return {"ok": False, "codigo": exc.codigo, "errores": [f"{exc.codigo}: {exc.detalle} ({exc.ruta})"],
                        "avisos": [], "por_paso": {}}
        return verificar(fa.leer, juegos, decodificador=decodificador)


class PasoUsearch:
    """Paso final de build: deja usearch sincronizado con el unitbase FINAL y falla si no lo consigue.

    ``preparar(base)`` (lo llama ``candidata.construir`` antes de copiar nada) resuelve el decodificador si la base trae
    pares de IE1/IE2: un fallo es un error claro y no deja ningún ``archive.fa`` a medias. ``paso(archive)`` aplica la
    sincronía y devuelve el informe que se anota en ``build.json``.
    """

    nombre = "busqueda_usearch"

    def __init__(self, juegos: Iterable[str] = ("ie1", "ie2", "ie3"), *, decodificador=None, raiz=None):
        self.juegos = tuple(juegos)
        self.decodificador = decodificador
        self.raiz = raiz
        #: unitbase de IE3 de la base (ruta -> bytes), si se llamó a ``preparar``; ver ``sincronizar(leer_base=…)``
        self._unitbase_base: dict[str, bytes] = {}

    def preparar(self, base) -> None:
        with FaFlujo(base) as fa:
            if self.decodificador is None and necesita_decodificador(fa.leer, self.juegos):
                self.decodificador = cargar_decodificador(self.raiz)
            self._unitbase_base = {
                esquema.ruta_unitbase: fa.leer(esquema.ruta_unitbase)
                for juego, paso in _pasos(self.juegos) if juego == "ie3"
                for esquema in (_esquema(juego, paso),) if _par_presente(fa.leer, esquema)
            }

    def __call__(self, archive: Path) -> dict:
        archive = Path(archive)
        with FaFlujo(archive) as fa:
            if self.decodificador is None and necesita_decodificador(fa.leer, self.juegos):
                self.decodificador = cargar_decodificador(self.raiz)
            cambios, informe = sincronizar(fa.leer, self.juegos, decodificador=self.decodificador,
                                           leer_base=self._unitbase_base.__getitem__)
            previo = verificar(fa.leer, self.juegos, decodificador=self.decodificador, sustituciones=cambios)
        exigir_sincronia(previo)
        if cambios:
            reemplazar_en_disco(archive, cambios)
        with FaFlujo(archive) as fa:
            final = verificar(fa.leer, self.juegos, decodificador=self.decodificador)
        exigir_sincronia(final)
        return {"paso": self.nombre, "juegos": list(self.juegos), "entradas_escritas": sorted(cambios),
                "pasos": informe, "avisos": final["avisos"]}


def paso_final(
    juegos: Iterable[str] = ("ie1", "ie2", "ie3"), *, decodificador: engine.Decodificador | None = None, raiz=None,
) -> PasoUsearch:
    """Paso final para ``candidata.construir(pasos_finales=[…])``. Sin argumentos funciona en el proyecto real: el
    decodificador se carga del ``work/`` de la raíz detectada (``raiz`` o ``find_root``)."""
    return PasoUsearch(juegos, decodificador=decodificador, raiz=raiz)


# --------------------------------------------------------------------------- capa ejecutable (apply.py)


def _sha256_fichero(ruta: Path) -> str:
    h = hashlib.sha256()
    with ruta.open("rb") as fh:
        for bloque in iter(lambda: fh.read(1 << 24), b""):
            h.update(bloque)
    return h.hexdigest()


def _sha256(datos: bytes) -> str:
    return hashlib.sha256(datos).hexdigest()


def _resumen_diferencias(antes: bytes, despues: bytes, registro: int) -> dict:
    """Qué cambió entre dos usearch: registros distintos, bytes distintos DENTRO del registro y si son los mismos
    registros recolocados (IE3: el orden)."""
    n = len(antes) // registro
    reg = [(antes[k * registro:(k + 1) * registro], despues[k * registro:(k + 1) * registro]) for k in range(n)]
    offsets = sorted({i for a, b in reg for i in range(registro) if a[i] != b[i]})
    return {
        "mismo_tamano": len(antes) == len(despues),
        "registros_distintos": sum(a != b for a, b in reg),
        "offsets_distintos_en_el_registro": [f"0x{o:02x}" for o in offsets],
        "mismos_registros_recolocados": sorted(a for a, _ in reg) == sorted(b for _, b in reg),
    }


def ejecutar_capa(
    capa: str, juegos: Iterable[str], archive: Path, raiz: Path, *, escribir: bool = False, informe: Path | None = None,
    ejemplos: int = 5, sha_archive: bool = True, original: Path | None = None,
) -> dict:
    """Cuerpo de las ``apply.py`` de ``busqueda_usearch``. Sin ``escribir`` solo calcula y verifica.

    Con ``escribir`` anexa los usearch nuevos al ``archive`` EN SITIO (hay que pasar una copia), relee las entradas,
    comprueba que la sincronía queda en 0 errores y que SOLO han cambiado las entradas esperadas. Con ``original``
    (copia intacta del archive) añade la comparación del contenedor: entradas distintas y bytes fuera de FileEntry.
    El informe no guarda rutas de la máquina: solo el nombre del fichero.
    """
    archive = Path(archive)
    juegos = tuple(juegos)
    datos: dict = {"capa": capa, "juegos": list(juegos), "archive": archive.name, "escrito": False,
                   "runtime_verified": False, "instalada": False}
    if sha_archive:
        datos["archive_sha256_antes"] = _sha256_fichero(archive)
    datos["archive_bytes_antes"] = archive.stat().st_size
    with FaFlujo(archive) as fa:
        decodificador = cargar_decodificador(raiz) if necesita_decodificador(fa.leer, juegos) else None
        antes = verificar(fa.leer, juegos, decodificador=decodificador)
        cambios, pasos = sincronizar(fa.leer, juegos, decodificador=decodificador, ejemplos=ejemplos)
        sha_antes = {r: _sha256(fa.leer(r)) for r in cambios}
        despues_previsto = verificar(fa.leer, juegos, decodificador=decodificador, sustituciones=cambios)
    datos["verificacion_antes"] = {k: antes[k] for k in ("ok", "errores", "avisos", "por_paso")}
    datos["pasos"] = pasos
    datos["entradas_a_cambiar"] = sorted(cambios)
    datos["verificacion_prevista"] = {k: despues_previsto[k] for k in ("ok", "errores", "avisos", "por_paso")}
    if escribir and cambios:
        reemplazar_en_disco(archive, cambios)
        datos["escrito"] = True
        with FaFlujo(archive) as fa:
            for ruta, nuevo in cambios.items():
                if fa.leer(ruta) != nuevo:
                    raise ValidacionError("USEARCH_REEXTRACCION", ruta=ruta, detalle="la reextracción no coincide")
            despues = verificar(fa.leer, juegos, decodificador=decodificador)
            datos["entradas_sha256"] = {r: {"antes": sha_antes[r], "despues": _sha256(fa.leer(r))} for r in cambios}
        datos["verificacion_despues"] = {k: despues[k] for k in ("ok", "errores", "avisos", "por_paso")}
        if sha_archive:
            datos["archive_sha256_despues"] = _sha256_fichero(archive)
        datos["archive_bytes_despues"] = archive.stat().st_size
        if original is not None:
            datos["comparacion_con_original"] = comparar_archives(original, archive)
            with FaFlujo(original) as fo, FaFlujo(archive) as fn:
                datos["diferencias_por_entrada"] = {
                    ruta: _resumen_diferencias(fo.leer(ruta), fn.leer(ruta), 44 if ruta.startswith("inazuma3") else 48)
                    for ruta in sorted(cambios)
                }
    if informe is not None:
        Path(informe).write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
    if datos["escrito"]:
        exigir_sincronia(datos["verificacion_despues"])
    return datos


# --------------------------------------------------------------------------- línea de órdenes


def main(argv: list[str] | None = None) -> int:
    """``python -m ie123kit.servicio.sincronia_usearch verificar|sincronizar|cerrar ARCHIVE.FA [--juegos ie1,ie2,ie3]``.

    * ``verificar``: sale con 1 si usearch no corresponde al nombre actual de unitbase (úsese antes de ``scp`` al PC).
    * ``sincronizar``: calcula; solo escribe con ``--escribir`` y sobre el fichero indicado (trabajar sobre una copia).
      Sale con 1 si, tras lo previsto/escrito, usearch sigue sin quedar sincronizado (también si no había nada que
      escribir).
    * ``cerrar``: PASO FINAL ÚNICO de la cadena en sitio (docs/HARNESS.md §4): sincroniza EN SITIO la copia, vuelve a
      verificarla desde el disco e imprime su sha256. Sale con 1 si no queda sincronizada; entonces la copia NO debe
      copiarse al PC ni instalarse.
    """
    import argparse

    from ie123kit.nucleo.config.raiz import find_root

    parser = argparse.ArgumentParser(prog="sincronia_usearch", description=main.__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("orden", choices=("verificar", "sincronizar", "cerrar"))
    parser.add_argument("archive", type=Path)
    parser.add_argument("--juegos", default="ie1,ie2,ie3")
    parser.add_argument("--escribir", action="store_true", help="(sincronizar) escribe en sitio; cerrar siempre escribe")
    parser.add_argument("--raiz", type=Path, default=None, help="raíz del repositorio (por defecto, la detectada)")
    parser.add_argument("--sin-sha", action="store_true", help="(cerrar) no calcula el sha256 final")
    args = parser.parse_args(argv)
    juegos = tuple(j for j in args.juegos.split(",") if j)
    raiz = args.raiz or find_root()
    if args.orden == "verificar":
        informe = verificar_archive(args.archive, raiz=raiz, juegos=juegos)
        print(json.dumps(informe, ensure_ascii=False, indent=1))
        return 0 if informe["ok"] else 1
    try:
        informe = ejecutar_capa("cli", juegos, args.archive, raiz, escribir=args.escribir or args.orden == "cerrar",
                                sha_archive=False)
        final = (verificar_archive(args.archive, raiz=raiz, juegos=juegos) if args.orden == "cerrar"
                 else informe["verificacion_despues" if informe["escrito"] else "verificacion_prevista"])
    except ValidacionError as exc:
        print(json.dumps({"ok": False, "codigo": exc.codigo, "detalle": f"{exc.detalle} ({exc.ruta})"},
                         ensure_ascii=False, indent=1))
        return 1
    resumen = {"ok": final["ok"], "escrito": informe["escrito"], "entradas_a_cambiar": informe["entradas_a_cambiar"],
               "errores": final["errores"], "avisos": len(final["avisos"])}
    if args.orden == "cerrar" and not args.sin_sha:
        resumen["archive_sha256"] = _sha256_fichero(args.archive)
    print(json.dumps(resumen, ensure_ascii=False, indent=1))
    return 0 if final["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
