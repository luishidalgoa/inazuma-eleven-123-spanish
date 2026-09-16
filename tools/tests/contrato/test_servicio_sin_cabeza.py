"""Ciclo completo de ServicioToolkit sin cabeza sobre el proyecto sintético (sin ROM, sin red)."""

from __future__ import annotations

import json
from pathlib import Path

from ie123kit.nucleo import util
from ie123kit.nucleo.tipos import Resultado
from ie123kit.servicio import esquemas
from ie123kit.servicio.api import ServicioToolkit, SolicitudConstruccion
from ie123kit.servicio.trabajos import Trabajos

OBJETIVO = "falso"


def _ok_serializable(res: Resultado) -> dict:
    assert isinstance(res, Resultado)
    datos = res.to_json()
    json.dumps(datos, ensure_ascii=False)
    assert esquemas.validar(datos, "resultado") == []
    return datos


def test_ciclo_completo(servicio: ServicioToolkit, proyecto_sintetico, tmp_path: Path) -> None:
    res_obj = servicio.objetivos()
    _ok_serializable(res_obj)
    assert res_obj.ok
    ids = [o["id"] for o in res_obj.datos["objetivos"]]
    assert OBJETIVO in ids

    res_act = servicio.activos(OBJETIVO)
    _ok_serializable(res_act)
    assert res_act.ok and res_act.datos["activos"]
    activo = res_act.datos["activos"][0]

    destino = tmp_path / "exportado"
    res_exp = servicio.exportar(OBJETIVO, [activo["id"]], destino)
    _ok_serializable(res_exp)
    assert res_exp.ok and res_exp.artefactos
    exportado = Path(res_exp.artefactos[0])
    assert exportado.is_file()

    antes = util.sha256_arbol(proyecto_sintetico.raiz)
    res_sim = servicio.importar(OBJETIVO, activo["id"], exportado, simular=True)
    _ok_serializable(res_sim)
    assert res_sim.ok and res_sim.datos["simulado"] is True
    assert util.sha256_arbol(proyecto_sintetico.raiz) == antes

    res_imp = servicio.importar(OBJETIVO, activo["id"], exportado, simular=False)
    _ok_serializable(res_imp)
    assert res_imp.ok and res_imp.artefactos
    assert Path(res_imp.artefactos[0]).is_file()
    assert util.sha256_arbol(proyecto_sintetico.raiz) != antes


def test_operaciones_aplazadas_no_soportadas(servicio: ServicioToolkit, tmp_path: Path) -> None:
    solicitud = SolicitudConstruccion(base="probe_ie1_v67", objetivos=("ie1",), capas=(), salida="probe_ie1_v68")
    resultados = {
        "construir": servicio.construir(solicitud),
        "verificar": servicio.verificar("probe_ie1_v67"),
        "instalar": servicio.instalar("probe_ie1_v67"),
        "parche": servicio.parche(tmp_path / "a.3ds", tmp_path / "b.3ds", tmp_path / "c.xdelta"),
    }
    for nombre, res in resultados.items():
        _ok_serializable(res)
        assert not res.ok, nombre
        assert [i.codigo for i in res.incidencias] == ["NOT_SUPPORTED"], nombre


def _base_lista(proyecto_sintetico) -> SolicitudConstruccion:
    """Crea la candidata base en el proyecto sintético y devuelve la solicitud de construcción."""
    from fa_sintetico import escribir_fa
    from juego_falso import FICHEROS

    base = Path(proyecto_sintetico.candidata("probe_ie1_v67"))
    base.mkdir(parents=True, exist_ok=True)
    escribir_fa(base / "archive.fa", FICHEROS)
    return SolicitudConstruccion(base="probe_ie1_v67", objetivos=(OBJETIVO,), capas=(), salida="probe_ie1_v68")


