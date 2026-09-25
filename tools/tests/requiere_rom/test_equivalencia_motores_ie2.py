"""Equivalencia de los motores portados en la F2.4 (#50) con las salidas vigentes de las capas de IE2.

Cada motor del paquete se ejecuta sobre las mismas entradas que su capa de ``work/`` y se exige la
salida de la capa byte a byte. Antes, cada salida de la capa se compara con su hash golden
(``tests/compat/golden/motores_ie2.json``: solo hashes, Norma 2) para detectar que work/ cambió.

Cuando la base de la capa ya no existe (``probe_ie2_v17``/``v18`` se borraron), la prueba usa la
base que la propia capa comprobaba como equivalente (la extracción japonesa) o la propiedad de
punto fijo (el reparto aplicado a la salida de la capa devuelve la misma salida).

Nunca escribe en work/. Requiere work/ local; en CI se deselecciona con ``-m "not requiere_rom"``.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

from ie123kit.nucleo.config.raiz import find_root

pytestmark = pytest.mark.requiere_rom

CAPAS = "work/ie2/shared/capas"
JP = "work/shared/base_3ds/romfs"
NDS = "work/ie2/tormenta_de_fuego/fuentes/nds_es/data_iz"


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


@pytest.fixture(scope="module")
def raiz() -> Path:
    r = find_root()
    for rel in (CAPAS, f"{JP}/archive.fa", NDS):
        if not (r / rel).exists():
            pytest.skip(f"falta recurso local: {rel}")
    return r


@pytest.fixture(scope="module")
def golden(raiz) -> dict:
    return json.loads((raiz / "tools/tests/compat/golden/motores_ie2.json").read_text(encoding="utf-8"))["capas"]


def _capa(raiz: Path, rel: str, golden: dict) -> bytes:
    """Bytes de una salida de capa, tras comprobar su hash golden."""
    datos = (raiz / CAPAS / rel).read_bytes()
    assert _sha(datos) == golden[rel], f"{rel}: work/ ha cambiado respecto al golden"
    return datos


def _modulo(nombre: str, ruta: Path):
    spec = importlib.util.spec_from_file_location(nombre, ruta)
    m = importlib.util.module_from_spec(spec)
    sys.modules[nombre] = m
    spec.loader.exec_module(m)
    return m


# ------------------------------------------------------------------ 1. paginado 37 × 3 / 131 B


def _dialogos(datos: bytes):
    from ie123kit.nucleo.eventos import ssd

    _end, ins, recs = ssd.parse(datos)
    return [r.body for r in recs if ins.get(r.instruction) == 0x301D and r.argument == 1]


def _conjunto(ficheros: list[Path]) -> str:
    h = hashlib.sha256()
    for f in ficheros:
        h.update(f.name.encode())
        h.update(bytes.fromhex(_sha(f.read_bytes())))
    return h.hexdigest()


@pytest.fixture(scope="module")
def glifos_font12(raiz):
    from ie123kit._legado.bcfnt import BCFNT
    from ie123kit.nucleo.contenedores.fa import FaArchive

    cm = {}
    for c in BCFNT(FaArchive(str(raiz / JP / "archive.fa")).read("font/FONT12.bcfnt")).cmaps():
        cm.update(c["entries"])
    return frozenset(cm)


def test_paginado_punto_fijo_sobre_toda_la_capa_saltos37(raiz, golden, glifos_font12):
    """Todo registro que la capa dejó rehecho sale idéntico al volver a repartirlo, y cabe en el modelo."""
    from ie123kit.ie2.comun import dialogo as D
    from ie123kit.nucleo.texto import paginado as P

    registros = rehechos = 0
    for pk in ("eve", "mch"):
        ficheros = sorted((raiz / CAPAS / f"dialogo/saltos37/ie2/{pk}").glob("*.ssd"))
        g = golden[f"dialogo/saltos37/ie2/{pk}"]
        assert (len(ficheros), _conjunto(ficheros)) == (g["ficheros"], g["sha256_conjunto"])
        for f in ficheros:
            for cuerpo in _dialogos(f.read_bytes()):
                registros += 1
                nuevo, _texto = D.reparte(cuerpo, glifos_font12)
                if nuevo is not None:
                    rehechos += 1
                    assert nuevo == cuerpo, f"{pk}/{f.name}: el reparto no es un punto fijo"
                    assert not P.problemas(cuerpo, D.MODELO_IE2)
    assert registros > 50_000 and rehechos > 40_000


def test_paginado_igual_que_comun19_en_una_muestra(raiz, glifos_font12):
    """El modelo portado da lo mismo que ``comun19``/``comun17`` (páginas, problemas, reajuste y reparto)."""
    from ie123kit.ie2.comun import dialogo as D
    from ie123kit.nucleo.texto import paginado as P

    legado = _modulo("comun19_equivalencia", raiz / CAPAS / "dialogo/saltos37/comun19.py")
    ficheros = sorted((raiz / CAPAS / "dialogo/saltos37/ie2/eve").glob("*.ssd"))[::150]
    ficheros += sorted((raiz / CAPAS / "dialogo/saltos37/ie2/mch").glob("*.ssd"))[::30]
    n = 0
    for f in ficheros:
        for cuerpo in _dialogos(f.read_bytes()):
            n += 1
            assert P.paginas(cuerpo, D.MODELO_IE2) == legado.paginas(cuerpo)
            assert P.problemas(cuerpo, D.MODELO_IE2) == legado.problemas(cuerpo)
            assert P.reajusta(cuerpo, D.MODELO_IE2) == legado.reajusta(cuerpo)
            assert D.reparte(cuerpo, glifos_font12) == legado.reparte(cuerpo)
            texto = cuerpo.decode("cp932", "replace")
            if "�" not in texto:
                assert P.partir_paginas(texto, D.MODELO_IE2) == legado.partir_paginas(texto)
    assert n > 300


# ------------------------------------------------------------------ 5. teclado en SPF_


def test_teclado_spf_igual_que_la_capa(raiz, golden):
    from ie123kit.ie2.comun import teclado as T
    from ie123kit.nucleo.contenedores.fa import FaArchive

    jp = FaArchive(str(raiz / JP / "archive.fa"))
    informe = json.loads((raiz / CAPAS / "teclado/teclado/informe.json").read_text(encoding="utf-8"))
    for ruta in T.PAQUETES:
        base = jp.read(ruta)
        # la base de la capa (probe_ie2_v18) llevaba estos paquetes sin tocar: los de la ROM
        assert _sha(base) == informe["base_sha256_entradas"][ruta]
        salida, _ = T.paquete_latino(base)
        assert salida == _capa(raiz, f"teclado/teclado/extra/{ruta}", golden)


# ------------------------------------------------------------------ 7. DSP-ADPCM y sound.pb


@pytest.fixture(scope="module")
def sonido(raiz):
    from ie123kit.nucleo.contenedores import sound_pb as SP

    jp_dir = raiz / JP / "inazuma2/data_iz/sound"
    es_dir = raiz / NDS / "sound/sp"
    jp = SP.leer_3ds((jp_dir / "sound.ph").read_bytes(), (jp_dir / "sound.pb").read_bytes())
    es = SP.leer_nds((es_dir / "sound.pkh").read_bytes(), (es_dir / "sound.pkb").read_bytes())
    return dict(jp), es


def test_voces_capitulo_v23_sound_pb_identico(raiz, golden, sonido):
    from ie123kit.ie2.comun import voces as VO
    from ie123kit.nucleo.contenedores import sound_pb as SP

    jd, es = sonido
    rel_base = "historial/media/v20_voces/romfs_mod/inazuma2/data_iz/sound"
    base = SP.leer_3ds(_capa(raiz, f"{rel_base}/sound.ph", golden), _capa(raiz, f"{rel_base}/sound.pb", golden))
    nuevos = {}
    for k in range(1, 11):
        n = f"2D_020_{k:02d}"
        nuevos[n + ".SED"], nuevos[n + ".SWD"], _ = VO.banco_desde_nds(
            jd[n + ".SWD"], jd[n + ".SED"], es[n + ".SWD"], es[n + ".SED"])
    pb, ph = SP.montar_3ds(base, nuevos)
    rel = "media/voces/romfs_mod/inazuma2/data_iz/sound"
    assert pb == _capa(raiz, f"{rel}/sound.pb", golden)
    assert ph == _capa(raiz, f"{rel}/sound.ph", golden)


def test_voces_gol_v20_muestra_de_bancos(raiz, golden, sonido):
    from ie123kit.ie2.comun import voces as VO
    from ie123kit.nucleo.contenedores import sound_pb as SP

    jd, es = sonido
    rel = "historial/media/v20_voces/romfs_mod/inazuma2/data_iz/sound"
    v20 = dict(SP.leer_3ds(_capa(raiz, f"{rel}/sound.ph", golden), _capa(raiz, f"{rel}/sound.pb", golden)))
    bancos = sorted({x[:-4] for x in jd if x.startswith("3D_003_")})
    assert len(bancos) == 35
    for n in bancos[::9]:
        sed, swd, _ = VO.banco_desde_nds(jd[n + ".SWD"], jd[n + ".SED"], es[n + ".SWD"], es[n + ".SED"])
        assert (sed, swd) == (v20[n + ".SED"], v20[n + ".SWD"]), n


def test_voz_titulo_v13_swd_identico(raiz, golden, sonido):
    """Remuestreo 24546 -> 32728 Hz, DSP-ADPCM y silencios; la v13 leía el SWD de DS sin alinear."""
    pytest.importorskip("scipy")
    from ie123kit.ie2.comun import voces as VO
    from ie123kit.nucleo.media import procyon as PR

    jd, es = sonido
    cw = VO.cwavs_desde_nds(jd["3D_901.SWD"], es["3D_901.SWD"], {8: 8, 10: 10, 11: 11}, alinear=1,
                            silencios=(9, 16, 17))
    assert PR.swd_con_cwavs(jd["3D_901.SWD"], cw) == _capa(raiz, "media/voz_titulo/par/3D_901.SWD", golden)


# ------------------------------------------------------------------ 6. subtítulos incrustados


def test_subtitulos_pistas_y_fotogramas_igual_que_el_informe(raiz, golden):
    """Texto, partición, tiempos y fotogramas con texto de las 35 cinemáticas, como en la capa."""
    from ie123kit.ie2.comun import subtitulos as IS
    from ie123kit.nucleo.media import subtitulos as S

    if not IS.estilo().fuente.is_file():
        pytest.skip(f"falta la fuente {IS.estilo().fuente}")
    informe = json.loads(_capa(raiz, "media/subtitulos/informe.json", golden).decode("utf-8"))
    assert len(informe["videos"]) == 35
    for v in informe["videos"]:
        pistas = IS.pistas((raiz / NDS / f"movie/txt/sp/{v['nombre']}.dat").read_bytes())
        assert pistas == v["subtitulos"], v["nombre"]
        idx = S.por_fotograma(pistas, v["fotogramas"], IS.FPS, IS.HZ)
        assert int((idx >= 0).sum()) == v["fotogramas_con_texto"], v["nombre"]


def test_subtitulos_dibujo_igual_que_comun_sub(raiz, golden):
    """El texto quemado sobre el plano Y es el mismo que el de ``comun_sub`` (antes de codificar)."""
    np = pytest.importorskip("numpy")
    from ie123kit.ie2.comun import subtitulos as IS
    from ie123kit.nucleo.media import subtitulos as S

    if not IS.estilo().fuente.is_file():
        pytest.skip(f"falta la fuente {IS.estilo().fuente}")
    sys.path.insert(0, str(raiz / CAPAS / "media/subtitulos"))
    try:
        legado = _modulo("comun_sub_equivalencia", raiz / CAPAS / "media/subtitulos/comun_sub.py")
    finally:
        sys.path.remove(str(raiz / CAPAS / "media/subtitulos"))
    informe = json.loads(_capa(raiz, "media/subtitulos/informe.json", golden).decode("utf-8"))
    for v in informe["videos"][::7]:
        subs = v["subtitulos"]
        idx = S.por_fotograma(subs, v["fotogramas"])
        assert (legado.por_fotograma(subs, v["fotogramas"]) == idx).all()
        rng = np.random.default_rng(len(subs))
        y_legado = rng.integers(0, 255, (v["fotogramas"], 320, 40), dtype=np.uint8)
        y_nuevo = y_legado.copy()
        legado.quemar(y_legado, subs, idx)
        S.quemar(y_nuevo, subs, idx, IS.estilo())
        assert (y_legado == y_nuevo).all(), v["nombre"]


# ------------------------------------------------------------------ 2. parches de CRO


def test_cro_ancho_dialogo_identica(raiz, golden):
    from ie123kit.ie2.comun.cro import parchear_ancho_dialogo

    base = _capa(raiz, "menus_cro/cofres/romfs/cro/ina_main2.cro", golden)
    salida, informe = parchear_ancho_dialogo(base)
    assert salida == _capa(raiz, "menus_cro/ancho_dialogo/romfs/cro/ina_main2.cro", golden)
    capa = json.loads((raiz / CAPAS / "menus_cro/ancho_dialogo/informe.json").read_text(encoding="utf-8"))["cro"]
    informe = json.loads(json.dumps(informe))
    for clave in ("base_sha256", "salida_sha256", "bytes_distintos", "segmentos", "tablas_parches",
                  "comprobacion_relocacion"):
        assert informe[clave] == capa[clave], clave
