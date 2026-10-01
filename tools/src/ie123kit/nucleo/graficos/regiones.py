"""Composición de capturas por regiones: diferencia, igualación de color y pegado escalado.

Motor genérico de las capturas de ayuda (la captura de 3DS es la de NDS redibujada a otra escala):
se escala la captura traducida al tamaño de la de 3DS, se calculan las **zonas donde las dos
difieren** (texto, rótulos, bocadillos), se **iguala el color** de la traducida a la de 3DS con una
recta por canal ajustada *fuera* de esas zonas, y solo esas zonas se pegan. Todo lo demás de la
captura de 3DS queda intacto, así que los degradados y el ruido de la versión de 3DS no se tocan.

Funciones puras sobre ``numpy`` y ``PIL`` (nada de rutas, juegos ni ficheros): los parámetros
medidos viven en el módulo del juego (``ie123kit.ie2.comun.ayuda``). ``scipy.ndimage`` se importa
dentro de las funciones que lo necesitan para no exigirlo al importar el paquete.
"""

from __future__ import annotations

from collections import Counter

import numpy as np
from PIL import Image

__all__ = [
    "caja_contenido",
    "desplazamiento_minimo",
    "igualar_color",
    "mascara_diferencias",
    "pegar_escalado",
    "pegar_regiones",
]


def mascara_diferencias(base: np.ndarray, nueva: np.ndarray, *, umbral: float, margen: int = 0,
                        filas_fijas: int = 0, suavizado: int = 7, dilatacion: int = 4,
                        area_minima: int = 40) -> np.ndarray:
    """Zonas (rectángulos envolventes) donde ``nueva`` difiere de ``base``.

    ``base`` y ``nueva`` son RGB del mismo tamaño. Se suma la diferencia absoluta de los tres
    canales, se suaviza con una media de ``suavizado`` px y se marca lo que pasa de ``umbral``; las
    ``filas_fijas`` primeras filas se marcan siempre (cabeceras que se toman enteras). Los grupos
    conexos (tras dilatar ``dilatacion`` veces) de menos de ``area_minima`` px de rectángulo se
    descartan; el resto se devuelve como su rectángulo envolvente crecido ``margen`` px, de modo que
    el texto de un bocadillo arrastre el bocadillo entero y no queden medias letras.
    """
    from scipy import ndimage

    if base.shape[:2] != nueva.shape[:2]:
        raise ValueError(f"tamaños distintos: {base.shape[:2]} y {nueva.shape[:2]}")
    diferencia = np.abs(base[..., :3].astype(int) - nueva[..., :3].astype(int)).sum(2).astype(np.float32)
    marcado = ndimage.uniform_filter(diferencia, suavizado) > umbral
    marcado[:filas_fijas] = True
    etiquetas, _n = ndimage.label(ndimage.binary_dilation(marcado, iterations=dilatacion))
    salida = np.zeros_like(marcado)
    for rodaja in ndimage.find_objects(etiquetas):
        ys, xs = rodaja
        if (ys.stop - ys.start) * (xs.stop - xs.start) < area_minima:
            continue
        salida[max(ys.start - margen, 0):ys.stop + margen, max(xs.start - margen, 0):xs.stop + margen] = True
    return salida


def igualar_color(base: np.ndarray, nueva: np.ndarray, mascara: np.ndarray, *,
                  minimo_muestras: int = 500, pendiente: tuple[float, float] = (0.85, 1.15),
                  desvio: tuple[float, float] = (-20.0, 20.0)) -> np.ndarray:
    """``nueva`` con el color llevado al de ``base`` por una recta por canal (``a·x + b``).

    La recta se ajusta por mínimos cuadrados **fuera** de ``mascara`` (donde las dos imágenes
    muestran lo mismo y la única diferencia es el tono), y se recorta a ``pendiente`` y ``desvio``
    para que un ajuste malo no pueda desteñir la imagen. Un canal con menos de ``minimo_muestras``
    píxeles fuera de la máscara se deja como está.
    """
    fuera = ~mascara
    resultado = nueva[..., :3].astype(np.float32).copy()
    for canal in range(3):
        x = nueva[..., canal][fuera].astype(np.float32)
        y = base[..., canal][fuera].astype(np.float32)
        if len(x) < minimo_muestras:
            continue
        a, b = np.polyfit(x, y, 1)
        a = float(np.clip(a, *pendiente))
        b = float(np.clip(b, *desvio))
        resultado[..., canal] = nueva[..., canal] * a + b
    return np.clip(resultado, 0, 255).astype(np.uint8)