def test_construir_no_enmascara_un_typeerror_del_constructor(servicio, proyecto_sintetico, monkeypatch) -> None:
    """Un TypeError INTERNO del constructor es un fallo, nunca un reintento sin aportaciones.

    Regresión de F2.2: el `except TypeError` que reintentaba con la firma corta convertía
    cualquier fallo del constructor (una aportación mal formada, un reempaquetado roto) en una
    candidata construida sin aportaciones y devuelta como `ok`.
    """
    from ie123kit.nucleo.construir import candidata as constructor

    solicitud = _base_lista(proyecto_sintetico)
    llamadas: list[dict] = []

    def explota(base, salida, **kw):
        llamadas.append(kw)
        raise TypeError("aportación no válida (se esperaba un dict): 'x'")

    monkeypatch.setattr(constructor, "construir", explota)
    res = servicio.construir(solicitud)
    _ok_serializable(res)
    assert not res.ok
    assert len(llamadas) == 1, "se ha reintentado en silencio"
    assert "aportación no válida" in res.incidencias[0].mensaje
    assert not Path(proyecto_sintetico.candidata("probe_ie1_v68")).exists()


def test_construir_avisa_si_el_nucleo_tiene_la_firma_vieja(servicio, proyecto_sintetico, monkeypatch) -> None:
    """Si el constructor no admite `aportaciones`, se dice; no se construye a medias."""
    from ie123kit.nucleo.construir import candidata as constructor

    solicitud = _base_lista(proyecto_sintetico)
    llamadas: list[str] = []

    def firma_vieja(base, salida, *, ui=None, capas=None, cro=None):
        llamadas.append("llamado")
        return {}

    monkeypatch.setattr(constructor, "construir", firma_vieja)
    res = servicio.construir(solicitud)
    _ok_serializable(res)
    assert not res.ok and llamadas == []
    assert "aportaciones" in res.incidencias[0].mensaje


def _capa(raiz: Path, nombre: str, *, extra=None, cro=(), eventos=None) -> Path:
    """Capa de work/ con lo que aporta: extra/<rel>, romfs/cro/*.cro y events/ | events_mch/."""
    capa = raiz / "work" / "ie1" / "capas" / "v68" / nombre
    for rel, datos in (extra or {}).items():
        destino = capa / "extra" / rel
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(datos)
    for nombre_cro in cro:
        destino = capa / "romfs" / "cro" / nombre_cro
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(f"{nombre_cro} de {nombre}".encode())
    for pack, ids in (eventos or {}).items():
        carpeta = capa / {"eve": "events", "mch": "events_mch"}[pack]
        carpeta.mkdir(parents=True, exist_ok=True)
        for eid in ids:
            (carpeta / f"{eid}.ssd").write_bytes(b"SSD\0")
    capa.mkdir(parents=True, exist_ok=True)
    return capa


def _kw_de_construir(servicio, proyecto_sintetico, monkeypatch, capas) -> dict:
    """Llama a `construir` con esas capas y devuelve los kwargs que recibe el constructor."""
    from ie123kit.nucleo.construir import candidata as constructor

    solicitud = _base_lista(proyecto_sintetico)
    capturado: list[dict] = []

    def capturar(base, salida, *, ui=None, capas=None, cro=None, aportaciones=None,
                 rehusar_sobrescribir=True):
        capturado.append({"base": base, "salida": salida, "ui": ui, "capas": capas, "cro": cro,
                          "aportaciones": aportaciones})
        raise RuntimeError("no se construye de verdad en esta prueba")

    monkeypatch.setattr(constructor, "construir", capturar)
    res = servicio.construir(
        SolicitudConstruccion(base=solicitud.base, objetivos=solicitud.objetivos,
                              capas=tuple(str(c) for c in capas), salida=solicitud.salida)
    )
    _ok_serializable(res)
    assert capturado, [i.mensaje for i in res.incidencias]
    return capturado[0]


