"""Relocalización por contenido de los parches de una CRO a otra compilación del mismo módulo.

Caso de uso: la actualización oficial 1.4 trae las cuatro CRO recompiladas; las funciones y las cadenas
son casi todas las mismas, pero desplazadas. Los parches de la traducción están anclados por posición en
la 1.0, así que se trasladan así:

1. Se calcula el diff ``base (1.0 original) -> candidata (1.0 traducida)`` y se agrupa en tramos.
2. Cada tramo se localiza en la CRO destino (1.4 original) por su contexto: una ventana de bytes de la
   base alrededor del tramo, *normalizada* (a cero los destinos de relocalización y de importación, los
   inmediatos de las ramas B/BL y los literales PIC ``ldr rX, [pc, #n]; add rY, pc, rX``), que debe
   aparecer UNA sola vez en la destino normalizada. Así se comprueba a la vez que el original de la 1.4
   es el mismo que el de la 1.0 (los bytes esperados) y dónde está.
3. Los bytes cambiados se copian, pero toda referencia relativa a la posición se recalcula con el mapa
   ``offset 1.0 -> offset 1.4``: ramas B/BL/BLX, cargas relativas al PC (LDR/LDRB/LDRH/LDRD/VLDR), ADR
   y literales PIC. Las direcciones absolutas del ``code.bin`` se traducen con el mapa ``absolutas``.
4. Las cuevas de código que el parche añadió en el relleno tras un segmento y el crecimiento de un
   segmento (p. ej. cadenas nuevas al final de ``.rodata``) se recolocan tras el mismo segmento de la
   destino, con la misma alineación módulo 16, y se amplía su tamaño en la tabla de segmentos.
5. Las relocalizaciones reapuntadas (tabla 0x128) y los sumandos de importación cambiados (tabla 0xF8)
   se trasladan buscando en la destino la entrada con el mismo destino ya mapeado.

Nada se aplica a ciegas: un tramo que no se localiza de forma única, una referencia cuyo destino no se
puede mapear o un inmediato que no cabe se informa como ``fallido`` con su motivo y no se escribe.

API sin efectos: funciones puras sobre ``bytes`` que devuelven datos e informes serializables.
"""

from __future__ import annotations

import struct
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from itertools import pairwise

import numpy as np

from ie123kit.nucleo.ejecutable.cro import Cro

__all__ = [
    "Localizacion",
    "Mapeador",
    "ParcheRelocalizado",
    "ResultadoRelocalizacion",
    "codificar_referencia",
    "es_texto_sjis",
    "literales_absolutos",
    "mapear_direccion_absoluta",
    "normalizar",
    "pares_pic",
    "referencia",
    "relocalizar",
    "tramos_cambiados",
    "verificar_estructura",
    "verificar_relocalizacion",
]

_REL_OFF, _REL_NUM = 0x128, 0x12C
_EXT_OFF, _EXT_NUM = 0xF8, 0xFC
_TABLAS = 0x84  # offset del nombre del módulo: aquí empiezan las tablas tras los segmentos de código
_MARGENES = (8, 16, 32, 64, 128, 256, 512, 1024, 2048)
_MINIMO = 32
_THUNK = 0xE51FF004  # ldr pc, [pc, #-4]

Progreso = Callable[[int, int], None]


def _u32(d, o: int) -> int:
    return struct.unpack_from("<I", d, o)[0]


# ---------------------------------------------------------------------------------------------------
# Instrucciones ARM relativas al PC
# ---------------------------------------------------------------------------------------------------


def _rotimm(w: int) -> int:
    rot = ((w >> 8) & 0xF) * 2
    imm = w & 0xFF
    return ((imm >> rot) | (imm << (32 - rot))) & 0xFFFFFFFF if rot else imm


def _codificar_rotimm(valor: int) -> int | None:
    for rot in range(16):
        imm = ((valor << (2 * rot)) | (valor >> (32 - 2 * rot))) & 0xFFFFFFFF if rot else valor
        if imm < 0x100:
            return (rot << 8) | imm
    return None


def referencia(pc: int, w: int) -> tuple[str, int] | None:
    """Clase y destino (offset de fichero) de una instrucción ARM relativa al PC en ``pc``, o None.

    Clases: ``rama`` (B/BL/BLX), ``ldr`` (LDR/LDRB inmediato), ``ldrh`` (LDRH/LDRSB/LDRSH/LDRD),
    ``vldr`` y ``adr`` (ADD/SUB Rd, PC, #imm).
    """
    cond = w >> 28
    if (w >> 25) & 7 == 5:
        imm = w & 0xFFFFFF
        if imm & 0x800000:
            imm -= 1 << 24
        destino = pc + 8 + imm * 4
        if cond == 0xF:
            destino += ((w >> 24) & 1) * 2
        return ("rama", destino)
    if cond == 0xF:
        return None
    signo = 1 if (w >> 23) & 1 else -1
    if (w & 0x0F3F0000) == 0x051F0000:
        return ("ldr", pc + 8 + signo * (w & 0xFFF))
    if (w & 0x0F6F0090) == 0x014F0090 and (w >> 5) & 3:
        return ("ldrh", pc + 8 + signo * ((((w >> 8) & 0xF) << 4) | (w & 0xF)))
    if (w & 0x0F3F0E00) == 0x0D1F0A00:
        return ("vldr", ((pc + 8) & ~3) + signo * (w & 0xFF) * 4)
    if (w & 0x0FFF0000) == 0x028F0000:
        return ("adr", pc + 8 + _rotimm(w))
    if (w & 0x0FFF0000) == 0x024F0000:
        return ("adr", pc + 8 - _rotimm(w))
    return None


