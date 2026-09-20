"""Busca por AST quién importa unos módulos concretos de tools/ (paso 1 del archivado de scripts).

Uso: python -m ie123kit.nucleo.compat.importadores [--work RUTA] [--json] MOD [MOD ...]
Recorre tools/*.py, tools/src/**, tools/tests/** y work/** (excluye __pycache__).
Sale con 1 si hay importadores externos; las referencias de ruta 'tools/<mod>.py' son solo informativas.
"""
import argparse
import ast
import json
import sys
from pathlib import Path

LIMITE_BYTES = 3_000_000
_DINAMICOS = {'import_module', '__import__'}


def _raiz():
    from ie123kit.nucleo.config.raiz import find_root
    return find_root()


def _ficheros(raiz, work):
    tools = raiz / 'tools'
    candidatos = []
    if tools.is_dir():
        candidatos += sorted(tools.glob('*.py'))
        for sub in ('src', 'tests'):
            if (tools / sub).is_dir():
                candidatos += sorted((tools / sub).rglob('*.py'))
    if work is not None:
        candidatos += sorted(work.rglob('*.py'))
    vistos, salida = set(), []
    for p in candidatos:
        if '__pycache__' in p.parts or p in vistos:
            continue
        vistos.add(p)
        salida.append(p)
    return salida


def _primero(nombre):
    return nombre.split('.')[0]


def _nombre_llamada(func):
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute) and func.attr == 'import_module':
        return func.attr
    return None


def _hallazgos(arbol, mods):
    """Genera (modulo, linea, tipo) para imports, imports dinámicos y referencias de ruta."""
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            for a in nodo.names:
                if _primero(a.name) in mods:
                    yield _primero(a.name), nodo.lineno, 'import'
        elif isinstance(nodo, ast.ImportFrom):
            if nodo.level == 0 and nodo.module and _primero(nodo.module) in mods:
                yield _primero(nodo.module), nodo.lineno, 'from'
        elif isinstance(nodo, ast.Call):
            if (_nombre_llamada(nodo.func) in _DINAMICOS and nodo.args
                    and isinstance(nodo.args[0], ast.Constant) and isinstance(nodo.args[0].value, str)
                    and _primero(nodo.args[0].value) in mods):
                yield _primero(nodo.args[0].value), nodo.lineno, 'dinamico'
        elif isinstance(nodo, ast.Constant) and isinstance(nodo.value, str):
            for m in sorted(mods):
                if f'tools/{m}.py' in nodo.value or f'tools\\{m}.py' in nodo.value:
                    yield m, nodo.lineno, 'ruta'


def buscar(mods, work=None) -> dict:
    raiz = Path(_raiz())
    mods = set(mods)
    res = {'importadores': [], 'internos': [], 'referencias': [], 'avisos': [], 'ficheros': 0}
    tools = raiz / 'tools'
    for m in sorted(mods):
        if not (tools / f'{m}.py').is_file():
            from ie123kit.nucleo.compat.superficie import RETIRADOS
            donde = 'retirado (docs/toolkit/SCRIPTS_RETIRADOS.md)' if m in RETIRADOS else 'no existe'
            res['avisos'].append(f'{m}: {donde} en tools/')
    work = raiz / 'work' if work is None else Path(work)
    if not work.is_dir():
        res['avisos'].append(f'{work}: no existe; se omite work/')
        work = None
    for ruta in _ficheros(raiz, work):
        try:
            if ruta.stat().st_size > LIMITE_BYTES:
                continue
            rel = ruta.resolve().relative_to(raiz.resolve()).as_posix()
        except (OSError, ValueError):
            rel = ruta.as_posix()
        res['ficheros'] += 1
        try:
            arbol = ast.parse(ruta.read_text(encoding='utf-8', errors='replace'))
        except SyntaxError as e:
            res['avisos'].append(f'{rel}:{e.lineno}: error de sintaxis')
            continue
        de_tools = ruta.parent.resolve() == tools.resolve()
        for mod, linea, tipo in _hallazgos(arbol, mods):
            if de_tools and ruta.stem == mod:
                continue
            entrada = {'modulo': mod, 'ruta': rel, 'linea': linea, 'tipo': tipo}
            if tipo == 'ruta':
                res['referencias'].append(entrada)
            elif de_tools and ruta.stem in mods:
                res['internos'].append(entrada)
            else:
                res['importadores'].append(entrada)
    for clave in ('importadores', 'internos', 'referencias'):
        res[clave].sort(key=lambda e: (e['modulo'], e['ruta'], e['linea'], e['tipo']))
    return res


def main(argv=None):
    ap = argparse.ArgumentParser(description='Busca importadores de módulos de tools/ en tools/ y work/.')
    ap.add_argument('--work', default=None, help='carpeta work (por defecto <raíz>/work)')
    ap.add_argument('--json', action='store_true', help='volcar el resultado en JSON')
    ap.add_argument('mods', nargs='+', metavar='MOD')
    args = ap.parse_args(argv)
    res = buscar(args.mods, args.work)
    n_ficheros = res.pop('ficheros')
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=1))
    else:
        for clave, etiqueta in (('importadores', 'IMPORTADOR'), ('internos', 'INTERNO'),
                                ('referencias', 'REFERENCIA')):
            for e in res[clave]:
                print(f"{etiqueta} {e['modulo']} <- {e['ruta']}:{e['linea']} ({e['tipo']})")
        for a in res['avisos']:
            print(f'AVISO {a}')
        print(f'{len(set(args.mods))} módulos; {n_ficheros} ficheros analizados; '
              f"{len(res['importadores'])} importadores externos; {len(res['internos'])} internos; "
              f"{len(res['referencias'])} referencias de ruta")
    return 1 if res['importadores'] else 0


if __name__ == '__main__':
    sys.exit(main())
