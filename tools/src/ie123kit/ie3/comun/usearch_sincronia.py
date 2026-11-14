"""IE3 · sincronía de ``usearch.dat`` con el nombre corto actual de ``unitbase.dat`` (paso del hook de nombres).

Formato (ver :mod:`ie123kit.ie3.comun.registro_usearch`): usearch de 44 B (+0x00 nombre mostrado, +0x24 id),
unitbase de 0x68 B (+0x1C nombre corto, +0x4E id). Hay tres pares, cada uno con SU unitbase (los de ``ex_binder``
salen de ``registro_datos`` y difieren en algunos ids): ``inazuma3/…/logic``, ``inazuma3_ogre/…/logic`` y
``inazuma3_ogre/…/logic/ex_binder``.

Diferencia con IE1/IE2: en IE3 no se ha localizado ningún comparador de texto tecleado contra usearch; +0x00 es el
texto de las listas del Registro/Álbum y se escribe con la misma codificación que el unitbase (latín de 1 byte y
portadores 0x83 0x9F…), no en ancho completo (el parche de la CRO calcula la pestaña con el primer byte).

Regla de coherencia (la que cumple hoy lo instalado, con 0 casos «otro» en los tres pares): para cada id != 0,
``+0x00`` es igual al corto de unitbase, o unitbase es ``acortar(+0x00)`` (la capa ``nombres_cortos_6`` recorta a 6
casillas el corto de unitbase, pero ``album_usearch`` escribió usearch con el corto previo, más largo; copiar el
corto recortado cambiaría 851/852/857 registros y la lista dejaría de verse con el nombre completo). Solo si un
registro deja de ser coherente (un nombre nuevo o renombrado en unitbase) se reescribe ``+0x00`` con el corto
actual, como hace ``registro_usearch.nombres``, y se reordena (``registro_usearch.ordenar``; ``ex_binder`` con la
regla de la capa ``lista_registro_latina``, que no cuenta como ordenable un nombre no visible con inicial en
portador). Sin cambios no se reordena: la salida es idéntica byte a byte a la actual.

LÍMITE DE LA REGLA «ACORTADO» y cómo se refuerza. Mirando solo el ``archive.fa`` final, un renombrado de unitbase cuyo
resultado coincide con ``acortar(usearch)`` es indistinguible del recorte legítimo de ``nombres_cortos_6`` (el mismo
texto, sin desincronía real que corregir), y ``verificar`` sobre un archive suelto no puede detectarlo: está documentado
como límite. En la CONSTRUCCIÓN sí se conoce el unitbase de la base: ``sincronizar(base_unitbase=…)`` solo acepta la
relación «acortado» para un id cuyo corto cambió respecto a la base si el nuevo es ``acortar`` del corto de la base
(el recorte legítimo); si cambió a otra cosa que casualmente coincide con ``acortar(usearch)`` (base ya desincronizada)
se trata como renombrado y se reescribe ``+0x00``. Sigue sin detectarse el renombrado a exactamente ``acortar`` del
nombre anterior (es ese mismo recorte).

Funciones puras (bytes -> bytes).
"""
from __future__ import annotations

import struct
from collections import Counter
from dataclasses import dataclass, field

from ie123kit.ie3.comun import registro_usearch as RU
from ie123kit.ie3.comun.nombres_cortos_limite import acortar

__all__ = ["ESQUEMAS", "EsquemaIe3", "Hallazgo", "Informe", "ordenar", "sincronizar", "verificar"]


@dataclass(frozen=True)
class EsquemaIe3:
    juego: str
    ruta_usearch: str
    ruta_unitbase: str
    #: ``logic`` (registro_usearch.ordenar) o ``ex_binder`` (regla de lista_registro_latina)
    orden: str


ESQUEMAS: dict[str, EsquemaIe3] = {
    "ie3.inazuma3": EsquemaIe3("ie3", "inazuma3/data_iz/logic/usearch.dat", "inazuma3/data_iz/logic/unitbase.dat", "logic"),
    "ie3.inazuma3_ogre": EsquemaIe3(
        "ie3", "inazuma3_ogre/data_iz/logic/usearch.dat", "inazuma3_ogre/data_iz/logic/unitbase.dat", "logic"
    ),
    "ie3.ex_binder": EsquemaIe3(
        "ie3",
        "inazuma3_ogre/data_iz/logic/ex_binder/usearch.dat",
        "inazuma3_ogre/data_iz/logic/ex_binder/unitbase.dat",
        "ex_binder",
    ),
}

R_US = RU.R_USEARCH
R_UB = RU.R_UNITBASE
#: el byte 15 del campo es la marca de fila de lista_registro_abc y no forma parte del nombre
UTILES = 15


def _campo(b: bytes, off: int) -> bytes:
    return b[off:off + 16].split(b"\0", 1)[0][:UTILES]