def codificar_referencia(pc: int, w: int, destino: int) -> int | None:
    """Recodifica la instrucción ``w`` (de :func:`referencia`) en ``pc`` para que apunte a ``destino``.

    Devuelve None si el desplazamiento no cabe en la codificación.
    """
    ref = referencia(pc, w)
    if ref is None:
        return None
    clase = ref[0]
    if clase == "rama":
        off = destino - pc - 8
        if w >> 28 == 0xF:  # BLX a Thumb: el bit H lleva el medio
            if off % 2:
                return None
            h, off = (off >> 1) & 1, off & ~2
            base = (w & 0xFE000000) | (h << 24)
        else:
            if off % 4:
                return None
            base = w & 0xFF000000
        imm = off >> 2
        if not -(1 << 23) <= imm < (1 << 23):
            return None
        return base | (imm & 0xFFFFFF)
    if clase == "vldr":
        off = destino - ((pc + 8) & ~3)
        if off % 4 or abs(off) > 0x3FC:
            return None
        return (w & ~0x008000FF) | ((1 << 23) if off >= 0 else 0) | (abs(off) >> 2)
    off = destino - pc - 8
    if clase == "ldr":
        if abs(off) > 0xFFF:
            return None
        return (w & ~0x00800FFF) | ((1 << 23) if off >= 0 else 0) | abs(off)
    if clase == "ldrh":
        if abs(off) > 0xFF:
            return None
        a = abs(off)
        return (w & ~0x00800F0F) | ((1 << 23) if off >= 0 else 0) | ((a >> 4) << 8) | (a & 0xF)
    # adr
    imm = _codificar_rotimm(abs(off))
    if imm is None:
        return None
    opcode = 0x028F0000 if off >= 0 else 0x024F0000
    return (w & 0xF000F000) | opcode | imm


def _es_carga_literal_palabra(w: int) -> bool:
    return (w >> 28) != 0xF and (w & 0x0F7F0000) == 0x051F0000


def pares_pic(datos, inicio: int, fin: int) -> dict[int, int]:
    """Literales PIC de ``[inicio, fin)``: ``{offset del literal: offset de la instrucción que suma el PC}``.

    Patrón del compilador (y de las capas): ``ldr rX, [pc, #n]`` seguido, a menos de 8 instrucciones, de
    ``add rY, pc, rX`` (o ``add rY, rX, pc``) o ``ldr rY, [pc, rX]``. El literal vale
    ``destino - (instrucción + 8)``: depende de la posición relativa de código y datos. Varias cargas
    condicionales al mismo registro antes de la suma (``ldreq``/``ldrne``) son literales alternativos.
    """
    inicio = max(0, inicio - inicio % 4)
    n = (min(fin, len(datos)) - inicio) // 4
    if n <= 0:
        return {}
    w = np.frombuffer(bytes(datos[inicio:inicio + 4 * n]), dtype="<u4")
    cond_ok = (w >> 28) != 0xF
    add_reg = cond_ok & ((w & 0x0FE00FF0) == 0x00800000)
    ldr_reg = cond_ok & ((w & 0x0F300FF0) == 0x07100000)
    candidatos = np.nonzero(add_reg | ldr_reg)[0]
    salida: dict[int, int] = {}
    for j in candidatos.tolist():
        x = int(w[j])
        rn, rm = (x >> 16) & 0xF, x & 0xF
        if rn == 15 and rm != 15:
            otro = rm
        elif rm == 15 and rn != 15:
            otro = rn
        else:
            continue
        for k in range(1, 9):
            i = j - k
            if i < 0:
                break
            y = int(w[i])
            if _es_carga_literal_palabra(y) and ((y >> 12) & 0xF) == otro:
                pc = inicio + 4 * i
                ref = referencia(pc, y)
                if ref is not None:
                    salida.setdefault(ref[1], inicio + 4 * j)
                if y >> 28 == 0xE:  # carga incondicional: define el registro; las condicionales
                    break           # (ldreq/ldrne) de antes son alternativas del mismo literal PIC
    return salida


# ---------------------------------------------------------------------------------------------------
# Imagen normalizada
# ---------------------------------------------------------------------------------------------------


def _destinos_tabla(cro: Cro, cabecera: int) -> list[int]:
    segs = cro.segments
    off, n = cro._u32(cabecera), cro._u32(cabecera + 4)
    salida = []
    for i in range(n):
        so = cro._u32(off + 12 * i)
        if (so & 0xF) < len(segs):
            salida.append(segs[so & 0xF].offset + (so >> 4))
    return salida


def literales_absolutos(base: bytes, cand: bytes, *, rango: tuple[int, int] = (0x100000, 0x400000)) -> dict[int, int]:
    """Literales de la candidata con una dirección absoluta del ``code.bin``: ``{offset: valor}``.

    Son las palabras cambiadas que el código de la candidata carga con ``ldr rX, [pc, #n]`` (no PIC) y
    cuyo valor cae en ``rango`` (por defecto, la imagen del ejecutable). Su valor depende de la versión
    del code.bin y hay que traducirlo (:func:`mapear_direccion_absoluta`).
    """
    cc = Cro(cand)
    ini, fin = _huecos_codigo(cc)
    n = (fin - ini) // 4
    w = np.frombuffer(bytes(cand[ini:ini + 4 * n]), dtype="<u4")
    idx = np.nonzero(((w >> 28) != 0xF) & ((w & 0x0F7F0000) == 0x051F0000))[0]
    pic = pares_pic(cand, ini, fin)
    salida: dict[int, int] = {}
    for i in idx.tolist():
        pc = ini + 4 * i
        destino = referencia(pc, int(w[i]))[1]
        if destino in pic or not 0 <= destino <= len(cand) - 4 or cand[destino:destino + 4] == base[destino:destino + 4]:
            continue
        valor = _u32(cand, destino)
        if rango[0] <= valor < rango[1]:
            salida[destino] = valor
    return salida


def _huecos_codigo(cro: Cro) -> tuple[int, int]:
    """``[inicio, fin)`` del código ejecutable: del segmento de texto hasta el siguiente segmento."""
    segs = cro.segments
    texto = segs[0]
    siguiente = min((s.offset for s in segs[1:] if s.size and s.offset > texto.offset),
                    default=cro._u32(_TABLAS))
    return texto.offset, siguiente


def normalizar(cro: Cro) -> bytes:
    """Imagen de la CRO con a cero lo que depende del enlazado o de la posición.

    Se anulan: las palabras destino de las tablas de parches 0x128/0x130/0xF8 (el cargador las escribe),
    los inmediatos de las ramas B/BL de la región de código y los literales PIC. Dos compilaciones con
    el mismo código fuente desplazado dan la misma imagen alrededor de cada función.
    """
    d = bytearray(cro.datos)
    for cabecera in (_REL_OFF, 0x130, _EXT_OFF):
        for x in _destinos_tabla(cro, cabecera):
            d[x:x + 4] = bytes(4)
    ini, fin = _huecos_codigo(cro)
    n = (fin - ini) // 4
    w = np.frombuffer(bytes(d[ini:ini + 4 * n]), dtype="<u4").copy()
    ramas = ((w >> 25) & 7) == 5
    w[ramas] &= np.uint32(0xFF000000)
    d[ini:ini + 4 * n] = w.tobytes()
    for lit in pares_pic(cro.datos, ini, fin):
        if ini <= lit < fin:
            d[lit:lit + 4] = bytes(4)
    return bytes(d)


