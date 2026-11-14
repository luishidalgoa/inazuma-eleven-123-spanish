import hashlib
import shutil
import subprocess

import pytest

from ie123kit.nucleo.compat import guardia
from ie123kit.nucleo.compat.guardia import EXTENSIONES_PROHIBIDAS, LIMITE_PNG, main, rutas_prohibidas


@pytest.mark.parametrize("ext", sorted(EXTENSIONES_PROHIBIDAS))
def test_extensiones_prohibidas(ext):
    for nombre in (f"docs/a{ext}", f"docs/A{ext.upper()}"):
        assert [r for r, _ in rutas_prohibidas([nombre])] == [nombre]


@pytest.mark.parametrize("ruta", ["Roms/x.txt", "roms/x.txt", "work/ie1/a.json", "WORK/b.md"])
def test_prefijos(ruta):
    assert rutas_prohibidas([ruta])


def test_png_grande():
    grande = LIMITE_PNG + 1
    assert rutas_prohibidas(["docs/img/a.png"], {"docs/img/a.png": grande})
    assert not rutas_prohibidas(["docs/logos/a.png"], {"docs/logos/a.png": grande})
    assert not rutas_prohibidas(["docs/img/a.png"], {"docs/img/a.png": LIMITE_PNG})


def test_lista_limpia():
    assert rutas_prohibidas(["tools/pyproject.toml", "docs/FORMATOS.md", "tools/src/ie123kit/__init__.py"]) == []


def _raiz(tmp_path):
    (tmp_path / "AGENTS.md").write_text("x", encoding="utf-8")
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "pyproject.toml").write_text("", encoding="utf-8")
    return tmp_path


def test_git_str_rastreado(tmp_path, monkeypatch):
    if shutil.which("git") is None:
        pytest.skip("git no disponible")
    raiz = _raiz(tmp_path)
    (raiz / "texto.STR").write_bytes(b"\x00\x01")
    subprocess.run(["git", "init", "-q"], cwd=raiz, check=True)
    subprocess.run(["git", "add", "texto.STR", "AGENTS.md"], cwd=raiz, check=True)
    monkeypatch.setenv("IE123_ROOT", str(raiz))
    assert main(["git"]) == 1
    subprocess.run(["git", "rm", "-q", "--cached", "texto.STR"], cwd=raiz, check=True)
    assert main(["git"]) == 0


def _raiz_bloqueados(tmp_path):
    raiz = _raiz(tmp_path)
    nombres = ["dialogue_typography.py", "font_patch.py", "dialogue_lock.py", "build_ie1_probe.py", "build_ui_revision.py"]
    contenidos = {n: f"# {n}\n".encode() for n in nombres}
    sha = {n: hashlib.sha256(c).hexdigest() for n, c in contenidos.items()}
    lock = (
        "SOURCE_HASHES = {\n"
        f"    'tools/dialogue_typography.py': '{sha['dialogue_typography.py']}',\n"
        f"    'tools/font_patch.py': '{sha['font_patch.py']}',\n"
        "}\n"
    ).encode()
    contenidos["dialogue_lock.py"] = lock
    sha["dialogue_lock.py"] = hashlib.sha256(lock).hexdigest()
    for n, c in contenidos.items():
        (raiz / "tools" / n).write_bytes(c)
    golden = raiz / "tools" / "tests" / "compat" / "golden"
    golden.mkdir(parents=True)
    (golden / "congelados.sha256").write_text("".join(f"{sha[n]}  tools/{n}\n" for n in nombres), encoding="utf-8")
    return raiz


def test_bloqueados_sintetico(tmp_path, monkeypatch):
    raiz = _raiz_bloqueados(tmp_path)
    monkeypatch.setenv("IE123_ROOT", str(raiz))
    assert main(["bloqueados"]) == 0
    p = raiz / "tools" / "font_patch.py"
    p.write_bytes(p.read_bytes() + b" ")
    assert main(["bloqueados"]) == 1


def test_bloqueados_falta_entrada(tmp_path, monkeypatch):
    raiz = _raiz_bloqueados(tmp_path)
    m = raiz / guardia.RUTA_CONGELADOS
    m.write_text("".join(m.read_text(encoding="utf-8").splitlines(keepends=True)[:4]), encoding="utf-8")
    monkeypatch.setenv("IE123_ROOT", str(raiz))
    assert main(["bloqueados"]) == 1


def test_bloqueados_repo_real(monkeypatch):
    monkeypatch.delenv("IE123_ROOT", raising=False)
    assert main(["bloqueados"]) == 0


def _proyecto_version(tmp_path, version="3.1", render=None):
    (tmp_path / "ie123.toml").write_text(f'[release]\nversion = "{version}"\n', encoding="utf-8")
    if render is not None:
        ruta = tmp_path / guardia.RUTA_CREDITOS
        ruta.parent.mkdir(parents=True)
        ruta.write_text(render, encoding="utf-8")
    return tmp_path


def test_version_coherente_con_tag(tmp_path, capsys):
    raiz = _proyecto_version(tmp_path, render="VERSION = 'v' + toml['release']  # ie123.toml\n")
    assert guardia.comprobar_version(raiz) == 0
    assert guardia.comprobar_version(raiz, "v3.1") == 0


def test_version_tag_distinto(tmp_path, capsys):
    raiz = _proyecto_version(tmp_path)
    assert guardia.comprobar_version(raiz, "v3.0") == 1
    assert "no coincide" in capsys.readouterr().out


def test_version_escrita_a_mano_en_creditos(tmp_path, capsys):
    raiz = _proyecto_version(tmp_path, render="VERSION = 'v3.0'\n")
    assert guardia.comprobar_version(raiz) == 1
    assert "escrita a mano" in capsys.readouterr().out


def test_version_toml_invalido(tmp_path):
    assert guardia.comprobar_version(_proyecto_version(tmp_path, version="tres")) == 1


def test_version_repo_real():
    from ie123kit.nucleo.config.raiz import find_root

    assert guardia.comprobar_version(find_root()) == 0
