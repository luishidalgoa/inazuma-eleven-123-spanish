"""Hook de nombres con datos reales de work/ (solo lectura; se salta sin ellos)."""
import importlib.util
import os
import struct

import pytest

from ie123kit.ie3.comun import usearch_sincronia as S3
from ie123kit.nucleo.config.raiz import find_root
from ie123kit.nucleo.contenedores.fa_flujo import FaFlujo
from ie123kit.nucleo.registros import usearch as U
from ie123kit.nucleo.texto.ancho_completo import encode_fullwidth
from ie123kit.servicio import capas_nombres
from ie123kit.servicio import sincronia_usearch as S

pytestmark = pytest.mark.requiere_rom

RAIZ = find_root()
WORK = RAIZ / "work"
#: archive.fa con los tres juegos: una copia del instalado en Azahar, pasada por IE123_ARCHIVE.
#: (La candidata work/shared/candidatas/probe_ie3_fuego_v17/archive.fa se borró el 2026-11-12.)
ARCHIVE = [p for p in (os.environ.get("IE123_ARCHIVE"),) if p and os.path.isfile(p)][:1]


def _exigir_archive():
    if not ARCHIVE:
        pytest.skip("requiere un archive.fa: exporta IE123_ARCHIVE con una copia del instalado en Azahar")
    return ARCHIVE[0]


def test_toda_capa_sospechosa_de_work_esta_clasificada():
    """Guardia heurística (ver servicio/capas_nombres.py: NO es la protección, es un detector de capas nuevas)."""
    if not WORK.is_dir():
        pytest.skip("requiere work/")
    sin_clasificar = capas_nombres.sin_clasificar(WORK)
    assert not sin_clasificar, (
        "capas de work/ con señales de tocar nombres de jugador sin clasificar en servicio/capas_nombres.py "
        f"(CAPAS_NOMBRES_JUGADOR o CAPAS_SIN_NOMBRES_DE_JUGADOR): {sin_clasificar}"
    )


def test_las_capas_registradas_existen():
    if not WORK.is_dir():
        pytest.skip("requiere work/")
    assert capas_nombres.entradas_obsoletas(WORK) == []


def test_cada_juego_tiene_su_capa_busqueda_usearch():
    if not WORK.is_dir():
        pytest.skip("requiere work/")
    for ruta in ("ie1/capas/nombres", "ie2/shared/capas/nombres", "ie3/shared/capas/nombres"):
        assert (WORK / ruta / "busqueda_usearch/apply.py").is_file(), ruta


def test_fa_flujo_coincide_con_b123archive_en_el_archive_europeo():
    b123 = pytest.importorskip("ie123kit.ie3.comun.b123")
    eu = WORK / "ie1/fuentes/3ds_eu/romfs/archive.fa"
    if not eu.is_file():
        pytest.skip("requiere el archive.fa europeo de IE1")
    with FaFlujo(eu) as nuevo, b123.B123Archive(eu) as viejo:
        assert len(nuevo.entradas) == len(viejo.entries)
        for e in viejo.entries:
            assert nuevo.entradas[e.path.decode("shift-jis", "replace")] == (e.index, e.offset, e.size)


