"""Tests de los comprobadores de compatibilidad (F1.1, #42) sobre una raíz sintética sin datos del juego."""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from ie123kit.nucleo.compat import golden, importaciones, superficie

AQUI = Path(__file__).resolve().parent


@pytest.fixture
def raiz(tmp_path, monkeypatch):
    (tmp_path / 'AGENTS.md').write_text('sintético\n', encoding='utf-8')
    (tmp_path / 'tools').mkdir()
    (tmp_path / 'tools' / 'pyproject.toml').write_text('', encoding='utf-8')
    monkeypatch.setenv('IE123_ROOT', str(tmp_path))
    return tmp_path


def _escribir(ruta, texto):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(texto, encoding='utf-8')


def _preparar_importaciones(raiz):
    _escribir(raiz / 'tools' / 'modreal.py', 'def f(): pass\n')
    _escribir(raiz / 'tools' / 'alias.py', "import importlib\nimport sys\n"
              "sys.modules[__name__] = importlib.import_module('ie123kit.nucleo.falso')\n")
    _escribir(raiz / 'tools' / 'src' / 'ie123kit' / 'nucleo' / 'falso.py', 'def g(): pass\n')
    _escribir(raiz / 'work' / 'capa' / 'apply.py',
              "import sys; sys.path.insert(0, 'tools')\n"
              "from modreal import f\nfrom modreal import noexiste\n"
              "from alias import g\nfrom alias import h\nimport modulo_inexistente_xyz\n")


def test_importaciones_analizar(raiz):
    _preparar_importaciones(raiz)
    total, fallos = importaciones.analizar(str(raiz / 'work'))
    assert total == 1
    assert fallos == sorted([
        'work/capa/apply.py:3: modreal.noexiste',
        'work/capa/apply.py:5: alias.h',
        'work/capa/apply.py:6: módulo modulo_inexistente_xyz',
    ])
    assert not any('alias.g' in f for f in fallos)


def test_importaciones_main_baseline(raiz, tmp_path, monkeypatch):
    _preparar_importaciones(raiz)
    _, fallos = importaciones.analizar(str(raiz / 'work'))
    llena, vacia = tmp_path / 'llena.json', tmp_path / 'vacia.json'
    llena.write_text(json.dumps(fallos), encoding='utf-8')
    vacia.write_text('[]', encoding='utf-8')
    for fichero, esperado in ((llena, 0), (vacia, 1)):
        monkeypatch.setattr(sys, 'argv', ['x', '--work', str(raiz / 'work'), '--baseline', str(fichero)])
        assert importaciones.main() == esperado


def test_importaciones_externos_no_son_fallos(raiz):
    """Dependencias de terceros declaradas (cv2, scipy de las capas v69/v70) no cuentan como no resueltas."""
    _escribir(raiz / 'work' / 'capa' / 'apply.py',
              "import sys; sys.path.insert(0, 'tools')\n"
              "import cv2\nimport numpy as np\nfrom PIL import Image\nfrom scipy import ndimage as nd\n")
    total, fallos = importaciones.analizar(str(raiz / 'work'))
    assert (total, fallos) == (1, [])


def test_importaciones_paquete_src(raiz):
    """Las capas que importan ie123kit directamente se comprueban contra tools/src (tras la reorganización)."""
    _escribir(raiz / 'tools' / 'src' / 'ie123kit' / '__init__.py', '')
    _escribir(raiz / 'tools' / 'src' / 'ie123kit' / 'nucleo' / '__init__.py', '')
    _escribir(raiz / 'tools' / 'src' / 'ie123kit' / 'nucleo' / 'real.py', 'def f(): pass\n')
    _escribir(raiz / 'tools' / 'src' / 'ie123kit' / 'nucleo' / 'perezoso.py',
              "NOMBRES = ('servido',)\n\ndef __getattr__(n):\n    return n\n")
    _escribir(raiz / 'work' / 'capa' / 'apply.py',
              "import sys; sys.path.insert(0, 'tools/src')\n"
              "from ie123kit.nucleo.real import f\nfrom ie123kit.nucleo.real import falta\n"
              "from ie123kit.nucleo import real\nfrom ie123kit.nucleo.perezoso import servido\n"
              "import ie123kit.nucleo.inexistente\n")
    total, fallos = importaciones.analizar(str(raiz / 'work'))
    assert total == 1
    assert fallos == sorted([
        'work/capa/apply.py:3: ie123kit.nucleo.real.falta',
        'work/capa/apply.py:6: módulo ie123kit.nucleo.inexistente',
    ])


