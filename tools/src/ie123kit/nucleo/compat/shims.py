"""Generador de shims de compatibilidad para los módulos trasladados de tools/.

Cada módulo movido al paquete ie123kit deja en tools/<nombre>.py un alias que
sustituye su entrada en sys.modules por el módulo real, de modo que la identidad
y la mutación de globales se conservan. Importar este módulo no produce I/O.
"""
from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

__all__ = [
    "CONGELADOS",
    "MAPA",
    "RETIRADOS",
    "destino_de_shim",
    "detectar_cli",
    "es_shim_sin_logica",
    "fuente_de",
    "generar",
    "main",
    "renderizar",
]

CONGELADOS = frozenset(
    {"dialogue_typography", "font_patch", "dialogue_lock", "build_ie1_probe", "build_ui_revision"}
)

#: Shims de CLI retirados en la F2.4 (#50): ninguna capa los importaba (comprobador AST) y su orden
#: vive en ``ie123`` (``ie123 compat equivalencias``). Sus módulos siguen en ``ie123kit._legado``.
RETIRADOS: frozenset[str] = frozenset({"blz", "nds_unpack", "harvest_log", "limpiar_work", "verify_candidate"})

MAPA: dict[str, str] = {
    "lz10": "ie123kit.nucleo.compresion.lz10",
    "sszl": "ie123kit.nucleo.compresion.sszl",
    "ui_archive": "ie123kit._legado.ui_archive",
    "qna_regions": "ie123kit.nucleo.graficos.qna",
    "legacy_sprite": "ie123kit.nucleo.graficos.pac_sprite",
    "nftr_metrics": "ie123kit._legado.nftr_metrics",
    "bcfnt": "ie123kit._legado.bcfnt",
    "ctpk_ui": "ie123kit.nucleo.graficos.ctpk",
    "ssd_records": "ie123kit.nucleo.eventos.ssd",
    "fa_unpack": "ie123kit._legado.fa_unpack",
    "fa_repack": "ie123kit._legado.fa_repack",
    "patch_smdh_title": "ie123kit._legado.patch_smdh_title",
    "ie1_keyboard": "ie123kit.ie1.graficos.teclado",
}
MAPA.update(
    {
        _n: f"ie123kit._legado.{_n}"
        for _n in (
            "pkb_unpack",
            "build_glossary",
            "ds_official",
            "reinsert",
            "translate_ui_textures",
            "mods_to_moflex",
            "audit_dialogo_ids",
            "ds_roster",
            "reinsert_var",
            "ssd_reinsert",
            "validate",
        )
    }
)

_RE_DESTINO = re.compile(r"^ie123kit(\.[A-Za-z_][A-Za-z0-9_]*)+$")
_CLIS = (None, "llamar", "salir")

_PLANTILLA = (
    '"""Shim generado por ie123kit.nucleo.compat.shims (no editar): alias de {destino}."""\n'
    "import importlib\n"
    "import sys\n"
    "from pathlib import Path\n"
    "\n"
    "_SRC = str(Path(__file__).resolve().parent / 'src')\n"
    "if _SRC not in sys.path:\n"
    "    sys.path.insert(0, _SRC)\n"
    "sys.modules[__name__] = importlib.import_module('{destino}')\n"
)
_COLA = {
    "llamar": "\nif __name__ == '__main__':\n    sys.modules[__name__].main()\n",
    "salir": "\nif __name__ == '__main__':\n    raise SystemExit(sys.modules[__name__].main())\n",
}


def _validar_destino(destino: str) -> None:
    if not isinstance(destino, str) or not _RE_DESTINO.match(destino):
        raise ValueError(f"destino no válido (debe ser ie123kit.<...>): {destino!r}")


def renderizar(destino: str, cli: str | None) -> str:
    """Devuelve el texto exacto del shim para ``destino``."""
    _validar_destino(destino)
    if cli not in _CLIS:
        raise ValueError(f"cli no válido: {cli!r}")
    texto = _PLANTILLA.format(destino=destino)
    if cli is not None:
        texto += _COLA[cli]
    return texto


def fuente_de(destino: str, src: Path) -> Path | None:
    """Localiza el fichero fuente del módulo ``destino`` bajo ``src``."""
    _validar_destino(destino)
    base = Path(src).joinpath(*destino.split("."))
    modulo = base.with_suffix(".py")
    if modulo.is_file():
        return modulo
    paquete = base / "__init__.py"
    if paquete.is_file():
        return paquete
    return None


