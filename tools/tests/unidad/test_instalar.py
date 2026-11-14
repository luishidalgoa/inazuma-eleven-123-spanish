"""Instalación de una candidata en el LayeredFS de Azahar (raíz de mods falsa en tmp_path)."""
import json

import pytest

from ie123kit.nucleo.construir import instalar
from ie123kit.nucleo.errores import ValidacionError


def _candidata(tmp_path):
    c = tmp_path / "probe_ie1_v70"
    (c / "romfs" / "cro").mkdir(parents=True)
    (c / "archive.fa").write_bytes(b"archive sintetico")
    (c / "romfs" / "cro" / "ina_main1.cro").write_bytes(b"cro 1")
    (c / "romfs" / "cro" / "ina_menu.cro").write_bytes(b"cro menu")
    return c


def test_instala_y_rehashea(tmp_path, monkeypatch):
    monkeypatch.setattr(instalar, "_azahar_en_ejecucion", lambda: False)
    candidata = _candidata(tmp_path)
    mods = tmp_path / "mods"
    informe = instalar.azahar(candidata, raiz_mods=mods, comprobar_sincronia_usearch=False)
    romfs = mods / instalar.TITLE_ID / "romfs"
    assert (romfs / "archive.fa").read_bytes() == b"archive sintetico"
    assert (romfs / "cro" / "ina_menu.cro").read_bytes() == b"cro menu"
    rels = {f["rel"] for f in informe["ficheros"]}
    assert rels == {"archive.fa", "romfs/cro/ina_main1.cro", "romfs/cro/ina_menu.cro"}
    assert informe["runtime_verified"] is False
    guardado = json.loads((candidata / "installation.json").read_text(encoding="utf-8"))
    assert guardado == informe


def test_rehash_manipulado_lanza(tmp_path, monkeypatch):
    monkeypatch.setattr(instalar, "_azahar_en_ejecucion", lambda: False)
    candidata = _candidata(tmp_path)
    original = instalar.shutil.copyfile

    def copia_sucia(src, dst):
        original(src, dst)
        with open(dst, "ab") as fh:
            fh.write(b"basura")

    monkeypatch.setattr(instalar.shutil, "copyfile", copia_sucia)
    with pytest.raises(ValidacionError) as err:
        instalar.azahar(candidata, raiz_mods=tmp_path / "mods", comprobar_sincronia_usearch=False)
    assert err.value.codigo == "HASH_TRAS_COPIA"


def test_se_niega_con_azahar_abierto(tmp_path, monkeypatch):
    monkeypatch.setattr(instalar, "_azahar_en_ejecucion", lambda: True)
    candidata = _candidata(tmp_path)
    with pytest.raises(ValidacionError) as err:
        instalar.azahar(candidata, raiz_mods=tmp_path / "mods", comprobar_sincronia_usearch=False)
    assert err.value.codigo == "AZAHAR_EN_EJECUCION"
    assert not (tmp_path / "mods").exists()
    # Con rehusar_si_ejecuta=False sí instala (para automatizaciones que ya han cerrado el emulador).
    informe = instalar.azahar(candidata, raiz_mods=tmp_path / "mods", rehusar_si_ejecuta=False,
                               comprobar_sincronia_usearch=False)
    assert informe["ficheros"]


def test_limpiar_obsoletos(tmp_path, monkeypatch):
    monkeypatch.setattr(instalar, "_azahar_en_ejecucion", lambda: False)
    candidata = _candidata(tmp_path)
    mods = tmp_path / "mods"
    viejo = mods / instalar.TITLE_ID / "romfs" / "cro" / "ina_main3ogre.cro"
    viejo.parent.mkdir(parents=True)
    viejo.write_bytes(b"de una candidata anterior")
    instalar.azahar(candidata, raiz_mods=mods, limpiar_obsoletos=True, comprobar_sincronia_usearch=False)
    assert not viejo.exists()


def test_raiz_mods_por_defecto(tmp_path):
    raiz = instalar.raiz_mods_por_defecto({"APPDATA": str(tmp_path)})
    assert raiz == tmp_path / "Azahar" / "load" / "mods"
