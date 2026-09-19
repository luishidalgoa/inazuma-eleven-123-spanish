"""Equivalencia de ie123kit.nucleo.construir.candidata con tools/build_ui_revision.py (congelado)."""
import ast
import json
import os
import struct
import subprocess
import sys
from pathlib import Path

import pytest

from ie123kit.nucleo.config.raiz import find_root
from ie123kit.nucleo.construir import candidata as C

RAIZ = find_root()
CONGELADO = RAIZ / "tools" / "build_ui_revision.py"
FUNCIONES = ("digest", "archive_payload", "replace_entry", "rebuild_events")


def _fa_sintetico(ruta: Path, ficheros: dict[str, bytes]) -> Path:
    """Escribe un contenedor B123 mínimo que FaArchive sabe recorrer."""
    carpetas: dict[str, list[tuple[str, bytes]]] = {}
    for rel, datos in ficheros.items():
        carpeta, _, nombre = rel.rpartition("/")
        carpetas.setdefault(carpeta + "/" if carpeta else "", []).append((nombre, datos))
    nombres, datos_blob, de, fe = bytearray(), bytearray(), bytearray(), bytearray()
    primero = 0
    for carpeta, lista in carpetas.items():
        dir_name_off = len(nombres)
        nombres += carpeta.encode("ascii") + b"\0"
        name_base = len(nombres)
        for nombre, datos in lista:
            fe += struct.pack("<IIII", 0, len(nombres) - name_base, len(datos_blob), len(datos))
            nombres += nombre.encode("ascii") + b"\0"
            datos_blob += datos
        de += struct.pack("<IHHIIII", 0, len(lista), 0, name_base, primero, 0, dir_name_off)
        primero += len(lista)
    de_off = 32
    fe_off = de_off + len(de)
    name_off = fe_off + len(fe)
    data_off = name_off + len(nombres)
    cabecera = b"B123" + struct.pack("<5i", de_off, de_off, fe_off, name_off, data_off)
    cabecera += struct.pack("<HHI", len(carpetas), 0, primero)
    ruta.write_bytes(cabecera + de + fe + nombres + datos_blob)
    return ruta


def _preparar(tmp_path):
    base = _fa_sintetico(tmp_path / "base.fa", {"a/uno.bin": b"uno" * 5, "b/dos.bin": b"dos", "c/tres.bin": b"t"})
    ui = tmp_path / "ui"
    (ui / "romfs/cro").mkdir(parents=True)
    (ui / "romfs/cro/ina_main1.cro").write_bytes(b"CRO sintetica" * 3)
    extra = tmp_path / "extra"
    (extra / "b").mkdir(parents=True)
    (extra / "b/dos.bin").write_bytes(b"DOS nuevo y mas largo")
    return base, ui, extra


def test_equivalencia_con_congelado(tmp_path):
    base, ui, extra = _preparar(tmp_path)
    o1 = tmp_path / "o1" / "archive.fa"
    o2 = tmp_path / "o2" / "archive.fa"
    env = dict(os.environ)
    env.pop("IE123_ROOT", None)
    r = subprocess.run([sys.executable, "-X", "utf8", "tools/build_ui_revision.py", "--base", str(base),
                        "--ui", str(ui), "--output", str(o1), "--extra", str(extra)],
                       cwd=RAIZ, env=env, capture_output=True, text=True, encoding="utf-8", check=False)
    assert r.returncode == 0, r.stderr
    report = C.construir(base, o2, ui=ui, capas=[extra])
    assert o1.read_bytes() == o2.read_bytes()
    cro = "romfs/cro/ina_main1.cro"
    assert (o1.parent / cro).read_bytes() == (o2.parent / cro).read_bytes()
    j1 = json.loads(o1.with_suffix(".build.json").read_text(encoding="utf-8"))
    j2 = json.loads(o2.with_suffix(".build.json").read_text(encoding="utf-8"))

    def normalizar(informe, salida):
        texto = json.dumps(informe, indent=2)
        return texto.replace(json.dumps(str(salida.parent.resolve()))[1:-1], "<SALIDA>")

    # F2.2 añade claves nuevas al build.json sin quitar ninguna: se comparan las del congelado.
    assert normalizar(j1, o1) == normalizar({k: j2[k] for k in j1}, o2)
    assert {"cros", "events_mch", "aportaciones"} <= set(j2)
    assert j2 == report
    with pytest.raises(FileExistsError):
        C.construir(base, o2, ui=ui, capas=[extra])


