"""Comprueba por AST que los imports de módulos de tools/ en los scripts de work/ se resuelven.

Uso: python -m ie123kit.nucleo.compat.importaciones [--work work] [--baseline B.json] [--capturar B.json]
Sale con 1 si hay imports no resueltos que no estén ya en la línea base.
Si tools/<mod>.py es un shim, los nombres importados se comprueban contra el módulo real de tools/src.
"""
import argparse
import ast
import json
import sys
from pathlib import Path

# Dependencias de terceros que usan tools/ y las capas de work/ (no son módulos de tools/).
# cv2 (opencv-python-headless) y scipy los usan las capas gráficas v69/v70; ver el extra
# 'graficos' de tools/pyproject.toml. Añadir aquí cada dependencia externa nueva.
EXTERNOS = {'numpy', 'PIL', 'capstone', 'cv2', 'scipy'}


def _raiz():
    from ie123kit.nucleo.config.raiz import find_root
    return find_root()


def modulos_tools(tools):
    return {p.stem for p in tools.glob('*.py')} | {p.name for p in tools.iterdir() if (p / '__init__.py').is_file()}


def usa_tools(texto):
    return any(m in texto for m in ("'tools'", '"tools"', '/tools', 'tools/'))


def importados(arbol, completo=False):
    """(línea, módulo, nombres) de cada import absoluto; con completo=True, el módulo con puntos."""
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            for a in nodo.names:
                yield nodo.lineno, a.name if completo else a.name.split('.')[0], None
        elif isinstance(nodo, ast.ImportFrom) and nodo.level == 0 and nodo.module:
            yield nodo.lineno, nodo.module if completo else nodo.module.split('.')[0], [a.name for a in nodo.names]


def paquetes_src(tools):
    """Paquetes instalables de tools/src (p. ej. ie123kit), que las capas importan directamente."""
    src = tools / 'src'
    return {p.name for p in src.iterdir() if (p / '__init__.py').is_file()} if src.is_dir() else set()


def _fallos_paquete(tools, modulo, nombres):
    """Fallos de `import ie123kit.a.b` o `from ie123kit.a.b import n` contra el código de tools/src."""
    base = tools / 'src' / Path(*modulo.split('.'))
    if base.with_suffix('.py').is_file():
        fuente, paquete = base.with_suffix('.py'), None
    elif (base / '__init__.py').is_file():
        fuente, paquete = base / '__init__.py', base
    else:
        return [f'módulo {modulo}']
    if not nombres:
        return []
    arbol = ast.parse(fuente.read_text(encoding='utf-8', errors='replace'))
    if any(isinstance(n, ast.ImportFrom) and any(a.name == '*' for a in n.names) for n in ast.walk(arbol)):
        return []
    # Un __getattr__ de módulo sirve nombres por atributo (fachadas perezosas): valen los literales.
    dinamicos = set()
    if any(isinstance(n, ast.FunctionDef) and n.name == '__getattr__' for n in arbol.body):
        dinamicos = {n.value for n in ast.walk(arbol) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    fallos = []
    for n in nombres:
        if n == '*' or n in definidos(fuente) or n in dinamicos:
            continue
        # `from paquete import submodulo`
        if paquete is not None and ((paquete / f'{n}.py').is_file() or (paquete / n / '__init__.py').is_file()):
            continue
        fallos.append(f'{modulo}.{n}')
    return fallos


_CACHE_DEFINIDOS = {}


def definidos(ruta, cache=None):
    cache = _CACHE_DEFINIDOS if cache is None else cache
    if ruta not in cache:
        nombres = set()
        for nodo in ast.walk(ast.parse(ruta.read_text(encoding='utf-8', errors='replace'))):
            if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                nombres.add(nodo.name)
            elif isinstance(nodo, (ast.Assign, ast.AnnAssign)):
                for t in (nodo.targets if isinstance(nodo, ast.Assign) else [nodo.target]):
                    nombres.update(n.id for n in ast.walk(t) if isinstance(n, ast.Name))
            elif isinstance(nodo, (ast.Import, ast.ImportFrom)):
                nombres.update((a.asname or a.name).split('.')[0] for a in nodo.names)
        cache[ruta] = nombres
    return cache[ruta]


def _destino_de_shim(ruta) -> str | None:
    """Primer argumento literal de importlib.import_module('<destino>') en un shim, o None."""
    try:
        arbol = ast.parse(Path(ruta).read_text(encoding='utf-8', errors='replace'))
    except SyntaxError:
        return None
    for nodo in ast.walk(arbol):
        if (isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Attribute)
                and nodo.func.attr == 'import_module' and isinstance(nodo.func.value, ast.Name)
                and nodo.func.value.id == 'importlib' and nodo.args
                and isinstance(nodo.args[0], ast.Constant) and isinstance(nodo.args[0].value, str)):
            return nodo.args[0].value
    return None


