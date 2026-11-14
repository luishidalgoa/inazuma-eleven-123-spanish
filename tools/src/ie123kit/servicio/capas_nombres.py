"""Registro y guardia de las capas de ``work/`` que escriben nombres de jugador (hook de ``usearch.dat``).

QUÉ PROTEGE CADA PIEZA (leer antes de fiarse de ella):

* La protección FIABLE es la VALIDACIÓN DE LA SALIDA: ``ServicioToolkit.construir`` y ``candidata.construir`` (también su
  ``__main__``) dejan ``usearch.dat`` sincronizado como paso final (por defecto; opt-out nombrado),
  ``ServicioToolkit.verificar`` falla con ``USEARCH_DESINCRONIZADO`` e ``instalar`` (fachada e ``instalar.azahar``)
  se niega.
  Eso cubre cualquier capa, pasada o futura, sepa o no que existe el hook (``servicio.sincronia_usearch``).
* ESTE registro NO protege nada por sí mismo: es documentación comprobable. Dice qué capas de ``work/`` escriben nombres
  de jugador (y por tanto exigen cerrar la cadena imperativa de ``apply.py`` sobre una copia del ``archive.fa`` instalado
  con ``python -m ie123kit.servicio.sincronia_usearch cerrar <copia>``, docs/HARNESS.md §4) y cuáles se ha mirado y no
  los tocan. Las ``apply.py`` de esas capas no se modifican: la regla es la de HARNESS.md y la validación de la salida.
* La GUARDIA (:func:`sin_clasificar`, usada por ``tests/requiere_rom``; corre solo con ``work/``, nunca en CI) detecta
  capas nuevas que probablemente toquen nombres y exige clasificarlas. NO es una prueba: es un detector heurístico con
  falsos positivos (obliga a clasificar de más) y falsos negativos (una capa que escriba unitbase por un camino que
  ninguna señal ve pasa sin clasificar; la salida se valida igualmente al construir/instalar).

Señales por fichero ``apply*.py`` / ``aplicar*.py`` (se ignoran ``historial/``, ``salida/`` y ``candidatas/``):

1. ``S1`` el texto, tras quitar espacios, comillas y ``+``, contiene ``unitbase`` o ``usearch`` (detecta rutas
   construidas por concatenación como ``"unit" + "base"``);
2. ``S2`` importa un módulo cuyo nombre contiene ``usearch``, ``unitbase``, ``nombres``, ``bigramas`` o
   ``registro_usearch`` (cubre un ayudante que escribe los jugadores sin nombrar el fichero);
3. ``S3`` la capa vive bajo una carpeta de tema ``nombres/``;
4. ``S4`` importa un módulo hermano de la capa (``.py`` en su carpeta) cuyo texto da ``S1``.

Importar este módulo no tiene efectos.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

__all__ = [
    "CAPAS_NOMBRES_JUGADOR",
    "CAPAS_SIN_NOMBRES_DE_JUGADOR",
    "MODULOS_SENSIBLES",
    "capas_relevantes",
    "entradas_obsoletas",
    "senales_de_fichero",
    "sin_clasificar",
]

#: Capas de work/ que escriben nombres de jugador en unitbase.dat (o equivalentes): tras ellas hay que ejecutar la
#: capa ``busqueda_usearch`` del juego. Clave: carpeta de la capa relativa a work/; valor: juegos afectados.
CAPAS_NOMBRES_JUGADOR: dict[str, str] = {
    "ie1/capas/fuentes/bigramas_ritmo": "ie1",
    "ie1/capas/nombres/nombre_ficha": "ie1",
    "ie2/shared/capas/nombres/nombres_compactos": "ie1 ie2",
    "shared/capas/nombres/excepciones_corto": "ie2 ie3",
    "shared/capas/nombres/restaurar_oficiales/latin1": "ie1 ie2",
    "ie3/amenaza_del_ogro/capas/nombres/registro_datos": "ie3",
    "ie3/amenaza_del_ogro/capas/nombres/cortos_ogro": "ie3",
    "ie3/amenaza_del_ogro/capas/nombres/lista_registro": "ie3",
    "ie3/amenaza_del_ogro/capas/nombres/lista_registro_abc": "ie3",
    "ie3/amenaza_del_ogro/capas/nombres/lista_registro_latina": "ie3",
    "ie3/shared/capas/nombres/nombres_cortos_6": "ie3",
    "ie3/shared/capas/nombres/nombres_cortos_bigramas": "ie3",
    "ie3/shared/capas/textos_logic/nombres_largos": "ie3",
}

#: Capas que disparan alguna señal pero NO escriben el nombre de jugador (equipos, títulos, descripciones, rótulos,
#: gráficos, parches de CRO, validadores) o que ya son el propio hook. Valor: por qué.
CAPAS_SIN_NOMBRES_DE_JUGADOR: dict[str, str] = {
    "ie1/capas/menus_cro/font8_ancho_real": "parche de CRO (ancho de FONT8)",
    "ie2/shared/capas/graficos/afinidad_pastilla": "gráfico del icono de afinidad de la ficha (status_t.arc); solo lee unitbase.dat para comprobar el mapeo celda-elemento, no lo escribe",
    "ie1/capas/blog/texto_oficial_eu": "textos del Inablog (blogpost.dat/blogres.dat); lo sustituye menus_cro/blog_ie1_oficial",
    "ie1/capas/menus_cro/blog_ie1_oficial": "parche de CRO (avance proporcional del Inablog) y textos del Inablog; no escribe unitbase",
    "ie1/capas/menus_cro/pachanga_objetivos_equipos": "parche de CRO (pantalla previa de pachanga) y objetivos (games.STR); no escribe unitbase",
    "ie1/capas/menus_cro/fundir_capas/paquete_final": "paquete de instalación de las capas de menús de IE1; ejecuta verificar y cerrar de usearch sin cambiar el archive.fa",
    "ie1/capas/menus_cro/salir_abandonar": "gráfico del cuadro de salir (quit_b.arc); solo ejecuta verificar de usearch",
    "ie1/capas/nombres/busqueda_usearch": "es el hook (IE1)",
    "ie1/capas/nombres/equipos": "nombres de equipo (team.pkb)",
    "ie1/capas/nombres/niv_por": "gráficos (NIV/POR)",
    "ie1/capas/nombres/pestanas": "gráficos (pestañas de Formación)",
    "ie1/capas/nombres/restaurar_oficiales": "equipos, objetos, órdenes y títulos; no unitbase",
    "ie1/capas/nombres/titulos": "títulos de equipo (rpgtitle.STR)",
    "ie1/legacy/desc_revision": "descripciones (unitbase.STR); no toca el nombre",
    "ie2/shared/capas/menus_cro/fichar_unido_completo": "parche de CRO (menú Fichar: avance, rótulos y expansión de piezas al dibujar); no escribe unitbase",
    "ie2/shared/capas/menus_cro/paquete_final": "paquete final de CRO (Fichar IE2); no escribe unitbase",
    "ie2/shared/capas/menus_cro/goles_ancho_real": "parche de CRO (ancho de FONT8)",
    "ie2/shared/capas/nombres/busqueda_usearch": "es el hook (IE2)",
    "ie2/shared/capas/nombres/codigos_secretos": "códigos secretos (ScoutSpCode.dat); no escribe unitbase ni usearch (solo comprueba que los ids coinciden con los 0xD7)",
    "ie2/shared/capas/nombres/practicegame": "nombres de equipo (PracticeGame)",
    "ie2/shared/capas/nombres/restaurar_oficiales": "equipos, objetos, órdenes y títulos; no unitbase",
    "ie2/shared/capas/nombres/textos": "textos de evento y menús",
    "ie2/shared/capas/nombres/titulos": "títulos de equipo (rpgtitle.STR)",
    "ie2/shared/capas/rotulos_objetivos/rotulos_completos": "rótulos de objetivos",
    "ie3/fuego_explosivo/capas/dialogo/emision": "diálogo",
    "ie3/shared/capas/blog/oficial": "blog",
    "ie3/shared/capas/dialogo/nombres_jugador": "nombres dentro del diálogo, no unitbase",
    "ie3/shared/capas/dialogo/saltos_eu": "diálogo",
    "ie3/shared/capas/menus_cro/descripciones_256": "descripciones de la ficha",
    "ie3/shared/capas/menus_cro/ficha_descripcion_256": "descripciones de la ficha",
    "ie3/shared/capas/menus_cro/literales_registro": "parche de CRO (siglas de posición)",
    "ie3/shared/capas/menus_cro/nombres_menu_jugadores": "parche de CRO (centrado del nombre en el menú)",
    "ie3/shared/capas/menus_cro/nombres_casilla_resto": "parche de CRO (nombre a X=0 como el EU en las cinco cabeceras, lectura en blanco, clamp de Tokkun y de la etiqueta de partido)",
    "ie3/shared/capas/menus_cro/fichar_literales_eu": "parche de CRO (literales japoneses de Fichar/Contactos y menús con el texto oficial EU)",
    "ie3/shared/capas/menus_cro/tope_11_letras": "parche de CRO (tope de 11 letras de la rutina de teclas del campo de nombre); no escribe unitbase ni usearch",
    "ie3/shared/capas/graficos/contactos_mensajes_eu": "gráfico de los mensajes de Contactos (connection_b.arc); solo ejecuta verificar de usearch",
    "ie3/shared/capas/menus_cro/paquete_final": "paquete de instalación de las capas de menús de IE3 (CRO + connection_b.arc); ejecuta verificar y cerrar de usearch sin cambiar el archive.fa",
    "ie3/shared/capas/nombres/album_usearch": "escribe usearch (lo sustituye busqueda_usearch)",
    "ie3/shared/capas/nombres/busqueda_usearch": "es el hook (IE3)",
    "ie3/shared/capas/nombres/equipos": "nombres de equipo (team.pkb)",
    "ie3/shared/capas/rotulos_objetivos/objetivos": "rótulos de objetivos",
    "ie3/shared/capas/rotulos_objetivos/rotulos_completos": "rótulos de objetivos",
    "ie3/shared/capas/textos_logic/fichas": "descripciones de la ficha (unitbase.STR)",
    "ie3/shared/capas/textos_logic/posiciones_pr": "siglas de posición",
    "ie3/shared/capas/textos_logic/rotulos": "rótulos",
    "shared/capas/nombres/restaurar_oficiales/sonda_pachanga": "nombres de equipo de pachanga",
}

#: Fragmentos de nombre de módulo cuya importación hace sospechosa a una capa (señal S2).
MODULOS_SENSIBLES: tuple[str, ...] = ("usearch", "unitbase", "nombres", "bigramas")

_IGNORADAS = frozenset({"historial", "salida", "candidatas", "__pycache__"})
_PALABRAS = ("unitbase", "usearch")


def _normalizado(texto: str) -> str:
    return re.sub(r"[\s\"'+()\[\],]", "", texto.lower())


def _importaciones(arbol: ast.AST) -> list[str]:
    nombres: list[str] = []
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            nombres += [a.name for a in nodo.names]
        elif isinstance(nodo, ast.ImportFrom) and nodo.module:
            nombres.append(nodo.module)
            nombres += [f"{nodo.module}.{a.name}" for a in nodo.names]
    return nombres


def senales_de_fichero(fichero: Path, work: Path) -> set[str]:
    """Señales (S1..S4) que dispara un ``apply*.py`` / ``aplicar*.py`` de ``work/``."""
    texto = fichero.read_text(encoding="utf-8", errors="replace")
    senales: set[str] = set()
    if any(p in _normalizado(texto) for p in _PALABRAS):
        senales.add("S1")
    try:
        importadas = _importaciones(ast.parse(texto))
    except SyntaxError:
        importadas = []
        senales.add("S1")  # no se puede analizar: se trata como sospechosa
    if any(m in x for x in importadas for m in MODULOS_SENSIBLES):
        senales.add("S2")
    if "nombres" in fichero.relative_to(work).parts:
        senales.add("S3")
    for x in importadas:
        hermano = fichero.parent / f"{x.split('.')[0]}.py"
        if hermano.is_file() and hermano != fichero and any(
            p in _normalizado(hermano.read_text(encoding="utf-8", errors="replace")) for p in _PALABRAS
        ):
            senales.add("S4")
    return senales


def capas_relevantes(work: Path) -> dict[str, set[str]]:
    """Carpeta de capa (relativa a ``work/``, con ``/``) -> señales, para toda capa con alguna señal."""
    work = Path(work)
    encontradas: dict[str, set[str]] = {}
    ficheros = [*work.rglob("apply*.py"), *work.rglob("aplicar*.py")]
    for fichero in sorted(set(ficheros)):
        rel = fichero.relative_to(work)
        if _IGNORADAS & set(rel.parts):
            continue
        senales = senales_de_fichero(fichero, work)
        if senales:
            clave = rel.parent.as_posix()
            encontradas[clave] = encontradas.get(clave, set()) | senales
    return encontradas


def sin_clasificar(work: Path) -> dict[str, set[str]]:
    """Capas con señales que no están en ninguna de las dos tablas (la guardia falla si no está vacío)."""
    conocidas = set(CAPAS_NOMBRES_JUGADOR) | set(CAPAS_SIN_NOMBRES_DE_JUGADOR)
    return {capa: s for capa, s in capas_relevantes(work).items() if capa not in conocidas}


def entradas_obsoletas(work: Path) -> list[str]:
    """Entradas de las tablas cuya carpeta ya no existe en ``work/`` (hay que retirarlas)."""
    work = Path(work)
    return sorted(c for c in (*CAPAS_NOMBRES_JUGADOR, *CAPAS_SIN_NOMBRES_DE_JUGADOR) if not (work / c).is_dir())
