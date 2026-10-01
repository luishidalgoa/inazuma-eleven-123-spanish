"""Capturas de ayuda y pestañas de la pantalla de ayuda de IE2 (``a_data_replace``, ``a_menu``).

Porteo de la capa ``work/ie2/shared/capas/graficos/ayuda`` (v22, issue #77) sobre el motor genérico
:mod:`ie123kit.nucleo.graficos.regiones`. Aquí solo están los parámetros **medidos** de IE2 y las
rutas; ningún texto ni dato del juego se lee de git (Norma 2): las capturas de la NDS española y la
base japonesa las pasa quien llama.

Qué hace el motor, tal como se midió en la capa:

- Las 68 capturas de ayuda de la pantalla inferior (``help_b/data/ie02_tt*.arc``, 320x240 dentro de
  una textura de 512x256) son las de la NDS (256x192) redibujadas a ×1,25. Se escala la captura
  española de la NDS a 320x240 (bilineal), se iguala su color al de la de 3DS con una recta por canal
  ajustada fuera de las zonas que difieren, y **solo** esas zonas se pegan: cabecera (las 44 primeras
  filas, enteras), título, bocadillos y cajas de pista. El resto de la captura de 3DS no se toca.
- Las 3 capturas de la pantalla superior (``help_t/data/ie02_syup_bg*.arc`` y sus copias en
  ``demo_bg/data``, 400x240) **no** son la NDS ×1,25: su panel está recompuesto. Se localiza el panel
  sobre el fondo liso en las dos imágenes y se escala el panel de la NDS a la caja del de 3DS.
- Las pestañas de la pantalla de ayuda (``a_menu/system_b.arc``: そうさ/システム en sus 4 estados y el
  rótulo きほんそうさ) se repintan con los términos oficiales de la NDS. El pintado en sí lo hace el
  motor de rótulos que pase quien llama (``pintar``): aquí están las cajas medidas y cómo se deduce de
  la propia textura japonesa qué colores hay que borrar y de qué color es la sombra.

El alfa de las texturas nunca se toca (es el recorte del atlas) y la metadata CTPK se conserva.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

import numpy as np
from PIL import Image

from ie123kit.nucleo.compresion import lz10, sszl
from ie123kit.nucleo.graficos import ctpk, pac_sprite, texturas
from ie123kit.nucleo.graficos import regiones as R

__all__ = [
    "AR",
    "BLANCO",
    "MASTUTORIAL",
    "MODELO_IE2",
    "PESTANAS",
    "SYSTEM_B",
    "ModeloAyuda",
    "captura_arc",
    "captura_nds",
    "capturas",
    "componer_captura",
    "componer_panel",
    "es_panel",
    "operacion_pestana",
    "pestanas_arc",
]

#: Carpeta de las capturas de ayuda dentro del contenedor japonés.
AR = "inazuma2/data_iz/a_data_replace/"
#: Atlas con las pestañas y el rótulo de la pantalla de ayuda.
SYSTEM_B = "inazuma2/data_iz/a_menu/system_b.arc"
#: Paquete DS de tutorial que el 3DS no dibuja (se deja japonés; ver el informe de la capa v22).
MASTUTORIAL = "inazuma2/data_iz/pic2d/menu/MASTutorial.SPF_"


@dataclass(frozen=True)
class ModeloAyuda:
    """Parámetros medidos de las capturas de ayuda de un juego.

    ``ancho``/``alto``: captura de 3DS de la pantalla inferior dentro de su textura;
    ``ancho_superior``: la de la pantalla superior; ``nds``: tamaño de la captura de la NDS;
    ``umbral``/``margen``/``cabecera``: diferencia suavizada que marca «texto distinto», margen
    alrededor de cada zona y filas de cabecera que se toman enteras de la NDS.
    """

    nombre: str
    ancho: int = 320
    alto: int = 240
    ancho_superior: int = 400
    nds: tuple[int, int] = (256, 192)
    umbral: float = 70
    margen: int = 3
    cabecera: int = 44

    def ancho_pantalla(self, nombre: str) -> int:
        """Ancho útil de la captura ``nombre`` (la pantalla superior es más ancha)."""
        return self.ancho_superior if es_panel(nombre) else self.ancho


#: IE2: 320x240 (inferior) y 400x240 (superior) desde la NDS de 256x192 (×1,25).
MODELO_IE2 = ModeloAyuda("IE2")


def es_panel(nombre: str) -> bool:
    """¿Es una captura de la pantalla superior (``syup_bg``), cuyo panel está recompuesto?"""
    return "syup_bg" in nombre


def capturas(rutas: Iterable[str]) -> list[tuple[str, str]]:
    """``[(ruta del .arc, nombre de la captura NDS)]`` de las capturas de ayuda que haya en ``rutas``."""
    salida = []
    for ruta in sorted(rutas):
        if not ruta.endswith(".arc") or "/ie02_" not in ruta:
            continue
        nombre = ruta.rsplit("/", 1)[1][len("ie02_"):-len(".arc")]
        if ("/help_b/data/" in ruta and nombre.startswith("tt")) or (
                ("/help_t/data/" in ruta or "/demo_bg/data/" in ruta) and nombre.startswith("syup_bg")):
            salida.append((ruta, nombre))
    return salida


def captura_nds(datos: bytes, modelo: ModeloAyuda = MODELO_IE2) -> Image.Image:
    """Captura de ayuda de la NDS española (``*.pac_``, LZ10 opcional) en RGB."""
    if datos[:1] == b"\x10":
        datos = lz10.decompress(datos)
    return pac_sprite.decodificar_pac8(datos, *modelo.nds)


def componer_captura(imagen_3ds: Image.Image, imagen_nds: Image.Image, ancho: int,
                     modelo: ModeloAyuda = MODELO_IE2) -> tuple[Image.Image, np.ndarray, int]:
    """Captura de 3DS con las zonas traducidas de la NDS pegadas; devuelve ``(imagen, máscara, dx)``."""
    base = np.array(imagen_3ds.convert("RGBA"))
    nds = np.array(imagen_nds.resize((modelo.ancho, modelo.alto), Image.BILINEAR))
    dx = R.desplazamiento_minimo(base[:modelo.alto, :ancho], nds)
    zona = base[:modelo.alto, dx:dx + modelo.ancho, :3]
    mascara = R.mascara_diferencias(zona, nds, umbral=modelo.umbral, margen=modelo.margen,
                                    filas_fijas=modelo.cabecera)
    igualada = R.igualar_color(zona, nds, mascara)
    salida = R.pegar_regiones(base, igualada, mascara, dx=dx)
    return Image.fromarray(salida, "RGBA"), mascara, dx


def componer_panel(imagen_3ds: Image.Image, imagen_nds: Image.Image,
                   modelo: ModeloAyuda = MODELO_IE2) -> tuple[Image.Image, tuple, tuple]:
    """Captura superior con el panel de la NDS escalado a la caja del panel de 3DS.

    Devuelve ``(imagen, caja del panel 3DS, caja del panel NDS)``.
    """
    base = np.array(imagen_3ds.convert("RGBA"))
    caja_3ds = R.caja_contenido(base[:modelo.alto, :modelo.ancho_superior])
    caja_nds = R.caja_contenido(np.array(imagen_nds))
    salida = R.pegar_escalado(base, imagen_nds, caja_3ds, recorte=caja_nds)
    return Image.fromarray(salida, "RGBA"), caja_3ds, caja_nds


def _unica_textura(datos: bytes) -> tuple[bytes, texturas.Ctpk]:
    raw = bytearray(sszl.unwrap(datos))
    encontradas = list(texturas.iter_ctpk(datos))
    if len(encontradas) != 1:
        raise ValueError(f"se esperaba una textura CTPK, hay {len(encontradas)}")
    return raw, encontradas[0]


def _codificar(blob: bytes, imagen: Image.Image) -> bytes:
    nuevo = ctpk.encode(blob, imagen.convert("RGBA"))
    if len(nuevo) != len(blob) or ctpk.metadata(nuevo) != ctpk.metadata(blob):
        raise ValueError("la textura codificada cambia de tamaño o de metadata")
    return nuevo


def captura_arc(original: bytes, nds: bytes, nombre: str,
                modelo: ModeloAyuda = MODELO_IE2) -> tuple[bytes, dict[str, Any]]:
    """``.arc`` de una captura de ayuda con su versión española; devuelve ``(bytes, informe)``.

    ``original`` es el ``.arc`` japonés y ``nds`` el ``*.pac_`` de la NDS española. Se comprueba que
    el resto del atlas esté vacío (alfa 0) antes de tocar nada.
    """
    raw, textura = _unica_textura(original)
    antes = ctpk.decode(textura.blob)
    arr = np.array(antes.convert("RGBA"))
    ancho = modelo.ancho_pantalla(nombre)
    if not (arr[modelo.alto:, :, 3] == 0).all() or not (arr[:, ancho:, 3] == 0).all():
        raise ValueError(f"{nombre}: el atlas no está vacío fuera de la captura")
    imagen_nds = captura_nds(nds, modelo)
    if es_panel(nombre):
        nueva, caja_3ds, caja_nds = componer_panel(antes, imagen_nds, modelo)
        zona: Any = {"panel_3ds": [int(v) for v in caja_3ds], "panel_nds": [int(v) for v in caja_nds]}
        pixeles = 0
    else:
        nueva, mascara, zona = componer_captura(antes, imagen_nds, ancho, modelo)
        pixeles = int(mascara.sum())
    blob = _codificar(textura.blob, nueva)
    raw[textura.offset:textura.offset + textura.tamano] = blob
    datos = sszl.reenvolver_como(original, bytes(raw), "keep")
    return datos, {"clase": "captura_ayuda", "textura": textura.nombre, "captura_nds": nombre,
                   "zona_px": pixeles, "dx": zona, "tam_original": len(original), "tam_nuevo": len(datos)}


# ------------------------------------------------------------------ pestañas (system_b)

#: Relleno de los rótulos de las pestañas (el japonés es blanco con sombra de 1 px).
BLANCO = (255, 255, 255, 255)

#: Cajas medidas de las pestañas de ayuda y su texto oficial de la NDS (MASTutorial SYDN_T00/B05).
#: ``window_b02``: 4 estados en filas de 32 px; pestaña izquierda x 56..154, derecha x 162..264.
PESTANAS: dict[str, list[tuple[tuple[int, int, int, int], str]]] = {
    "ie02_menu_system_window_b02.tga": [((56, y + 7, 154, y + 25), "Controles") for y in (0, 32, 64, 96)]
    + [((162, y + 7, 264, y + 25), "Recursos") for y in (0, 32, 64, 96)],
    "ie02_menu_system_panel_b04.tga": [((3, 3, 93, 25), "Controles básicos")],
}


def operacion_pestana(arr: np.ndarray, caja: tuple[int, int, int, int], texto: str) -> dict[str, Any]:
    """Operación de pintado de una pestaña, deducida de la propia textura japonesa.

    El fondo es el color más frecuente de la caja; se borran todos los demás; la sombra es el color de
    trazo opaco más oscuro que no se confunde con el fondo (como hace el japonés). El texto va en
    blanco, centrado y con la fuente ``auto12`` del motor de rótulos de menús.
    """
    x0, y0, x1, y1 = caja
    zona = arr[y0:y1, x0:x1].reshape(-1, 4)
    from collections import Counter

    fondo = tuple(int(v) for v in Counter(map(tuple, zona)).most_common(1)[0][0])
    otros = [tuple(int(v) for v in c) for c in set(map(tuple, zona))]
    otros = [c for c in otros if c != fondo]
    oscuros = sorted((c for c in otros if c[3] == 255 and sum(c[:3]) < sum(BLANCO[:3])), key=lambda c: sum(c[:3]))
    sombra = next((c for c in oscuros if abs(sum(c[:3]) - sum(fondo[:3])) > 60), None)
    operacion = {"caja": caja, "texto": texto, "fuente": "auto12", "borrar": "colores",
                 "colores_borrar": otros, "fondo_color": fondo, "color": BLANCO, "alinear": "c"}
    if sombra is not None:
        operacion["sombra"] = (1, 1, sombra)
    return operacion


def pestanas_arc(original: bytes, base: bytes | None = None, *,
                 pintar: Callable[[np.ndarray, list[dict[str, Any]]], np.ndarray],
                 tabla: dict[str, list[tuple[tuple[int, int, int, int], str]]] | None = None,
                 ) -> tuple[bytes | None, dict[str, Any]]:
    """``system_b.arc`` con las pestañas de ayuda en español; devuelve ``(bytes o None, informe)``.

    ``original`` es el ``.arc`` japonés (fija la política de reenvoltura) y ``base`` el ``.arc`` de
    partida si otra capa ya lo tocó (por defecto, el japonés). ``pintar`` es el motor de rótulos:
    recibe ``(array RGBA, [operación])`` y devuelve el array pintado (``ValueError`` si no cabe).
    Devuelve ``(None, informe)`` si no se pudo cambiar ninguna textura.
    """
    tabla = PESTANAS if tabla is None else tabla
    raw = bytearray(sszl.unwrap(base if base is not None else original))
    cambios: list[str] = []
    fallos: list[dict[str, str]] = []
    for textura in texturas.iter_ctpk(bytes(raw)):
        if textura.nombre not in tabla:
            continue
        arr = np.array(ctpk.decode(textura.blob).convert("RGBA"))
        try:
            for caja, texto in tabla[textura.nombre]:
                arr = pintar(arr, [operacion_pestana(arr, caja, texto)])
        except ValueError as e:
            fallos.append({"tipo": "pintado_fallido", "textura": textura.nombre, "motivo": str(e)})
            continue
        raw[textura.offset:textura.offset + textura.tamano] = _codificar(
            textura.blob, Image.fromarray(arr, "RGBA"))
        cambios.append(textura.nombre)
    informe: dict[str, Any] = {"clase": "textura", "cambios": cambios, "fallos": fallos}
    if not cambios:
        return None, informe
    return sszl.reenvolver_como(original, bytes(raw), "keep"), informe