def desplazamiento_minimo(base: np.ndarray, nueva: np.ndarray) -> int:
    """``x`` donde ``nueva`` encaja mejor en ``base`` (diferencia media mínima); 0 si son igual de anchas."""
    alto, ancho = nueva.shape[:2]
    if base.shape[1] == ancho:
        return 0
    if base.shape[1] < ancho or base.shape[0] < alto:
        raise ValueError(f"{nueva.shape[:2]} no cabe en {base.shape[:2]}")
    return min(range(base.shape[1] - ancho + 1),
               key=lambda dx: np.abs(base[:alto, dx:dx + ancho, :3].astype(int)
                                     - nueva[..., :3].astype(int)).mean())


def pegar_regiones(base: np.ndarray, nueva: np.ndarray, mascara: np.ndarray, dx: int = 0,
                   dy: int = 0) -> np.ndarray:
    """Copia de ``base`` (RGBA) con el RGB de ``nueva`` solo donde ``mascara``, colocada en (``dx``, ``dy``).

    El alfa de ``base`` no se toca: las texturas de la interfaz lo usan para el recorte del atlas.
    """
    alto, ancho = mascara.shape
    salida = base.copy()
    zona = salida[dy:dy + alto, dx:dx + ancho]
    zona[..., :3][mascara] = nueva[..., :3][mascara]
    return salida


def caja_contenido(arr: np.ndarray, *, tolerancia: int = 60, borde: int = 8) -> tuple[int, int, int, int]:
    """``(x0, y0, x1, y1)`` del grupo conexo mayor que no es el fondo liso de ``arr``.

    El fondo es el color más frecuente de un muestreo de 1 de cada 4 px; se ignora un marco de
    ``borde`` px (los bordes de la pantalla y del atlas no son contenido).
    """
    from scipy import ndimage

    rgb = arr[..., :3].astype(int)
    fondo = Counter(map(tuple, rgb[::4, ::4].reshape(-1, 3))).most_common(1)[0][0]
    marcado = np.abs(rgb - np.array(fondo)).sum(2) > tolerancia
    marcado[:, :borde] = marcado[:, -borde:] = False
    marcado[:borde] = marcado[-borde:] = False
    etiquetas, _n = ndimage.label(marcado)
    cuentas = np.bincount(etiquetas.ravel())[1:]
    if not len(cuentas) or not cuentas.any():
        raise ValueError("no hay contenido sobre el fondo")
    mayor = int(cuentas.argmax()) + 1
    ys, xs = np.nonzero(etiquetas == mayor)
    return int(xs.min()), int(ys.min()), int(xs.max() + 1), int(ys.max() + 1)


def pegar_escalado(base: np.ndarray, pieza: Image.Image, caja: tuple[int, int, int, int],
                   recorte: tuple[int, int, int, int] | None = None,
                   remuestreo: int = Image.LANCZOS) -> np.ndarray:
    """Copia de ``base`` (RGBA) con ``pieza`` (o su ``recorte``) escalada dentro de ``caja``, sin tocar el alfa."""
    x0, y0, x1, y1 = caja
    if not (0 <= x0 < x1 <= base.shape[1] and 0 <= y0 < y1 <= base.shape[0]):
        raise ValueError(f"caja fuera de la imagen: {caja}")
    if recorte is not None:
        pieza = pieza.crop(recorte)
    escalada = np.array(pieza.convert("RGB").resize((x1 - x0, y1 - y0), remuestreo))
    salida = base.copy()
    salida[y0:y1, x0:x1, :3] = escalada
    return salida