# ---------------------------------------------------------------------------------------------------
# Localización por contenido
# ---------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Localizacion:
    """Un tramo ``[inicio, fin)`` del origen localizado en ``destino`` con la ventana ``(izquierda, derecha)``."""

    inicio: int
    fin: int
    destino: int
    ventana: tuple[int, int]
    metodo: str = "contexto"

    @property
    def delta(self) -> int:
        return self.destino - self.inicio


class Mapeador:
    """Mapa ``offset en la CRO origen -> offset en la CRO destino`` por contenido normalizado."""

    def __init__(self, origen: Cro, destino: Cro, *, minimo: int = _MINIMO,
                 margenes: Sequence[int] = _MARGENES) -> None:
        self.origen, self.destino = origen, destino
        self.no, self.nd = normalizar(origen), normalizar(destino)
        self.segs_o, self.segs_d = origen.segments, destino.segments
        self.codigo_o, self.codigo_d = _huecos_codigo(origen), _huecos_codigo(destino)
        self.minimo, self.margenes = minimo, tuple(margenes)
        self.regiones: list[tuple[int, int, int]] = []
        self._cache: dict[int, int | None] = {}
        # Stubs de importación (``ldr pc, [pc, #-4]`` + palabra que escribe el cargador): tras normalizar
        # son todos iguales, así que se emparejan por el nombre del símbolo importado.
        self.thunks_o = {o: n for o, n in origen.imports().items() if _u32(origen.datos, o) == _THUNK}
        por_nombre: dict[str, list[int]] = {}
        for off, nombre in destino.imports().items():
            if _u32(destino.datos, off) == _THUNK:
                por_nombre.setdefault(nombre, []).append(off)
        self.thunks_d = por_nombre

    # -- regiones fijadas por el llamador (tramos ya localizados, cuevas, crecimiento) --
    def fijar(self, inicio: int, fin: int, destino: int) -> None:
        self.regiones.append((inicio, fin, destino))
        self._cache.clear()

    def _segmento(self, segs, off: int, codigo: tuple[int, int]) -> int | None:
        for i, s in enumerate(segs[:3]):
            if s.size and s.offset <= off < s.offset + s.size:
                return i
        if codigo[0] <= off < codigo[1]:
            return 0
        return None

    def _limites(self, segs, i: int, codigo: tuple[int, int]) -> tuple[int, int]:
        if i == 0:
            return codigo
        s = segs[i]
        return s.offset, s.offset + s.size

    def _buscar(self, patron: bytes, lo: int, hi: int) -> list[int]:
        hits, p = [], self.nd.find(patron, lo, hi)
        while p >= 0 and len(hits) < 2:
            hits.append(p)
            p = self.nd.find(patron, p + 1, hi)
        return hits

    def localizar(self, inicio: int, fin: int, *, preferir_derecha: bool = False) -> Localizacion | None:
        """Localiza ``[inicio, fin)`` en la destino: ventana normalizada que aparezca una sola vez."""
        seg = self._segmento(self.segs_o, inicio, self.codigo_o)
        if seg is None:
            return None
        lo_o, hi_o = self._limites(self.segs_o, seg, self.codigo_o)
        if seg >= len(self.segs_d) or not self.segs_d[seg].size:
            return None
        lo_d, hi_d = self._limites(self.segs_d, seg, self.codigo_d)
        formas = ((0, 1), (1, 1), (1, 0)) if preferir_derecha else ((1, 1), (0, 1), (1, 0))
        alinear = seg == 0
        for m in self.margenes:
            for fl, fr in formas:
                izq = min(m * fl, inicio - lo_o)
                der = min(m * fr, max(0, hi_o - fin))
                patron = self.no[inicio - izq:fin + der]
                if len(patron) < self.minimo:
                    continue
                hits = [h for h in self._buscar(patron, lo_d, hi_d) if not alinear or (h + izq - inicio) % 4 == 0]
                if len(hits) == 1:
                    return Localizacion(inicio, fin, hits[0] + izq, (izq, der))
        return None

    def mapear(self, off: int) -> int | None:
        """Offset destino de ``off`` (regiones fijadas, thunks de importación por nombre o contexto)."""
        if off in self._cache:
            return self._cache[off]
        res: int | None = None
        for ini, fin, dst in self.regiones:
            if ini <= off < fin:
                res = dst + (off - ini)
                break
        else:
            if off in self.thunks_o:
                cand = self.thunks_d.get(self.thunks_o[off], [])
                res = cand[0] if len(cand) == 1 else None
            else:
                loc = self.localizar(off, off + 4, preferir_derecha=True)
                res = loc.destino if loc else None
        self._cache[off] = res
        return res


# ---------------------------------------------------------------------------------------------------
# Diff e informes
# ---------------------------------------------------------------------------------------------------


def tramos_cambiados(a: bytes, b: bytes, *, separacion: int = 4, inicio: int = 0,
                     fin: int | None = None) -> list[tuple[int, int]]:
    """Tramos ``[ini, fin)`` donde ``a`` y ``b`` difieren, fusionando huecos de hasta ``separacion`` B."""
    fin = min(len(a), len(b)) if fin is None else fin
    if fin <= inicio:
        return []
    x = np.frombuffer(a, dtype=np.uint8, count=fin - inicio, offset=inicio)
    y = np.frombuffer(b, dtype=np.uint8, count=fin - inicio, offset=inicio)
    idx = np.nonzero(x != y)[0]
    salida: list[tuple[int, int]] = []
    for i in idx.tolist():
        i += inicio
        if salida and i - salida[-1][1] <= separacion:
            salida[-1] = (salida[-1][0], i + 1)
        else:
            salida.append((i, i + 1))
    return salida