def test_ie1_la_salida_coincide_con_el_usearch_oficial_europeo():
    archive = _exigir_archive()
    eu = WORK / "ie1/fuentes/3ds_eu/romfs/archive.fa"
    if not eu.is_file():
        pytest.skip("requiere el archive.fa europeo de IE1")
    esquema = U.ESQUEMAS["ie1"]
    with FaFlujo(archive) as fa, FaFlujo(eu) as e:
        us, ub = fa.leer(esquema.ruta_usearch), fa.leer(esquema.ruta_unitbase)
        oficial = e.leer("es/inazuma1/data_iz/logic/usearch.dat")
    nuevo, _ = U.sincronizar(esquema, us, ub, S.cargar_decodificador(RAIZ))
    por_id = {U._u16(oficial[n * 48:(n + 1) * 48], 0x24): oficial[n * 48:n * 48 + 16].split(b"\0")[0].decode("cp932")
              for n in range(len(oficial) // 48)}
    comprobados = 0
    for n in range(len(nuevo) // 48):
        r = nuevo[n * 48:(n + 1) * 48]
        if not U.es_buscable(us[n * 48:(n + 1) * 48]):
            continue
        assert r[0x10:0x20] == U.campo_busqueda(por_id[U._u16(r, 0x24)])[0], (n, por_id[U._u16(r, 0x24)])
        assert r[:16] == us[n * 48:n * 48 + 16]  # +0x00 (kana) intacto
        comprobados += 1
    assert comprobados > 500


@pytest.mark.parametrize("juego", ["ie1", "ie2"])
def test_ie1_ie2_toda_cadena_tecleable_encuentra_su_registro_y_el_japones_no(juego):
    archive = _exigir_archive()
    esquema = U.ESQUEMAS[juego]
    dec = S.cargar_decodificador(RAIZ)
    with FaFlujo(archive) as fa:
        us, ub = fa.leer(esquema.ruta_usearch), fa.leer(esquema.ruta_unitbase)
    nuevo, inf = U.sincronizar(esquema, us, ub, dec)
    assert inf.sin_unitbase == 0 and inf.sin_traduccion == 0
    indice = U.indice_unitbase(ub)
    probados = fallos_japones = 0
    for n in range(len(us) // 48):
        r = us[n * 48:(n + 1) * 48]
        if not U.es_buscable(r):
            continue
        k = indice[U._u16(r, 0x24)]
        texto, _ = U.nombre_unitbase(ub[k * 96:(k + 1) * 96], dec, esquema.campos_nombre)
        campo = U.campo_busqueda(texto)[0].rstrip(b"\0")
        for letras in range(1, len(campo) // 2 + 1):
            assert n in U.simular_busqueda(nuevo, campo[:2 * letras]), (texto, letras)
            probados += 1
            fallos_japones += n not in U.simular_busqueda(us, campo[:2 * letras])
    assert probados > 2000 and fallos_japones == probados  # con el usearch japonés no se encuentra nada
    # lo que cambia es SOLO +0x10 de los alcanzables: +0x00, flags y el resto idénticos; la lista «Por nombre» no pierde a nadie
    for n in range(len(us) // 48):
        antes, despues = us[n * 48:(n + 1) * 48], nuevo[n * 48:(n + 1) * 48]
        assert antes[:16] == despues[:16] and antes[32:] == despues[32:], n
    assert U.lista_por_nombre(nuevo) == U.lista_por_nombre(us) and len(U.lista_por_nombre(us)) > 700


def test_ie3_el_hook_equivale_a_album_usearch_y_solo_recoloca_sue():
    archive = _exigir_archive()
    capa = WORK / "ie3/shared/capas/nombres/busqueda_usearch/comprobar_equivalencia.py"
    if not capa.is_file():
        pytest.skip("requiere la capa busqueda_usearch de IE3")
    spec = importlib.util.spec_from_file_location("comprobar_equivalencia_ie3", capa)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    with FaFlujo(archive) as fa:
        for clave, esquema in S3.ESQUEMAS.items():
            r = modulo.comprobar(esquema, fa.leer(esquema.ruta_usearch), fa.leer(esquema.ruta_unitbase))
            assert r["hook_igual_a_nombres_mas_ordenar"], clave
            assert r["hook_sobre_el_archive_igual_a_album_usearch_tras_excepciones_corto"], clave
            assert r["hook_sobre_el_archive"]["nombres_reescritos"] == 0 and r["hook_sobre_el_archive"]["mismos_registros"]
            assert r["referencia_vs_archive_ids_distintos"] in ([2450], []), clave


def test_renombrar_un_jugador_en_unitbase_sin_sincronizar_falla_la_validacion_en_los_tres_juegos():
    archive = _exigir_archive()
    dec = S.cargar_decodificador(RAIZ)
    with FaFlujo(archive) as fa:
        cambios, _ = S.sincronizar(fa.leer, decodificador=dec)
        base = {**{r: fa.leer(r) for r in (e.ruta_unitbase for e in (U.ESQUEMAS["ie1"], U.ESQUEMAS["ie2"]))}}
        ie3 = {k: fa.leer(e.ruta_unitbase) for k, e in S3.ESQUEMAS.items()}
        us_ie1 = cambios[U.ESQUEMAS["ie1"].ruta_usearch]
        us_ie2 = cambios[U.ESQUEMAS["ie2"].ruta_usearch]
        # IE1/IE2: «Mark»-like: cambia el nombre del primer jugador alcanzable
        for juego, us in (("ie1", us_ie1), ("ie2", us_ie2)):
            esquema = U.ESQUEMAS[juego]
            ub = bytearray(base[esquema.ruta_unitbase])
            n = next(i for i in range(len(us) // 48) if U.es_buscable(us[i * 48:(i + 1) * 48]))
            k = U.indice_unitbase(bytes(ub))[U._u16(us, n * 48 + 0x24)]
            ub[k * 96 + 0x10:k * 96 + 0x20] = encode_fullwidth("Zzyzx").ljust(16, b"\0")
            ub[k * 96:k * 96 + 0x10] = encode_fullwidth("Zzyzx").ljust(16, b"\0")
            assert U.verificar(esquema, us, bytes(ub), dec) and any(
                h.codigo == "USEARCH_DESINCRONIZADO" for h in U.verificar(esquema, us, bytes(ub), dec))
            de_nuevo, _ = U.sincronizar(esquema, us, bytes(ub), dec)
            assert not [h for h in U.verificar(esquema, de_nuevo, bytes(ub), dec) if h.gravedad == "error"]
        # IE3: renombra el primer jugador con id
        esquema = S3.ESQUEMAS["ie3.inazuma3"]
        ub = bytearray(ie3["ie3.inazuma3"])
        k = next(i for i in range(len(ub) // 0x68) if struct.unpack_from("<H", ub, i * 0x68 + 0x4E)[0])
        ub[k * 0x68 + 0x1C:k * 0x68 + 0x2C] = b"Zzyzx".ljust(16, b"\0")
        us = fa.leer(esquema.ruta_usearch)
        assert any(h.gravedad == "error" for h in S3.verificar(esquema, us, bytes(ub)))
        arreglado, inf = S3.sincronizar(esquema, us, bytes(ub))
        assert inf.reescritos == 1 and not [h for h in S3.verificar(esquema, arreglado, bytes(ub))
                                           if h.gravedad == "error"]


def test_ningun_nombre_alcanzable_vuelve_a_kana_en_los_datos_reales():
    """Justifica que ``EXCEPCIONES_VUELTO_A_KANA`` esté vacía: con los datos reales no hay ningún caso, así que
    convertir el aviso en error no bloquea ninguna build actual."""
    archive = _exigir_archive()
    with FaFlujo(archive) as fa:
        cambios, _ = S.sincronizar(fa.leer, decodificador=S.cargar_decodificador(RAIZ))
        previsto = S.verificar(fa.leer, decodificador=S.cargar_decodificador(RAIZ), sustituciones=cambios)
    assert previsto["ok"], previsto["errores"]
    assert not any("USEARCH_NOMBRE_VUELTO_A_KANA" in x for x in previsto["errores"] + previsto["avisos"])
    assert U.EXCEPCIONES_VUELTO_A_KANA == {"ie1": {}, "ie2": {}}
