"""Orden `ie123`: adaptador argparse 1:1 sobre `ServicioToolkit`. Sin lógica propia.

F2.3 añade los verbos que cierran los paquetes de juego: `proyecto init`,
`proyecto migrar-juego-principal`, `objetivos`, `work limpiar` y la acción
`<objetivo> activos`, con un subparser por cada id de `servicio.api.OBJETIVOS`.
F2.4 completa el resto (`extraer`, `verificar`, `instalar`, `compat`) y la tabla
completa de alias en inglés. No añadir aquí ninguna regla de negocio: si algo
falta, va en `nucleo` y se expone por `servicio`.

Las banderas comunes (`--json`, `--proyecto`) se declaran en un parser padre con
`default=argparse.SUPPRESS` y se cuelgan de cada subparser, así que valen antes y
después del verbo (`ie123 --json X activos` y `ie123 X activos --json`) sin que el
valor por defecto del hijo pise al que ya trajo el padre.

Códigos de salida (docs/toolkit/ESPECIFICACION.md, spec.cli):
0 ok · 1 incidencias de validación · 2 uso incorrecto · 3 bloqueo tipográfico
4 falta una herramienta externa · 5 operación no soportada.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from ie123kit.servicio.api import OBJETIVOS, ServicioToolkit, SolicitudConstruccion

__all__ = ["ALIAS", "CODIGOS_SALIDA", "abrir_servicio", "construir_parser", "main"]

OK = 0
VALIDACION = 1
USO = 2
BLOQUEO = 3
HERRAMIENTA = 4
NO_SOPORTADO = 5

#: Código de incidencia → código de salida del proceso.
CODIGOS_SALIDA: dict[str, int] = {
    "BLOQUEO_V20": BLOQUEO,
    "HERRAMIENTA_AUSENTE": HERRAMIENTA,
    "NOT_SUPPORTED": NO_SOPORTADO,
}

#: Alias en inglés → verbo canónico en español (la tabla completa es F2.4).
ALIAS: dict[str, str] = {
    "build": "construir",
    "patch": "parche",
    "targets": "objetivos",
    "project": "proyecto",
    "init": "init",
    "assets": "activos",
    "clean": "limpiar",
}


def abrir_servicio(raiz: str | None = None) -> ServicioToolkit:
    """Fábrica de la fachada; los tests la sustituyen para no tocar disco."""
    return ServicioToolkit.abrir(raiz)


def _comunes() -> argparse.ArgumentParser:
    """Banderas válidas antes y después del verbo. `SUPPRESS`: el hijo no pisa al padre."""
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--proyecto", metavar="RUTA", default=argparse.SUPPRESS,
                   help="Raíz del repositorio (por defecto se busca).")
    p.add_argument("--json", action="store_true", dest="json_", default=argparse.SUPPRESS,
                   help="Imprime el Resultado serializado.")
    return p


def construir_parser() -> argparse.ArgumentParser:
    """Parser de la CLI."""
    comunes = _comunes()
    p = argparse.ArgumentParser(prog="ie123", parents=[comunes],
                                description="Herramientas de la traducción de Inazuma Eleven 1·2·3.")
    # Sin `set_defaults`: `parents=` COMPARTE los objetos Action, y `set_defaults` les cambia
    # el `default` a todos a la vez, con lo que el hijo volvería a poner `--json` en False y
    # `ie123 --json X activos` dejaría de imprimir JSON. Los ausentes se leen con `getattr`.
    sub = p.add_subparsers(dest="orden", required=True)

    c = sub.add_parser("construir", parents=[comunes], aliases=["build"],
                       help="Construye una candidata de toda la recopilación.")
    c.add_argument("--base", required=True, help="Candidata base (nombre o ruta).")
    c.add_argument("--objetivos", default="", help="Lista separada por comas (por defecto, ninguno).")
    c.add_argument("--capas", action="append", default=[], metavar="RUTA", help="Capa a aplicar (repetible).")
    c.add_argument("--salida", required=True, help="Candidata de salida (nombre o ruta).")

    x = sub.add_parser("parche", parents=[comunes], aliases=["patch"],
                       help="Genera el .xdelta entre la ROM base y la parcheada.")
    x.add_argument("--rom-base", required=True, dest="rom_base")
    x.add_argument("--rom-parcheada", required=True, dest="rom_parcheada")
    x.add_argument("--salida", required=True)

    sub.add_parser("doctor", parents=[comunes], help="Comprueba el entorno local.")
    sub.add_parser("objetivos", parents=[comunes], aliases=["targets"],
                   help="Lista los objetivos de la recopilación.")

    proyecto = sub.add_parser("proyecto", parents=[comunes], aliases=["project"],
                              help="Prepara y migra el espacio de trabajo.")
    acc_proyecto = proyecto.add_subparsers(dest="accion", required=True)
    ini = acc_proyecto.add_parser("init", parents=[comunes],
                                 help="Crea work/<objetivo>/ y translation/<objetivo>/ (idempotente).")
    ini.add_argument("--rom3ds", metavar="RUTA", default=None, help="Ruta de la ROM 3DS japonesa.")
    ini.add_argument("--nds-es-ie1", dest="nds_es_ie1", metavar="RUTA", default=None,
                     help="Ruta de la ROM NDS española de IE1 (fuente canónica del texto ES).")
    ini.add_argument("--simular", action="store_true", help="Solo informa de lo que haría.")
    mig = acc_proyecto.add_parser("migrar-juego-principal", parents=[comunes],
                                  help="Escribe work/juego_principal/historico.json (no mueve nada).")
    mig.add_argument("--simular", action="store_true", default=True,
                     help="Por defecto: mover capas no está soportado.")
    mig.add_argument("--no-simular", action="store_false", dest="simular",
                     help="Intenta la migración real (responde NOT_SUPPORTED).")

    work = sub.add_parser("work", parents=[comunes], help="Mantenimiento de work/.")
    acc_work = work.add_subparsers(dest="accion", required=True)
    lim = acc_work.add_parser("limpiar", parents=[comunes], aliases=["clean"],
                              help="Lista (o borra con --borrar) lo regenerable de work/.")
    lim.add_argument("--borrar", action="store_true", help="Borra de verdad; sin esto solo lista.")

    for objetivo in sorted(OBJETIVOS):
        obj = sub.add_parser(objetivo, parents=[comunes], help=f"Acciones sobre {objetivo}.")
        acciones = obj.add_subparsers(dest="accion", required=True)
        act = acciones.add_parser("activos", parents=[comunes], aliases=["assets"],
                                  help="Inventario de activos del objetivo.")
        act.add_argument("--tipo", default=None, help="Filtra por tipo de activo.")
        act.add_argument("--filtro", metavar="PATRON", default=None, help="Subcadena del id del activo.")
    return p


def _codigo(resultado: Any) -> int:
    if getattr(resultado, "ok", False):
        return OK
    codigos = [getattr(i, "codigo", "") for i in getattr(resultado, "incidencias", ())]
    for codigo in ("BLOQUEO_V20", "HERRAMIENTA_AUSENTE", "NOT_SUPPORTED"):
        if codigo in codigos:
            return CODIGOS_SALIDA[codigo]
    return VALIDACION


def _imprimir(resultado: Any, como_json: bool) -> None:
    salida = sys.stdout
    reconfigurar = getattr(salida, "reconfigure", None)
    if reconfigurar is not None:
        try:
            reconfigurar(encoding="utf-8")
        except (OSError, ValueError):
            pass
    if como_json:
        print(json.dumps(resultado.to_json(), ensure_ascii=False, indent=2))
        return
    print("ok" if getattr(resultado, "ok", False) else "FALLO")
    for clave, valor in (getattr(resultado, "datos", {}) or {}).items():
        if clave != "informe":
            print(f"  {clave}: {valor}")
    for incidencia in getattr(resultado, "incidencias", ()):
        print(f"  [{incidencia.severidad}] {incidencia.codigo}: {incidencia.mensaje}")
    for artefacto in getattr(resultado, "artefactos", ()):
        print(f"  -> {artefacto}")


def _canonico(nombre: str | None) -> str:
    return ALIAS.get(nombre or "", nombre or "")


def _ejecutar(args: argparse.Namespace) -> Any:
    servicio = abrir_servicio(getattr(args, "proyecto", None))
    orden = _canonico(getattr(args, "orden", None))
    accion = _canonico(getattr(args, "accion", None))
    if orden == "construir":
        objetivos = tuple(o.strip() for o in args.objetivos.split(",") if o.strip())
        solicitud = SolicitudConstruccion(
            base=args.base, objetivos=objetivos, capas=tuple(args.capas), salida=args.salida
        )
        return servicio.construir(solicitud)
    if orden == "parche":
        return servicio.parche(args.rom_base, args.rom_parcheada, args.salida)
    if orden == "objetivos":
        return servicio.objetivos()
    if orden == "proyecto":
        if accion == "init":
            return servicio.init(rom_3ds=args.rom3ds, roms={"nds_es_ie1": args.nds_es_ie1},
                                 simular=args.simular)
        return servicio.migrar_juego_principal(simular=args.simular)
    if orden == "work":
        return servicio.limpiar(borrar=args.borrar)
    if orden in OBJETIVOS:
        return servicio.activos(orden, tipo=args.tipo, filtro=args.filtro)
    return servicio.doctor()


def main(argv: list[str] | None = None) -> int:
    """Analiza `argv`, llama a la fachada e imprime su Resultado."""
    parser = construir_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:  # argparse ya ha impreso el error
        codigo = exc.code
        if codigo in (0, None):
            return OK
        return USO
    resultado = _ejecutar(args)
    _imprimir(resultado, getattr(args, "json_", False))
    return _codigo(resultado)