def _es_lider(x: int) -> bool:
    return 0x81 <= x <= 0x9F or 0xE0 <= x <= 0xEF


def _es_cola(x: int) -> bool:
    return 0x40 <= x <= 0xFC and x != 0x7F


def es_texto_sjis(datos: bytes, *, max_control: float = 0.25) -> bool:
    """¿Son ``datos`` cadenas Shift-JIS (cp932 sin área de usuario) separadas por NUL?

    Se admiten ASCII imprimible, kana de medio ancho, pares de doble byte y códigos de control del juego
    (0x01-0x1F, como mucho ``max_control`` de los bytes no nulos). Hacen falta al menos 2 bytes visibles.
    Las instrucciones ARM casi nunca pasan: llevan bytes como 0xA0, 0x80, 0xFD-0xFF o muchos controles.
    """
    d = bytes(datos)
    i, visibles, control, no_nulos = 0, 0, 0, 0
    while i < len(d):
        x = d[i]
        if x == 0:
            i += 1
            continue
        if _es_lider(x):
            if i + 1 < len(d) and _es_cola(d[i + 1]):
                visibles += 2
                no_nulos += 2
                i += 2
                continue
            return False
        no_nulos += 1
        if 0x20 <= x <= 0x7E or 0xA1 <= x <= 0xDF or x in (0x09, 0x0A):
            visibles += 1
        elif x < 0x20:
            control += 1
        else:
            return False
        i += 1
    return visibles >= 2 and control <= max_control * max(no_nulos, 1)


def _limites_texto(d: bytes, a: int, e: int) -> tuple[int, int]:
    """Amplía ``[a, e)`` para no cortar un carácter de doble byte por ninguno de los dos extremos."""
    s = a
    # retrocede hasta un límite seguro (NUL o byte que no puede ser cola) para sincronizar los pares
    while s > 0 and a - s < 64 and d[s - 1] != 0 and _es_cola(d[s - 1]):
        s -= 1
    i = s
    while i < a:
        i += 2 if _es_lider(d[i]) and i + 1 < len(d) and _es_cola(d[i + 1]) else 1
    s = a - 1 if i > a else a
    t = e
    j = s
    while j < e:
        j += 2 if _es_lider(d[j]) and j + 1 < len(d) and _es_cola(d[j + 1]) else 1
    t = max(e, j)
    return s, t


def _es_subtramo_texto(base: bytes, cand: bytes, x: int, y: int) -> bool:
    """¿Es texto el cambio ``[x, y)`` (sin cortar caracteres de doble byte) en base y candidata?

    Solo se miran los bytes cambiados: con contexto, una cadena junto a un entero (``ff 7f 00 00``) deja
    de parecer texto y sus bytes se tomarían por ramas. El caso contrario (un cambio de 1-2 bytes en un
    inmediato ARM que forma un par Shift-JIS válido, p. ej. ``add r1, pc, #n``) lo recoge
    :func:`_misma_instruccion_pc` dentro de los subtramos de texto.
    """
    s1, t1 = _limites_texto(base, x, y)
    s2, t2 = _limites_texto(cand, x, y)
    return es_texto_sjis(base[s1:t1]) and es_texto_sjis(cand[s2:t2])


@dataclass
class ParcheRelocalizado:
    """Un parche (tramo coherente) de la candidata y su traslado a la CRO destino."""

    tipo: str
    inicio: int
    fin: int
    destino: int | None = None
    estado: str = "pendiente"
    motivo: str = ""
    ventana: tuple[int, int] | None = None
    remapeos: list[dict] = field(default_factory=list)
    escrituras: list[tuple[int, bytes]] = field(default_factory=list, repr=False)

    def a_dict(self) -> dict:
        return {
            "tipo": self.tipo,
            "inicio": hex(self.inicio),
            "fin": hex(self.fin),
            "bytes": self.fin - self.inicio,
            "destino": hex(self.destino) if self.destino is not None else None,
            "estado": self.estado,
            "motivo": self.motivo,
            "ventana": list(self.ventana) if self.ventana else None,
            "remapeos": self.remapeos,
        }


@dataclass
class ResultadoRelocalizacion:
    datos: bytes
    parches: list[ParcheRelocalizado]
    rangos: list[tuple[int, int]]
    segmentos: dict[int, tuple[int, int]] = field(default_factory=dict)

    @property
    def fallidos(self) -> list[ParcheRelocalizado]:
        return [p for p in self.parches if p.estado != "relocalizado"]

    @property
    def ok(self) -> bool:
        return not self.fallidos

    def resumen(self) -> dict:
        por: dict[str, dict[str, int]] = {}
        for p in self.parches:
            d = por.setdefault(p.tipo, {"total": 0, "relocalizados": 0, "fallidos": 0, "bytes": 0})
            d["total"] += 1
            d["bytes"] += p.fin - p.inicio
            d["relocalizados" if p.estado == "relocalizado" else "fallidos"] += 1
        return {
            "parches": len(self.parches),
            "relocalizados": len(self.parches) - len(self.fallidos),
            "fallidos": len(self.fallidos),
            "por_tipo": por,
            "segmentos_ampliados": {str(k): [hex(a), hex(b)] for k, (a, b) in self.segmentos.items()},
        }

    def informe(self) -> dict:
        return {"resumen": self.resumen(), "parches": [p.a_dict() for p in self.parches]}


# ---------------------------------------------------------------------------------------------------
# Relocalización
# ---------------------------------------------------------------------------------------------------


def _region_libre(datos: bytes, ini: int, fin: int) -> bool:
    return not any(datos[ini:fin])


def _agrupar(tramos: list[tuple[int, int]], separacion: int) -> list[tuple[int, int]]:
    salida: list[tuple[int, int]] = []
    for a, e in tramos:
        if salida and a - salida[-1][1] <= separacion:
            salida[-1] = (salida[-1][0], e)
        else:
            salida.append((a, e))
    return salida