def test_errores(tmp_path):
    base, ui, _ = _preparar(tmp_path)
    with pytest.raises(FileNotFoundError):
        C.construir(tmp_path / "no.fa", tmp_path / "o" / "archive.fa", ui=ui)
    malo = tmp_path / "malo" / "z"
    malo.mkdir(parents=True)
    (malo / "x.bin").write_bytes(b"x")
    with pytest.raises(ValueError):
        C.construir(base, tmp_path / "o3" / "archive.fa", ui=ui, capas=[tmp_path / "malo"])


def _funciones(texto):
    return {n.name: ast.dump(n) for n in ast.parse(texto).body
            if isinstance(n, ast.FunctionDef) and n.name in FUNCIONES}


def test_literalidad():
    a = _funciones(CONGELADO.read_text(encoding="utf-8"))
    b = _funciones(Path(C.__file__).read_text(encoding="utf-8"))
    assert set(a) == set(FUNCIONES)
    assert a == b


def test_congelado_conserva_rutas_de_eventos():
    texto = CONGELADO.read_text(encoding="utf-8")
    assert "inazuma1/data_iz/script/eve.pkh" in texto
    assert "inazuma1/data_iz/script/eve.pkb" in texto


# -- F2.2: varias CRO, aportaciones por objetivo y «la última capa gana» ----------------


def _cro(ui: Path, nombres, sufijo=b""):
    carpeta = ui / "romfs/cro"
    carpeta.mkdir(parents=True, exist_ok=True)
    for nombre in nombres:
        (carpeta / nombre).write_bytes(nombre.encode() + sufijo)
    return carpeta


def test_cuatro_cro_descubiertas(tmp_path):
    base, ui, _ = _preparar(tmp_path)
    _cro(ui, C.CRO_CONOCIDAS)
    salida = tmp_path / "o" / "archive.fa"
    informe = C.construir(base, salida, ui=ui)
    assert [c["nombre"] for c in informe["cros"]] == sorted(C.CRO_CONOCIDAS)
    assert all(c["conocida"] for c in informe["cros"])
    for nombre in C.CRO_CONOCIDAS:
        assert (salida.parent / "romfs/cro" / nombre).is_file()
    assert informe["cro"].endswith("ina_main1.cro")


def test_aportaciones_por_objetivo_y_ultima_gana(tmp_path):
    base, ui, extra = _preparar(tmp_path)
    ap_dir = tmp_path / "ap" / "extra" / "b"
    ap_dir.mkdir(parents=True)
    (ap_dir / "dos.bin").write_bytes(b"DOS de la aportacion")
    ap_cro = tmp_path / "ap" / "romfs" / "cro"
    ap_cro.mkdir(parents=True)
    (ap_cro / "ina_main1.cro").write_bytes(b"CRO de la aportacion")
    salida = tmp_path / "o" / "archive.fa"
    informe = C.construir(
        base, salida, ui=ui, capas=[extra],
        aportaciones=[{"objetivo": "ie2.comun", "extra": tmp_path / "ap" / "extra",
                       "cro": [ap_cro / "ina_main1.cro"]}],
    )
    anuladas = informe["overridden_by_later_overlay"]
    assert {"b/dos.bin", "romfs/cro/ina_main1.cro"} == {a["entry"] for a in anuladas}
    assert {a["objetivo"] for a in anuladas} == {"ie2.comun"}
    assert (salida.parent / "romfs/cro/ina_main1.cro").read_bytes() == b"CRO de la aportacion"
    assert informe["aportaciones"][0]["objetivo"] == "ie2.comun"
    # La última capa gana también dentro del archive.
    assert b"DOS de la aportacion" in salida.read_bytes()


