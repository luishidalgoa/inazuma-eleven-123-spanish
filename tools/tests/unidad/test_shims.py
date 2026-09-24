"""Pruebas del generador de shims (sin ROM, todo en tmp_path)."""
import os
import subprocess
import sys

import pytest

from ie123kit.nucleo.compat import shims

DESTINO = "ie123kit.nucleo.compresion.falso"


@pytest.fixture
def arbol(tmp_path):
    base = tmp_path / "src" / "ie123kit"
    (base / "nucleo" / "compresion").mkdir(parents=True)
    for rel in ("__init__.py", "nucleo/__init__.py", "nucleo/compresion/__init__.py"):
        (base / rel).write_text("", encoding="utf-8")
    (base / "nucleo" / "compresion" / "falso.py").write_text(
        "VALOR = 1\n\n\ndef main():\n    print('hola')\n    return 3\n\n\n"
        "if __name__ == '__main__':\n    import sys\n    sys.exit(main())\n",
        encoding="utf-8",
    )
    return tmp_path


def _entorno():
    env = dict(os.environ)
    env["PYTHONPATH"] = ""
    env["PYTHONUTF8"] = "1"
    return env


def _generar(arbol, **kw):
    return shims.generar("falso", destino=DESTINO, salida=arbol, src=arbol / "src", **kw)


def test_genera_shim_valido(arbol):
    ruta = _generar(arbol)
    assert ruta == arbol / "falso.py"
    assert shims.es_shim_sin_logica(ruta)[0] is True
    assert shims.destino_de_shim(ruta) == DESTINO
    assert shims.detectar_cli(shims.fuente_de(DESTINO, arbol / "src")) == "salir"
    texto = ruta.read_bytes().decode("utf-8")
    assert texto == shims.renderizar(DESTINO, "salir")
    assert "parents[" not in texto
    assert "\r" not in texto
    assert _generar(arbol) == ruta


def test_identidad_y_mutacion(arbol):
    _generar(arbol)
    codigo = (
        "import sys\nsys.path.insert(0, '.')\n"
        "import falso, ie123kit.nucleo.compresion.falso as real\n"
        "assert falso is real\nfalso.VALOR = 9\nassert real.VALOR == 9\n"
    )
    r = subprocess.run([sys.executable, "-c", codigo], cwd=arbol, env=_entorno(), check=False)
    assert r.returncode == 0


def test_cli_del_shim(arbol):
    ruta = _generar(arbol)
    r = subprocess.run(
        [sys.executable, str(ruta), "x"],
        cwd=arbol,
        env=_entorno(),
        check=False,
        capture_output=True,
        text=True,
    )
    assert r.returncode == 3
    assert r.stdout.strip() == "hola"


def test_linea_extra_es_logica(arbol):
    ruta = arbol / "otro.py"
    ruta.write_text(shims.renderizar(DESTINO, None) + "print(1)\n", encoding="utf-8")
    assert shims.es_shim_sin_logica(ruta)[0] is False


@pytest.mark.parametrize("forzar", [False, True])
def test_congelados(arbol, forzar):
    for nombre in shims.CONGELADOS:
        with pytest.raises(ValueError):
            shims.generar(nombre, destino=DESTINO, salida=arbol, src=arbol / "src", forzar=forzar)
        assert not (arbol / f"{nombre}.py").exists()


def test_no_sobrescribe_no_shim(arbol):
    (arbol / "falso.py").write_text("X = 1\n", encoding="utf-8")
    with pytest.raises(FileExistsError):
        _generar(arbol)
    assert (arbol / "falso.py").read_text(encoding="utf-8") == "X = 1\n"


def test_destino_inexistente(arbol):
    with pytest.raises(FileNotFoundError):
        shims.generar("nada", destino="ie123kit.nucleo.nada", salida=arbol, src=arbol / "src")


def test_fuera_de_mapa(arbol):
    with pytest.raises(ValueError):
        shims.generar("desconocido_xyz", salida=arbol, src=arbol / "src", cli="ninguno")


def test_destino_invalido():
    with pytest.raises(ValueError):
        shims.renderizar("os.path", None)


def test_simular_no_escribe(arbol):
    ruta = shims.generar("falso", destino=DESTINO, salida=arbol, src=arbol / "src", cli="ninguno", simular=True)
    assert not ruta.exists()


def test_retirado_no_se_regenera(arbol):
    """F2.7: un shim retirado no vuelve a tools/; el error dice qué importar."""
    with pytest.raises(ValueError, match="ie123kit.nucleo.compresion.lz10"):
        shims.generar("lz10", salida=arbol, src=arbol / "src", cli="ninguno", simular=True)


def test_bloque_main_sin_main(tmp_path):
    f = tmp_path / "m.py"
    f.write_text("if __name__ == '__main__':\n    print(1)\n", encoding="utf-8")
    with pytest.raises(ValueError):
        shims.detectar_cli(f)
    f.write_text("def main():\n    pass\n\n\nif __name__ == '__main__':\n    main()\n", encoding="utf-8")
    assert shims.detectar_cli(f) == "llamar"