class _Traductor:
    """Recalcula las palabras cambiadas de la candidata con referencias relativas a la posición."""

    def __init__(self, mapa: Mapeador, base: bytes, cand: bytes, dest: bytes,
                 absolutas: Mapping[int, int], pic_cand: dict[int, int], codigo: tuple[int, int],
                 ejecutable: tuple[int, int]) -> None:
        self.mapa, self.base, self.cand, self.dest = mapa, base, cand, dest
        self.absolutas, self.pic = absolutas, pic_cand
        self.pendientes = literales_absolutos(base, cand)
        #: destinos plausibles: ramas dentro del código (con las cuevas), cargas en código + rodata
        self.codigo, self.ejecutable = codigo, ejecutable

    def palabra(self, off: int, off_d: int, codigo: bool) -> tuple[int | None, dict | None, str]:
        """``(palabra nueva, remapeo o None, motivo si falla)`` para la palabra cambiada de ``off``."""
        w = _u32(self.cand, off)
        if off in self.pic:
            j = self.pic[off]
            destino = j + 8 + struct.unpack("<i", struct.pack("<I", w))[0]
            nd, nj = self.mapa.mapear(destino), self.mapa.mapear(j)
            if nd is None or nj is None:
                return None, None, f"literal PIC en {off:#x}: destino {destino:#x} o suma {j:#x} sin mapear"
            nuevo = (nd - (nj + 8)) & 0xFFFFFFFF
            return nuevo, {"offset": hex(off), "clase": "pic", "destino_origen": hex(destino),
                           "destino_nuevo": hex(nd)}, ""
        if off in self.pendientes and w not in self.absolutas:
            return None, None, f"literal {off:#x} = dirección del code.bin {w:#x} sin traducir (falta en absolutas)"
        if w in self.absolutas:
            nuevo = self.absolutas[w]
            return nuevo, {"offset": hex(off), "clase": "absoluta", "destino_origen": hex(w),
                           "destino_nuevo": hex(nuevo)}, ""
        if codigo:
            ref = referencia(off, w)
            if ref is not None and self._plausible(*ref):
                clase, destino = ref
                nd = self.mapa.mapear(destino)
                if nd is None:
                    return None, None, f"{clase} en {off:#x}: destino {destino:#x} sin mapear"
                nuevo = codificar_referencia(off_d, w, nd)
                if nuevo is None:
                    return None, None, f"{clase} en {off:#x}: {nd:#x} no cabe desde {off_d:#x}"
                return nuevo, {"offset": hex(off), "clase": clase, "destino_origen": hex(destino),
                               "destino_nuevo": hex(nd)}, ""
        return w, None, ""

    def _plausible(self, clase: str, destino: int) -> bool:
        """Una palabra de datos que parece una rama suele apuntar fuera del código: se copia tal cual."""
        lo, hi = self.codigo if clase == "rama" else self.ejecutable
        return lo <= destino < hi and destino % (4 if clase in ("rama", "ldr", "vldr") else 1) == 0

    def tramo(self, p: ParcheRelocalizado, subtramos: Sequence[tuple[int, int, bool]], codigo: bool, *,
              todo: bool = False) -> None:
        """Rellena ``p.escrituras`` para los subtramos ``(inicio, fin, es_texto)`` de ``p``.

        ``codigo``: el parche está en la región de código (se recalculan las instrucciones de los
        subtramos que no son texto). ``todo``: la región no existía en el origen (cueva/crecimiento).
        """
        for a, e, texto in subtramos:
            self._subtramo(p, a, e, codigo and not texto, todo)

    def _subtramo(self, p: ParcheRelocalizado, a: int, e: int, codigo: bool, todo: bool) -> None:
        delta = p.destino - p.inicio
        if not codigo:
            for i in range(a, e):
                if todo or self.cand[i] != self.base[i]:
                    p.escrituras.append((i + delta, bytes([self.cand[i]])))
            # Un inmediato retocado (``adr r1, #n`` -> ``#m``) puede parecer texto: si base y candidata
            # son la misma instrucción relativa al PC con el mismo registro, es código.
            if not todo:
                for w0 in range(a - a % 4, e, 4):
                    if _misma_instruccion_pc(self.base, self.cand, w0):
                        self._palabra(p, w0, w0 + delta, True)
            # Aquí no se buscan literales PIC ni direcciones absolutas: en texto, un par «ldr/add pc»
            # aparente es casualidad de los bytes Shift-JIS (y los pools reales van en subtramos de código).
            return
        for w0 in range(a - a % 4, e, 4):
            if not todo and self.cand[w0:w0 + 4] == self.base[w0:w0 + 4]:
                continue
            self._palabra(p, w0, w0 + delta, True)

    def _palabra(self, p: ParcheRelocalizado, off: int, off_d: int, codigo: bool) -> None:
        nuevo, rem, motivo = self.palabra(off, off_d, codigo)
        if nuevo is None:
            p.estado, p.motivo = "fallido", (p.motivo + "; " if p.motivo else "") + motivo
            return
        if rem is not None:
            p.remapeos.append(rem)
        p.escrituras = [(o, b) for o, b in p.escrituras if not off_d <= o < off_d + 4]
        p.escrituras.append((off_d, struct.pack("<I", nuevo)))


def _misma_instruccion_pc(base: bytes, cand: bytes, w0: int) -> bool:
    """¿La palabra de ``w0`` es, en base y candidata, la misma instrucción relativa al PC (otro inmediato)?"""
    wb, wc = _u32(base, w0), _u32(cand, w0)
    if wb == wc:
        return False
    rb, rc = referencia(w0, wb), referencia(w0, wc)
    if rb is None or rc is None or rb[0] != rc[0]:
        return False
    if rb[0] == "rama":
        return (wb >> 24) == (wc >> 24)
    return (wb & 0x0000F000) == (wc & 0x0000F000) and (wb >> 28) == (wc >> 28)


def _tabla(cro: Cro, cabecera: int) -> list[tuple[int, tuple]]:
    off, n = cro._u32(cabecera), cro._u32(cabecera + 4)
    return [(off + 12 * i, struct.unpack_from("<IBBBBI", cro.datos, off + 12 * i)) for i in range(n)]


def _destino_registro(segs, rec: tuple) -> int:
    so = rec[0]
    return segs[so & 0xF].offset + (so >> 4)


