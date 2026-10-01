"""Captura o compara la superficie pública (nombres y firmas, por AST) de los módulos de tools/.

Uso: python -m ie123kit.nucleo.compat.superficie capturar|comprobar|comparar [FICHERO] [--fichero superficie_v0.json]
Va por AST para no ejecutar módulos con efectos al importar. comprobar (o su alias comparar) falla si
desaparece un nombre o cambia una firma; un módulo convertido en shim (sys.modules[__name__]) se da por bueno.
Un módulo ausente de tools/ que figure en RETIRADOS() (scripts borrados + shims planos retirados) se
omite y se cuenta como retirado; si sigue en tools/ pese a estar ahí se marca como duplicado. Hasta la F2.6 (#55) los retirados vivían en
tools/_archivo/; ahora solo están en el historial de git y su motivo en
docs/toolkit/SCRIPTS_RETIRADOS.md, que debe coincidir con RETIRADOS.
Los tests heredados de la raíz trasladados en F1.5 (#46) a tools/tests/unidad (TESTS_TRASLADADOS) se omiten
y se cuentan aparte si ya no están en tools/ y existen todas sus rutas nuevas; si siguen en tools/ y las
rutas nuevas existen se marcan como duplicados; si falta alguna ruta nueva, módulo ausente.
Importar este módulo no produce I/O.
"""
import argparse
import ast
import json
import sys
from pathlib import Path

#: Scripts retirados de tools/: archivados en F1.2/F1.4 (en tools/_archivo/) y borrados del árbol en la
#: F2.6 (#55). Su motivo y su sustituto están en docs/toolkit/SCRIPTS_RETIRADOS.md; el test
#: tests/compat/test_superficie_retirados.py comprueba que las dos listas coinciden.
SCRIPTS_RETIRADOS = frozenset({
    'align_events', 'audit_ie1_voiced_text', 'build_3ds', 'build_3ds_var', 'build_fontui',
    'build_ie1_movies', 'build_match_content_patch', 'build_mch_patch', 'build_translation',
    'compact_typography', 'fix_ie1_title_logo', 'ie1_media', 'ie1_tables', 'nds_str_dump',
    'patch_code', 'patch_cro', 'patch_exefs', 'pkb_scan', 'probe_ie1_spacing', 'recompress_test',
    'reinsert_test', 'reorganizar_proyecto', 'str_align', 'test_compact_typography',
    'test_validate_inputs', 'tr_merge', 'tr_prepare', 'ui_insert', 'validate_ie1_media',
    'verify_build', 'verify_v21',
    # F2.6 (#55): shims planos sin ningún importador (evidencia AST); sus módulos siguen en
    # ie123kit._legado y `ie123 compat equivalencias` da la orden sustituta.
    'ds_roster', 'reinsert_var', 'ssd_reinsert', 'validate',
})


def _shims_retirados():
    """Shims planos retirados (ie123kit.nucleo.compat.shims.RETIRADOS), sin importar el módulo al cargar."""
    from ie123kit.nucleo.compat.shims import RETIRADOS as _R
    return frozenset(_R)


def RETIRADOS():  # el nombre en mayúsculas se mantiene por continuidad con el conjunto anterior
    """Todo lo que ya no está en tools/ y no debe contar como ausente.

    Son dos listas con dueños distintos: los scripts archivados y borrados (SCRIPTS_RETIRADOS, con su
    motivo en docs/toolkit/SCRIPTS_RETIRADOS.md) y los shims planos retirados por no tener importadores
    (shims.RETIRADOS, documentados en tools/README.md). Hasta la F2.6 los 5 shims de CLI retirados en la
    F2.4 (#50) no estaban en ninguna de las dos y `superficie comprobar` los daba por ausentes: eran las
    5 diferencias que arrastraba el gate.
    """
    return SCRIPTS_RETIRADOS | _shims_retirados()

TESTS_TRASLADADOS = {
    'test_dialogue_lock': ('tools/tests/unidad/texto/test_dialogue_lock.py',),
    'test_dialogue_typography': ('tools/tests/unidad/texto/test_ancho_completo.py',),
    'test_probe_layout': ('tools/tests/unidad/texto/test_tipografia_v20.py',),
    'test_legacy_sprite': ('tools/tests/unidad/graficos/test_pac_sprite.py',
                           'tools/tests/unidad/compresion/test_lz10.py'),
    'test_ssd_records': ('tools/tests/unidad/eventos/test_ssd.py',),
    'test_ui_formats': ('tools/tests/unidad/graficos/test_formatos_ui.py',),
}


