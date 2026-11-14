"""Hook de nombres: lectura/escritura por flujo, orquestación de los tres juegos y enganche en la construcción."""
import json
import struct
import sys
from pathlib import Path

import pytest

from ie123kit.nucleo.construir import candidata as C
from ie123kit.nucleo.contenedores.fa import FaArchive
from ie123kit.nucleo.contenedores.fa_flujo import FaFlujo, comparar_archives, reemplazar_en_disco
from ie123kit.nucleo.errores import ValidacionError
from ie123kit.nucleo.registros import usearch as U
from ie123kit.nucleo.texto.ancho_completo import encode_fullwidth
from ie123kit.servicio import sincronia_usearch as S

CONTRATO = Path(__file__).resolve().parent.parent / "contrato"
if str(CONTRATO) not in sys.path:
    sys.path.insert(0, str(CONTRATO))

from fa_sintetico import bytes_fa

REGISTRO = {"bigramas": [{"sjis": "9ABA", "par": "ck"}]}
IE1 = U.ESQUEMAS["ie1"]
IE2 = U.ESQUEMAS["ie2"]


@pytest.fixture(scope="module")
def dec():
    return U.Decodificador([REGISTRO])


def _ub48(ident: int, corto: bytes) -> bytes:
    r = bytearray(96)
    r[0:16] = corto.ljust(16, b"\0")
    r[16:32] = corto.ljust(16, b"\0")
    struct.pack_into("<H", r, 0x42, ident)
    return bytes(r)


def _us48(ident: int, nivel: int = 0x3C, flags: int = 3) -> bytes:
    r = bytearray(48)
    kana = "あいう".encode("cp932").ljust(16, b"\0")
    r[0:16], r[16:32] = kana, kana
    struct.pack_into("<H", r, 0x24, ident)
    r[0x26], r[0x2A], r[0x2B] = nivel, 1 if ident else 0, flags
    return bytes(r)


def _us44(nombre: bytes, ident: int) -> bytes:
    r = bytearray(44)
    r[0:16] = nombre.ljust(16, b"\0")
    r[16:32] = "あ".encode("cp932").ljust(16, b"\0")
    struct.pack_into("<H", r, 0x24, ident)
    r[0x2A], r[0x2B] = (1, 2) if ident else (0, 0)
    return bytes(r)


def _ub104(corto: bytes, ident: int) -> bytes:
    r = bytearray(0x68)
    r[0x1C:0x2C] = corto.ljust(16, b"\0")
    struct.pack_into("<H", r, 0x4E, ident)
    return bytes(r)


def _ficheros(nombre_ie1: bytes = b"Mark", nombre_ie3: bytes = b"Axel") -> dict[str, bytes]:
    cero = _ub48(0, b"\x81\x40")
    ie1_us = _us48(1) + _us48(0)
    ie1_ub = cero + _ub48(1, nombre_ie1)
    ie2_us = _us48(1) + _us48(2, nivel=0xD7) + _us48(0)
    ie2_ub = cero + _ub48(1, b"Nathan") + _ub48(2, b"Binder")
    scout = struct.pack("<H", 2) + bytes(20) + bytes(22)
    ficheros = {
        IE1.ruta_usearch: ie1_us, IE1.ruta_unitbase: ie1_ub,
        IE2.ruta_usearch: ie2_us, IE2.ruta_unitbase: ie2_ub, IE2.ruta_scout: scout,
        "otros/dato.bin": b"no tocar",
    }
    for ruta in ("inazuma3/data_iz/logic", "inazuma3_ogre/data_iz/logic", "inazuma3_ogre/data_iz/logic/ex_binder"):
        ficheros[f"{ruta}/usearch.dat"] = _us44(nombre_ie3, 1) + _us44(b"", 0)
        ficheros[f"{ruta}/unitbase.dat"] = _ub104(nombre_ie3, 1) + _ub104(b"", 0)
    return ficheros