def relocalizar(base: bytes, cand: bytes, destino: bytes, *, absolutas: Mapping[int, int] | None = None,
                separacion: int = 16, progreso: Progreso | None = None) -> ResultadoRelocalizacion:
    """Traslada a ``destino`` los parches ``base -> cand`` (ver el docstring del módulo).

    ``absolutas``: direcciones absolutas del code.bin que usan las cuevas (origen -> destino).
    ``separacion``: tramos a menos de estos bytes forman un mismo parche.
    Devuelve los bytes resultantes (solo con los parches relocalizados) y el informe de cada parche.
    """
    absolutas = dict(absolutas or {})
    if len(base) != len(cand):
        raise ValueError("la base y la candidata deben medir lo mismo (el parche no cambia el tamaño)")
    cb, cc, cd = Cro(base), Cro(cand), Cro(destino)
    segs_b, segs_c, segs_d = cb.segments, cc.segments, cd.segments
    mapa = Mapeador(cb, cd)
    salida = bytearray(destino)
    parches: list[ParcheRelocalizado] = []
    rangos: list[tuple[int, int]] = []
    ampliados: dict[int, tuple[int, int]] = {}
    tablas_b = cb._u32(_TABLAS)
    cubierto = np.zeros(len(base), dtype=bool)

    # 1) Regiones nuevas tras cada segmento (cuevas y crecimiento) --------------------------------
    extra: list[tuple[ParcheRelocalizado, bool]] = []
    limites_b = sorted({s.offset for s in segs_b[:3] if s.size} | {tablas_b})
    limites_d = sorted({s.offset for s in segs_d[:3] if s.size} | {cd._u32(_TABLAS)})
    for k in range(3):
        sb, sc, sd = segs_b[k], segs_c[k], segs_d[k]
        if not sb.size:
            continue
        fin_b = sb.offset + sb.size
        tope_b = min((x for x in limites_b if x >= fin_b), default=len(base))
        difs = tramos_cambiados(base, cand, inicio=fin_b, fin=tope_b)
        crece = sc.size != sb.size
        if not difs and not crece:
            continue
        ini = fin_b
        fin = max([e for _, e in difs] + [sc.offset + sc.size])
        fin += -fin % 4
        fin_d = sd.offset + sd.size
        tope_d = min((x for x in limites_d if x >= fin_d), default=len(destino))
        dst = fin_d + ((ini - fin_d) % 16)
        tipo = "cueva" if k == 0 else "crecimiento"
        p = ParcheRelocalizado(tipo, ini, fin, dst)
        if sc.offset != sb.offset:
            p.estado, p.motivo = "fallido", "la candidata mueve el segmento"
        elif dst + (fin - ini) > tope_d:
            p.estado, p.motivo = "fallido", f"no cabe tras el segmento {k} de la destino ({tope_d - dst:#x} B libres)"
        elif not _region_libre(destino, fin_d, dst + (fin - ini)):
            p.estado, p.motivo = "fallido", "el relleno tras el segmento de la destino no está libre"
        else:
            mapa.fijar(ini, fin, dst)
            if crece:
                nuevo = dst + (sc.offset + sc.size - ini) - sd.offset
                ampliados[k] = (sd.size, max(sd.size, nuevo))
        cubierto[ini:fin] = True
        parches.append(p)
        extra.append((p, k == 0))

    # 2) Tramos dentro de los segmentos --------------------------------------------------------------
    internos: list[tuple[ParcheRelocalizado, list[tuple[int, int, bool]], bool]] = []
    grupos: list[tuple[int, int, int]] = []
    for k in range(3):
        sb = segs_b[k]
        if not sb.size:
            continue
        for a, e in _agrupar(tramos_cambiados(base, cand, inicio=sb.offset, fin=sb.offset + sb.size), separacion):
            grupos.append((a, e, k))
    total = len(grupos)
    for n, (a, e, k) in enumerate(grupos):
        if progreso:
            progreso(n, total)
        subtramos = []
        for x, y in tramos_cambiados(base, cand, inicio=a, fin=e):
            instruccion = k == 0 and any(_misma_instruccion_pc(base, cand, w) for w in range(x - x % 4, y, 4))
            subtramos.append((x, y, not instruccion and _es_subtramo_texto(base, cand, x, y)))
        textos = sum(1 for *_x, t in subtramos if t)
        codigo = k == 0 and textos < len(subtramos)
        if textos == len(subtramos):
            tipo = "cadena"
        elif textos:
            tipo = "mixto"
        else:
            tipo = "codigo" if codigo else "datos"
        p = ParcheRelocalizado(tipo, a, e)
        cubierto[a:e] = True
        a4, e4 = (a - a % 4, e + (-e % 4)) if codigo else (a, e)
        loc = mapa.localizar(a4, e4)
        if loc is None:
            p.estado, p.motivo = "fallido", "contexto de la 1.0 no encontrado (o ambiguo) en la destino"
        else:
            p.destino, p.ventana = loc.destino + (a - a4), loc.ventana
            mapa.fijar(a, e, p.destino)
        parches.append(p)
        internos.append((p, subtramos, codigo))
    if progreso:
        progreso(total, total)

    # 3) Traducción de las palabras ------------------------------------------------------------------
    ini_c, fin_c = _huecos_codigo(cc)
    pic = pares_pic(cand, ini_c, max(fin_c, max((p.fin for p, c in extra if c), default=0)))
    trad = _Traductor(mapa, base, cand, destino, absolutas, pic, (ini_c, fin_c), (segs_b[0].offset, tablas_b))
    for p, subtramos, codigo in internos:
        if p.estado == "pendiente":
            trad.tramo(p, subtramos, codigo)
    for p, codigo in extra:
        if p.estado == "pendiente":
            trad.tramo(p, [(p.inicio, p.fin, False)], codigo, todo=True)

    # 4) Relocalizaciones internas (0x128) y parches de importación (0xF8) ---------------------------
    for cabecera, tipo in ((_REL_OFF, "relocacion"), (_EXT_OFF, "importacion")):
        tb, tc, td = _tabla(cb, cabecera), _tabla(cc, cabecera), _tabla(cd, cabecera)
        if len(tb) != len(tc):
            raise ValueError(f"la candidata cambia el número de entradas de la tabla {cabecera:#x}")
        por_destino: dict[int, list[int]] = {}
        for off, rec in td:
            por_destino.setdefault(_destino_registro(segs_d, rec), []).append(off)
        for (off_b, rb), (_off_c, rc) in zip(tb, tc):
            if rb == rc:
                continue
            p = ParcheRelocalizado(tipo, off_b, off_b + 12)
            cubierto[off_b:off_b + 12] = True
            parches.append(p)
            loc_b, loc_c = _destino_registro(segs_b, rb), _destino_registro(segs_c, rc)
            nloc = mapa.mapear(loc_c)
            cands = por_destino.get(mapa.mapear(loc_b) if loc_b is not None else -1, [])
            if nloc is None or len(cands) != 1:
                p.estado, p.motivo = "fallido", f"destino {loc_b:#x} sin entrada única en la tabla destino"
                continue
            off_d = cands[0]
            rd = struct.unpack_from("<IBBBBI", destino, off_d)
            p.destino = off_d
            if rd[1] != rb[1]:
                p.estado, p.motivo = "fallido", "tipo de relocalización distinto"
                continue
            if tipo == "relocacion":
                vb = segs_b[rb[2]].offset + rb[5]
                vd = segs_d[rd[2]].offset + rd[5]
                if mapa.mapear(vb) != vd:
                    p.estado, p.motivo = "fallido", f"el valor original {vb:#x} no corresponde al de la destino {vd:#x}"
                    continue
                vc = segs_c[rc[2]].offset + rc[5]
                nv = mapa.mapear(vc)
                if nv is None:
                    p.estado, p.motivo = "fallido", f"valor nuevo {vc:#x} sin mapear"
                    continue
                tamanos = {i: s.size for i, s in enumerate(segs_d)}
                tamanos.update({i: n for i, (_a, n) in ampliados.items()})
                seg = next((i for i, s in enumerate(segs_d[:3])
                            if tamanos[i] and s.offset <= nv < s.offset + tamanos[i]), None)
                if seg is None:
                    p.estado, p.motivo = "fallido", f"valor nuevo {nv:#x} fuera de los segmentos"
                    continue
                if nloc == _destino_registro(segs_d, rd):
                    so = rd[0]
                else:
                    sl = _destino_seg(segs_d, nloc)
                    so = ((nloc - segs_d[sl].offset) << 4) | sl
                nuevo = struct.pack("<IBBBBI", so, rd[1], seg, rd[3], rd[4], nv - segs_d[seg].offset)
                p.remapeos.append({"offset": hex(loc_b), "clase": "relocacion", "destino_origen": hex(vc),
                                   "destino_nuevo": hex(nv)})
            else:
                if rd[5] != rb[5] or rd[2] != rb[2]:
                    p.estado, p.motivo = "fallido", "la entrada de importación destino no coincide con la base"
                    continue
                if rc[0] != rb[0]:
                    p.estado, p.motivo = "fallido", "la candidata cambia el destino de una importación"
                    continue
                nuevo = struct.pack("<IBBBBI", rd[0], rd[1], rc[2], rc[3], rc[4], rc[5])
            p.escrituras.append((off_d, nuevo))

    # 5) Tabla de segmentos ------------------------------------------------------------------------
    seg_tabla_b, seg_tabla_d = cb._u32(0xC8), cd._u32(0xC8)
    cubierto[seg_tabla_b:seg_tabla_b + 12 * len(segs_b)] = True

    # 6) Todo cambio de la candidata debe estar explicado --------------------------------------------
    sin_explicar = [(a, e) for a, e in tramos_cambiados(base, cand) if not cubierto[a:e].all()]
    for a, e in sin_explicar:
        parches.append(ParcheRelocalizado("otro", a, e, estado="fallido",
                                          motivo="cambio fuera de segmentos y tablas conocidas"))

    for p in parches:
        if p.estado == "pendiente":
            p.estado = "relocalizado"
            for off, datos in p.escrituras:
                salida[off:off + len(datos)] = datos
                rangos.append((off, off + len(datos)))
    for k, (_antes, nuevo) in ampliados.items():
        struct.pack_into("<I", salida, seg_tabla_d + 12 * k + 4, nuevo)
        rangos.append((seg_tabla_d + 12 * k + 4, seg_tabla_d + 12 * k + 8))
    return ResultadoRelocalizacion(bytes(salida), parches, rangos, ampliados)


