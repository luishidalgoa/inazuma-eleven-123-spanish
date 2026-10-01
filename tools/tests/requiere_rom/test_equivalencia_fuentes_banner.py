"""Equivalencia de los motores de fuentes, menús y banner portados en la F2.5 (#51) con sus capas.

Cada motor del paquete se ejecuta sobre las mismas entradas que su capa de ``work/`` y se exige la
salida de la capa byte a byte. Antes se comprueba cada entrada y salida contra su hash golden
(``tests/compat/golden/fuentes_banner_f25.json``: solo hashes, Norma 2) para detectar que work/ cambió.

- Bigramas IE1 v89 (``ie1/capas/fuentes/bigramas_ritmo``): desde la FONT12 de la v88, el ritmo y el
  dibujo del paquete dan la FONT12 de la capa; la partición DP de cada tramo de las descripciones y
  objetivos cambiados es la del informe de la capa; el escáner de literales da las apariciones de la
  capa en las fuentes que siguen existiendo (base japonesa).
- Menús IE2 v23 (``ie2/shared/capas/menus_cro/menus``): desde las salidas de la v22, el reparto del
  paquete da la misma CRO, FONT12, FONT8 y registro.
- Banner HOME (``shared/capas/graficos/banner_home``): icon.bin, CGFX, BCWAV y banner.bnr iguales.

Ninguna fuente del proyecto cambia: todo se hace en memoria. Nunca escribe en work/.
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

BIGRAMAS = "work/ie1/capas/fuentes/bigramas_ritmo"
V88 = "work/ie1/capas/historial/fuentes/v88_bigramas_total"
MENUS = "work/ie2/shared/capas/menus_cro/menus"
BANNER = "work/shared/capas/graficos/banner_home"
EXEFS = "work/shared/base_3ds/exefs"


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


@pytest.fixture(scope="module")
def raiz() -> Path:
    r = find_root()
    for rel in (BIGRAMAS, V88, MENUS, BANNER, EXEFS):
        if not (r / rel).exists():
            pytest.skip(f"falta recurso local: {rel}")
    return r


@pytest.fixture(scope="module")
def leer(raiz):
    golden = json.loads((raiz / "tools/tests/compat/golden/fuentes_banner_f25.json")
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


# --------------------------------------------------------------------------- bigramas IE1 v89


@pytest.fixture(scope="module")
def v89(leer):
    from ie123kit.nucleo.fuentes import celdas, ritmo

    base = leer("ie1/capas/historial/fuentes/v88_bigramas_total/extra/font/FONT12.bcfnt")
    fuente = celdas.FuenteBCFNT.desde_bytes(base, "FONT12.bcfnt")
    registro = json.loads(leer("ie1/capas/fuentes/bigramas_ritmo/registro.json"))
    informe = json.loads(leer("ie1/capas/fuentes/bigramas_ritmo/informe.json"))
    return fuente, ritmo.Maqueta(fuente, celdas.codepoint), registro, informe


def test_bigramas_v89_dibujo_identico(v89, leer) -> None:
    from ie123kit.nucleo.fuentes import bigramas

    fuente, mq, registro, _ = v89
    reg = bigramas.Registro.desde_documento(registro)
    assert len(reg.entradas) == 847
    anotado = bigramas.dibujar_trozos(fuente, registro["bigramas"], mq)
    for e, a in zip(registro["bigramas"], anotado):
        assert (a["cwdh"], a["pixeles_sha1"]) == (e["cwdh"], e["pixeles_sha1"]), e["sjis"]
    esperado = leer("ie1/capas/fuentes/bigramas_ritmo/extra/font/FONT12.bcfnt")
    assert _sha(fuente.data()) == _sha(esperado) == registro["fuentes_dibujadas"]["font/FONT12.bcfnt"]


def test_bigramas_v89_particion_identica(v89) -> None:
    from ie123kit.nucleo.fuentes import bigramas, ritmo

    _, mq, registro, informe = v89
    claves = {bigramas.clave_de(e) for e in registro["bigramas"]}
    n = 0
    for tipo in ("descripcion", "objetivo"):
        for cambio in informe[tipo]:
            tramo: list[str] = []
            for c in cambio["celdas"].split("|") + ["¤"]:
                if c != "¤":
                    tramo.append(c)
                    continue
                if tramo:
                    coste, casillas = ritmo.particion("".join(tramo), mq, claves.__contains__)
                    assert coste < ritmo.INF
                    assert [ritmo.texto(k) for k in casillas] == tramo
                    n += 1
                tramo = []
    assert n == 2384


def test_escaner_de_literales_igual_en_la_base(raiz, leer) -> None:
    from ie123kit.nucleo.compresion import blz
    from ie123kit.nucleo.texto import escaneo

    literales = json.loads(leer("ie1/capas/fuentes/bigramas_ritmo/literales.json"))
    base = raiz / "work/shared/base_3ds"
    fuentes = {"base_3ds/cro/" + f.name: f.read_bytes() for f in sorted((base / "romfs/cro").glob("*.cr?"))}
    fuentes["code.bin"] = blz.decompress((base / "exefs/code.bin").read_bytes())
    res = escaneo.apariciones(fuentes, list(literales))
    esperado = {c: {k: n for k, n in v.items() if k in fuentes} for c, v in literales.items()}
    assert res == esperado


# --------------------------------------------------------------------------- menús IE2 v23


def test_menus_ie2_v23_identicos(raiz, leer) -> None:
    from ie123kit.ie2.comun import menus
    from ie123kit.nucleo.fuentes import celdas

    capa = _modulo("apply_v23_menus_test", raiz / MENUS / "apply.py")   # solo por sus constantes
    v22 = "ie2/shared/capas/rotulos_objetivos/menus_objetivos"
    fuentes = {f: celdas.FuenteBCFNT.desde_bytes(leer(f"{v22}/extra/{f}"), Path(f).name)
               for f in (menus.F12, menus.F8)}
    reg22 = json.loads(leer(f"{v22}/registro.json"))
    # Decisión del usuario en la capa: la entrada de guardar va con la palabra entera (sin texto del
    # juego en git: la clave se toma de los bloques de la capa).
    guardar = next(jp for jp, alts in capa.BLOQUES["menu_campo"][4] if "Guardar" in alts)
    res = menus.repartir(fuentes, leer(f"{v22}/romfs/cro/ina_main2.cro"), reg22["bigramas"], capa.BLOQUES,
                         capa.RECUPERAR, celdas.codepoint,
                         forzados={"menu_campo": {guardar: ["Guardar"]}},
                         espejo=(capa.ESPEJO, capa.ESPEJO_FIN, capa.ESPEJO_GUAR))
    salida = "ie2/shared/capas/menus_cro/menus"
    assert _sha(res["cro"]) == _sha(leer(f"{salida}/romfs/cro/ina_main2.cro"))
    for f, fu in fuentes.items():
        assert _sha(fu.data()) == _sha(leer(f"{salida}/extra/{f}")), f
    reg23 = json.loads(leer(f"{salida}/registro.json"))
    assert res["registro"] == reg23["bigramas"]
    assert res["libres"] == reg23["libres_ie2_v23"] == []


# --------------------------------------------------------------------------- banner HOME


def test_icono_smdh_identico(leer) -> None:
    from ie123kit.juego_principal import banner
    from ie123kit.nucleo.ejecutable import smdh

    icono = banner.construir_icono(leer("shared/base_3ds/exefs/icon.icn"))
    assert icono == leer("shared/capas/graficos/banner_home/salida/icon.bin")
    assert smdh.leer_titulos(icono, 5) == banner.TITULO


def test_banner_cgfx_y_cbmd_identicos(raiz, leer) -> None:
    import io

    from PIL import Image

    from ie123kit.juego_principal import banner
    from ie123kit.nucleo.compresion import lz11
    from ie123kit.nucleo.contenedores import cbmd

    logo = Image.open(io.BytesIO(leer("shared/capas/graficos/banner_home/extra/COMMON1_es.png")))
    cwav = leer("shared/capas/graficos/banner_home/extra/banner_es.bcwav")
    bnr, cgfx, _ = banner.construir_banner(leer("shared/base_3ds/exefs/banner.bnr"), logo)
    assert cgfx == leer("shared/capas/graficos/banner_home/extra/banner_es.cgfx")
    # Con el BCWAV de la capa, el contenedor sale igual que el banner.bnr de la capa.
    assert cbmd.construir(lz11.compress(cgfx), cwav) == leer("shared/capas/graficos/banner_home/salida/banner.bnr")
    assert cbmd.partes(bnr)[0].startswith(lz11.compress(cgfx))  # más el relleno hasta 0x20


def test_banner_bcwav_identico(raiz, leer) -> None:
    from ie123kit.nucleo.contenedores import cbmd
    from ie123kit.nucleo.media import bcwav

    if shutil.which("ffmpeg") is None:
        pytest.skip("falta ffmpeg (prepara el PCM de la capa)")
    carpeta = raiz / BANNER
    sys.path.insert(0, str(carpeta))
    try:
        audio = _modulo("banner_home_audio_test", carpeta / "audio.py")   # preparación del PCM de la capa
        pcm, _info = audio.grito()
    finally:
        sys.path.remove(str(carpeta))
    plantilla = cbmd.partes(leer("shared/base_3ds/exefs/banner.bnr"))[1]
    cwav = bcwav.codificar(plantilla, pcm)
    assert cwav == leer("shared/capas/graficos/banner_home/extra/banner_es.bcwav")
    assert bcwav.formato(cwav) == {"codificacion": 2, "bucle": 0, "rate": 48000, "muestras": 199246, "canales": 2}