@pytest.fixture
def fa(tmp_path):
    ruta = tmp_path / "archive.fa"
    ruta.write_bytes(bytes_fa(_ficheros()))
    return ruta


# ------------------------------------------------------------------ FaFlujo


def test_fa_flujo_lee_lo_mismo_que_fa_archive(fa):
    viejo = FaArchive(str(fa))
    with FaFlujo(fa) as nuevo:
        assert set(nuevo.entradas) == set(viejo.index)
        for ruta in viejo.index:
            assert nuevo.leer(ruta) == viejo.read(ruta)
        assert nuevo.existe(IE1.ruta_usearch) and not nuevo.existe("no/existe")
        with pytest.raises(KeyError):
            nuevo.leer("no/existe")


def test_fa_flujo_rechaza_un_fichero_que_no_es_b123(tmp_path):
    malo = tmp_path / "x.fa"
    malo.write_bytes(b"NOPE" + bytes(100))
    with pytest.raises(ValueError):
        FaFlujo(malo)


def test_reemplazar_en_disco_anexa_y_solo_cambia_los_filentry(fa, tmp_path):
    copia = tmp_path / "copia.fa"
    copia.write_bytes(fa.read_bytes())
    nuevo = b"datos nuevos y mas largos que antes" * 3
    reemplazar_en_disco(copia, {IE1.ruta_usearch: nuevo})
    with FaFlujo(copia) as c, FaFlujo(fa) as o:
        assert c.leer(IE1.ruta_usearch) == nuevo
        assert all(c.leer(r) == o.leer(r) for r in o.entradas if r != IE1.ruta_usearch)
    informe = comparar_archives(fa, copia)
    assert informe["entradas_distintas"] == [IE1.ruta_usearch]
    assert informe["bytes_distintos_fuera_de_filentry"] == 0
    assert informe["bytes_anexados"] >= len(nuevo)


def test_comparar_detecta_una_modificacion_fuera_de_lo_esperado(fa, tmp_path):
    copia = tmp_path / "copia.fa"
    datos = bytearray(fa.read_bytes())
    datos[-1] ^= 0xFF  # corrompe el último byte de datos sin declararlo
    copia.write_bytes(bytes(datos))
    assert comparar_archives(fa, copia)["bytes_distintos_fuera_de_filentry"] == 1


# ------------------------------------------------------------------ orquestación


def test_sincronizar_y_verificar_los_tres_juegos(fa, dec):
    with FaFlujo(fa) as f:
        antes = S.verificar(f.leer, decodificador=dec)
        cambios, informe = S.sincronizar(f.leer, decodificador=dec, ejemplos=2)
    assert not antes["ok"] and any("USEARCH_DESINCRONIZADO" in e for e in antes["errores"])
    # IE1 e IE2 cambian; en IE3 el nombre ya era coherente (usearch = unitbase)
    assert set(cambios) == {IE1.ruta_usearch, IE2.ruta_usearch}
    assert informe["ie1"]["cambiados"] == 1 and informe["ie2"]["cambiados"] == 1
    assert informe["ie1"]["ejemplos"][0]["despues"] == encode_fullwidth("Mark").ljust(16, b"\0").hex(" ")
    assert informe["ie3.inazuma3"]["reescritos"] == 0
    # el D7 de IE2 (código secreto por ScoutSpCode) queda sin tocar
    assert cambios[IE2.ruta_usearch][48:96] == _us48(2, nivel=0xD7)
    # el latín va a +0x10 y el kana de +0x00 y los flags no se tocan
    assert cambios[IE1.ruta_usearch][:16] == _us48(1)[:16] and cambios[IE1.ruta_usearch][0x2B] == 3
    # tras escribir la verificación pasa
    reemplazar_en_disco(fa, cambios)
    with FaFlujo(fa) as f:
        despues = S.verificar(f.leer, decodificador=dec)
    assert despues["ok"], despues["errores"]
    S.exigir_sincronia(despues)