def test_construir_toma_de_cada_capa_todo_lo_que_aporta(servicio, proyecto_sintetico, monkeypatch) -> None:
    """Regresión de F2.2: solo la PRIMERA capa hacía de `ui`; de las demás se cogía `extra/`.

    Sus `romfs/cro/*.cro` y sus `events/`/`events_mch/` se tiraban sin incidencia y la candidata
    incompleta se daba por buena.
    """
    raiz = proyecto_sintetico.raiz
    primera = _capa(raiz, "titulo", extra={"a/uno.bin": b"de la primera"},
                    cro=["ina_main1.cro"], eventos={"eve": [10010001]})
    segunda = _capa(raiz, "menus", cro=["ina_menu.cro", "ina_main2.cro"],
                    eventos={"mch": [10020001]})

    kw = _kw_de_construir(servicio, proyecto_sintetico, monkeypatch, [primera, segunda])

    # Una aportación por capa, en orden, y detrás la del objetivo (aquí, vacía).
    aportes = kw["aportaciones"][:2]
    assert [a["extra"] for a in aportes] == [primera / "extra", segunda / "extra"]
    assert [sorted(p.name for p in a["cro"]) for a in aportes] == [
        ["ina_main1.cro"], ["ina_main2.cro", "ina_menu.cro"],
    ]
    assert aportes[0]["eventos"] == {"eve": primera / "events"}
    assert aportes[1]["eventos"] == {"mch": segunda / "events_mch"}
    # Y ya no queda nada en los parámetros viejos que se aplicaban solo a la primera capa.
    assert kw["ui"] is None and kw["capas"] is None


def test_construir_arrastra_las_cro_de_la_base_que_ninguna_capa_rehace(
        servicio, proyecto_sintetico, monkeypatch) -> None:
    raiz = proyecto_sintetico.raiz
    cro_base = Path(proyecto_sintetico.candidata("probe_ie1_v67")) / "romfs" / "cro"
    cro_base.mkdir(parents=True, exist_ok=True)
    for nombre in ("ina_main1.cro", "ina_menu.cro"):
        (cro_base / nombre).write_bytes(f"{nombre} de la base".encode())
    capa = _capa(raiz, "menus", cro=["ina_menu.cro"])

    kw = _kw_de_construir(servicio, proyecto_sintetico, monkeypatch, [capa])

    # La capa rehace ina_menu (gana ella) y la ina_main1 de la base viaja para no perderse.
    assert [p.name for p in kw["cro"]] == ["ina_main1.cro"]
    assert [p.name for a in kw["aportaciones"] for p in a["cro"]] == ["ina_menu.cro"]


def test_construir_rechaza_una_capa_que_no_aporta_nada(servicio, proyecto_sintetico) -> None:
    capa = proyecto_sintetico.raiz / "work" / "ie1" / "capas" / "v68" / "vacia"
    capa.mkdir(parents=True)
    (capa / "apply.py").write_text("# sin ejecutar\n", encoding="utf-8")
    solicitud = _base_lista(proyecto_sintetico)

    res = servicio.construir(SolicitudConstruccion(
        base=solicitud.base, objetivos=solicitud.objetivos, capas=(str(capa),), salida=solicitud.salida))

    _ok_serializable(res)
    assert not res.ok and "no aporta nada" in res.incidencias[0].mensaje
    assert not Path(proyecto_sintetico.candidata("probe_ie1_v68")).exists()


def test_construir_traduce_la_aportacion_del_objetivo(servicio, proyecto_sintetico, monkeypatch) -> None:
    """La `Aportacion` de un objetivo se traduce a la forma del constructor (y no se tira nada).

    Sin traducción, `construir --objetivos ie1` moría en `_normalizar_aportaciones` porque
    `nucleo.juego.Aportacion` no es un dict.
    """
    from ie123kit.nucleo.juego import Aportacion

    eventos = proyecto_sintetico.raiz / "work" / "ie1" / "eventos_del_objetivo"
    eventos.mkdir(parents=True)
    cro = proyecto_sintetico.raiz / "work" / "ie1" / "ina_main2.cro"
    cro.write_bytes(b"cro del objetivo")
    monkeypatch.setattr(type(servicio.juegos[OBJETIVO]), "aportaciones",
                        lambda self, ws, capas=None, **kw: Aportacion(
                            eventos={"mch": eventos}, romfs_sueltos={"cro/ina_main2.cro": cro}),
                        raising=False)

    kw = _kw_de_construir(servicio, proyecto_sintetico, monkeypatch, [])

    assert kw["aportaciones"] == [
        {"objetivo": OBJETIVO, "extra": None, "eventos": {"mch": eventos}, "cro": [cro]},
    ]