def test_aportaciones_como_dict_y_rehusar_sobrescribir(tmp_path):
    base, ui, _ = _preparar(tmp_path)
    salida = tmp_path / "o" / "archive.fa"
    C.construir(base, salida, ui=ui)
    informe = C.construir(base, salida, ui=ui, rehusar_sobrescribir=False,
                          aportaciones={"ie3.comun": {"extra": None}})
    assert informe["aportaciones"] == [{"objetivo": "ie3.comun", "extra": None, "eventos": {}, "cro": [], "entradas": []}]


# -- F2.2: reempaquetado de mch contra el packnum.rebuild REAL -------------------------
# Nada de dobles de `rebuild`: un doble con la firma equivocada fue justo lo que dejó pasar el
# `rebuild(pkh, pkb, Path(directorio))` (TypeError: 'WindowsPath' object is not iterable).


def _ssd(cuerpos, ident=1, argumentos=None):
    """SSD mínimo válido para ``nucleo.eventos.ssd.parse``: 1 instrucción sin argumentos."""
    argumentos = list(argumentos) if argumentos is not None else [i + 1 for i in range(len(cuerpos))]
    codigo = struct.pack("<HHHBB", ident, 8, 0x20, 0, 0)
    tabla = bytearray()
    for i, cuerpo in enumerate(cuerpos):
        longitud = (4 + len(cuerpo) + 1 + 3) & ~3
        tabla += struct.pack("<HBB", ident, argumentos[i], longitud) + cuerpo + bytes(longitud - 4 - len(cuerpo))
    total = 32 + len(codigo) + len(tabla)
    cabecera = struct.pack("<4sIIHHIIII", b"SSD\0", 0, total, 1, len(cuerpos), len(codigo), len(tabla), 0, 0)
    return bytes(cabecera + codigo + tabla)


def _packnum(payloads, align=4):
    """Par (.pkh, .pkb) PackNum con los payloads comprimidos en LZ10."""
    from ie123kit.nucleo.compresion import lz10

    pkb, entradas = bytearray(), []
    for eid, datos in payloads:
        bloque = lz10.compress(datos)
        entradas.append((eid, len(pkb), len(bloque)))
        pkb += bloque + bytes((-len(bloque)) % align)
    cabecera = b"PackNum 20260101" + struct.pack("<I", 0x30 + 12 * len(entradas))
    cabecera += bytes(0x30 - len(cabecera))
    return cabecera + b"".join(struct.pack("<III", *e) for e in entradas), bytes(pkb)


EVENTO_MCH = (10010001, 10010002)
CUERPOS_MCH = ([b"hola mundo", b"segundo texto"], [b"otro evento"])


def _base_con_mch(tmp_path):
    """Base sintética con mch.pkh/mch.pkb reales + la ui y la carpeta de .ssd preparados."""
    pkh, pkb = _packnum(list(zip(EVENTO_MCH, [_ssd(c) for c in CUERPOS_MCH])))
    base = _fa_sintetico(tmp_path / "base.fa", {
        C.RUTA_MCH[0]: pkh,
        C.RUTA_MCH[1]: pkb,
        "a/uno.bin": b"uno" * 5,
    })
    ui = tmp_path / "ui"
    (ui / "romfs/cro").mkdir(parents=True)
    (ui / "romfs/cro/ina_main1.cro").write_bytes(b"CRO sintetica")
    eventos = tmp_path / "events_mch"
    eventos.mkdir()
    return base, ui, eventos


def _leer_mch(archive: Path):
    """{id: payload descomprimido} del mch de una candidata ya construida."""
    from ie123kit.nucleo.contenedores.fa import FaArchive
    from ie123kit.nucleo.eventos import packnum

    arc = FaArchive(str(archive))
    pkh = C.archive_payload(arc, C.RUTA_MCH[0])
    pkb = C.archive_payload(arc, C.RUTA_MCH[1])
    return {eid: packnum.entry_data(pkb, off, size) for eid, off, size in packnum.parse_index(pkh)}


