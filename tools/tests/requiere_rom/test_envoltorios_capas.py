"""Las capas activas de ``work/`` son envoltorios del paquete, no copias del motor (F2.6, #55).

Por cada módulo de capa que se desduplicó en la limpieza final se comprueba:

1. que **sigue exponiendo toda su superficie pública anterior** (los nombres que usan sus hermanos
   ``apply.py``/``validate.py``/…), con el mismo tipo;
2. que **delega en el paquete**: los límites y las tablas que antes estaban escritos a mano en la capa
   son ahora los del paquete, valor a valor;
3. que **no queda motor duplicado**: el módulo de la capa no vuelve a definir las funciones portadas
   ni carga su motor de una capa de ``historial/``.

La prueba de que la salida no cambia es aparte y por hash (``test_equivalencia_motores_ie1.py``,
``test_equivalencia_motores_ie2.py``, ``test_equivalencia_fuentes_banner.py``,
``test_equivalencia_ayuda_ie2.py`` y ``test_equivalencia_voz_recopilatorio.py``).

Nunca escribe en ``work/``. En CI se deselecciona con ``-m "not requiere_rom"``.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

from ie123kit.nucleo.config.raiz import find_root

pytestmark = pytest.mark.requiere_rom

#: Módulo de capa -> nombres públicos que sus hermanos usan y que no pueden desaparecer.
SUPERFICIE: dict[str, tuple[str, ...]] = {
    "work/ie2/shared/capas/dialogo/saltos37/comun19.py": (
        "LINEAS", "M", "MAX_BYTES", "MAX_CAR", "PAGINA_MAX", "PROTEGIDOS", "ROOT", "SALTO", "PAGINA",
        "es_espanol", "espanol", "ida_y_vuelta", "paginas", "palabras", "partir_paginas", "problemas",
        "reajusta", "reparte", "repartir",
    ),
    "work/ie1/capas/dialogo/motor_unificado/comun94.py": (
        "A23", "C17", "C92", "CONTEXTO", "CRO_BASE", "K", "M", "MAX_BYTES", "PAGINA_MAX", "PARCHES",
        "PROTEGIDOS", "W", "_modulo", "limpiar", "paginas", "paginas_antes", "paginas_despues",
        "palabras", "problemas", "reajusta", "rehacer", "unificar",
    ),
    "work/ie2/shared/capas/graficos/ayuda/ayuda22.py": (
        "AR", "C", "CANDIDATA", "EXTRA", "H3", "HERE", "MASTUTORIAL", "NDS_SP", "PREVIEWS", "ROOT",
        "SYSTEM_B", "W3", "capturas", "nds_captura",
    ),
}

#: Módulo de capa -> funciones del motor que ya NO puede volver a definir por su cuenta.
SIN_MOTOR: dict[str, tuple[str, ...]] = {
    "work/ie2/shared/capas/dialogo/saltos37/comun19.py": (),
    "work/ie1/capas/dialogo/motor_unificado/comun94.py": ("repartir", "partir_paginas"),
    "work/ie2/shared/capas/graficos/ayuda/apply.py": (
        "mascara_zonas", "ajuste_color", "desplazamiento", "componer", "caja_panel", "componer_panel",
    ),
    "work/shared/capas/graficos/banner_home/apply.py": ("build_cbmd",),
}


@pytest.fixture(scope="module")
def raiz() -> Path:
    r = find_root()
    if not (r / "work").is_dir():
        pytest.skip("falta work/ local")
    return r


def _cargar(ruta: Path, nombre: str):
    """Importa un módulo de capa por su ruta, con su carpeta en sys.path (como hacen las capas)."""
    carpeta = str(ruta.parent)
    if carpeta not in sys.path:
        sys.path.insert(0, carpeta)
    spec = importlib.util.spec_from_file_location(nombre, ruta)
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[nombre] = modulo
    spec.loader.exec_module(modulo)
    return modulo


#: Guion que importa un modulo de capa en un interprete limpio y escribe los nombres que faltan.
_GUION_SUPERFICIE = """
import importlib.util, json, sys
ruta, nombres = sys.argv[1], json.loads(sys.argv[2])
sys.path.insert(0, str(__import__('pathlib').Path(ruta).parent))
sys.path.insert(0, sys.argv[3])
spec = importlib.util.spec_from_file_location('capa_bajo_prueba', ruta)
m = importlib.util.module_from_spec(spec)
sys.modules['capa_bajo_prueba'] = m
spec.loader.exec_module(m)
print(json.dumps([n for n in nombres if not hasattr(m, n)]))
"""


def _superficie_en_subproceso(ruta: Path, nombres, src: Path) -> list[str]:
    """Nombres que le faltan a ``ruta``, comprobados en un intérprete nuevo.

    Algunas capas arrastran cadenas de `historial/` (v06 -> v03) cuyos módulos se llaman `comun`,
    `base`, `apply`… Importarlas dentro de la suite las mezcla con las de otras capas en
    `sys.modules` y el fallo depende del orden de los tests. En un proceso limpio se importan como
    cuando se ejecuta la capa de verdad.
    """
    r = subprocess.run(
        [sys.executable, "-X", "utf8", "-c", _GUION_SUPERFICIE, str(ruta), json.dumps(list(nombres)), str(src)],
        capture_output=True, text=True, encoding="utf-8", check=False,
    )
    if r.returncode != 0:
        pytest.fail(f"{ruta.name}: no se puede importar la capa\n{r.stderr[-1500:]}")
    return json.loads(r.stdout.strip().splitlines()[-1])


@pytest.mark.parametrize("rel", sorted(SUPERFICIE))
def test_la_capa_conserva_su_superficie(raiz, rel):
    ruta = raiz / rel
    if not ruta.is_file():
        pytest.skip(f"falta {rel}")
    faltan = _superficie_en_subproceso(ruta, SUPERFICIE[rel], raiz / "tools/src")
    assert not faltan, f"{rel}: la desduplicación se ha llevado {faltan}"


@pytest.mark.parametrize("rel", sorted(SIN_MOTOR))
def test_la_capa_no_redefine_el_motor(raiz, rel):
    """Por AST (sin ejecutar): el módulo no vuelve a definir las funciones que se portearon."""
    ruta = raiz / rel
    if not ruta.is_file():
        pytest.skip(f"falta {rel}")
    arbol = ast.parse(ruta.read_text(encoding="utf-8"))
    definidas = {n.name for n in arbol.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    repetidas = sorted(definidas & set(SIN_MOTOR[rel]))
    assert not repetidas, f"{rel}: vuelve a definir el motor portado: {repetidas}"


@pytest.mark.parametrize("rel", sorted(SUPERFICIE))
def test_la_capa_importa_el_paquete(raiz, rel):
    """El módulo importa ie123kit: es la señal de que el motor ya no está copiado."""
    ruta = raiz / rel
    if not ruta.is_file():
        pytest.skip(f"falta {rel}")
    arbol = ast.parse(ruta.read_text(encoding="utf-8"))
    modulos = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            modulos.update(a.name for a in nodo.names)
        elif isinstance(nodo, ast.ImportFrom) and nodo.module:
            modulos.add(nodo.module)
    assert any(m.startswith("ie123kit") for m in modulos), f"{rel}: no importa ie123kit"


def test_el_dialogo_de_ie2_usa_los_limites_del_paquete(raiz):
    """comun19 ya no escribe 37 × 3 / 131 B a mano: los toma de ie2.comun.dialogo."""
    from ie123kit.ie2.comun.dialogo import MODELO_IE2

    ruta = raiz / "work/ie2/shared/capas/dialogo/saltos37/comun19.py"
    if not ruta.is_file():
        pytest.skip("falta la capa saltos37")
    c = _cargar(ruta, "envoltorio_saltos37_comun19")
    assert (c.MAX_CAR, c.LINEAS) == (MODELO_IE2.max_car, MODELO_IE2.lineas) == (37, 3)
    assert (c.PAGINA_MAX, c.MAX_BYTES) == (MODELO_IE2.pagina_max, MODELO_IE2.registro_max) == (131, 247)


def test_el_dialogo_de_ie1_usa_la_tabla_de_parches_del_paquete(raiz):
    """comun94 ya no lleva su copia de PARCHES/CONTEXTO: los toma de ie1.texto.cro."""
    from ie123kit.ie1.texto import cro as CRO
    from ie123kit.ie1.texto.dialogo import MODELO_IE1_ANCHO

    ruta = raiz / "work/ie1/capas/dialogo/motor_unificado/comun94.py"
    if not ruta.is_file():
        pytest.skip("falta la capa motor_unificado")
    c = _cargar(ruta, "envoltorio_motor_unificado_comun94")
    assert [p[0] for p in c.PARCHES] == [p.direccion for p in CRO.PARCHES_ANCHO_DIALOGO]
    assert [p[:3] for p in c.PARCHES] == [(p.direccion, p.antes, p.despues) for p in CRO.PARCHES_ANCHO_DIALOGO]
    assert [x[0] for x in c.CONTEXTO] == [x.direccion for x in CRO.CONTEXTO_ANCHO_DIALOGO]
    assert (c.MAX_CAR, c.LINEAS) == (MODELO_IE1_ANCHO.max_car, MODELO_IE1_ANCHO.lineas) == (37, 3)


def test_las_pestanas_de_ayuda_usan_la_tabla_del_paquete(raiz):
    """apply.py de la capa ayuda ya no lleva su copia de PESTANAS ni de la operación de pintado.

    Se comprueba por AST y no importando el módulo: al importarlo suelto arrastra la cadena de capas
    de `historial/graficos` (v06 -> v03), que solo se inicializa bien al ejecutar la capa. La salida
    sí se comprueba byte a byte, en `test_equivalencia_ayuda_ie2.py`.
    """
    ruta = raiz / "work/ie2/shared/capas/graficos/ayuda/apply.py"
    if not ruta.is_file():
        pytest.skip("falta la capa ayuda")
    arbol = ast.parse(ruta.read_text(encoding="utf-8"))
    asignado = {}
    for nodo in arbol.body:
        if isinstance(nodo, ast.Assign) and len(nodo.targets) == 1 and isinstance(nodo.targets[0], ast.Name):
            asignado[nodo.targets[0].id] = ast.unparse(nodo.value)
    assert asignado.get("PESTANAS") == "AY.PESTANAS", asignado.get("PESTANAS")
    assert asignado.get("BLANCO") == "AY.BLANCO", asignado.get("BLANCO")
    assert asignado.get("MODELO") == "AY.MODELO_IE2", asignado.get("MODELO")
    assert asignado.get("_op_pestana") == "AY.operacion_pestana", asignado.get("_op_pestana")


def test_el_banner_reproduce_su_salida_con_el_paquete(raiz):
    """La capa banner_home delegada da el mismo banner.bnr y el mismo icon.bin, byte a byte."""
    capa = raiz / "work/shared/capas/graficos/banner_home"
    for rel in ("apply.py", "salida/banner.bnr", "salida/icon.bin"):
        if not (capa / rel).exists():
            pytest.skip(f"falta {rel} de banner_home")
    a = _cargar(capa / "apply.py", "envoltorio_banner_home_apply")
    from ie123kit.juego_principal import banner as B

    assert a.TITULO == B.TITULO
    assert a.build_icon() == (capa / "salida/icon.bin").read_bytes()
    _orig, bnr, _info = a.build_banner()
    assert bnr == (capa / "salida/banner.bnr").read_bytes()


def test_el_smdh_de_ie1_usa_los_campos_del_paquete(raiz):
    """La capa smdh importa el paquete en vez del shim plano y no copia los offsets."""
    from ie123kit.nucleo.ejecutable.smdh import CAMPOS_TITULO

    ruta = raiz / "work/ie1/capas/graficos/smdh/apply.py"
    if not ruta.is_file():
        pytest.skip("falta la capa smdh")
    a = _cargar(ruta, "envoltorio_smdh_apply")
    assert a.FIELDS == CAMPOS_TITULO