def test_construir_dice_lo_que_la_aportacion_usa_y_el_constructor_no_sabe_aplicar(
        servicio, proyecto_sintetico, monkeypatch) -> None:
    from ie123kit.nucleo.juego import Aportacion

    monkeypatch.setattr(type(servicio.juegos[OBJETIVO]), "aportaciones",
                        lambda self, ws, capas=None, **kw: Aportacion(entradas_fa={"a/uno.bin": b"x"}),
                        raising=False)
    solicitud = _base_lista(proyecto_sintetico)

    res = servicio.construir(solicitud)

    _ok_serializable(res)
    assert not res.ok and "entradas_fa" in res.incidencias[0].mensaje
    assert not Path(proyecto_sintetico.candidata("probe_ie1_v68")).exists()


def test_doctor_serializable(servicio: ServicioToolkit) -> None:
    res = servicio.doctor()
    datos = _ok_serializable(res)
    assert datos["datos"]["api_version"] == servicio.API_VERSION


def test_objetivo_desconocido_da_fallo_controlado(servicio: ServicioToolkit, tmp_path: Path) -> None:
    res = servicio.activos("no_existe")
    _ok_serializable(res)
    assert not res.ok
    mensaje = res.incidencias[0].mensaje
    assert "no_existe" in mensaje and OBJETIVO in mensaje


def test_enviar_trabajo_escribe_eventos_jsonl(proyecto_sintetico, juego_falso, tmp_path: Path) -> None:
    from ie123kit.servicio.api import descubrir_juegos

    dir_eventos = tmp_path / "trabajos"
    with Trabajos(dir_eventos=dir_eventos, max_hilos=1) as trabajos:
        servicio = ServicioToolkit(
            proyecto_sintetico,
            juegos=descubrir_juegos(extra={OBJETIVO: juego_falso}),
            trabajos=trabajos,
        )
        activo = servicio.activos(OBJETIVO).datos["activos"][0]
        res = servicio.enviar_trabajo("exportar", objetivo=OBJETIVO, ids=[activo["id"]],
                                      destino=tmp_path / "trabajo_salida")
        _ok_serializable(res)
        assert res.ok
        id_trabajo = res.datos["trabajo"]
        trabajo = trabajos.esperar(id_trabajo, timeout=30)
        assert str(trabajo.estado) == "hecho", trabajo.to_json()

    fichero = dir_eventos / f"{id_trabajo}.jsonl"
    assert fichero.is_file()
    lineas = [json.loads(linea) for linea in fichero.read_text(encoding="utf-8").splitlines() if linea.strip()]
    assert lineas
    for linea in lineas:
        assert esquemas.validar(linea, "evento_trabajo") == [], linea


# --- F2.3: el inventario funde el escaneo del archive.fa con lo que aporta el juego ---


def _juego_con_activos_fuera_del_fa():
    """Juego falso que, como harán ie1 y juego_principal, aporta lo que NO vive en el archive.fa.

    Contrato de F2.3: `activos()` devuelve SOLO las CRO sueltas, los `.SAD` y el ExeFS; el
    `archive.fa` lo escanea el registro. El servicio tiene que entregar la unión de ambos.
    """
    from juego_falso import JuegoFalso

    from ie123kit.nucleo.tipos import AssetRef, componer_id

    def ref(tipo: str, ruta: str) -> AssetRef:
        return AssetRef(id=componer_id(OBJETIVO, tipo, ruta), objetivo=OBJETIVO, tipo=tipo,
                        ruta_romfs=ruta, cadena_contenedores=(), tamano=1, editable=True)

    class JuegoConActivosFuera(JuegoFalso):
        FUERA = (ref("literal_cro", "cro/ina_menu.cro"), ref("binario", "exefs/icon.icn"))

        def activos(self, ws, tipo=None, filtro=None):
            # Repite a propósito el PRIMER activo del archive.fa: el servicio lo deduplica.
            repetido = super().activos(ws)[:1]
            refs = [*repetido, *self.FUERA]
            if tipo is not None:
                refs = [r for r in refs if r.tipo == tipo]
            return refs

    return JuegoConActivosFuera()