def _es_bloque_main(nodo: ast.stmt) -> bool:
    if not isinstance(nodo, ast.If):
        return False
    t = nodo.test
    if not (isinstance(t, ast.Compare) and len(t.ops) == 1 and isinstance(t.ops[0], ast.Eq)):
        return False
    lados = [t.left, t.comparators[0]]
    nombre = any(isinstance(x, ast.Name) and x.id == "__name__" for x in lados)
    literal = any(isinstance(x, ast.Constant) and x.value == "__main__" for x in lados)
    return nombre and literal


def _es_llamada_main(nodo: ast.AST | None) -> bool:
    return isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Name) and nodo.func.id == "main"


def _es_salida(nodo: ast.AST) -> bool:
    if isinstance(nodo, ast.Raise) and isinstance(nodo.exc, ast.Call):
        f = nodo.exc.func
        return (
            isinstance(f, ast.Name)
            and f.id == "SystemExit"
            and len(nodo.exc.args) == 1
            and _es_llamada_main(nodo.exc.args[0])
        )
    if isinstance(nodo, ast.Call) and len(nodo.args) == 1 and _es_llamada_main(nodo.args[0]):
        f = nodo.func
        if isinstance(f, ast.Name) and f.id == "exit":
            return True
        return (
            isinstance(f, ast.Attribute)
            and f.attr == "exit"
            and isinstance(f.value, ast.Name)
            and f.value.id == "sys"
        )
    return False


def detectar_cli(fuente: Path) -> str | None:
    """Detecta por AST, sin ejecutar, cómo se lanza el módulo real como script."""
    arbol = ast.parse(Path(fuente).read_text(encoding="utf-8"), filename=str(fuente))
    bloques = [n for n in arbol.body if _es_bloque_main(n)]
    if not bloques:
        return None
    llama = False
    for bloque in bloques:
        for nodo in ast.walk(bloque):
            if _es_salida(nodo):
                return "salir"
            if _es_llamada_main(nodo):
                llama = True
    if llama:
        return "llamar"
    raise ValueError(
        f"{fuente}: tiene bloque __main__ sin llamar a main(); "
        "necesita una fachada _legado con main()"
    )


def destino_de_shim(ruta: Path) -> str | None:
    """Devuelve el literal de ``sys.modules[__name__] = importlib.import_module('...')``."""
    try:
        arbol = ast.parse(Path(ruta).read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError, ValueError):
        return None
    for nodo in arbol.body:
        if not (isinstance(nodo, ast.Assign) and len(nodo.targets) == 1):
            continue
        obj = nodo.targets[0]
        if not (
            isinstance(obj, ast.Subscript)
            and isinstance(obj.value, ast.Attribute)
            and obj.value.attr == "modules"
            and isinstance(obj.value.value, ast.Name)
            and obj.value.value.id == "sys"
            and isinstance(obj.slice, ast.Name)
            and obj.slice.id == "__name__"
        ):
            continue
        v = nodo.value
        if (
            isinstance(v, ast.Call)
            and isinstance(v.func, ast.Attribute)
            and v.func.attr == "import_module"
            and isinstance(v.func.value, ast.Name)
            and v.func.value.id == "importlib"
            and len(v.args) == 1
            and not v.keywords
            and isinstance(v.args[0], ast.Constant)
            and isinstance(v.args[0].value, str)
        ):
            return v.args[0].value
    return None


def es_shim_sin_logica(ruta: Path) -> tuple[bool, str]:
    """Comprueba por AST que ``ruta`` es exactamente un shim generado, sin lógica extra."""
    try:
        volcado = ast.dump(ast.parse(Path(ruta).read_text(encoding="utf-8")))
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        return False, f"no se puede leer: {exc}"
    except SyntaxError as exc:
        return False, f"error de sintaxis: {exc}"
    destino = destino_de_shim(ruta)
    if destino is None:
        return False, "no asigna sys.modules[__name__] = importlib.import_module('<literal>')"
    if not _RE_DESTINO.match(destino):
        return False, f"destino no válido: {destino!r}"
    for cli in _CLIS:
        if volcado == ast.dump(ast.parse(renderizar(destino, cli))):
            return True, f"shim de {destino}"
    return False, "el cuerpo difiere de la plantilla (sentencias o lógica adicionales)"


def generar(
    nombre: str,
    *,
    destino: str | None = None,
    salida: Path,
    src: Path,
    cli: str = "auto",
    forzar: bool = False,
    simular: bool = False,
) -> Path:
    """Genera (o simula) el shim ``salida/<nombre>.py`` y devuelve su ruta."""
    return _preparar(nombre, destino, salida, src, cli, forzar, simular)[0]