def test_exigir_sincronia_falla_si_hay_errores():
    with pytest.raises(ValidacionError) as e:
        S.exigir_sincronia({"ok": False, "errores": ["ie1: USEARCH_DESINCRONIZADO: x"]})
    assert e.value.codigo == "USEARCH_DESINCRONIZADO"


def test_sin_decodificador_los_juegos_ie1_ie2_fallan_claro(fa):
    with FaFlujo(fa) as f, pytest.raises(ValidacionError) as e:
        S.sincronizar(f.leer, ("ie1",))
    assert e.value.codigo == "USEARCH_SIN_DECODIFICADOR"
    with FaFlujo(fa) as f, pytest.raises(ValueError, match="juego desconocido"):
        S.sincronizar(f.leer, ("ie9",))


def test_un_archive_sin_el_par_se_omite(tmp_path, dec):
    ruta = tmp_path / "solo_ie1.fa"
    ficheros = _ficheros()
    ruta.write_bytes(bytes_fa({k: v for k, v in ficheros.items() if k.startswith("inazuma1")}))
    with FaFlujo(ruta) as f:
        cambios, informe = S.sincronizar(f.leer, decodificador=dec)
    assert set(cambios) == {IE1.ruta_usearch} and "omitido" in informe["ie3.ex_binder"]


def test_ejecutar_capa_escribe_sobre_la_copia_y_deja_informe(fa, tmp_path, dec, monkeypatch):
    monkeypatch.setattr(S, "cargar_decodificador", lambda raiz=None: dec)
    original = tmp_path / "original.fa"
    original.write_bytes(fa.read_bytes())
    informe = tmp_path / "informe.json"
    seco = S.ejecutar_capa("prueba", ("ie1", "ie2", "ie3"), fa, tmp_path, informe=informe)
    assert not seco["escrito"] and fa.read_bytes() == original.read_bytes()  # sin --escribir no toca nada
    datos = S.ejecutar_capa("prueba", ("ie1", "ie2", "ie3"), fa, tmp_path, escribir=True, informe=informe,
                            original=original)
    assert datos["escrito"] and datos["verificacion_despues"]["ok"]
    assert datos["runtime_verified"] is False and datos["instalada"] is False
    assert datos["comparacion_con_original"]["entradas_distintas"] == sorted([IE1.ruta_usearch, IE2.ruta_usearch])
    assert datos["comparacion_con_original"]["bytes_distintos_fuera_de_filentry"] == 0
    assert json.loads(informe.read_text(encoding="utf-8"))["archive_sha256_antes"] != datos["archive_sha256_despues"]
    # segunda pasada: nada que hacer
    otra = S.ejecutar_capa("prueba", ("ie1", "ie2", "ie3"), fa, tmp_path, escribir=True)
    assert otra["entradas_a_cambiar"] == [] and not otra["escrito"]


# ------------------------------------------------------------------ enganche en la construcción


def _preparar(tmp_path, nombre_ie1=b"Mark"):
    base = tmp_path / "base.fa"
    base.write_bytes(bytes_fa(_ficheros()))
    ui = tmp_path / "ui"
    (ui / "romfs/cro").mkdir(parents=True)
    (ui / "romfs/cro/ina_main1.cro").write_bytes(b"CRO sintetica")
    # una «capa de nombres» que solo actualiza el unitbase de IE1 (nadie toca usearch)
    extra = tmp_path / "extra" / "inazuma1/data_iz/logic"
    extra.mkdir(parents=True)
    (extra / "unitbase.dat").write_bytes(_ub48(0, b"\x81\x40") + _ub48(1, nombre_ie1))
    return base, ui, tmp_path / "extra"


