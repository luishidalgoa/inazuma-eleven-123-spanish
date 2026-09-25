"""Los módulos de las capas de media de IE2 son envoltorios finos de ``ie123kit`` (F2.6, #55).

Por cada módulo desduplicado se comprueba:

(a) que sigue exponiendo toda su superficie pública anterior (nombres que usan sus hermanos
    ``apply.py``/``validate.py`` y las capas de ``media/voces``);
(b) que delega en el paquete: identidad de objeto donde el envoltorio reexporta la función tal cual,
    y el mismo resultado que el paquete (y que la salida ya escrita en la capa) donde adapta la firma.

Nunca escribe en ``work/``. Requiere ``work/`` local; en CI se deselecciona con ``-m "not requiere_rom"``.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

from ie123kit.nucleo.config.raiz import find_root

pytestmark = pytest.mark.requiere_rom

CAPAS = "work/ie2/shared/capas"
JP_SONIDO = "work/shared/base_3ds/romfs/inazuma2/data_iz/sound"
NDS = "work/ie2/tormenta_de_fuego/fuentes/nds_es/data_iz"

MEDIA = "media/media"
SUBTITULOS = "media/subtitulos"
VOZ = "media/voz_titulo"


@pytest.fixture(scope="module")
def raiz() -> Path:
    r = find_root()
    for rel in (CAPAS, JP_SONIDO, NDS):
        if not (r / rel).exists():
            pytest.skip(f"falta recurso local: {rel}")
    return r


def _modulo(nombre: str, ruta: Path, extra: list[Path] = ()):
    """Carga un módulo de capa por ruta, con sus carpetas hermanas en sys.path."""
    añadidas = [str(p) for p in extra if str(p) not in sys.path]
    sys.path[:0] = añadidas
    try:
        spec = importlib.util.spec_from_file_location(nombre, ruta)
        m = importlib.util.module_from_spec(spec)
        sys.modules[nombre] = m
        spec.loader.exec_module(m)
        return m
    finally:
        for p in añadidas:
            sys.path.remove(p)


def _superficie(modulo, nombres: list[str]) -> None:
    faltan = [n for n in nombres if not hasattr(modulo, n)]
    assert not faltan, f"{modulo.__name__}: superficie pública perdida: {faltan}"


# ------------------------------------------------------------------ media/subtitulos/comun_sub.py

SUPERFICIE_SUB = [
    "ROOT",
    "SALIDA",
    "SALIDA_FUEGO",
    "RUTA_VIDEOS",
    "C",
    "V",
    "FUENTE",
    "FUENTE_INDICE",
    "TAM",
    "Y0",
    "ALTO",
    "BASE_Y",
    "BLANCO",
    "ANCHO_MAX",
    "CENTRO",
    "destino",
    "dir_tiras",
    "fuente",
    "texto_nds",
    "ancho",
    "partir",
    "pistas",
    "tick",
    "por_fotograma",
    "alfa",
    "a_columnas",
    "quemar",
]


@pytest.fixture(scope="module")
def comun_sub(raiz):
    capa = raiz / CAPAS / SUBTITULOS
    return _modulo("comun_sub_envoltorio", capa / "comun_sub.py", [raiz / CAPAS / MEDIA])


def test_comun_sub_superficie_y_delegacion(comun_sub):
    from ie123kit.ie2.comun import subtitulos as IS
    from ie123kit.nucleo.media import subtitulos as S

    _superficie(comun_sub, SUPERFICIE_SUB)
    # (b) las medidas son las del estilo del paquete y el giro de la banda es la misma función
    assert comun_sub.ESTILO is IS.ESTILO_IE2
    assert comun_sub.a_columnas is S.a_columnas
    est = IS.ESTILO_IE2
    assert (
        comun_sub.TAM,
        comun_sub.Y0,
        comun_sub.ALTO,
        comun_sub.BASE_Y,
        comun_sub.BLANCO,
        comun_sub.ANCHO_MAX,
        comun_sub.CENTRO,
        comun_sub.FUENTE,
        comun_sub.FUENTE_INDICE,
    ) == (est.tam, est.y0, est.alto, est.base_y, est.blanco, est.ancho_max, est.centro, est.fuente, est.indice_fuente)
    assert [comun_sub.tick(k) for k in (0, 1, 24, 1000)] == [S.tick(k, IS.FPS, IS.HZ) for k in (0, 1, 24, 1000)]


def test_comun_sub_pistas_y_fotogramas_como_la_capa(raiz, comun_sub):
    """``pistas``/``por_fotograma``/``ancho`` dan lo mismo que el informe ya escrito en la capa."""
    from ie123kit.ie2.comun import subtitulos as IS
    from ie123kit.nucleo.media import subtitulos as S

    if not IS.estilo().fuente.is_file():
        pytest.skip(f"falta la fuente {IS.estilo().fuente}")
    informe = json.loads((raiz / CAPAS / SUBTITULOS / "informe.json").read_text(encoding="utf-8"))
    for v in informe["videos"][::7]:
        n = v["nombre"]
        pistas = comun_sub.pistas(n)
        assert pistas == v["subtitulos"], n
        assert pistas == IS.pistas((raiz / NDS / f"movie/txt/sp/{n}.dat").read_bytes(), comun_sub.ESTILO)
        idx = comun_sub.por_fotograma(pistas, v["fotogramas"])
        assert int((idx >= 0).sum()) == v["fotogramas_con_texto"], n
        for s in pistas:
            assert comun_sub.ancho(s["texto"]) == S.ancho_texto(s["texto"], comun_sub.ESTILO)
            assert comun_sub.ancho(s["texto"]) <= comun_sub.ANCHO_MAX


def test_comun_sub_dibujo_delegado(comun_sub):
    """``alfa``/``quemar`` pintan exactamente lo que pinta el paquete con el estilo de IE2."""
    np = pytest.importorskip("numpy")
    from ie123kit.ie2.comun import subtitulos as IS
    from ie123kit.nucleo.media import subtitulos as S

    if not IS.estilo().fuente.is_file():
        pytest.skip(f"falta la fuente {IS.estilo().fuente}")
    subs = [
        {"registro_nds": 0, "inicio": 0, "fin": 10, "texto": "¡Vamos, Raimon!"},
        {"registro_nds": 1, "inicio": 10, "fin": 20, "texto": "Esto es una prueba de dibujo."},
    ]
    assert (comun_sub.alfa(subs[0]["texto"]) == S.alfa(subs[0]["texto"], comun_sub.ESTILO)).all()
    idx = comun_sub.por_fotograma(subs, 30)
    assert (idx == S.por_fotograma(subs, 30, IS.FPS, IS.HZ)).all()
    rng = np.random.default_rng(7)
    y_capa = rng.integers(0, 255, (30, 320, 40), dtype=np.uint8)
    y_pkg = y_capa.copy()
    comun_sub.quemar(y_capa, subs, idx)
    S.quemar(y_pkg, subs, idx, comun_sub.ESTILO)
    assert (y_capa == y_pkg).all()


# ------------------------------------------------------------------ media/voz_titulo/dsp_adpcm.py


@pytest.fixture(scope="module")
def dsp(raiz):
    return _modulo("dsp_adpcm_envoltorio", raiz / CAPAS / VOZ / "dsp_adpcm.py")


def test_dsp_adpcm_superficie_y_delegacion(dsp):
    from ie123kit.nucleo.media import dsp_adpcm as DA

    _superficie(dsp, ["DBL_EPS", "coeficientes", "codificar", "decodificar"])
    assert dsp.codificar is DA.codificar
    assert dsp.decodificar is DA.decodificar
    assert dsp.coeficientes is DA.coeficientes
    assert dsp.DBL_EPS == DA.DBL_EPS
    pcm = [int(3000 * (k % 37 - 18) / 18) for k in range(280)]
    datos, coefs, ps = dsp.codificar(pcm)
    assert (datos, coefs, ps) == DA.codificar(pcm)
    assert dsp.decodificar(datos, coefs, len(pcm)) == DA.decodificar(datos, coefs, len(pcm))


# ------------------------------------------------------------------ media/voz_titulo/sonido.py

SUPERFICIE_SONIDO = [
    "TABLA_SEQ",
    "leer_3ds",
    "leer_nds",
    "chunks_3ds",
    "fila_chunk",
    "muestras_3ds",
    "chunks_nds",
    "muestras_nds",
    "prgi_teclas",
    "ima_nds",
    "secuencias",
    "montar_sed",
    "notas",
]


@pytest.fixture(scope="module")
def sonido(raiz):
    return _modulo("sonido_envoltorio", raiz / CAPAS / VOZ / "sonido.py")


@pytest.fixture(scope="module")
def bancos_rom(raiz):
    from ie123kit.nucleo.contenedores import sound_pb as SP

    jp_dir, es_dir = raiz / JP_SONIDO, raiz / NDS / "sound/sp"
    ph = (jp_dir / "sound.ph").read_bytes()
    jp = SP.leer_3ds(ph, (jp_dir / "sound.pb").read_bytes())
    es = SP.leer_nds((es_dir / "sound.pkh").read_bytes(), (es_dir / "sound.pkb").read_bytes())
    return ph, jp, es


def test_sonido_superficie_y_delegacion(sonido, bancos_rom, raiz):
    from ie123kit.nucleo.media import procyon as PR

    ph, jp, es = bancos_rom
    _superficie(sonido, SUPERFICIE_SONIDO)
    for nombre in ("chunks_3ds", "fila_chunk", "muestras_3ds", "ima_nds", "secuencias", "montar_sed", "notas"):
        assert getattr(sonido, nombre) is getattr(PR, nombre), nombre
    assert sonido.TABLA_SEQ == PR.TABLA_SEQ
    assert sonido.ALINEAR == 1, "la v13 lee el SWD de DS sin alinear: cambiarlo cambiaría la salida"
    # leer_3ds / leer_nds: misma lectura que el paquete, con la carpeta en vez de los bytes
    assert sonido.leer_3ds(raiz / JP_SONIDO) == (ph, jp)
    assert sonido.leer_nds(raiz / NDS / "sound/sp") == es
    # lectores de DS: el paquete con alinear=1 (la v13)
    swd_es = es["3D_901.SWD"]
    assert sonido.chunks_nds(swd_es) == PR.chunks_nds(swd_es, 1)
    assert sonido.muestras_nds(swd_es) == PR.muestras_nds(swd_es, 1)
    assert sonido.prgi_teclas(swd_es, nds=True) == PR.prgi_teclas(swd_es, True, 1)
    swd_jp = dict(jp)["3D_901.SWD"]
    assert sonido.prgi_teclas(swd_jp) == PR.prgi_teclas(swd_jp)
    assert (
        sonido.ima_nds(sonido.muestras_nds(swd_es)[1][0]["data"])[:64]
        == PR.ima_nds(PR.muestras_nds(swd_es, 1)[1][0]["data"])[:64]
    )


def test_sonido_swd_de_la_capa_sigue_saliendo_igual(raiz, sonido, bancos_rom):
    """El SWD ya escrito en ``media/voz_titulo/par`` se relee con el envoltorio sin cambios."""
    from ie123kit.nucleo.media import procyon as PR

    par = raiz / CAPAS / VOZ / "par/3D_901.SWD"
    if not par.is_file():
        pytest.skip("falta media/voz_titulo/par/3D_901.SWD")
    swd = par.read_bytes()
    ch, ents = sonido.muestras_3ds(swd)
    assert (ch, ents) == PR.muestras_3ds(swd)
    assert PR.swd_con_cwavs(swd, {e["id"]: e["cwav"] for e in ents}) == swd
    sed = sonido.leer_nds(raiz / NDS / "sound/sp")["3D_901.SED"]
    seqs = sonido.secuencias(sed)
    assert sonido.montar_sed(sed, seqs, [s["eventos"] for s in seqs]) == PR.montar_sed(
        sed, seqs, [s["eventos"] for s in seqs]
    )
    assert [sonido.notas(s["eventos"]) for s in seqs] == [PR.notas(s["eventos"]) for s in seqs]


# ------------------------------------------------------------------ media/media/bancos.py


@pytest.fixture(scope="module")
def bancos(raiz):
    capa = raiz / CAPAS / MEDIA
    return _modulo("bancos_envoltorio", capa / "bancos.py", [capa])


def test_bancos_superficie_y_delegacion(bancos, bancos_rom):
    from ie123kit.nucleo.contenedores import sound_pb as SP

    ph, jp, es = bancos_rom
    _superficie(bancos, ["leer_3ds", "leer_nds", "version", "inventario", "probar", "main"])
    assert bancos.leer_3ds() == (ph, jp)
    assert bancos.leer_nds() == es
    # el montaje del paquete reproduce el índice y el contenedor japoneses sin cambios (probar sin cambios)
    pb_jp = (bancos.C.SONIDO_JP / "sound.pb").read_bytes()
    pb, idx = SP.montar_3ds(jp)
    assert (pb, idx) == (pb_jp, ph)
    # y con un par sustituido cambia solo ese par (lo que hace `probar`)
    nombre = "3D_003_01.SWD"
    if nombre in es and nombre in dict(jp):
        pb2, idx2 = SP.montar_3ds(jp, {nombre: es[nombre]})
        assert dict(SP.leer_3ds(idx2, pb2))[nombre] == es[nombre]
        assert len(idx2) == len(ph)