def _preparar(nombre, destino, salida, src, cli, forzar, simular) -> tuple[Path, str]:
    if not isinstance(nombre, str) or not nombre.isidentifier():
        raise ValueError(f"nombre de módulo no válido: {nombre!r}")
    if nombre in CONGELADOS:
        raise ValueError(f"{nombre} está congelado (bloqueo v20): nunca se genera su shim")
    destino = destino or MAPA.get(nombre)
    if destino is None:
        raise ValueError(f"{nombre} no está en MAPA: indica el destino")
    _validar_destino(destino)
    if cli == "auto":
        fuente = fuente_de(destino, Path(src))
        if fuente is None:
            raise FileNotFoundError(f"no existe el módulo real {destino} bajo {src}")
        modo = detectar_cli(fuente)
    elif cli == "ninguno":
        modo = None
    elif cli in ("llamar", "salir"):
        modo = cli
    else:
        raise ValueError(f"cli no válido: {cli!r}")
    texto = renderizar(destino, modo)
    ruta = Path(salida) / f"{nombre}.py"
    if simular:
        return ruta, texto
    if ruta.exists():
        try:
            actual = ruta.read_bytes().decode("utf-8")
        except UnicodeDecodeError:
            actual = None
        if actual == texto:
            return ruta, texto
        if not forzar and not es_shim_sin_logica(ruta)[0]:
            raise FileExistsError(f"{ruta} existe y no es un shim sin lógica (usa forzar)")
    with open(ruta, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(texto)
    return ruta, texto


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m ie123kit.nucleo.compat.shims",
        description="Genera y comprueba los shims de compatibilidad de tools/.",
    )
    sub = p.add_subparsers(dest="orden", required=True, metavar="ORDEN")
    g = sub.add_parser("generar", help="genera shims en tools/")
    g.add_argument("nombres", nargs="+", metavar="NOMBRE")
    g.add_argument("--destino", metavar="MOD", help="módulo real (solo con un NOMBRE)")
    g.add_argument("--salida", type=Path, metavar="DIR", help="carpeta del shim (tools/)")
    g.add_argument("--src", type=Path, metavar="DIR", help="carpeta src del paquete")
    g.add_argument("--cli", choices=("auto", "ninguno", "llamar", "salir"), default="auto")
    g.add_argument("--forzar", action="store_true", help="sobrescribe ficheros que no son shims")
    g.add_argument("--simular", action="store_true", help="muestra el texto sin escribir")
    c = sub.add_parser("comprobar", help="verifica que los shims no tienen lógica")
    c.add_argument("rutas", nargs="*", type=Path, metavar="RUTA")
    sub.add_parser("listar", help="muestra el mapa de traslados")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.orden == "listar":
        for nombre in sorted(MAPA):
            print(f"{nombre}\t{MAPA[nombre]}")
        return 0

    from ie123kit.nucleo.config.raiz import find_root

    if args.orden == "generar":
        if args.destino and len(args.nombres) != 1:
            print("ERROR: --destino solo admite un NOMBRE", file=sys.stderr)
            return 2
        salida = args.salida if args.salida is not None else find_root() / "tools"
        src = args.src if args.src is not None else find_root() / "tools" / "src"
        for nombre in args.nombres:
            try:
                ruta, texto = _preparar(
                    nombre, args.destino, salida, src, args.cli, args.forzar, args.simular
                )
            except (ValueError, FileNotFoundError, FileExistsError) as exc:
                print(f"ERROR {nombre}: {exc}", file=sys.stderr)
                return 1
            if args.simular:
                print(f"# {ruta}")
                sys.stdout.write(texto)
            else:
                print(f"generado {ruta}")
        return 0

    rutas = list(args.rutas)
    if not rutas:
        tools = find_root() / "tools"
        rutas = sorted(
            r
            for r in tools.glob("*.py")
            if "sys.modules[__name__]" in r.read_text(encoding="utf-8", errors="replace")
        )
    malos = 0
    for ruta in rutas:
        ok, motivo = es_shim_sin_logica(ruta)
        if not ok:
            malos += 1
            print(f"SHIM CON LÓGICA {ruta}: {motivo}")
    if malos:
        return 1
    print(f"{len(rutas)} shim(s) sin lógica")
    return 0


if __name__ == "__main__":
    sys.exit(main())