def test_mch_reempaqueta_con_packnum_real(tmp_path):
    base, ui, eventos = _base_con_mch(tmp_path)
    traducido = _ssd([b"HOLA MUNDO TRADUCIDO Y MAS LARGO", b"segundo texto"])
    (eventos / f"{EVENTO_MCH[0]}.ssd").write_bytes(traducido)
    salida = tmp_path / "o" / "archive.fa"

    informe = C.construir(base, salida, ui=ui,
                          aportaciones=[{"objetivo": "ie1", "eventos": {"mch": eventos}}])

    assert informe["events_mch_staged"] == 1
    entrada = informe["events_mch"][0]
    assert entrada["event"] == EVENTO_MCH[0]
    assert entrada["records_changed"] == 1
    assert entrada["new_compressed"] > entrada["old_compressed"]
    assert entrada["source_sha256"] == C.digest(eventos / f"{EVENTO_MCH[0]}.ssd")
    # Y lo que de verdad importa: el mch de la candidata lleva el texto nuevo y no toca el resto.
    leido = _leer_mch(salida)
    assert leido[EVENTO_MCH[0]] == traducido
    assert leido[EVENTO_MCH[1]] == _ssd(CUERPOS_MCH[1])


def test_mch_sin_ssd_no_toca_el_paquete(tmp_path):
    base, ui, eventos = _base_con_mch(tmp_path)
    salida = tmp_path / "o" / "archive.fa"
    informe = C.construir(base, salida, ui=ui,
                          aportaciones=[{"objetivo": "ie1", "eventos": {"mch": eventos}}])
    assert informe["events_mch"] == []
    assert _leer_mch(salida) == {e: _ssd(c) for e, c in zip(EVENTO_MCH, CUERPOS_MCH)}


def test_mch_rechaza_identidad_de_registro_cambiada(tmp_path):
    base, ui, eventos = _base_con_mch(tmp_path)
    (eventos / f"{EVENTO_MCH[0]}.ssd").write_bytes(_ssd([b"uno", b"dos"], ident=7))
    with pytest.raises(ValueError, match="instruction table changed"):
        C.construir(base, tmp_path / "o" / "archive.fa", ui=ui,
                    aportaciones=[{"objetivo": "ie1", "eventos": {"mch": eventos}}])


def test_mch_rechaza_registro_con_otro_argumento(tmp_path):
    base, ui, eventos = _base_con_mch(tmp_path)
    (eventos / f"{EVENTO_MCH[0]}.ssd").write_bytes(_ssd([b"uno", b"dos"], argumentos=[1, 9]))
    with pytest.raises(ValueError, match="record identity changed at 1"):
        C.construir(base, tmp_path / "o" / "archive.fa", ui=ui,
                    aportaciones=[{"objetivo": "ie1", "eventos": {"mch": eventos}}])


def test_mch_rechaza_numero_de_registros_distinto(tmp_path):
    base, ui, eventos = _base_con_mch(tmp_path)
    (eventos / f"{EVENTO_MCH[0]}.ssd").write_bytes(_ssd([b"solo uno"]))
    with pytest.raises(ValueError, match="record count changed"):
        C.construir(base, tmp_path / "o" / "archive.fa", ui=ui,
                    aportaciones=[{"objetivo": "ie1", "eventos": {"mch": eventos}}])


def test_mch_rechaza_id_desconocido(tmp_path):
    base, ui, eventos = _base_con_mch(tmp_path)
    (eventos / "99999999.ssd").write_bytes(_ssd([b"x"]))
    with pytest.raises(ValueError, match="unknown staged event ids"):
        C.construir(base, tmp_path / "o" / "archive.fa", ui=ui,
                    aportaciones=[{"objetivo": "ie1", "eventos": {"mch": eventos}}])


def test_mch_rechaza_nombre_que_no_es_id(tmp_path):
    base, ui, eventos = _base_con_mch(tmp_path)
    (eventos / "mapa_del_instituto.ssd").write_bytes(_ssd([b"x"]))
    with pytest.raises(Exception, match="PACKNUM_SSD_SIN_ID"):
        C.construir(base, tmp_path / "o" / "archive.fa", ui=ui,
                    aportaciones=[{"objetivo": "ie1", "eventos": {"mch": eventos}}])


def test_aportacion_no_valida_no_construye_nada(tmp_path):
    """Un TypeError de `_normalizar_aportaciones` no puede dejar una candidata a medias."""
    base, ui, _ = _base_con_mch(tmp_path)
    salida = tmp_path / "o" / "archive.fa"
    with pytest.raises(TypeError, match="aportación no válida"):
        C.construir(base, salida, ui=ui, aportaciones=["no soy un dict"])
    assert not salida.exists()