def test_superficie(raiz, monkeypatch):
    mod = raiz / 'tools' / 'modulo.py'
    _escribir(mod, 'def funcion(a, b=1): pass\n')
    _escribir(raiz / 'tools' / 'tests' / 'compat' / '.keep', '')
    monkeypatch.setattr(sys, 'argv', ['x', 'capturar'])
    assert superficie.main() == 0
    monkeypatch.setattr(sys, 'argv', ['x', 'comprobar'])
    assert superficie.main() == 0
    fichero = raiz / 'tools' / 'tests' / 'compat' / 'superficie_v0.json'
    monkeypatch.setattr(sys, 'argv', ['x', 'comparar', str(fichero)])
    assert superficie.main() == 0
    mod.write_text('X = 1\n', encoding='utf-8')
    monkeypatch.setattr(sys, 'argv', ['x', 'comprobar'])
    assert superficie.main() == 1
    monkeypatch.setattr(sys, 'argv', ['x', 'comparar', str(fichero)])
    assert superficie.main() == 1


def test_golden_grupo(raiz):
    ruta = raiz / 'tools' / 'dialogue_lock.py'
    _escribir(ruta, 'contenido sintético\n')
    bueno = hashlib.sha256(ruta.read_bytes()).hexdigest()
    gold = raiz / 'tools' / 'tests' / 'compat' / 'golden' / 'congelados.sha256'
    _escribir(gold, f'{bueno}  tools/dialogue_lock.py\n')
    assert golden.comprobar_grupo('congelados.sha256') == (1, [])
    _escribir(gold, f'{"0" * 64}  tools/dialogue_lock.py\n')
    total, malos = golden.comprobar_grupo('congelados.sha256')
    assert total == 1 and len(malos) == 1


def test_golden_candidata_sin_capa(raiz, monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['x', 'comprobar', '--candidata', 'probe_ie1_v67'])
    assert golden.main() == 2


@pytest.mark.parametrize('nombre', ['importaciones', 'superficie', 'golden'])
def test_envoltorios_help(nombre):
    entorno = {k: v for k, v in os.environ.items() if k != 'IE123_ROOT'}
    r = subprocess.run([sys.executable, '-X', 'utf8', str(AQUI / f'{nombre}.py'), '--help'],
                       env=entorno, capture_output=True, check=False)
    assert r.returncode == 0, r.stderr


@pytest.mark.requiere_rom
def test_golden_real(monkeypatch):
    monkeypatch.delenv('IE123_ROOT', raising=False)
    from ie123kit.nucleo.config.raiz import find_root
    raiz = find_root()
    if not (raiz / golden.BASE_REFERENCIA / 'archive.fa').is_file():
        pytest.skip(f'sin {golden.BASE_REFERENCIA}/archive.fa')
    import ie123kit
    entorno = {k: v for k, v in os.environ.items() if k != 'IE123_ROOT'}
    src = str(Path(ie123kit.__file__).resolve().parent.parent)
    entorno['PYTHONPATH'] = os.pathsep.join(filter(None, [src, entorno.get('PYTHONPATH')]))
    r = subprocess.run([sys.executable, '-X', 'utf8', '-m', 'ie123kit.nucleo.compat.golden', 'comprobar'],
                       cwd=raiz, env=entorno, check=False)
    assert r.returncode == 0
