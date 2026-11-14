import os
import time

from ie123kit.nucleo.construir import limpieza as lz


def _viejo(p, horas=5):
    t = time.time() - horas * 3600
    for f in [p, *(p.rglob('*') if p.is_dir() else [])]:
        os.utime(f, (t, t), follow_symlinks=False)
    return p


def _raiz(tmp_path):
    (tmp_path / "work").mkdir(parents=True)
    (tmp_path / "tools" / "src").mkdir(parents=True)
    return tmp_path


def _rutas(r, raiz):
    return {p.relative_to(raiz).as_posix(): m for p, m in r}


def test_cache_vieja_se_borra_y_reciente_no(tmp_path):
    raiz = _raiz(tmp_path)
    vieja = raiz / "work/a/__pycache__"
    vieja.mkdir(parents=True)
    (vieja / "x.pyc").write_bytes(b"1")
    _viejo(vieja)
    (raiz / "work/b").mkdir()
    reciente = raiz / "work/b/__pycache__"
    reciente.mkdir()
    (reciente / "y.pyc").write_bytes(b"1")
    r = _rutas(lz.objetivos_auto(raiz), raiz)
    assert "work/a/__pycache__" in r
    assert "work/b/__pycache__" not in r


def test_temporales_y_egg_info(tmp_path):
    raiz = _raiz(tmp_path)
    t = raiz / "work/c.partial"
    t.write_bytes(b"1")
    _viejo(t)
    (raiz / "work/d.partial").write_bytes(b"1")  # reciente: una construcción en curso
    egg = raiz / "tools/src/ie123kit.egg-info"
    egg.mkdir()
    _viejo(egg)
    r = _rutas(lz.objetivos_auto(raiz), raiz)
    assert set(r) == {"work/c.partial", "tools/src/ie123kit.egg-info"}


def test_copias_previas_conserva_la_mas_reciente_de_cada_familia(tmp_path):
    raiz = _raiz(tmp_path)
    d = raiz / "work/shared/backups_instalado"
    d.mkdir(parents=True)
    horas = {"archive.fa.antes_a": 30, "archive.fa.antes_b": 20, "archive.fa.antes_c": 10,
             "ina_main1.cro.antes_x": 25, "otro.txt": 40}
    for n, h in horas.items():
        f = d / n
        f.write_bytes(b"1")
        _viejo(f, h)
    r = _rutas(lz.objetivos_auto(raiz), raiz)
    assert set(r) == {"work/shared/backups_instalado/archive.fa.antes_a",
                      "work/shared/backups_instalado/archive.fa.antes_b"}


def test_nunca_toca_enlaces_ni_rutas_fuera_de_la_raiz(tmp_path):
    raiz = _raiz(tmp_path / "proy")
    fuera = tmp_path / "fuera"
    fuera.mkdir()
    (fuera / "dato.bin").write_bytes(b"1")
    enlace = raiz / "work/__pycache__"
    enlace.symlink_to(fuera, target_is_directory=True)
    assert lz.objetivos_auto(raiz) == []
    assert not lz._seguro(fuera, raiz)
    assert not lz._seguro(raiz, raiz)
    assert (fuera / "dato.bin").exists()


def test_informe_no_cuenta_originales_ni_copias_previas(tmp_path):
    raiz = _raiz(tmp_path)
    for rel in ("work/ie1/fuentes/a.fa", "work/shared/backups_instalado/b.fa", "work/shared/candidatas/c/archive.fa"):
        f = raiz / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(b"1" * 10)
    r = lz.informe_espacio(raiz, umbral=5)
    assert [p.name for p, _ in r] == ["archive.fa"]