def _tools():
    from ie123kit.nucleo.config.raiz import find_root
    return find_root() / 'tools'


def firma(nodo):
    a = nodo.args
    partes = [x.arg for x in a.posonlyargs + a.args]
    if a.vararg:
        partes.append('*' + a.vararg.arg)
    partes += [x.arg for x in a.kwonlyargs]
    if a.kwarg:
        partes.append('**' + a.kwarg.arg)
    return 'def(' + ', '.join(partes) + ')'


def superficie(ruta):
    out = {}
    for nodo in ast.parse(ruta.read_text(encoding='utf-8', errors='replace')).body:
        if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out[nodo.name] = firma(nodo)
        elif isinstance(nodo, ast.ClassDef):
            out[nodo.name] = 'class'
            out.update({f'{nodo.name}.{m.name}': firma(m) for m in nodo.body
                        if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))})
        elif isinstance(nodo, (ast.Assign, ast.AnnAssign)):
            for t in (nodo.targets if isinstance(nodo, ast.Assign) else [nodo.target]):
                if isinstance(t, ast.Name):
                    out[t.id] = 'var'
    return out


def es_shim(mod, tools=None):
    ruta = (tools or _tools()) / f'{mod}.py'
    return ruta.is_file() and 'sys.modules[__name__]' in ruta.read_text(encoding='utf-8', errors='replace')


def es_retirado(mod, tools=None):
    """True si mod se retiró de tools/: script archivado y borrado, o shim plano sin importadores."""
    return mod in RETIRADOS()


def _rutas_nuevas_existen(mod, tools):
    raiz = tools.parent
    return all((raiz / r).is_file() for r in TESTS_TRASLADADOS[mod])


def es_test_trasladado(mod, tools=None):
    """True si mod es un test heredado trasladado: no está en tools/ y existen todas sus rutas nuevas."""
    if mod not in TESTS_TRASLADADOS:
        return False
    tools = tools or _tools()
    return not (tools / f'{mod}.py').is_file() and _rutas_nuevas_existen(mod, tools)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('accion', choices=['capturar', 'comprobar', 'comparar'])
    ap.add_argument('posicional', nargs='?', metavar='FICHERO')
    ap.add_argument('--fichero')
    args = ap.parse_args()
    tools = _tools()
    fichero = args.posicional or args.fichero or str(tools / 'tests' / 'compat' / 'superficie_v0.json')
    actual = {p.stem: superficie(p) for p in sorted(tools.glob('*.py'))}
    if args.accion == 'capturar':
        Path(fichero).write_text(json.dumps(actual, ensure_ascii=False, indent=1, sort_keys=True) + '\n',
                                 encoding='utf-8')
        print(f'{len(actual)} módulos, {sum(map(len, actual.values()))} nombres capturados')
        return 0
    esperado = json.loads(Path(fichero).read_text(encoding='utf-8'))
    errores = []
    retirados = 0
    trasladados = 0
    for mod, nombres in esperado.items():
        if es_shim(mod, tools):
            continue
        if es_test_trasladado(mod, tools):
            trasladados += 1
            continue
        if mod in TESTS_TRASLADADOS and mod in actual and _rutas_nuevas_existen(mod, tools):
            errores.append(f'{mod}: duplicado en tools/ y tools/tests')
        if es_retirado(mod, tools):
            if mod not in actual:
                retirados += 1
                continue
            errores.append(f'{mod}: en RETIRADOS pero sigue en tools/')
        if mod not in actual:
            errores.append(f'{mod}: módulo ausente')
            continue
        for n, tipo in nombres.items():
            if n not in actual[mod]:
                errores.append(f'{mod}.{n}: desaparecido')
            elif actual[mod][n] != tipo:
                errores.append(f'{mod}.{n}: {tipo} -> {actual[mod][n]}')
    for e in errores:
        print('SUPERFICIE', e)
    print(f'{len(esperado)} módulos comprobados; {retirados} retirados omitidos; '
          f'{trasladados} tests trasladados omitidos; {len(errores)} diferencias')
    return 1 if errores else 0


if __name__ == '__main__':
    sys.exit(main())