def test_activos_funde_el_registro_con_lo_que_aporta_el_juego(proyecto_sintetico) -> None:
    from ie123kit.servicio.api import ServicioToolkit, descubrir_juegos

    juego = _juego_con_activos_fuera_del_fa()
    servicio = ServicioToolkit(proyecto_sintetico, juegos=descubrir_juegos(extra={OBJETIVO: juego}))

    res = servicio.activos(OBJETIVO)

    _ok_serializable(res)
    assert res.ok
    ids = [a["id"] for a in res.datos["activos"]]
    assert len(ids) == len(set(ids)), f"hay ids repetidos: {ids}"
    # Lo del archive.fa (por el registro) y lo de fuera (por el juego), en ese orden.
    assert any(a["ruta_romfs"].startswith("falso/") for a in res.datos["activos"])
    rutas = [a["ruta_romfs"] for a in res.datos["activos"]]
    assert "cro/ina_menu.cro" in rutas
    assert "exefs/icon.icn" in rutas
    assert rutas.index("cro/ina_menu.cro") > max(i for i, r in enumerate(rutas) if r.startswith("falso/"))


def test_un_id_de_fuera_del_archive_fa_se_resuelve(proyecto_sintetico) -> None:
    """Sin la fusión, un id que solo aporta el juego era «activo desconocido» para el servicio."""
    from ie123kit.servicio.api import ServicioToolkit, descubrir_juegos

    juego = _juego_con_activos_fuera_del_fa()
    servicio = ServicioToolkit(proyecto_sintetico, juegos=descubrir_juegos(extra={OBJETIVO: juego}))

    for ref in juego.FUERA:
        assert servicio._resolver(juego, ref.id) is not None, ref.id
    assert servicio._resolver(juego, "falso:literal_cro:cro/no_existe.cro") is None


def test_entradas_fa_de_un_arbol_en_disco_se_colapsan_a_extra(
        servicio, proyecto_sintetico, monkeypatch) -> None:
    """`entradas_fa` con una raíz común ES una carpeta `extra/`: ya no se rechaza ni se tira."""
    from ie123kit.nucleo.juego import Aportacion

    raiz = proyecto_sintetico.raiz / "work" / "juego_principal" / "exportaciones" / "menu"
    entradas = {}
    for rel in ("menu/uno.ctpk", "message/dos.str"):
        destino = raiz / rel
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(b"x")
        entradas[rel] = destino
    monkeypatch.setattr(type(servicio.juegos[OBJETIVO]), "aportaciones",
                        lambda self, ws, capas=None, **kw: Aportacion(entradas_fa=entradas),
                        raising=False)

    kw = _kw_de_construir(servicio, proyecto_sintetico, monkeypatch, [])

    assert kw["aportaciones"] == [
        {"objetivo": OBJETIVO, "extra": raiz, "eventos": {}, "cro": []},
    ]


def test_entradas_fa_sin_raiz_comun_se_sigue_reportando(servicio, proyecto_sintetico,
                                                        monkeypatch) -> None:
    """Bytes en memoria o rutas sin raíz común: se dice, no se tira en silencio."""
    from ie123kit.nucleo.juego import Aportacion

    monkeypatch.setattr(type(servicio.juegos[OBJETIVO]), "aportaciones",
                        lambda self, ws, capas=None, **kw: Aportacion(entradas_fa={"menu/uno.ctpk": b"x"}),
                        raising=False)

    res = servicio.construir(_base_lista(proyecto_sintetico))

    _ok_serializable(res)
    assert not res.ok and "entradas_fa" in res.incidencias[0].mensaje