def _destino_seg(segs, off: int) -> int:
    for i, s in enumerate(segs):
        if s.size and s.offset <= off < s.offset + s.size:
            return i
    return 0


# ---------------------------------------------------------------------------------------------------
# Verificación estructural
# ---------------------------------------------------------------------------------------------------


def verificar_estructura(original: bytes, resultado: bytes, rangos: Iterable[tuple[int, int]] = ()) -> list[str]:
    """Problemas estructurales de ``resultado`` (lista vacía = CRO coherente).

    Comprueba: mismo tamaño y cabecera; segmentos dentro del fichero, sin solaparse entre sí ni con las
    tablas; cada relocalización y parche de importación escribe dentro de un segmento y apunta dentro de
    uno; las tablas de importación/exportación intactas; y, si se dan ``rangos``, que solo cambian ellos.
    """
    problemas: list[str] = []
    if len(original) != len(resultado):
        problemas.append("el tamaño del fichero cambia")
        return problemas
    if original[0x80:0x138] != resultado[0x80:0x138]:
        problemas.append("la cabecera 0x80-0x138 cambia")
    cro = Cro(resultado)
    segs = cro.segments
    tablas = cro._u32(_TABLAS)
    activos = [(i, s) for i, s in enumerate(segs) if s.size and s.offset]
    for i, s in activos:
        if s.offset + s.size > len(resultado):
            problemas.append(f"segmento {i} fuera del fichero")
        if i < 3 and s.offset < tablas < s.offset + s.size:
            problemas.append(f"segmento {i} pisa las tablas")
    for (i, s), (j, t) in pairwise(activos):
        if s.offset + s.size > t.offset and s.offset < t.offset:
            problemas.append(f"segmentos {i} y {j} se solapan")
    for cabecera in (_REL_OFF, 0x130, _EXT_OFF):
        for off, rec in _tabla(cro, cabecera):
            so = rec[0]
            if (so & 0xF) >= len(segs):
                problemas.append(f"tabla {cabecera:#x} @{off:#x}: segmento inexistente")
                continue
            s = segs[so & 0xF]
            if not s.offset <= s.offset + (so >> 4) < s.offset + max(s.size, 4):
                problemas.append(f"tabla {cabecera:#x} @{off:#x}: destino fuera del segmento")
            if cabecera == _REL_OFF and (rec[2] >= len(segs) or rec[5] > segs[rec[2]].size):
                problemas.append(f"relocación @{off:#x}: valor fuera del segmento {rec[2]}")
    if rangos:
        permitido = np.zeros(len(resultado), dtype=bool)
        for a, e in rangos:
            permitido[a:e] = True
        difs = np.nonzero(np.frombuffer(original, np.uint8) != np.frombuffer(resultado, np.uint8))[0]
        fuera = [int(x) for x in difs if not permitido[x]]
        if fuera:
            problemas.append(f"{len(fuera)} B cambiados fuera de los parches (primero {fuera[0]:#x})")
    return problemas


