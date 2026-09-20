"""Equivalencia del motor del grito del título del recopilatorio (F2.6) con su capa de ``work/``.

El motor del paquete (``juego_principal.voz_titulo``) se ejecuta sobre las mismas entradas que
``work/shared/capas/media/voz_titulo_recopilatorio`` y se exige su salida byte a byte. Antes se
comprueba cada entrada y salida contra su hash golden (``tests/compat/golden/voz_recopilatorio.json``:
solo hashes, Norma 2) para detectar que work/ cambió.

También cierra la parte que faltaba del banner HOME (TAREA B): la preparación del PCM del grito, que
hasta ahora solo vivía en ``work/shared/capas/graficos/banner_home/audio.py``, sale idéntica con
``juego_principal.banner.preparar_grito``.

Nada se escribe en work/: todo se hace en memoria. Requiere work/ local y ffmpeg; en CI se
deselecciona con ``-m "not requiere_rom"``.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import sys
from pathlib import Path

import pytest

from ie123kit.nucleo.config.raiz import find_root

pytestmark = pytest.mark.requiere_rom

CAPA = "shared/capas/media/voz_titulo_recopilatorio"
BASE = "shared/base_3ds/romfs/sound"
BANNER = "shared/capas/graficos/banner_home"
MP3 = f"{CAPA}/fuentes/Banner title complto.mp3"


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


@pytest.fixture(scope="module")
def raiz() -> Path:
    r = find_root()
    for rel in (CAPA, BASE, f"{CAPA}/romfs_mod/sound/CM_000.SWD", MP3):
        if not (r / "work" / rel).exists():
            pytest.skip(f"falta recurso local: work/{rel}")
    return r


@pytest.fixture(scope="module")
def leer(raiz):
    golden = json.loads((raiz / "tools/tests/compat/golden/voz_recopilatorio.json")
                        .read_text(encoding="utf-8"))["ficheros"]

    def _leer(rel: str) -> bytes:
        datos = (raiz / "work" / rel).read_bytes()
        assert _sha(datos) == golden[rel], f"{rel}: work/ ha cambiado respecto al golden"
        return datos

    return _leer


def _modulo(nombre: str, ruta: Path):
    spec = importlib.util.spec_from_file_location(nombre, ruta)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture(scope="module")
def grabacion(raiz, leer):
    """PCM mono flotante de la grabación del usuario, leído como lo lee la capa (ffmpeg)."""
    pytest.importorskip("scipy")
    if shutil.which("ffmpeg") is None:
        pytest.skip("falta ffmpeg (lee el MP3 de la capa)")
    import numpy as np

    from ie123kit.juego_principal import voz_titulo as VT

    leer(MP3)   # el golden cubre la fuente
    import subprocess

    crudo = subprocess.run(["ffmpeg", "-v", "error", "-i", str(raiz / "work" / MP3), "-ac", "1",
                            "-ar", str(VT.SR_FUENTE), "-f", "f32le", "-"],
                           capture_output=True, check=True).stdout
    return np.frombuffer(crudo, "<f4").astype(np.float64)


def test_voz_recopilatorio_swd_y_sed_identicos(leer, grabacion) -> None:
    """El motor reproduce byte a byte el CM_000.SWD y el CM_000.SED vigentes de la capa."""
    from ie123kit.juego_principal import voz_titulo as VT

    swd, sed, informe = VT.construir(leer(f"{BASE}/CM_000.SWD"), leer(f"{BASE}/CM_000.SED"), grabacion)
    assert swd == leer(f"{CAPA}/romfs_mod/sound/CM_000.SWD")
    assert sed == leer(f"{CAPA}/romfs_mod/sound/CM_000.SED")
    assert informe["ticks"] == 548 and informe["muestras"] == 175624
    # el SED no cambia de tamaño y el SWD crece solo lo que crece la muestra 162
    assert informe["tamanos"]["sed"] == len(sed) == len(leer(f"{BASE}/CM_000.SED"))
    assert informe["tamanos"]["swd"] == len(swd) > informe["tamanos"]["swd_jp"]


def test_voz_recopilatorio_coincide_con_el_informe_de_la_capa(raiz, leer, grabacion) -> None:
    """Ticks, muestras, frases, huecos y ganancia son los del informe.json de la capa."""
    from ie123kit.juego_principal import voz_titulo as VT

    capa = json.loads((raiz / "work" / CAPA / "informe.json").read_text(encoding="utf-8"))
    _swd, _sed, informe = VT.construir(leer(f"{BASE}/CM_000.SWD"), leer(f"{BASE}/CM_000.SED"), grabacion)
    assert informe["frases_s"] == capa["frases_s"]
    assert informe["huecos"] == capa["huecos"]
    assert informe["ganancia_db"] == capa["tratamiento"]["ganancia_db"]
    assert informe["pico_jp"] == capa["tratamiento"]["pico_jp"]
    assert informe["ticks"] == capa["despues"]["ticks"]
    assert informe["muestras"] == capa["despues"]["muestras"]
    assert informe["duracion_s"] == capa["despues"]["duracion_s"]
    assert informe["antes"] == capa["antes"]
    assert informe["tamanos"] == capa["tamanos"]


def test_capa_es_un_envoltorio_del_paquete(raiz) -> None:
    """La capa ya no tiene motor propio: importa ie123kit y no duplica el montaje del SWD/SED."""
    fuente = (raiz / "work" / CAPA / "apply.py").read_text(encoding="utf-8")
    assert "ie123kit" in fuente
    for duplicado in ("def swd_nuevo", "def nota_nueva", "def montar(", "resample_poly"):
        assert duplicado not in fuente, duplicado


def test_grito_del_banner_igual_que_la_capa(raiz) -> None:
    """TAREA B: la preparación del PCM del banner HOME sale idéntica desde el paquete."""
    pytest.importorskip("scipy")
    np = pytest.importorskip("numpy")
    carpeta = raiz / "work" / BANNER
    if not carpeta.exists():
        pytest.skip(f"falta recurso local: work/{BANNER}")
    if shutil.which("ffmpeg") is None:
        pytest.skip("falta ffmpeg (prepara el PCM de la capa)")
    from ie123kit.juego_principal import banner

    sys.path.insert(0, str(carpeta))
    try:
        audio = _modulo("banner_home_audio_voz", carpeta / "audio.py")
        pcm_capa, info_capa = audio.grito()
        x, rate = audio.fuente()
    finally:
        sys.path.remove(str(carpeta))
    pcm, info = banner.preparar_grito(x, rate)
    assert np.array_equal(np.asarray(pcm_capa), np.asarray(pcm))
    assert info == {k: v for k, v in info_capa.items() if k != "fuente"}
