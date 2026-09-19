"""Subtítulos incrustados (quemados) en los fotogramas de una cinemática MOFLEX.

Porteo de ``work/ie2/shared/capas/media/subtitulos/comun_sub.py`` (IE2 v11) y de las piezas de
``media/media/comun_media.py`` que usa (``leer_dat``, ``cortes``, ``repartir``). La 3DS no enseña
``movie/txt/*.dat`` encima del vídeo (se pinta en la VRAM DS emulada), así que el subtítulo va
incrustado en la banda negra del fotograma, como en el japonés.

Todo lo que depende del juego va en :class:`EstiloSubtitulo` (fuente, banda, color, anchos) y en
los parámetros de tiempo (fps del vídeo y Hz de los ticks del .dat). La codificación con mobipeg y
la limpieza de la banda siguen en ``nucleo.media.moflex`` y en la capa; aquí solo están el texto, el
tiempo y el dibujo, que son deterministas y comprobables sin codificar vídeo.

Fotogramas: plano Y con forma ``(fotogramas, 320, columnas)``: el MOFLEX va girado, la fila de
pantalla ``y`` es la columna ``estilo.y0 + alto - 1 - y`` del bloque (:func:`a_columnas`).
"""

from __future__ import annotations

import re
import struct
import unicodedata
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

__all__ = [
    "EstiloSubtitulo",
    "RegistroDat",
    "a_columnas",
    "alfa",
    "ancho_texto",
    "cortes",
    "decodificar_nds",
    "leer_dat",
    "partir",
    "pistas",
    "por_fotograma",
    "quemar",
    "repartir_intervalo",
    "texto_nds",
    "tick",
]

_PUNTO = re.compile(r"(?<=[.!?…])\s+")
_COMA = re.compile(r"(?<=[,;:])\s+")
_ESPACIO = re.compile(r"\s+")


@dataclass(frozen=True)
class EstiloSubtitulo:
    """Geometría y estilo del subtítulo, medidos en los fotogramas japoneses del juego."""

    fuente: Path
    indice_fuente: int = 0
    tam: int = 16
    y0: int = 208            # primera fila de pantalla de la banda
    alto: int = 32
    base_y: int = 226        # línea base en pantalla
    blanco: int = 235        # Y del texto (BT.601 limitado)
    ancho_max: int = 300
    centro: int = 160
    ancho_pantalla: int = 320


@dataclass(frozen=True)
class RegistroDat:
    inicio: int
    fin: int
    cuerpo: bytes            # sin NUL


# ------------------------------------------------------------------ .dat y texto


def leer_dat(datos: bytes) -> list[RegistroDat]:
    """Registros de ``movie/txt/*.dat`` (``<III`` inicio, fin, tamaño + carga con NUL; fin 0xFFFFFFFF)."""
    out, pos = [], 0
    while True:
        if pos + 4 > len(datos):
            raise ValueError("falta el terminador")
        ini = struct.unpack_from("<I", datos, pos)[0]
        if ini == 0xFFFFFFFF:
            if pos + 4 != len(datos):
                raise ValueError("datos tras el terminador")
            return out
        if pos + 12 > len(datos):
            raise ValueError(f"cabecera truncada en 0x{pos:x}")
        fin, tam = struct.unpack_from("<II", datos, pos + 4)
        if tam == 0 or tam % 4 or pos + 12 + tam > len(datos) or fin < ini:
            raise ValueError(f"registro inválido en 0x{pos:x}")
        carga = datos[pos + 12:pos + 12 + tam]
        if b"\0" not in carga:
            raise ValueError(f"registro sin NUL en 0x{pos:x}")
        out.append(RegistroDat(ini, fin, carga.split(b"\0", 1)[0]))
        pos += 12 + tam


def decodificar_nds(cuerpo: bytes) -> str | None:
    """Latín propio del DS (``nds_latin.DS_TABLE``) con pares Shift-JIS incrustados; None si hay bytes desconocidos."""
    from ie123kit.nucleo.texto.nds_latin import DS_TABLE

    out, i = [], 0
    while i < len(cuerpo):
        c = cuerpo[i]
        if 0x81 <= c <= 0x9F or 0xE0 <= c <= 0xEF:
            out.append(cuerpo[i:i + 2].decode("cp932"))
            i += 2
            continue
        if c < 0x80:
            out.append(chr(c))
        elif c in DS_TABLE:
            out.append(DS_TABLE[c])
        else:
            return None
        i += 1
    return "".join(out)


def texto_nds(cuerpo: bytes) -> str:
    """Texto oficial de la NDS tal cual; solo NFKC (paréntesis de ancho completo)."""
    t = decodificar_nds(cuerpo)
    if t is None:
        raise ValueError(f"bytes NDS desconocidos: {cuerpo!r}")
    return unicodedata.normalize("NFKC", t.strip()).strip()


def cortes(texto: str) -> Iterator[list[tuple[int, int]]]:
    """Puntos de corte candidatos ``(fin del 1.º trozo, inicio del 2.º)`` por prioridad: frase, coma, palabra."""
    for pat in (_PUNTO, _COMA, _ESPACIO):
        idx = [(m.start(), m.end()) for m in pat.finditer(texto)]
        if idx:
            yield idx