def _fuente_real(tools, mod):
    """Fuente con la que comprobar nombres de tools/<mod>.py (el módulo real si es shim), o None."""
    ruta = tools / f'{mod}.py'
    if not ruta.is_file():
        return None
    if 'sys.modules[__name__]' not in ruta.read_text(encoding='utf-8', errors='replace'):
        return ruta
    destino = _destino_de_shim(ruta)
    if not destino:
        return None
    base = tools / 'src' / Path(*destino.split('.'))
    for real in (base.with_suffix('.py'), base / '__init__.py'):
        if real.is_file():
            arbol = ast.parse(real.read_text(encoding='utf-8', errors='replace'))
            if any(isinstance(n, ast.ImportFrom) and any(a.name == '*' for a in n.names) for n in ast.walk(arbol)):
                return None
            return real
    return None


def analizar(work):
    raiz = _raiz()
    tools = raiz / 'tools'
    disponibles = modulos_tools(tools)
    paquetes = paquetes_src(tools)
    scripts = sorted(Path(work).rglob('*.py'))
    # Módulos hermanos de otras capas (p. ej. v33/eve_labels/common.py) no son de tools/.
    conocidos = set(sys.stdlib_module_names) | EXTERNOS | ({p.stem for p in scripts} - disponibles)
    fallos, total = [], 0
    for script in scripts:
        if script.stat().st_size > 3_000_000:
            continue
        texto = script.read_text(encoding='utf-8', errors='replace')
        if not usa_tools(texto):
            continue
        total += 1
        rel = script.resolve().relative_to(raiz).as_posix()
        try:
            arbol = ast.parse(texto)
        except SyntaxError as e:
            fallos.append(f'{rel}: sintaxis línea {e.lineno}')
            continue
        locales = {p.stem for p in script.parent.glob('*.py')}
        for linea, completo, nombres in importados(arbol, completo=True):
            mod = completo.split('.')[0]
            if mod in paquetes and mod not in disponibles:
                fallos += [f'{rel}:{linea}: {f}' for f in _fallos_paquete(tools, completo, nombres)]
                continue
            if mod in conocidos or mod in locales:
                continue
            if mod not in disponibles:
                fallos.append(f'{rel}:{linea}: módulo {mod}')
            elif nombres and (fuente := _fuente_real(tools, mod)) is not None:
                fallos += [f'{rel}:{linea}: {mod}.{n}' for n in nombres
                           if n != '*' and n not in definidos(fuente)]
    return total, sorted(set(fallos))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--work')
    ap.add_argument('--baseline')
    ap.add_argument('--capturar')
    args = ap.parse_args()
    if args.work is None:
        args.work = str(_raiz() / 'work')
    total, fallos = analizar(args.work)
    if args.capturar:
        Path(args.capturar).write_text(json.dumps(fallos, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    previos = set(json.loads(Path(args.baseline).read_text(encoding='utf-8'))) if args.baseline else set()
    nuevos = [f for f in fallos if f not in previos]
    for f in nuevos:
        print('NO RESUELTO', f)
    print(f'{total} scripts de work/ usan tools/; {len(fallos)} no resueltos '
          f'({len(fallos) - len(nuevos)} en línea base); {len(nuevos)} nuevos')
    return 1 if nuevos and not args.capturar else 0


if __name__ == '__main__':
    sys.exit(main())