# -- F2.2: las fuentes de CRO son aditivas y los eventos se fusionan por id ------------
# Regresión doble: `cro=` excluía el descubrimiento de `<ui>/romfs/cro/*.cro` (una capa con
# ina_menu/ina_main2/ina_main3ogre perdía sus CRO en cuanto se pasaba la ina_main1 de la base) y
# de varias carpetas de eventos solo se aplicaba la última entera.


def _leer_pack(archive: Path, rutas):
    """{id: payload descomprimido} de un PackNum (eve o mch) de una candidata ya construida."""
    from ie123kit.nucleo.contenedores.fa import FaArchive
    from ie123kit.nucleo.eventos import packnum

    arc = FaArchive(str(archive))
    pkh = C.archive_payload(arc, rutas[0])
    pkb = C.archive_payload(arc, rutas[1])
    return {eid: packnum.entry_data(pkb, off, size) for eid, off, size in packnum.parse_index(pkh)}


def test_cro_declarada_se_suma_a_las_descubiertas_en_ui(tmp_path):
    base, ui, _ = _preparar(tmp_path)
    (ui / "romfs/cro/ina_main1.cro").unlink()
    _cro(ui, ("ina_menu.cro", "ina_main2.cro"), sufijo=b" de la capa")
    de_la_base = tmp_path / "base_cro"
    de_la_base.mkdir()
    (de_la_base / "ina_main1.cro").write_bytes(b"ina_main1 de la base")

    informe = C.construir(base, tmp_path / "o" / "archive.fa", ui=ui,
                          cro=[de_la_base / "ina_main1.cro"])

    assert [c["nombre"] for c in informe["cros"]] == ["ina_main1.cro", "ina_main2.cro", "ina_menu.cro"]
    salida_cro = (tmp_path / "o" / "romfs" / "cro")
    assert (salida_cro / "ina_menu.cro").read_bytes() == b"ina_menu.cro de la capa"
    assert (salida_cro / "ina_main2.cro").read_bytes() == b"ina_main2.cro de la capa"
    assert (salida_cro / "ina_main1.cro").read_bytes() == b"ina_main1 de la base"
    assert informe["cro"].endswith("ina_main1.cro")
    assert informe["overridden_by_later_overlay"] == []


def test_cro_declarada_gana_por_nombre_a_la_de_ui(tmp_path):
    base, ui, _ = _preparar(tmp_path)
    suelta = tmp_path / "suelta"
    suelta.mkdir()
    (suelta / "ina_main1.cro").write_bytes(b"la declarada gana")

    informe = C.construir(base, tmp_path / "o" / "archive.fa", ui=ui, cro=suelta / "ina_main1.cro")

    assert (tmp_path / "o" / "romfs" / "cro" / "ina_main1.cro").read_bytes() == b"la declarada gana"
    assert [a["entry"] for a in informe["overridden_by_later_overlay"]] == ["romfs/cro/ina_main1.cro"]


def test_cro_declarada_que_no_existe_es_un_error(tmp_path):
    base, ui, _ = _preparar(tmp_path)
    salida = tmp_path / "o" / "archive.fa"
    with pytest.raises(Exception, match="CRO_DECLARADA_AUSENTE"):
        C.construir(base, salida, ui=ui,
                    aportaciones=[{"objetivo": "ie2.comun", "cro": [tmp_path / "no_existe.cro"]}])
    assert not salida.exists()


EVENTO_EVE = (20010001, 20010002)
CUERPOS_EVE = ([b"hola"], [b"adios"])


def _base_con_eve(tmp_path):
    """Base sintética con eve.pkh/eve.pkb reales (el camino literal del congelado)."""
    pkh, pkb = _packnum(list(zip(EVENTO_EVE, [_ssd(c) for c in CUERPOS_EVE])))
    return _fa_sintetico(tmp_path / "base.fa", {
        C.RUTA_EVE[0]: pkh,
        C.RUTA_EVE[1]: pkb,
        "a/uno.bin": b"uno" * 5,
    })