def test_construir_con_paso_final_deja_usearch_sincronizado(tmp_path, dec):
    base, ui, extra = _preparar(tmp_path, b"Mack")
    # el paso se aplica a IE1 y IE3 (la base sintética de IE2 ya trae unitbase sin cambios)
    paso = S.paso_final(("ie1", "ie3"), decodificador=dec)
    salida = tmp_path / "salida" / "archive.fa"
    informe = C.construir(base, salida, ui=ui, capas=[extra], pasos_finales=[paso])
    assert informe["pasos_finales"][0]["entradas_escritas"] == [IE1.ruta_usearch]
    with FaFlujo(salida) as f:
        assert S.verificar(f.leer, ("ie1", "ie3"), decodificador=dec)["ok"]
        assert f.leer(IE1.ruta_usearch)[0x10:0x18] == encode_fullwidth("Mack")
    assert json.loads(Path(str(salida).replace(".fa", ".build.json")).read_text())["pasos_finales"]


def test_construir_sin_paso_final_no_anota_la_clave_y_verificar_detecta_la_desincronia(tmp_path, dec):
    base, ui, extra = _preparar(tmp_path, b"Mack")
    salida = tmp_path / "salida" / "archive.fa"
    # opt-out nombrado del constructor (reproducir un hash anterior al hook): sin paso final no se anota la clave
    informe = C.construir(base, salida, ui=ui, capas=[extra], sincronia_usearch=False)
    assert "pasos_finales" not in informe  # el build.json de quien no los usa no cambia
    assert "pasos_finales" not in json.loads(salida.with_suffix(".build.json").read_text())
    with FaFlujo(salida) as f:
        assert not S.verificar(f.leer, ("ie1",), decodificador=dec)["ok"]


def test_construir_sincroniza_por_defecto_sin_pedirlo(tmp_path, monkeypatch):
    """Ninguna llamada a ``candidata.construir`` (ni su ``__main__``) se salta el hook sin pedirlo por su nombre."""
    _fijar_raiz(monkeypatch, _raiz_con_bigramas(tmp_path))
    base, ui, extra = _preparar(tmp_path, b"Mack")
    salida = tmp_path / "salida" / "archive.fa"
    informe = C.construir(base, salida, ui=ui, capas=[extra])  # sin pasos_finales ni opciones
    assert informe["pasos_finales"][0]["paso"] == "busqueda_usearch"
    assert IE1.ruta_usearch in informe["pasos_finales"][0]["entradas_escritas"]
    assert S.verificar_archive(salida)["ok"]
    # y si el llamante ya trae el paso no se ejecuta dos veces
    salida2 = tmp_path / "salida2" / "archive.fa"
    informe2 = C.construir(base, salida2, ui=ui, capas=[extra], pasos_finales=[S.paso_final()])
    assert len(informe2["pasos_finales"]) == 1


#: ejecuta el bloque ``__main__`` REAL de candidata.py con el registro de bigramas sintético (sin ``work/``)
_MAIN_CANDIDATA = """
import json, runpy, sys
from ie123kit.nucleo.registros import usearch as U
from ie123kit.servicio import sincronia_usearch as S
registro = json.loads(sys.argv[1])
S.cargar_decodificador = lambda raiz=None: U.Decodificador([registro])
sys.argv = ["candidata"] + sys.argv[2:]
runpy.run_module("ie123kit.nucleo.construir.candidata", run_name="__main__")
"""


