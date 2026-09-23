"""Los envoltorios de las capas de fuentes, menús, CRO y teclado (F2.6, #55) delegan en ie123kit.

La F2.6 retira de las capas vigentes de ``work/`` el código de motor ya portado y deja cada módulo
como envoltorio fino del paquete. Por cada módulo envuelto se comprueba:

a) que sigue exponiendo toda su superficie pública anterior (los nombres que usan sus hermanos
   ``apply.py``, ``validate.py``, ``validar.py``, ``previsualizar.py``, ``explora*.py`` y la capa
   ``nombres/nombres_compactos``), con el mismo tipo y la misma forma de retorno;
b) que delega en el paquete y da el mismo resultado que la salida YA ESCRITA en la capa
   (``extra/``, ``romfs/cro``, ``registro.json``, ``informe.json``): nunca se reescribe la capa.

Módulos cubiertos:

- ``ie1/capas/fuentes/bigramas_ritmo/ritmo.py`` y ``escaneo_literales.py``
  -> ``nucleo.fuentes.ritmo``, ``nucleo.fuentes.bigramas`` y ``nucleo.texto.escaneo``;
- ``ie2/shared/capas/menus_cro/menus/modelo23.py``
  -> ``nucleo.fuentes.rebanadas`` + ``ie2.comun.menus``;
- ``ie2/shared/capas/menus_cro/ancho_dialogo/apply.py`` -> ``ie2.comun.cro`` +
  ``nucleo.ejecutable.parches_cro``;
- ``ie2/shared/capas/teclado/teclado/apply.py`` -> ``ie2.comun.teclado`` +
  ``nucleo.contenedores.spf`` + ``nucleo.texto.teclado``.

Tipografía bloqueada (CLAUDE.md, AGENTS.md): todo se hace en memoria y ninguna fuente cambia. Si un
dibujo o una métrica no coincide con lo que la capa dejó escrito, el envoltorio está mal.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

from ie123kit.nucleo.config.raiz import find_root

pytestmark = pytest.mark.requiere_rom

BIGRAMAS = "work/ie1/capas/fuentes/bigramas_ritmo"
MENUS = "work/ie2/shared/capas/menus_cro/menus"
ANCHO = "work/ie2/shared/capas/menus_cro/ancho_dialogo"
TECLADO = "work/ie2/shared/capas/teclado/teclado"


@pytest.fixture(scope="module")
def raiz() -> Path:
    return find_root()


def _capa(raiz: Path, rel: str) -> Path:
    ruta = raiz / rel
    if not ruta.exists():
        pytest.skip(f"falta recurso local: {rel}")
    return ruta


def _modulo(nombre: str, ruta: Path):
    """Carga un módulo de capa por ruta (su carpeta va al path, como cuando se ejecuta la capa)."""
    if not ruta.is_file():
        pytest.skip(f"falta recurso local: {ruta.name}")
    sys.path.insert(0, str(ruta.parent))
    try:
        spec = importlib.util.spec_from_file_location(nombre, ruta)
        m = importlib.util.module_from_spec(spec)
        sys.modules[nombre] = m
        spec.loader.exec_module(m)
    finally:
        sys.path.remove(str(ruta.parent))
    return m


def _superficie(modulo, nombres) -> None:
    faltan = [n for n in nombres if not hasattr(modulo, n)]
    assert not faltan, f"{modulo.__name__}: falta superficie pública {faltan}"


def _leer_json(ruta: Path):
    return json.loads(ruta.read_text(encoding="utf-8"))


def _decodificar(body: bytes) -> list[str]:
    """Cuerpo Shift-JIS -> caracteres (el mismo troceo que hace la capa de menús)."""
    out, i = [], 0
    while i < len(body):
        b = body[i]
        if 0x81 <= b <= 0x9F or 0xE0 <= b <= 0xFC:
            out.append(body[i : i + 2].decode("cp932"))
            i += 2
        else:
            out.append(chr(b))
            i += 1
    return out


# --------------------------------------------------------------------------- IE1 v89: ritmo


@pytest.fixture(scope="module")
def ritmo_capa(raiz):
    return _modulo("ritmo_capa_f26", _capa(raiz, BIGRAMAS) / "ritmo.py")


def test_ritmo_superficie_y_delegacion(ritmo_capa) -> None:
    from ie123kit.nucleo.fuentes import ritmo as P

    _superficie(
        ritmo_capa,
        [
            "CELDA",
            "SOLIDO",
            "ESP",
            "PAL_MIN",
            "INF",
            "IZQ",
            "DER",
            "Maqueta",
            "ParametrosRitmo",
            "IE1_FONT12",
            "texto",
            "variante",
            "coste_hueco",
            "particion",
            "huecos",
            "medir",
            "metricas",
        ],
    )
    for nombre in (
        "Maqueta",
        "ParametrosRitmo",
        "IE1_FONT12",
        "texto",
        "variante",
        "coste_hueco",
        "particion",
        "huecos",
        "medir",
        "metricas",
    ):
        assert getattr(ritmo_capa, nombre) is getattr(P, nombre), nombre
    # las constantes de la v89 son los campos de los parámetros de IE1
    assert (ritmo_capa.CELDA, ritmo_capa.SOLIDO, ritmo_capa.ESP, ritmo_capa.PAL_MIN) == (15, 5, 5, 4)
    assert (ritmo_capa.INF, ritmo_capa.IZQ, ritmo_capa.DER) == (P.INF, P.IZQ, P.DER)


def test_ritmo_reproduce_las_metricas_de_la_capa(raiz, ritmo_capa) -> None:
    """`medir`/`metricas` del paquete dan el dibujo y la CWDH que la capa escribió en registro.json."""
    from ie123kit.nucleo.fuentes import celdas

    capa = _capa(raiz, BIGRAMAS)
    fuente = "font/FONT12.bcfnt"
    F = celdas.FuenteBCFNT.desde_bytes((capa / "extra" / fuente).read_bytes(), "FONT12.bcfnt")
    registro = _leer_json(capa / "registro.json")
    n = 0
    for e in registro["bigramas"]:
        f = e["fuentes"].get(fuente, {})
        if f.get("maqueta") != "v89":
            continue
        m = ritmo_capa.medir(F, f["glifo"])
        assert [m["D"], m["ancho"], [m["S0"], m["S1"]]] == [f["columna"], f["tinta_px"], f["solido"]], e["sjis"]
        assert list(ritmo_capa.metricas(m, e["par"])) == f["cwdh"], e["sjis"]
        assert m["medido"] is True
        n += 1
    assert n == 847


def test_ritmo_particion_reproduce_las_celdas_del_informe(raiz, ritmo_capa) -> None:
    """La partición DP del paquete devuelve las mismas casillas que la capa dejó en informe.json."""
    from ie123kit.nucleo.fuentes import celdas

    capa = _capa(raiz, BIGRAMAS)
    F = celdas.FuenteBCFNT.desde_bytes((capa / "extra/font/FONT12.bcfnt").read_bytes(), "FONT12.bcfnt")
    mq = ritmo_capa.Maqueta(F, celdas.codepoint)
    registro = _leer_json(capa / "registro.json")
    informe = _leer_json(capa / "informe.json")
    claves = {e.get("clave", e["par"]) for e in registro["bigramas"]}
    n = 0
    for tipo in ("descripcion", "objetivo"):
        for cambio in informe[tipo]:
            tramo: list[str] = []
            for c in cambio["celdas"].split("|") + ["¤"]:
                if c != "¤":
                    tramo.append(c)
                    continue
                if tramo:
                    coste, casillas = ritmo_capa.particion("".join(tramo), mq, claves.__contains__)
                    assert coste < ritmo_capa.INF
                    assert [ritmo_capa.texto(k) for k in casillas] == tramo
                    n += 1
                tramo = []
    assert n == 2384


# --------------------------------------------------------------------------- IE1 v89: escaneo


def test_escaneo_literales_superficie_y_delegacion(raiz) -> None:
    from ie123kit.nucleo.texto import escaneo

    capa = _capa(raiz, BIGRAMAS)
    mod = _modulo("escaneo_literales_capa_f26", capa / "escaneo_literales.py")
    _superficie(mod, ["valido2", "en_cadena", "apariciones", "binarios", "main", "BASE", "CAND_CRO"])
    for nombre in ("valido2", "en_cadena", "apariciones"):
        assert getattr(mod, nombre) is getattr(escaneo, nombre), nombre
    if not (mod.BASE / "exefs/code.bin").exists():
        pytest.skip("faltan los binarios de base_3ds")
    literales = _leer_json(capa / "literales.json")
    # si probe_ie1_v88 ya no existe, `binarios()` solo devuelve base_3ds y la comparación se restringe
    fuentes = mod.binarios()
    res = mod.apariciones(fuentes, list(literales))
    assert res == {c: {k: v for k, v in ap.items() if k in fuentes} for c, ap in literales.items()}


# --------------------------------------------------------------------------- IE2 v23: menús


def test_modelo23_superficie_y_delegacion(raiz) -> None:
    from ie123kit.ie2.comun import menus
    from ie123kit.nucleo.fuentes import rebanadas as P

    mod = _modulo("modelo23_capa_f26", _capa(raiz, MENUS) / "modelo23.py")
    _superficie(
        mod,
        [
            "INF",
            "CAJA",
            "glifo",
            "pintar",
            "pintar_fijo",
            "tira",
            "columnas",
            "huecos",
            "resolver",
            "concretar",
            "metricas_rebanada",
            "Reparto",
            "ParametrosReparto",
            "tira_nucleo",
            "rebanar",
            "existentes",
            "frente_bloque",
            "elegir",
            "escribir_glifo",
            "escribir_rebanada",
            "huella",
            "PARAM",
            "PARAM_PAQUETE",
            "LETRAS",
            "F12",
            "F8",
            "PASO8",
            "HUECO8",
            "repartir",
        ],
    )
    for nombre in (
        "INF",
        "CAJA",
        "glifo",
        "pintar",
        "pintar_fijo",
        "tira",
        "columnas",
        "huecos",
        "resolver",
        "concretar",
        "metricas_rebanada",
        "Reparto",
        "ParametrosReparto",
        "tira_nucleo",
        "rebanar",
        "existentes",
        "frente_bloque",
        "elegir",
        "escribir_glifo",
        "escribir_rebanada",
        "huella",
    ):
        assert getattr(mod, nombre) is getattr(P, nombre), nombre
    assert (mod.F12, mod.F8, mod.PASO8, mod.HUECO8) == (menus.F12, menus.F8, menus.PASO8, menus.HUECO8)
    assert mod.LETRAS == menus.LETRAS and mod.repartir is menus.repartir
    # PARAM conserva la forma de diccionario de la capa con los valores del paquete
    assert set(mod.PARAM) == set(menus.PARAM)
    for f, p in menus.PARAM.items():
        assert mod.PARAM[f] == {
            "nombre": p.nombre,
            "ancho": p.ancho,
            "umbral": p.umbral,
            "permitidos": p.permitidos,
            "inicio": dict(p.inicio),
        }


def test_modelo23_reproduce_los_huecos_del_informe(raiz) -> None:
    """`pintar`/`huecos` del paquete dan los huecos y la primera columna que la capa dejó escritos."""
    from ie123kit.nucleo.fuentes import celdas

    capa = _capa(raiz, MENUS)
    mod = _modulo("modelo23_capa_f26_b", capa / "modelo23.py")
    F = {f: celdas.FuenteBCFNT.desde_bytes((capa / "extra" / f).read_bytes(), Path(f).name) for f in (mod.F12, mod.F8)}
    informe = _leer_json(capa / "informe.json")
    n = 0
    for nombre, bloque in informe["bloques"].items():
        f = mod.F12 if bloque["fuente"] == "FONT12" else mod.F8
        umbral = mod.PARAM[f]["umbral"]
        for fila in bloque["entradas"]:
            body = bytes.fromhex(fila["despues_hex"])
            gis = [F[f].gi(ord(ch)) for ch in _decodificar(body)]
            assert None not in gis, (nombre, fila["texto"])
            px, _pos = mod.pintar(F[f], mod.CAJA[f], gis)
            tinta = {k: v for k, v in px.items() if v >= umbral}
            assert mod.huecos(tinta) == fila["huecos"], (nombre, fila["texto"])
            assert min(x for x, _ in tinta) == fila["primera_columna"], (nombre, fila["texto"])
            n += 1
    assert n == len([1 for b in informe["bloques"].values() for _ in b["entradas"]]) > 0


# --------------------------------------------------------------------------- IE2 v15: ancho del diálogo


def test_ancho_dialogo_superficie_y_cro_identica(raiz) -> None:
    from ie123kit.ie2.comun import cro as CRO
    from ie123kit.nucleo.ejecutable import parches_cro as PC

    capa = _capa(raiz, ANCHO)
    base = capa.parent / "cofres/romfs/cro/ina_main2.cro"
    salida = capa / "romfs/cro/ina_main2.cro"
    if not base.is_file() or not salida.is_file():
        pytest.skip("faltan las CRO de la capa (cofres / ancho_dialogo)")
    mod = _modulo("ancho_dialogo_capa_f26", capa / "apply.py")
    _superficie(
        mod,
        [
            "PARCHES",
            "CONTEXTO",
            "TABLAS",
            "EVENTOS",
            "u32",
            "sha",
            "parches_cro",
            "comprobar_reloc",
            "parchear_cro",
            "espanol",
            "palabras",
            "comprobar_cuerpo",
            "CRO_BASE",
            "CRO_OUT",
            "ANCHO",
            "MAX_CAR",
            "LINEAS",
        ],
    )
    # forma antigua: tuplas de 4 y de 3, con los mismos valores que la tabla del paquete
    assert mod.PARCHES == [(p.direccion, p.antes, p.despues, p.texto) for p in CRO.PARCHES_ANCHO_DIALOGO]
    assert mod.CONTEXTO == [(c.direccion, c.palabra, c.texto) for c in CRO.CONTEXTO_ANCHO_DIALOGO]
    assert mod.TABLAS == PC.TABLAS_PARCHES

    datos = base.read_bytes()
    parcheada, inf = CRO.parchear_ancho_dialogo(datos)
    assert parcheada == salida.read_bytes(), "la CRO del paquete no es la que dejó la capa"
    # el informe de la capa, salvo `base` (ruta de cuando la capa vivía en work/ie2/shared/capas/v09)
    escrito = _leer_json(capa / "informe.json")["cro"]
    nuestro = json.loads(json.dumps({"base": str(mod.CRO_BASE), **inf}))  # tuplas -> listas, como en JSON
    assert {k: v for k, v in nuestro.items() if k != "base"} == {k: v for k, v in escrito.items() if k != "base"}
    # los envoltorios de lectura devuelven la misma forma que antes
    tablas, segs = mod.parches_cro(datos)
    assert set(tablas) == set(PC.TABLAS_PARCHES) and len(segs) > 0
    reloc, resumen, seghex = mod.comprobar_reloc(datos)
    assert set(reloc) == {hex(p.direccion) for p in CRO.PARCHES_ANCHO_DIALOGO}
    assert all(not v["choques"] for v in reloc.values())
    assert set(resumen) == set(PC.TABLAS_PARCHES) and len(seghex) == len(segs)


# --------------------------------------------------------------------------- IE2: teclado en SPF_


def test_teclado_superficie_y_paquetes_identicos(raiz) -> None:
    from ie123kit.ie2.comun import teclado as T
    from ie123kit.nucleo.contenedores import spf
    from ie123kit.nucleo.contenedores.fa import FaArchive
    from ie123kit.nucleo.texto import teclado as TT

    capa = _capa(raiz, TECLADO)
    mod = _modulo("teclado_capa_f26", capa / "apply.py")
    _superficie(mod, ["BASE", "JP", "PAQUETES", "MODOS", "IE1", "ROWS", "sha", "sfp_entradas", "patch_map", "main"])
    assert mod.PAQUETES == T.PAQUETES and mod.MODOS == T.MODOS
    assert mod.patch_map is TT.parchear_fcode
    assert mod.ROWS == list(TT.FILAS_LATINAS)

    if not mod.JP.is_file():
        pytest.skip("falta archive.fa de base_3ds")
    # la base de la capa (probe_ie2_v18) llevaba estos paquetes sin tocar; si ya no existe se usa la
    # ROM japonesa, que la propia capa comprobó idéntica (base_sha256_entradas del informe)
    jp = FaArchive(str(mod.JP))
    arc = FaArchive(str(mod.BASE)) if mod.BASE.is_file() else jp
    informe = _leer_json(capa / "informe.json")
    for ruta in mod.PAQUETES:
        escrito = capa / "extra" / ruta
        if not escrito.is_file():
            pytest.skip(f"falta la salida de la capa: {ruta}")
        comp = arc.read(ruta)
        assert mod.sha(comp) == informe["base_sha256_entradas"][ruta], ruta
        plano_jp = spf.descomprimir(jp.read(ruta))
        nuevo, inf = T.paquete_latino(comp, original=lambda n, p=plano_jp: spf.leer(p, n))
        assert nuevo == escrito.read_bytes(), f"{ruta}: el paquete no da el .SPF_ de la capa"
        # la tabla de nombres no cambia y `sfp_entradas` sigue devolviendo (offset, tamaño)
        ent = mod.sfp_entradas(spf.descomprimir(nuevo))
        assert ent == mod.sfp_entradas(spf.descomprimir(comp))
        assert all(isinstance(v, tuple) and len(v) == 2 for v in ent.values())
        de_la_capa = informe["paquetes"][ruta]
        for clave in ("bytes_antes", "bytes_despues", "sha256", "descomprimido", "intactas"):
            assert inf[clave] == de_la_capa[clave], (ruta, clave)
        for nombre in mod.MODOS:
            for clave in ("offset", "bytes", "modo", "sha256_antes", "sha256_despues"):
                assert inf["entradas"][nombre][clave] == de_la_capa["entradas"][nombre][clave], (ruta, nombre, clave)