def partir(texto: str, ancho: Callable[[str], float], ancho_max: float) -> list[str]:
    """Trozos de ``<= ancho_max`` px, cortando por frase, coma o palabra (lo más equilibrado)."""
    if ancho(texto) <= ancho_max:
        return [texto]
    mejor = None
    for grupo in cortes(texto):
        for a, b in grupo:
            i, d = texto[:a].rstrip(), texto[b:].lstrip()
            if not i or not d:
                continue
            clave = (max(ancho(i), ancho(d)) > ancho_max, abs(ancho(i) - ancho(d)))
            if mejor is None or clave < mejor[0]:
                mejor = (clave, i, d)
        if mejor is not None and not mejor[0][0]:
            break
    if mejor is None:
        raise ValueError(f"no se puede partir: {texto!r}")
    return partir(mejor[1], ancho, ancho_max) + partir(mejor[2], ancho, ancho_max)


def repartir_intervalo(inicio: int, fin: int, trozos: list[str]) -> list[tuple[int, int]]:
    """Intervalos ``[ini, fin)`` contiguos proporcionales a la longitud de cada trozo."""
    pesos = [max(1, len(t)) for t in trozos]
    total, acum, out = sum(pesos), 0, []
    ini = inicio
    for k, p in enumerate(pesos):
        acum += p
        f = fin if k == len(pesos) - 1 else inicio + round((fin - inicio) * acum / total)
        out.append((ini, f))
        ini = f
    return out


def pistas(dat: bytes, ancho: Callable[[str], float], ancho_max: float,
           texto: Callable[[bytes], str] = texto_nds) -> list[dict]:
    """``[{registro_nds, inicio, fin, texto}]`` de un .dat, con cada registro partido a ``ancho_max``
    y su intervalo repartido entre los trozos."""
    out = []
    for k, s in enumerate(leer_dat(dat)):
        trozos = partir(texto(s.cuerpo), ancho, ancho_max)
        for t, (a, b) in zip(trozos, repartir_intervalo(s.inicio, s.fin, trozos), strict=True):
            out.append({"registro_nds": k, "inicio": a, "fin": b, "texto": t})
    return out


# ------------------------------------------------------------------ tiempo


def tick(k: int, fps: int = 24, hz: int = 30) -> int:
    """Tick del .dat del fotograma ``k``: ``floor(floor(k*1000/fps) * hz / 1000)`` (CRO de IE2 0xe84bc)."""
    return (k * 1000 // fps) * hz // 1000


def por_fotograma(subs: list[dict], n_fotogramas: int, fps: int = 24, hz: int = 30):
    """Índice del subtítulo visible en cada fotograma (-1 = ninguno), máquina secuencial del CRO.

    Un registro cada vez y en orden: se dibuja cuando ``tick >= inicio``; con ``tick >= fin`` se pasa
    al siguiente, que se dibuja en el mismo fotograma si su inicio ya pasó (sin parpadeo).
    """
    import numpy as np

    idx = np.full(n_fotogramas, -1, int)
    cur, dibujado = 0, False
    for k in range(n_fotogramas):
        if cur >= len(subs):
            break
        t = tick(k, fps, hz)
        s = subs[cur]
        if dibujado:
            if t < s["fin"]:
                idx[k] = cur
                continue
            cur, dibujado = cur + 1, False
            if cur < len(subs) and t >= subs[cur]["inicio"]:
                dibujado = True
                idx[k] = cur
        elif t >= s["inicio"]:
            dibujado = True
            idx[k] = cur
    return idx


# ------------------------------------------------------------------ dibujo


@lru_cache(maxsize=8)
def _fuente(ruta: str, indice: int, tam: int):
    from PIL import ImageFont

    return ImageFont.truetype(ruta, tam, index=indice)


def ancho_texto(texto: str, estilo: EstiloSubtitulo) -> float:
    return _fuente(str(estilo.fuente), estilo.indice_fuente, estilo.tam).getlength(texto)


def alfa(texto: str, estilo: EstiloSubtitulo):
    """Banda de pantalla ``(alto, ancho_pantalla)`` con la cobertura 0..255 del texto centrado."""
    import numpy as np
    from PIL import Image, ImageDraw

    im = Image.new("L", (estilo.ancho_pantalla, estilo.alto), 0)
    d = ImageDraw.Draw(im)
    x = round(estilo.centro - ancho_texto(texto, estilo) / 2)
    d.text((x, estilo.base_y - estilo.y0), texto,
           font=_fuente(str(estilo.fuente), estilo.indice_fuente, estilo.tam), fill=255, anchor="ls")
    return np.array(im)


def a_columnas(banda):
    """Banda de pantalla ``(alto, ancho)`` -> bloque del fotograma girado ``(ancho, alto)``."""
    return banda[::-1, :].T


def quemar(Y, subs: list[dict], idx, estilo: EstiloSubtitulo) -> None:
    """Pinta el texto sobre la banda ya limpia del plano Y (en el sitio)."""
    import numpy as np

    cache: dict[str, object] = {}
    for k in np.where(idx >= 0)[0]:
        texto = subs[idx[k]]["texto"]
        if texto not in cache:
            cache[texto] = a_columnas(alfa(texto, estilo)).astype(np.float32) / 255
        a = cache[texto]
        base = Y[k, :, :estilo.alto].astype(np.float32)
        Y[k, :, :estilo.alto] = np.clip(base + a * (estilo.blanco - base), 0, 255).round().astype(np.uint8)