def test_main_de_candidata_sincroniza_por_defecto_y_tiene_opt_out_nombrado(tmp_path, dec):
    import os
    import subprocess

    base, ui, _ = _preparar(tmp_path, b"Mack")
    src = Path(C.__file__).resolve().parents[3]
    entorno = {**os.environ, "PYTHONPATH": str(src), "PYTHONIOENCODING": "utf-8"}

    def correr(salida, *extra):
        orden = [sys.executable, "-X", "utf8", "-c", _MAIN_CANDIDATA, json.dumps(REGISTRO), "--base", str(base),
                 "--ui", str(ui), "--output", str(salida), "--extra", str(tmp_path / "extra"), *extra]
        return subprocess.run(orden, capture_output=True, text=True, encoding="utf-8", env=entorno, check=False)

    por_defecto = tmp_path / "a" / "archive.fa"
    r = correr(por_defecto)
    assert r.returncode == 0, r.stdout + r.stderr
    assert S.verificar_archive(por_defecto, decodificador=dec)["ok"]
    pasos = json.loads(por_defecto.with_suffix(".build.json").read_text())["pasos_finales"]
    assert pasos[0]["paso"] == "busqueda_usearch" and IE1.ruta_usearch in pasos[0]["entradas_escritas"]

    sin = tmp_path / "b" / "archive.fa"
    r = correr(sin, "--sin-sincronia-usearch")
    assert r.returncode == 0, r.stdout + r.stderr
    assert not S.verificar_archive(sin, decodificador=dec)["ok"]  # desincronizada y lo dice la validación de la salida
    assert "pasos_finales" not in json.loads(sin.with_suffix(".build.json").read_text())


def test_paso_final_falla_si_no_puede_sincronizar_y_no_deja_archive_a_medias(tmp_path, dec):
    ficheros = _ficheros()
    # usearch de IE1 con un id que no existe en unitbase: ninguna regeneración lo arregla
    ficheros[IE1.ruta_usearch] = _us48(1) + _us48(77)
    ruta = tmp_path / "huerfano.fa"
    ruta.write_bytes(bytes_fa(ficheros))
    with pytest.raises(ValidacionError) as e:
        S.paso_final(("ie1",), decodificador=dec)(ruta)
    assert e.value.codigo == "USEARCH_DESINCRONIZADO" and "USEARCH_ID_HUERFANO" in str(e.value)
    # dentro de la construcción el archive construido se borra y no se escribe el .build.json
    salida = tmp_path / "salida" / "archive.fa"
    with pytest.raises(ValidacionError):
        C.construir(ruta, salida, pasos_finales=[S.paso_final(("ie1",), decodificador=dec)])
    assert not salida.exists() and not salida.with_suffix(".build.json").exists()


