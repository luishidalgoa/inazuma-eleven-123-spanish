"""Tests del buscador de importadores (F1.2, #43) sobre una raíz sintética sin datos del juego."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from ie123kit.nucleo.compat import importadores


@pytest.fixture
def raiz(tmp_path, monkeypatch):
    (tmp_path / 'AGENTS.md').write_text('sintético\n', encoding='utf-8')
    (tmp_path / 'tools').mkdir()
    (tmp_path / 'tools' / 'pyproject.toml').write_text('', encoding='utf-8')
    (tmp_path / 'tools' / 'viejo.py').write_text('def f(): pass\n', encoding='utf-8')
    (tmp_path / 'work').mkdir()
    monkeypatch.setenv('IE123_ROOT', str(tmp_path))
    return tmp_path


def _escribir(ruta, texto):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(texto, encoding='utf-8')


def test_import_directo(raiz):
    _escribir(raiz / 'tools' / 'activo.py', 'import viejo\n')
    res = importadores.buscar(['viejo'])
    assert res['importadores'] == [{'modulo': 'viejo', 'ruta': 'tools/activo.py', 'linea': 1, 'tipo': 'import'}]
    assert importadores.main(['viejo']) == 1


def test_from_en_work(raiz):
    _escribir(raiz / 'work' / 'capa' / 'apply.py', "import sys; sys.path.insert(0, 'tools')\nfrom viejo import f\n")
    res = importadores.buscar(['viejo'])
    assert [(e['ruta'], e['linea'], e['tipo']) for e in res['importadores']] == [('work/capa/apply.py', 2, 'from')]


def test_dinamico(raiz):
    _escribir(raiz / 'tools' / 'src' / 'pkg' / 'm.py', "import importlib\nimportlib.import_module('viejo')\n")
    res = importadores.buscar(['viejo'])
    assert [e['tipo'] for e in res['importadores']] == ['dinamico']


def test_referencia_no_cuenta(raiz):
    _escribir(raiz / 'work' / 'v' / 'validate.py', "print('ver tools/viejo.py')\n")
    res = importadores.buscar(['viejo'])
    assert res['importadores'] == []
    assert [e['tipo'] for e in res['referencias']] == ['ruta']
    assert importadores.main(['viejo']) == 0


def test_interno(raiz):
    _escribir(raiz / 'tools' / 'otro_viejo.py', 'import viejo\n')
    res = importadores.buscar(['viejo', 'otro_viejo'])
    assert res['importadores'] == []
    assert [e['ruta'] for e in res['internos']] == ['tools/otro_viejo.py']
    assert importadores.main(['viejo', 'otro_viejo']) == 0


def test_archivo_ignorado(raiz):
    _escribir(raiz / 'tools' / '_archivo' / 'x.py', 'import viejo\n')
    _escribir(raiz / 'tools' / '_archivo' / 'tests' / 'test_x.py', 'import viejo\n')
    assert importadores.buscar(['viejo'])['importadores'] == []


def test_error_sintaxis(raiz):
    _escribir(raiz / 'work' / 'roto.py', 'def (:\n')
    _escribir(raiz / 'work' / 'bueno.py', 'import viejo\n')
    res = importadores.buscar(['viejo'])
    assert any('work/roto.py' in a for a in res['avisos'])
    assert len(res['importadores']) == 1


def test_mod_inexistente(raiz):
    res = importadores.buscar(['fantasma'])
    assert 'fantasma: no existe en tools/' in res['avisos']


def test_json(raiz, capsys):
    _escribir(raiz / 'tools' / 'activo.py', 'import viejo\n')
    assert importadores.main(['--json', 'viejo']) == 1
    datos = json.loads(capsys.readouterr().out)
    assert set(datos) == {'importadores', 'internos', 'referencias', 'avisos'}


def test_help_subprocess(raiz):
    import ie123kit
    entorno = {k: v for k, v in os.environ.items() if k != 'IE123_ROOT'}
    src = str(Path(ie123kit.__file__).resolve().parent.parent)
    entorno['PYTHONPATH'] = os.pathsep.join(filter(None, [src, entorno.get('PYTHONPATH')]))
    r = subprocess.run([sys.executable, '-X', 'utf8', '-m', 'ie123kit.nucleo.compat.importadores', '--help'],
                       cwd=raiz, env=entorno, check=False, capture_output=True)
    assert r.returncode == 0
