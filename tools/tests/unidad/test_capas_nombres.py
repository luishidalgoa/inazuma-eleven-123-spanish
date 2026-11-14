"""Guardia de capas de nombres de jugador: detecta lo que el grep literal de «unitbase» no veía (sin work/ real)."""
from pathlib import Path

from ie123kit.servicio import capas_nombres as C


def _capa(work: Path, ruta: str, codigo: str, nombre: str = "apply.py", extra: dict[str, str] | None = None) -> None:
    carpeta = work / ruta
    carpeta.mkdir(parents=True, exist_ok=True)
    (carpeta / nombre).write_text(codigo, encoding="utf-8")
    for fichero, texto in (extra or {}).items():
        (carpeta / fichero).write_text(texto, encoding="utf-8")


def test_una_ruta_construida_por_concatenacion_se_detecta(tmp_path):
    _capa(tmp_path, "ie9/capas/otros/concatena", 'ruta = "inazuma1/data_iz/logic/" + "unit" + "base" + ".dat"\n')
    assert "S1" in C.capas_relevantes(tmp_path)["ie9/capas/otros/concatena"]


def test_un_aplicar_py_que_abre_unitbase_se_detecta(tmp_path):
    _capa(tmp_path, "ie9/capas/otros/aplicar", "open('unitbase.dat', 'rb')\n", nombre="aplicar_nombres.py")
    assert list(C.capas_relevantes(tmp_path)) == ["ie9/capas/otros/aplicar"]


def test_un_ayudante_que_escribe_los_jugadores_se_detecta_por_el_import_o_el_hermano(tmp_path):
    _capa(tmp_path, "ie9/capas/otros/por_modulo", "from ie123kit.ie3.comun import nombres_cortos_limite\n")
    _capa(tmp_path, "ie9/capas/otros/por_hermano", "import ayudante\nayudante.hazlo()\n",
          extra={"ayudante.py": "def hazlo():\n    return 'usearch.dat'\n"})
    encontradas = C.capas_relevantes(tmp_path)
    assert "S2" in encontradas["ie9/capas/otros/por_modulo"]
    assert "S4" in encontradas["ie9/capas/otros/por_hermano"]


def test_toda_capa_bajo_un_tema_nombres_se_considera_sospechosa(tmp_path):
    _capa(tmp_path, "ie9/capas/nombres/lo_que_sea", "print('hola')\n")
    assert C.capas_relevantes(tmp_path)["ie9/capas/nombres/lo_que_sea"] == {"S3"}


def test_historial_salida_y_capas_sin_senal_se_ignoran(tmp_path):
    _capa(tmp_path, "ie9/capas/nombres/historial/vieja", "unitbase\n")
    _capa(tmp_path, "ie9/capas/otros/salida", "unitbase\n")
    _capa(tmp_path, "ie9/capas/otros/limpia", "print('graficos')\n")
    assert C.capas_relevantes(tmp_path) == {}


def test_sin_clasificar_pide_clasificar_y_las_tablas_lo_arreglan(tmp_path, monkeypatch):
    _capa(tmp_path, "ie9/capas/otros/nueva", "usearch = 1\n")
    assert list(C.sin_clasificar(tmp_path)) == ["ie9/capas/otros/nueva"]
    monkeypatch.setitem(C.CAPAS_SIN_NOMBRES_DE_JUGADOR, "ie9/capas/otros/nueva", "prueba")
    assert C.sin_clasificar(tmp_path) == {}
    assert "ie9/capas/otros/nueva" not in C.entradas_obsoletas(tmp_path)
    monkeypatch.setitem(C.CAPAS_SIN_NOMBRES_DE_JUGADOR, "ie9/capas/otros/borrada", "prueba")
    assert "ie9/capas/otros/borrada" in C.entradas_obsoletas(tmp_path)


def test_el_fichero_con_sintaxis_rota_se_trata_como_sospechoso(tmp_path):
    _capa(tmp_path, "ie9/capas/otros/rota", "def (:\n")
    assert "S1" in C.capas_relevantes(tmp_path)["ie9/capas/otros/rota"]