def _raiz_con_bigramas(tmp_path) -> Path:
    raiz = tmp_path / "proyecto"
    (raiz / "tools").mkdir(parents=True)
    (raiz / "AGENTS.md").write_text("sintético", encoding="utf-8")
    (raiz / "tools" / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    for relativa in S.REGISTROS_BIGRAMAS:
        ruta = raiz / relativa
        ruta.parent.mkdir(parents=True)
        ruta.write_text(json.dumps(REGISTRO), encoding="utf-8")
    return raiz


def _fijar_raiz(monkeypatch, raiz: Path) -> None:
    """``find_root`` (el que usa cargar_decodificador) devuelve ``raiz``; el cargador de congelados no se toca."""
    from ie123kit.nucleo.config import raiz as modulo

    monkeypatch.setattr(modulo, "find_root", lambda inicio=None: raiz)


def test_paso_final_sin_argumentos_localiza_el_registro_por_la_raiz_del_proyecto(tmp_path, monkeypatch):
    _fijar_raiz(monkeypatch, _raiz_con_bigramas(tmp_path))
    base, ui, extra = _preparar(tmp_path, b"Mack")
    salida = tmp_path / "salida" / "archive.fa"
    informe = C.construir(base, salida, ui=ui, capas=[extra], pasos_finales=[S.paso_final()])
    assert IE1.ruta_usearch in informe["pasos_finales"][0]["entradas_escritas"]
    assert S.verificar_archive(salida)["ok"]


def test_sin_registro_de_bigramas_el_error_es_explicito_y_antes_de_copiar(tmp_path, monkeypatch):
    raiz = tmp_path / "ci"  # como un clon de CI: raíz válida pero sin work/
    (raiz / "tools").mkdir(parents=True)
    (raiz / "AGENTS.md").write_text("x", encoding="utf-8")
    (raiz / "tools" / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    _fijar_raiz(monkeypatch, raiz)
    base, ui, extra = _preparar(tmp_path)
    salida = tmp_path / "salida" / "archive.fa"
    with pytest.raises(ValidacionError) as e:
        C.construir(base, salida, ui=ui, capas=[extra], pasos_finales=[S.paso_final()])
    assert e.value.codigo == "USEARCH_SIN_DECODIFICADOR" and "registro.json" in str(e.value)
    assert not salida.parent.exists(), "se ha copiado la base antes de resolver el decodificador"
    informe = S.verificar_archive(base)
    assert not informe["ok"] and informe["codigo"] == "USEARCH_SIN_DECODIFICADOR"


def test_construir_por_defecto_sin_registro_de_bigramas_falla_claro_antes_de_copiar(tmp_path, monkeypatch):
    raiz = tmp_path / "ci"
    (raiz / "tools").mkdir(parents=True)
    (raiz / "AGENTS.md").write_text("x", encoding="utf-8")
    (raiz / "tools" / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    _fijar_raiz(monkeypatch, raiz)
    base, ui, extra = _preparar(tmp_path)
    salida = tmp_path / "salida" / "archive.fa"
    with pytest.raises(ValidacionError) as e:
        C.construir(base, salida, ui=ui, capas=[extra])
    assert e.value.codigo == "USEARCH_SIN_DECODIFICADOR"
    assert not salida.parent.exists()


def test_un_archive_sin_pares_de_ie1_ie2_no_necesita_decodificador(tmp_path, monkeypatch):
    def no_debe_llamarse(inicio=None):
        raise AssertionError("no hacía falta localizar la raíz")

    from ie123kit.nucleo.config import raiz as modulo

    monkeypatch.setattr(modulo, "find_root", no_debe_llamarse)
    solo_otros = tmp_path / "otros.fa"
    solo_otros.write_bytes(bytes_fa({"otros/dato.bin": b"x"}))
    assert S.verificar_archive(solo_otros)["ok"]
    C.construir(solo_otros, tmp_path / "s" / "archive.fa", pasos_finales=[S.paso_final()])


# ------------------------------------------------------------------ línea de órdenes (cadena en sitio)


def _cli(monkeypatch, capsys, dec, tmp_path, *args):
    monkeypatch.setattr(S, "cargar_decodificador", lambda raiz=None: dec)
    codigo = S.main([*args, "--raiz", str(tmp_path)])
    return codigo, json.loads(capsys.readouterr().out)


def test_cli_verificar_sincronizar_y_cerrar(fa, tmp_path, dec, monkeypatch, capsys):
    codigo, salida = _cli(monkeypatch, capsys, dec, tmp_path, "verificar", str(fa))
    assert codigo == 1 and not salida["ok"]
    original = fa.read_bytes()
    codigo, salida = _cli(monkeypatch, capsys, dec, tmp_path, "sincronizar", str(fa))  # sin --escribir
    assert codigo == 0 and not salida["escrito"] and fa.read_bytes() == original
    codigo, salida = _cli(monkeypatch, capsys, dec, tmp_path, "cerrar", str(fa))
    assert codigo == 0 and salida["ok"] and salida["escrito"]
    import hashlib
    assert salida["archive_sha256"] == hashlib.sha256(fa.read_bytes()).hexdigest()
    assert _cli(monkeypatch, capsys, dec, tmp_path, "verificar", str(fa))[0] == 0
    codigo, salida = _cli(monkeypatch, capsys, dec, tmp_path, "cerrar", str(fa))  # idempotente
    assert codigo == 0 and not salida["escrito"]


def test_cli_cerrar_y_sincronizar_salen_con_1_si_no_queda_sincronizado(tmp_path, dec, monkeypatch, capsys):
    ficheros = _ficheros()
    # nombre de unitbase vuelto a kana con el latín viejo en usearch +0x10: el hook no puede arreglarlo
    us = bytearray(_us48(1))
    us[0x10:0x20] = encode_fullwidth("Mark").ljust(16, b"\0")
    ficheros[IE1.ruta_usearch] = bytes(us) + _us48(0)
    ficheros[IE1.ruta_unitbase] = _ub48(0, b"\x81\x40") + _ub48(1, "あいう".encode("cp932"))
    ruta = tmp_path / "kana.fa"
    ruta.write_bytes(bytes_fa(ficheros))
    for orden in ("cerrar", "sincronizar"):
        codigo, salida = _cli(monkeypatch, capsys, dec, tmp_path, orden, str(ruta), "--juegos", "ie1", "--escribir")
        assert codigo == 1 and not salida["ok"], orden
        assert any("USEARCH_NOMBRE_VUELTO_A_KANA" in e for e in salida["errores"])
    # un archive imposible de sincronizar (id huérfano) también sale con 1 y dice el código
    ficheros[IE1.ruta_usearch] = _us48(1) + _us48(77)
    ficheros[IE1.ruta_unitbase] = _ub48(0, b"\x81\x40") + _ub48(1, b"Mark")
    ruta.write_bytes(bytes_fa(ficheros))
    codigo, salida = _cli(monkeypatch, capsys, dec, tmp_path, "cerrar", str(ruta), "--juegos", "ie1")
    assert codigo == 1 and salida["codigo"] == "USEARCH_DESINCRONIZADO"


def test_instalar_azahar_se_niega_con_usearch_desincronizado_y_no_copia_nada(tmp_path, dec, monkeypatch):
    from ie123kit.nucleo.construir import instalar

    monkeypatch.setattr(S, "cargar_decodificador", lambda raiz=None: dec)
    monkeypatch.setattr(instalar, "_azahar_en_ejecucion", lambda: False)
    candidata = tmp_path / "cand"
    candidata.mkdir()
    (candidata / "archive.fa").write_bytes(bytes_fa(_ficheros()))
    mods = tmp_path / "mods"
    with pytest.raises(ValidacionError) as e:
        instalar.azahar(candidata, raiz_mods=mods)
    assert e.value.codigo == "USEARCH_DESINCRONIZADO" and not mods.exists()
    # el cierre de la cadena en sitio la deja instalable
    assert S.main(["cerrar", str(candidata / "archive.fa"), "--raiz", str(tmp_path), "--sin-sha"]) == 0
    assert instalar.azahar(candidata, raiz_mods=mods)["runtime_verified"] is False
    # un archive que no se puede leer tampoco se da por bueno, salvo el opt-out nombrado
    (candidata / "archive.fa").write_bytes(b"no es un B123")
    with pytest.raises(ValidacionError):
        instalar.azahar(candidata, raiz_mods=mods)
    instalar.azahar(candidata, raiz_mods=mods, comprobar_sincronia_usearch=False)


# ------------------------------------------------------------------ registro de capas


def test_las_tablas_de_capas_no_se_solapan_y_apuntan_a_juegos_conocidos():
    assert not set(S.CAPAS_NOMBRES_JUGADOR) & set(S.CAPAS_SIN_NOMBRES_DE_JUGADOR)
    assert all(S.CAPAS_SIN_NOMBRES_DE_JUGADOR.values())  # cada capa descartada dice por qué
    for capa, juegos in S.CAPAS_NOMBRES_JUGADOR.items():
        assert not capa.startswith(("work/", "/")), capa
        assert set(juegos.split()) <= set(S.JUEGOS), (capa, juegos)


def test_la_cli_verifica_con_codigo_de_salida(fa, dec, monkeypatch, capsys):
    monkeypatch.setattr(S, "cargar_decodificador", lambda raiz=None: dec)
    assert S.main(["verificar", str(fa), "--raiz", str(fa.parent)]) == 1
    assert "USEARCH_DESINCRONIZADO" in capsys.readouterr().out
    assert S.main(["sincronizar", str(fa), "--escribir", "--raiz", str(fa.parent)]) == 0
    assert S.main(["verificar", str(fa), "--raiz", str(fa.parent)]) == 0