def _capa_eventos(tmp_path, nombre, pack, preparados):
    carpeta = tmp_path / nombre / C.CARPETA_EVENTOS[pack]
    carpeta.mkdir(parents=True)
    for eid, payload in preparados.items():
        (carpeta / f"{eid}.ssd").write_bytes(payload)
    return carpeta


def test_eve_de_varias_capas_se_fusiona_por_id(tmp_path):
    base = _base_con_eve(tmp_path)
    de_a = _ssd([b"HOLA DE LA CAPA A"])
    de_b = _ssd([b"ADIOS DE LA CAPA B"])
    capa_a = _capa_eventos(tmp_path, "a", "eve", {EVENTO_EVE[0]: de_a})
    capa_b = _capa_eventos(tmp_path, "b", "eve", {EVENTO_EVE[1]: de_b})
    salida = tmp_path / "o" / "archive.fa"

    informe = C.construir(base, salida, aportaciones=[
        {"objetivo": "capa_a", "eventos": {"eve": capa_a}},
        {"objetivo": "capa_b", "eventos": {"eve": capa_b}},
    ])

    assert informe["events_staged"] == 2
    assert _leer_pack(salida, C.RUTA_EVE) == {EVENTO_EVE[0]: de_a, EVENTO_EVE[1]: de_b}
    assert [f["objetivo"] for f in informe["events_sources"]] == ["capa_a", "capa_b"]
    assert informe["overridden_by_later_overlay"] == []


def test_eve_solapado_lo_gana_la_ultima_capa_y_queda_anotado(tmp_path):
    base = _base_con_eve(tmp_path)
    capa_a = _capa_eventos(tmp_path, "a", "eve", {EVENTO_EVE[0]: _ssd([b"DE LA CAPA A"])})
    de_b = _ssd([b"DE LA CAPA B"])
    capa_b = _capa_eventos(tmp_path, "b", "eve", {EVENTO_EVE[0]: de_b})
    salida = tmp_path / "o" / "archive.fa"

    informe = C.construir(base, salida, aportaciones=[
        {"objetivo": "capa_a", "eventos": {"eve": capa_a}},
        {"objetivo": "capa_b", "eventos": {"eve": capa_b}},
    ])

    assert _leer_pack(salida, C.RUTA_EVE)[EVENTO_EVE[0]] == de_b
    assert informe["overridden_by_later_overlay"] == [
        {"entry": f"{C.RUTA_EVE[1]}#{EVENTO_EVE[0]}", "overlay": str(capa_b), "objetivo": "capa_b"},
    ]


def test_mch_de_varias_capas_se_fusiona_por_id(tmp_path):
    base, ui, _ = _base_con_mch(tmp_path)
    de_a = _ssd([b"HOLA MUNDO DE LA CAPA A", b"segundo texto"])
    de_b = _ssd([b"otro evento de la capa B"])
    capa_a = _capa_eventos(tmp_path, "a", "mch", {EVENTO_MCH[0]: de_a})
    capa_b = _capa_eventos(tmp_path, "b", "mch", {EVENTO_MCH[1]: de_b})
    salida = tmp_path / "o" / "archive.fa"

    informe = C.construir(base, salida, ui=ui, aportaciones=[
        {"objetivo": "capa_a", "eventos": {"mch": capa_a}},
        {"objetivo": "capa_b", "eventos": {"mch": capa_b}},
    ])

    assert informe["events_mch_staged"] == 2
    assert _leer_mch(salida) == {EVENTO_MCH[0]: de_a, EVENTO_MCH[1]: de_b}


def test_ui_tambien_aporta_events_mch(tmp_path):
    base, ui, _ = _base_con_mch(tmp_path)
    traducido = _ssd([b"desde la propia ui", b"segundo texto"])
    carpeta = ui / C.CARPETA_EVENTOS["mch"]
    carpeta.mkdir(parents=True)
    (carpeta / f"{EVENTO_MCH[0]}.ssd").write_bytes(traducido)

    informe = C.construir(base, tmp_path / "o" / "archive.fa", ui=ui)

    assert informe["events_mch_staged"] == 1
    assert _leer_mch(tmp_path / "o" / "archive.fa")[EVENTO_MCH[0]] == traducido