def _indice(unitbase: bytes) -> dict[int, int]:
    indice: dict[int, int] = {}
    for k in range(len(unitbase) // R_UB):
        ident = struct.unpack_from("<H", unitbase, k * R_UB + RU.ID)[0]
        if ident:
            indice.setdefault(ident, k)
    return indice


def _coherente(usearch_nombre: bytes, unitbase_nombre: bytes) -> bool:
    return usearch_nombre == unitbase_nombre or acortar(usearch_nombre) == unitbase_nombre


def ordenar(us: bytes, orden: str) -> bytes:
    """Orden alfabético por pestaña: ``logic`` es ``registro_usearch.ordenar``; ``ex_binder`` usa la regla de
    ``lista_registro_latina.reordenar`` (ordenable = visible o inicial ASCII alfabética)."""
    if orden == "logic":
        return RU.ordenar(us, us)
    if orden != "ex_binder":
        raise ValueError(f"orden desconocido: {orden!r}")
    regs = [us[k * R_US:(k + 1) * R_US] for k in range(len(us) // R_US)]

    def ordenable(r: bytes) -> bool:
        n = r[:16].split(b"\0", 1)[0]
        return RU.visible(r) or (n[:1].isalpha() and n[:1].isascii())

    def clave_orden(r: bytes):
        n = r[:16].split(b"\0", 1)[0]
        latina = RU.letra(n) != RU.RESERVA or RU.clave(n)[:1] == "Z"
        return (RU.letra(n), 0 if latina else 1, RU.clave(n), n, struct.unpack_from("<H", r, 0x24)[0])

    posiciones = [k for k, r in enumerate(regs) if ordenable(r)]
    for k, r in zip(posiciones, sorted((regs[k] for k in posiciones), key=clave_orden)):
        regs[k] = r
    return b"".join(regs)


@dataclass
class Informe:
    registros: int = 0
    sin_id: int = 0
    iguales: int = 0
    acortados: int = 0
    reescritos: int = 0
    #: ids cuyo corto de unitbase cambió respecto a la base a algo que solo coincidía con ``acortar(usearch)`` (se
    #: reescriben: es un renombrado, no el recorte de nombres_cortos_6); 0 si no se conoce la base
    renombrados_coincidentes: int = 0
    sin_unitbase: int = 0
    reordenado: bool = False
    posiciones_movidas: int = 0
    #: el registro que más se desplaza al ordenar (en lo instalado, «Sue» id 2450): id, nombre, de, a
    mayor_desplazamiento: dict | None = None
    ejemplos: list[dict] = field(default_factory=list)
    #: registros ya coherentes (nombre de unitbase -> bytes de usearch), solo para el informe
    coherentes: list[dict] = field(default_factory=list)

    def a_json(self) -> dict:
        return {
            "registros": self.registros,
            "id_cero_sin_tocar": self.sin_id,
            "iguales_al_corto": self.iguales,
            "acortados_por_nombres_cortos_6": self.acortados,
            "reescritos": self.reescritos,
            "renombrados_coincidentes_con_acortado": self.renombrados_coincidentes,
            "sin_unitbase": self.sin_unitbase,
            "reordenado": self.reordenado,
            "posiciones_movidas_al_ordenar": self.posiciones_movidas,
            "mayor_desplazamiento_al_ordenar": self.mayor_desplazamiento,
            "ejemplos": self.ejemplos,
            "ejemplos_coherentes": self.coherentes,
        }


def _cortos_por_id(unitbase: bytes) -> dict[int, bytes]:
    return {ident: _campo(unitbase, k * R_UB + RU.CORTO) for ident, k in _indice(unitbase).items()}


def sincronizar(
    esquema: EsquemaIe3, usearch: bytes, unitbase: bytes, *, ejemplos: int = 0, base_unitbase: bytes | None = None,
) -> tuple[bytes, Informe]:
    """usearch coherente con el corto actual de unitbase y en orden; idéntico al de entrada si ya lo está.

    ``base_unitbase`` es el unitbase de la BASE de la construcción (si se conoce): permite distinguir un renombrado que
    coincide con ``acortar(usearch)`` del recorte legítimo (ver la docstring del módulo).
    """
    if len(usearch) % R_US or len(unitbase) % R_UB:
        raise ValueError("usearch/unitbase con un tamaño que no es múltiplo del registro")
    indice = _indice(unitbase)
    cortos_base = _cortos_por_id(base_unitbase) if base_unitbase and not len(base_unitbase) % R_UB else {}
    salida = bytearray(usearch)
    inf = Informe(registros=len(usearch) // R_US)
    for n in range(inf.registros):
        o = n * R_US
        ident = struct.unpack_from("<H", usearch, o + 0x24)[0]
        if not ident:
            inf.sin_id += 1
            continue
        k = indice.get(ident)
        if k is None:
            inf.sin_unitbase += 1
            continue
        actual, corto = _campo(usearch, o), _campo(unitbase, k * R_UB + RU.CORTO)
        previo = cortos_base.get(ident)
        renombrado = previo is not None and previo != corto and acortar(previo) != corto
        if actual != corto and acortar(actual) == corto and renombrado:
            inf.renombrados_coincidentes += 1
        if actual == corto or (acortar(actual) == corto and not renombrado):
            tipo = "igual" if actual == corto else "acortado"
            inf.iguales += tipo == "igual"
            inf.acortados += tipo == "acortado"
            if (sum(1 for x in inf.coherentes if x["tipo"] == tipo) < ejemplos
                    and any(c.isalpha() for c in corto.decode("cp932", "replace"))):
                inf.coherentes.append({"tipo": tipo, "id": ident, "indice_usearch": n, "indice_unitbase": k,
                                       "unitbase_corto": corto.decode("cp932", "replace"),
                                       "unitbase_bytes": corto.hex(" "), "usearch_bytes": actual.hex(" ")})
        else:
            salida[o:o + 16] = corto.ljust(16, b"\0")
            inf.reescritos += 1
            if len(inf.ejemplos) < ejemplos:
                inf.ejemplos.append({"id": ident, "indice_usearch": n, "indice_unitbase": k,
                                     "antes": usearch[o:o + 16].hex(" "), "despues": bytes(salida[o:o + 16]).hex(" "),
                                     "nombre": corto.decode("cp932", "replace")})
    resultado = ordenar(bytes(salida), esquema.orden)
    inf.reordenado = resultado != bytes(salida)
    inf.posiciones_movidas = sum(
        resultado[i * R_US:(i + 1) * R_US] != salida[i * R_US:(i + 1) * R_US] for i in range(inf.registros)
    )
    if inf.reordenado:
        antes = {struct.unpack_from("<H", salida, i * R_US + 0x24)[0]: i for i in range(inf.registros)}
        despues = {struct.unpack_from("<H", resultado, i * R_US + 0x24)[0]: i for i in range(inf.registros)}
        ident = max((i for i in antes if i), key=lambda i: abs(despues[i] - antes[i]))
        inf.mayor_desplazamiento = {
            "id": ident, "nombre": _campo(resultado, despues[ident] * R_US).decode("cp932", "replace"),
            "de": antes[ident], "a": despues[ident],
        }
    return resultado, inf


@dataclass(frozen=True)
class Hallazgo:
    codigo: str
    gravedad: str
    mensaje: str
    ident: int | None = None

    def __str__(self) -> str:
        return f"[{self.gravedad}] {self.codigo}: {self.mensaje}"


def verificar(esquema: EsquemaIe3, usearch: bytes, unitbase: bytes) -> list[Hallazgo]:
    """Hallazgos de sincronía de un par usearch/unitbase de IE3 (lista vacía de errores = en sincronía)."""
    h: list[Hallazgo] = []
    if not usearch or len(usearch) % R_US:
        return [Hallazgo("USEARCH_TAMANO", "error", f"usearch mide {len(usearch)} B (registros de {R_US})")]
    if not unitbase or len(unitbase) % R_UB:
        return [Hallazgo("UNITBASE_TAMANO", "error", f"unitbase mide {len(unitbase)} B (registros de {R_UB})")]
    indice = _indice(unitbase)
    for n in range(len(usearch) // R_US):
        o = n * R_US
        ident = struct.unpack_from("<H", usearch, o + 0x24)[0]
        if not ident:
            continue
        k = indice.get(ident)
        if k is None:
            h.append(Hallazgo("USEARCH_ID_HUERFANO", "error", f"usearch[{n}] id={ident}: no existe en unitbase", ident))
            continue
        actual, corto = _campo(usearch, o), _campo(unitbase, k * R_UB + RU.CORTO)
        if not _coherente(actual, corto):
            h.append(Hallazgo("USEARCH_DESINCRONIZADO", "error",
                              f"usearch[{n}] id={ident}: +0x00={actual!r} no es el corto de unitbase[{k}]={corto!r} "
                              f"ni su acortado", ident))
        if usearch[o + 15]:
            h.append(Hallazgo("USEARCH_BYTE15", "aviso", f"usearch[{n}] id={ident}: +0x0F != 0 (marca de fila)", ident))
    ordenado = ordenar(usearch, esquema.orden)
    if ordenado != usearch:
        movidos = [i for i in range(len(usearch) // R_US)
                   if ordenado[i * R_US:(i + 1) * R_US] != usearch[i * R_US:(i + 1) * R_US]]
        h.append(Hallazgo("USEARCH_ORDEN", "error",
                          f"los registros no están en el orden alfabético por pestaña ({len(movidos)} posiciones "
                          f"cambiarían; primera: {movidos[0]})"))
    return h


def contar(hallazgos: list[Hallazgo]) -> Counter:
    return Counter(f"{x.gravedad}:{x.codigo}" for x in hallazgos)
