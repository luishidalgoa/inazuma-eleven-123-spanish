"""Orden `ie123`: adaptador argparse 1:1 sobre `ServicioToolkit`. Sin lógica propia.

Verbos (F2.4, #50; docs/toolkit/ESPECIFICACION.md, «CLI»):

- proyecto: `proyecto init`, `proyecto migrar-juego-principal`, `objetivos`, `doctor`,
  `work limpiar`, `compat comprobar [--golden]`, `compat equivalencias`;
- ROM y candidatas: `extraer romfs|nds`, `construir`, `verificar`, `instalar`, `parche`,
  `registro` (cosecha del log de Azahar);
- por objetivo: `<objetivo> activos`;
- motores portados de las capas: `motor listar`, `motor paginar|teclado|cro-ancho-dialogo|voces|subtitulos|
  voz-recopilatorio|ayuda`.

No añadir aquí ninguna regla de negocio: si algo falta, va en `nucleo` o en el juego y se expone
por `servicio`. Esta capa solo importa `ie123kit.servicio`.

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

#: Código de incidencia (de severidad error) → código de salida del proceso.
CODIGOS_SALIDA: dict[str, int] = {
    "BLOQUEO_V20": BLOQUEO,
    "HERRAMIENTA_AUSENTE": HERRAMIENTA,
    "NOT_SUPPORTED": NO_SOPORTADO,
}

#: Alias en inglés → verbo canónico en español (tabla completa, F2.4).
ALIAS: dict[str, str] = {
    "build": "construir",
    "patch": "parche",
    "targets": "objetivos",
    "project": "proyecto",
    "init": "init",
    "migrate-main-game": "migrar-juego-principal",
    "assets": "activos",
    "clean": "limpiar",
    "extract": "extraer",
    "verify": "verificar",
    "install": "instalar",
    "check": "comprobar",
    "equivalences": "equivalencias",
    "log": "registro",
    "engine": "motor",
    "list": "listar",
    "paginate": "paginar",
    "keyboard": "teclado",
    "voices": "voces",
    "subtitles": "subtitulos",
    "cro-dialogue-width": "cro-ancho-dialogo",
    "help-screens": "ayuda",
    "compilation-voice": "voz-recopilatorio",
}

#: Motores de `ie123 motor`: nombre → (juego por defecto, juegos admitidos).
_MOTORES: dict[str, tuple[str, tuple[str, ...]]] = {
    "paginar": ("ie2", ("ie1", "ie2")),
    "teclado": ("ie2", ("ie2",)),
    "cro-ancho-dialogo": ("ie2", ("ie2",)),
    "voces": ("ie2", ("ie2",)),
    "subtitulos": ("ie2", ("ie2",)),
    "voz-recopilatorio": ("juego_principal", ("juego_principal",)),
    "ayuda": ("ie2", ("ie2",)),
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


def _alias(canonico: str) -> list[str]:
    return [a for a, c in ALIAS.items() if c == canonico and a != canonico]


def _parser_motor(sub: Any, comunes: argparse.ArgumentParser) -> None:
    motor = sub.add_parser("motor", parents=[comunes], aliases=_alias("motor"),
                           help="Motores portados de las capas (por juego).")
    acc = motor.add_subparsers(dest="accion", required=True)
    acc.add_parser("listar", parents=[comunes], aliases=_alias("listar"), help="Motores disponibles por juego.")
    for nombre, (defecto, juegos) in _MOTORES.items():
        m = acc.add_parser(nombre, parents=[comunes], aliases=_alias(nombre), help=f"Motor {nombre}.")
        m.add_argument("--juego", default=defecto, choices=juegos, help=f"Juego (por defecto {defecto}).")
        if nombre == "paginar":
            m.add_argument("--texto", required=True, help="Texto íntegro (los saltos se rehacen).")
        elif nombre == "teclado":
            m.add_argument("--archive", required=True, help="archive.fa de partida.")
            m.add_argument("--salida", required=True, help="Carpeta extra/ de salida (no se sobrescribe).")
        elif nombre == "cro-ancho-dialogo":
            m.add_argument("--cro", required=True, help="ina_main2.cro de partida.")
            m.add_argument("--salida", required=True, help="CRO de salida (no se sobrescribe).")
        elif nombre == "voces":
            m.add_argument("--sonido-3ds", required=True, dest="sonido_3ds", help="Carpeta con sound.ph/pb de la 3DS.")
            m.add_argument("--sonido-nds", required=True, dest="sonido_nds", help="Carpeta con sound.pkh/pkb de la NDS.")
            m.add_argument("--bancos", required=True, help="Bancos separados por comas (p. ej. 2D_020_01).")
            m.add_argument("--base", default=None, help="Carpeta del sound.pb base (por defecto, el de la 3DS).")
            m.add_argument("--salida", required=True, help="Carpeta de salida (no se sobrescribe).")
        elif nombre == "subtitulos":
            m.add_argument("--dat", required=True, help="movie/txt/<n>.dat de la NDS española.")
            m.add_argument("--fotogramas", type=int, default=None, help="Fotogramas del vídeo (opcional).")
        elif nombre == "ayuda":
            m.add_argument("--archive", required=True, help="archive.fa japonés de partida.")
            m.add_argument("--capturas-nds", required=True, dest="capturas_nds",
                           help="Carpeta pic3d/script/sp de la NDS española.")
            m.add_argument("--rutas", default=None, help="Solo estos .arc, separados por comas (opcional).")
            m.add_argument("--salida", required=True, help="Carpeta extra/ de salida (no se sobrescribe).")
        elif nombre == "voz-recopilatorio":
            m.add_argument("--sonido", required=True, help="Carpeta con CM_000.SWD/CM_000.SED japoneses.")
            m.add_argument("--fuente", required=True, help="Audio de la voz española (lo lee ffmpeg).")
            m.add_argument("--salida", required=True, help="Carpeta de salida (no se sobrescribe).")


def construir_parser() -> argparse.ArgumentParser:
    """Parser de la CLI."""
    comunes = _comunes()
    p = argparse.ArgumentParser(prog="ie123", parents=[comunes],
                                description="Herramientas de la traducción de Inazuma Eleven 1·2·3.")
    # Sin `set_defaults`: `parents=` COMPARTE los objetos Action, y `set_defaults` les cambia
    # el `default` a todos a la vez, con lo que el hijo volvería a poner `--json` en False y
    # `ie123 --json X activos` dejaría de imprimir JSON. Los ausentes se leen con `getattr`.
    sub = p.add_subparsers(dest="orden", required=True)

    c = sub.add_parser("construir", parents=[comunes], aliases=_alias("construir"),
                       help="Construye una candidata de toda la recopilación.")
    c.add_argument("--base", required=True, help="Candidata base (nombre o ruta).")
    c.add_argument("--objetivos", default="", help="Lista separada por comas (por defecto, ninguno).")
    c.add_argument("--capas", action="append", default=[], metavar="RUTA", help="Capa a aplicar (repetible).")
    c.add_argument("--salida", required=True, help="Candidata de salida (nombre o ruta).")

    x = sub.add_parser("parche", parents=[comunes], aliases=_alias("parche"),
                       help="Genera el .xdelta entre la ROM base y la parcheada.")
    x.add_argument("--rom-base", required=True, dest="rom_base")
    x.add_argument("--rom-parcheada", required=True, dest="rom_parcheada")
    x.add_argument("--salida", required=True)

    e = sub.add_parser("extraer", parents=[comunes], aliases=_alias("extraer"),
                       help="Extrae una ROM a work/ (romfs: 3DS con 3dstool; nds: sin herramientas).")
    e.add_argument("tipo", choices=("romfs", "nds"))
    e.add_argument("--rom", default=None, help="ROM de entrada (romfs: por defecto la de ie123.local.toml).")
    e.add_argument("--salida", default=None, help="Carpeta de salida (romfs: work/shared/base_3ds).")

    v = sub.add_parser("verificar", parents=[comunes], aliases=_alias("verificar"),
                       help="Verifica una candidata (bloqueo v20 siempre).")
    v.add_argument("--candidata", required=True)
    v.add_argument("--golden", action="store_true", help="Compara también con los hashes golden.")

    i = sub.add_parser("instalar", parents=[comunes], aliases=_alias("instalar"),
                       help="Instala una candidata en Azahar (LayeredFS).")
    i.add_argument("--candidata", required=True)
    i.add_argument("--lanzar", action="store_true", help="Abre Azahar al terminar.")

    r = sub.add_parser("registro", parents=[comunes], aliases=_alias("registro"),
                       help="Cosecha el log de Azahar en logs/runtime_errors.json.")
    r.add_argument("--sesion", default=None, help="Solo el log actual, marcado con esta build.")
    r.add_argument("--logdir", default=None, help="Carpeta del log (por defecto %%APPDATA%%/Azahar/log).")
    r.add_argument("--forzar", action="store_true", help="Reprocesa aunque el log no haya cambiado.")

    sub.add_parser("doctor", parents=[comunes], help="Comprueba el entorno local.")
    sub.add_parser("objetivos", parents=[comunes], aliases=_alias("objetivos"),
                   help="Lista los objetivos de la recopilación.")

    compat = sub.add_parser("compat", parents=[comunes], help="Gates de la migración y equivalencias.")
    acc_compat = compat.add_subparsers(dest="accion", required=True)
    cc = acc_compat.add_parser("comprobar", parents=[comunes], aliases=_alias("comprobar"),
                               help="Ejecuta los gates (con --golden, también los que necesitan work/).")
    cc.add_argument("--golden", action="store_true")
    acc_compat.add_parser("equivalencias", parents=[comunes], aliases=_alias("equivalencias"),
                          help="Orden nueva de cada script retirado.")

    proyecto = sub.add_parser("proyecto", parents=[comunes], aliases=_alias("proyecto"),
                              help="Prepara y migra el espacio de trabajo.")
    acc_proyecto = proyecto.add_subparsers(dest="accion", required=True)
    ini = acc_proyecto.add_parser("init", parents=[comunes],
                                 help="Crea work/<objetivo>/ y translation/<objetivo>/ (idempotente).")
    ini.add_argument("--rom3ds", metavar="RUTA", default=None, help="Ruta de la ROM 3DS japonesa.")
    ini.add_argument("--nds-es-ie1", dest="nds_es_ie1", metavar="RUTA", default=None,
                     help="Ruta de la ROM NDS española de IE1 (fuente canónica del texto ES).")
    ini.add_argument("--simular", action="store_true", help="Solo informa de lo que haría.")
    mig = acc_proyecto.add_parser("migrar-juego-principal", parents=[comunes],
                                  aliases=_alias("migrar-juego-principal"),
                                  help="Índice work/juego_principal/historico.json de las capas del menú (no mueve nada).")
    mig.add_argument("--simular", action="store_true", default=True,
                     help="Por defecto: solo informa, no escribe.")
    mig.add_argument("--no-simular", action="store_false", dest="simular",
                     help="Escribe el índice (las capas no se mueven).")

    work = sub.add_parser("work", parents=[comunes], help="Mantenimiento de work/.")
    acc_work = work.add_subparsers(dest="accion", required=True)
    lim = acc_work.add_parser("limpiar", parents=[comunes], aliases=_alias("limpiar"),
                              help="Lista (o borra con --borrar) lo regenerable de work/.")
    lim.add_argument("--borrar", action="store_true", help="Borra de verdad; sin esto solo lista.")

    _parser_motor(sub, comunes)

    for objetivo in sorted(OBJETIVOS):
        obj = sub.add_parser(objetivo, parents=[comunes], help=f"Acciones sobre {objetivo}.")
        acciones = obj.add_subparsers(dest="accion", required=True)
        act = acciones.add_parser("activos", parents=[comunes], aliases=_alias("activos"),
                                  help="Inventario de activos del objetivo.")
        act.add_argument("--tipo", default=None, help="Filtra por tipo de activo.")
        act.add_argument("--filtro", metavar="PATRON", default=None, help="Subcadena del id del activo.")
    return p


def _codigo(resultado: Any) -> int:
    if getattr(resultado, "ok", False):
        return OK
    codigos = [getattr(i, "codigo", "") for i in getattr(resultado, "incidencias", ())
               if getattr(i, "severidad", "error") == "error"]
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
        if clave == "informe":
            continue
        if isinstance(valor, list) and valor and all(isinstance(x, dict) for x in valor):
            print(f"  {clave}:")
            for fila in valor:
                print("    - " + " · ".join(f"{k}={v}" for k, v in fila.items() if v not in ("", None)))
        else:
            print(f"  {clave}: {valor}")
    for incidencia in getattr(resultado, "incidencias", ()):
        print(f"  [{incidencia.severidad}] {incidencia.codigo}: {incidencia.mensaje}")
    for artefacto in getattr(resultado, "artefactos", ()):
        print(f"  -> {artefacto}")


def _canonico(nombre: str | None) -> str:
    return ALIAS.get(nombre or "", nombre or "")


def _parametros_motor(nombre: str, args: argparse.Namespace) -> dict[str, Any]:
    if nombre == "paginar":
        return {"texto": args.texto}
    if nombre == "teclado":
        return {"archive": args.archive, "salida": args.salida}
    if nombre == "cro-ancho-dialogo":
        return {"cro": args.cro, "salida": args.salida}
    if nombre == "voces":
        bancos = [b.strip() for b in args.bancos.split(",") if b.strip()]
        return {"sonido_3ds": args.sonido_3ds, "sonido_nds": args.sonido_nds, "bancos": bancos,
                "salida": args.salida, "base": args.base}
    if nombre == "voz-recopilatorio":
        return {"sonido": args.sonido, "fuente": args.fuente, "salida": args.salida}
    if nombre == "ayuda":
        rutas = [r.strip() for r in args.rutas.split(",") if r.strip()] if args.rutas else None
        return {"archive": args.archive, "capturas_nds": args.capturas_nds, "salida": args.salida,
                "rutas": rutas}
    return {"dat": args.dat, "fotogramas": args.fotogramas}


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
    if orden == "extraer":
        return servicio.extraer(args.tipo, rom=args.rom, salida=args.salida)
    if orden == "verificar":
        return servicio.verificar(args.candidata, golden=args.golden)
    if orden == "instalar":
        return servicio.instalar(args.candidata, lanzar=args.lanzar)
    if orden == "registro":
        return servicio.registro(sesion=args.sesion, logdir=args.logdir, forzar=args.forzar)
    if orden == "objetivos":
        return servicio.objetivos()
    if orden == "compat":
        if accion == "equivalencias":
            return servicio.equivalencias()
        return servicio.compat(golden=args.golden)
    if orden == "proyecto":
        if accion == "init":
            return servicio.init(rom_3ds=args.rom3ds, roms={"nds_es_ie1": args.nds_es_ie1},
                                 simular=args.simular)
        return servicio.migrar_juego_principal(simular=args.simular)
    if orden == "work":
        return servicio.limpiar(borrar=args.borrar)
    if orden == "motor":
        if accion == "listar":
            return servicio.motores()
        return servicio.motor(args.juego, accion, _parametros_motor(accion, args))
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
