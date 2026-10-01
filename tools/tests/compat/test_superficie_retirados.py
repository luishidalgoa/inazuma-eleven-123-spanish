"""Tests de la regla de módulos retirados (RETIRADOS) del comparador de superficie."""
import json
import sys
from pathlib import Path

import pytest

from ie123kit.nucleo.compat import superficie


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


def _ejecutar(monkeypatch, *argv):
    monkeypatch.setattr(sys, 'argv', ['x', *argv])
    return superficie.main()


@pytest.fixture
def base(raiz, monkeypatch):
    tools = raiz / 'tools'
    _escribir(tools / 'a.py', 'def fa(x): pass\n')
    _escribir(tools / 'b.py', 'def fb(y): pass\n')
    fichero = raiz / 'superficie.json'
    assert _ejecutar(monkeypatch, 'capturar', str(fichero)) == 0
    return tools, fichero


def test_retirado_se_omite(base, monkeypatch, capsys):
    tools, fichero = base
    monkeypatch.setattr(superficie, 'SCRIPTS_RETIRADOS', frozenset({'b'}))
    monkeypatch.setattr(superficie, '_shims_retirados', frozenset)
    (tools / 'b.py').unlink()
    capsys.readouterr()
    assert _ejecutar(monkeypatch, 'comparar', str(fichero)) == 0
    assert '1 retirados omitidos' in capsys.readouterr().out


def test_ausente_no_retirado_falla(base, monkeypatch, capsys):
    tools, fichero = base
    (tools / 'b.py').unlink()
    assert _ejecutar(monkeypatch, 'comparar', str(fichero)) == 1
    assert 'b: módulo ausente' in capsys.readouterr().out


def test_retirado_que_sigue_en_tools_falla(base, monkeypatch, capsys):
    _tools, fichero = base
    monkeypatch.setattr(superficie, 'SCRIPTS_RETIRADOS', frozenset({'b'}))
    monkeypatch.setattr(superficie, '_shims_retirados', frozenset)
    assert _ejecutar(monkeypatch, 'comparar', str(fichero)) == 1
    assert 'b: en RETIRADOS pero sigue en tools/' in capsys.readouterr().out


def test_capturar_no_mira_subcarpetas(base, monkeypatch, raiz):
    tools, _ = base
    _escribir(tools / 'sub' / 'c.py', 'def fc(): pass\n')
    nuevo = raiz / 'nuevo.json'
    assert _ejecutar(monkeypatch, 'capturar', str(nuevo)) == 0
    assert sorted(json.loads(nuevo.read_text(encoding='utf-8'))) == ['a', 'b']


def test_retirados_coincide_con_el_documento():
    """SCRIPTS_RETIRADOS y la tabla de docs/toolkit/SCRIPTS_RETIRADOS.md dicen lo mismo (F2.6, #55)."""
    import re

    from ie123kit.nucleo.config.raiz import find_root

    doc = (find_root() / 'docs/toolkit/SCRIPTS_RETIRADOS.md').read_text(encoding='utf-8')
    citados = {
        Path(m).stem
        for m in re.findall(r'^\| `([^`]+\.py)` \|', doc, flags=re.MULTILINE)
    }
    assert citados == set(superficie.SCRIPTS_RETIRADOS), (
        f'solo en el documento: {sorted(citados - superficie.SCRIPTS_RETIRADOS)}; '
        f'solo en SCRIPTS_RETIRADOS: {sorted(superficie.SCRIPTS_RETIRADOS - citados)}'
    )


# F1.5 (#46): tests heredados de la raíz trasladados a tools/tests/unidad.

@pytest.fixture
def con_test_heredado(raiz, monkeypatch):
    tools = raiz / 'tools'
    _escribir(tools / 'a.py', 'def fa(x): pass\n')
    _escribir(tools / 'test_ssd_records.py', 'def sample(): pass\n')
    fichero = raiz / 'superficie.json'
    assert _ejecutar(monkeypatch, 'capturar', str(fichero)) == 0
    return tools, fichero


def _escribir_rutas_nuevas(raiz, mod):
    for ruta in superficie.TESTS_TRASLADADOS[mod]:
        _escribir(raiz / ruta, 'def test_x(): pass\n')


def test_test_trasladado_se_omite(con_test_heredado, raiz, monkeypatch, capsys):
    tools, fichero = con_test_heredado
    _escribir_rutas_nuevas(raiz, 'test_ssd_records')
    (tools / 'test_ssd_records.py').unlink()
    assert superficie.es_test_trasladado('test_ssd_records', tools) is True
    capsys.readouterr()
    assert _ejecutar(monkeypatch, 'comprobar', str(fichero)) == 0
    assert '1 tests trasladados omitidos' in capsys.readouterr().out


def test_test_trasladado_duplicado_falla(con_test_heredado, raiz, monkeypatch, capsys):
    tools, fichero = con_test_heredado
    _escribir_rutas_nuevas(raiz, 'test_ssd_records')
    assert superficie.es_test_trasladado('test_ssd_records', tools) is False
    assert _ejecutar(monkeypatch, 'comprobar', str(fichero)) == 1
    assert 'test_ssd_records: duplicado en tools/ y tools/tests' in capsys.readouterr().out


def test_test_trasladado_incompleto_falla(con_test_heredado, raiz, monkeypatch, capsys):
    tools, fichero = con_test_heredado
    (tools / 'test_ssd_records.py').unlink()
    assert superficie.es_test_trasladado('test_ssd_records', tools) is False
    assert superficie.es_test_trasladado('a', tools) is False
    assert _ejecutar(monkeypatch, 'comprobar', str(fichero)) == 1
    assert 'test_ssd_records: módulo ausente' in capsys.readouterr().out


def test_los_shims_retirados_tambien_cuentan_como_retirados():
    """RETIRADOS() suma los shims planos retirados: si no, `superficie comprobar` los da por ausentes.

    Es la regresión que arrastraba el gate desde la F2.4 (#50): los 5 shims de CLI retirados entonces no
    estaban en ninguna lista y salían como «módulo ausente» (5 diferencias). Lo arregló la F2.6 (#55).
    """
    from ie123kit.nucleo.compat import shims

    todos = superficie.RETIRADOS()
    assert set(shims.RETIRADOS) <= todos
    assert superficie.SCRIPTS_RETIRADOS <= todos
    for nombre in ('blz', 'nds_unpack', 'harvest_log', 'limpiar_work', 'verify_candidate'):
        assert superficie.es_retirado(nombre) is True, nombre