# ---------------------------------------------------------------------------------------------------
# Direcciones absolutas del code.bin
# ---------------------------------------------------------------------------------------------------


def mapear_direccion_absoluta(code_origen: bytes, code_destino: bytes, direccion: int, *,
                              carga: int = 0x100000, ventanas: Sequence[int] = (32, 64, 128, 256)) -> dict:
    """Traduce una dirección absoluta (p. ej. un global de ``.data``) entre dos ``code.bin`` planos.

    Busca los literales del origen que valen ``direccion``, localiza el código que los precede en el
    destino (ramas y direcciones absolutas normalizadas) y lee el literal equivalente. Devuelve
    ``{"direccion", "destino" (None si no hay consenso), "votos", "referencias", "candidatos"}``.
    """

    def norm(d: bytes) -> bytes:
        n = len(d) // 4
        w = np.frombuffer(d[:4 * n], dtype="<u4").copy()
        w[((w >> 25) & 7) == 5] &= np.uint32(0xFF000000)
        w[(w >= carga) & (w < carga + 0x1000000)] = 0
        return w.tobytes()

    no, nd = norm(code_origen), norm(code_destino)
    w = np.frombuffer(code_origen[:len(code_origen) // 4 * 4], dtype="<u4")
    refs = (np.nonzero(w == direccion)[0] * 4).tolist()
    votos: dict[int, int] = {}
    for r in refs:
        for v in ventanas:
            if r < v:
                continue
            patron = no[r - v:r]
            hits, p = [], nd.find(patron)
            while p >= 0 and len(hits) < 2:
                if p % 4 == 0:
                    hits.append(p)
                p = nd.find(patron, p + 1)
            if len(hits) == 1:
                valor = _u32(code_destino, hits[0] + v)
                votos[valor] = votos.get(valor, 0) + 1
                break
    mejor = max(votos, key=votos.get) if votos else None
    consenso = mejor is not None and votos[mejor] >= 2 and all(
        n * 4 <= votos[mejor] for k, n in votos.items() if k != mejor)
    return {"direccion": direccion, "destino": mejor if consenso else None,
            "votos": votos.get(mejor, 0) if mejor is not None else 0, "referencias": len(refs),
            "candidatos": {hex(k): n for k, n in votos.items()}}


def verificar_relocalizacion(base: bytes, cand: bytes, destino: bytes, resultado: ResultadoRelocalizacion, *,
                             ventana: int = 16) -> list[str]:
    """Comprobación independiente de un :class:`ResultadoRelocalizacion` (lista vacía = todo cuadra).

    Para cada parche relocalizado de código/datos: los bytes escritos en la destino son los de la
    candidata salvo las palabras remapeadas. Para cada remapeo (rama, carga PC, ADR, PIC, relocalización):
    lo que hay en el destino nuevo, normalizado, es lo mismo que en el destino original de la candidata
    (``ventana`` bytes). Así se comprueba que cada salto o puntero trasladado llega a la misma función,
    cadena o literal. Y cada literal PIC/rama de la salida decodifica al destino anotado.
    """
    problemas: list[str] = []
    nc, nr = normalizar(Cro(cand)), normalizar(Cro(resultado.datos))
    out = resultado.datos
    for p in resultado.parches:
        if p.estado != "relocalizado" or p.tipo in ("relocacion", "importacion"):
            continue
        delta = p.destino - p.inicio
        remapeadas = {int(r["offset"], 16) for r in p.remapeos}
        nuevo = p.tipo in ("cueva", "crecimiento")
        for i in range(p.inicio, p.fin):
            if i - i % 4 in remapeadas:
                continue
            # lo cambiado debe ser lo de la candidata; lo no cambiado, lo que ya tenía la destino
            esperado = cand[i] if nuevo or cand[i] != base[i] else destino[i + delta]
            if out[i + delta] != esperado:
                problemas.append(f"{p.tipo} {p.inicio:#x}: byte {i:#x} inesperado en {i + delta:#x}")
                break
    absolutas = {int(r["offset"], 16) for p in resultado.parches for r in p.remapeos if r["clase"] == "absoluta"}
    for p in resultado.parches:
        if p.estado != "relocalizado":
            continue
        for r in p.remapeos:
            if r["clase"] == "absoluta":
                continue
            a, b = int(r["destino_origen"], 16), int(r["destino_nuevo"], 16)
            n = ventana
            if r["clase"] in ("relocacion", "pic", "adr"):  # datos: hasta el fin de la cadena
                nul = cand.find(b"\0", a, a + ventana)
                n = nul - a + 1 if nul >= 0 else ventana
            if a in absolutas:  # literal cuyo valor es una dirección del code.bin ya traducida
                continue
            if nc[a:a + n] != nr[b:b + n]:
                problemas.append(f"{p.tipo} {p.inicio:#x}: {r['clase']} {r['offset']} llega a contenido distinto "
                                 f"({a:#x} -> {b:#x})")
            if r["clase"] in ("rama", "ldr", "ldrh", "vldr", "adr"):
                off = int(r["offset"], 16) + (p.destino - p.inicio)
                ref = referencia(off, _u32(out, off))
                if ref is None or ref[1] != b:
                    problemas.append(f"{p.tipo} {p.inicio:#x}: la instrucción de {off:#x} no apunta a {b:#x}")
            elif r["clase"] == "pic":
                off = int(r["offset"], 16) + (p.destino - p.inicio)
                if off not in pares_pic(out, off - 0x1000, off + 0x1000):
                    problemas.append(f"{p.tipo} {p.inicio:#x}: el literal PIC {off:#x} ya no se usa como tal")
    return problemas
