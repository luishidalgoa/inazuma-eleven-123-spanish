"""IE3 · listas de búsqueda del Registro/Álbum (usearch.dat) con los nombres cortos en español.

usearch.dat: registros de 44 B.
  +0x00  nombre que muestra la lista (16 B; en japonés, el nombre corto en kana)
  +0x10  clave de orden/búsqueda (16 B, kana)
  +0x20  cola de 12 B; +0x24 u16 = identificador del jugador (unitbase +0x4E)
unitbase.dat: registros de 0x68 B; +0x1C nombre corto (16 B), +0x4E identificador.

Hay tres: ``inazuma3_ogre/.../ex_binder/usearch.dat`` (Registro de Extras) y ``logic/usearch.dat`` de las dos raíces
(Álbum). Con la capa lista_registro_latina en la CRO, la pestaña sale del nombre mostrado (0x26b568: A..Z en las
10 filas kana: A-C D-F G-I J-L M-O P-R S T-V W-Y Z) y los contadores se recalculan al abrir la lista, así que
usearch va en orden alfabético global, como el europeo.

Funciones puras (bytes -> bytes): la lectura y escritura del archive la hace la capa que las llama.
"""
from __future__ import annotations

import struct
import unicodedata

__all__ = [
    "FILAS",
    "GRUPOS",
    "INDICE",
    "R_UNITBASE",
    "R_USEARCH",
    "clave",
    "fila_kana",
    "letra",
    "nombres",
    "ordenar",
    "visible",
]

R_USEARCH = 44
R_UNITBASE = 0x68
CORTO = 0x1C
ID = 0x4E
#: segundo byte de los portadores 0x83 0x9F..0xAE (á é í ó ú ü ñ Á É Í Ó Ú Ñ ¡ ¿ È) -> letra base
PORTADOR = "AEIOUUNAEIOUN\0\0E"
#: pestañas latinas de lista_registro_latina sobre las 10 filas kana (índices 1..46 de 0x26b568)
GRUPOS = ["ABC", "DEF", "GHI", "JKL", "MNO", "PQR", "S", "TUV", "WXY", "Z"]
INICIOS = [1, 6, 11, 16, 21, 26, 31, 36, 39, 44]
INDICE = {c: INICIOS[t] + i for t, g in enumerate(GRUPOS) for i, c in enumerate(g)}
RESERVA = INDICE["Z"]
#: (fila, rangos Shift-JIS) de la función japonesa 0xc054 (hiragana y katakana de cada fila)
FILAS = [(0, [(0x829F, 10), (0x8340, 10), (0x8394, 1)]), (1, [(0x82A9, 10), (0x834A, 10), (0x8395, 2)]),
         (2, [(0x82B3, 10), (0x8354, 10)]), (3, [(0x82BD, 11), (0x835E, 11)]), (4, [(0x82C8, 5), (0x8369, 5)]),
         (5, [(0x82CD, 15), (0x836E, 15)]), (6, [(0x82DC, 5), (0x837D, 2), (0x8380, 3)]),
         (7, [(0x82E1, 6), (0x8383, 6)]), (8, [(0x82E7, 5), (0x8389, 5)]), (9, [(0x82ED, 6), (0x838E, 6)])]


def fila_kana(texto: bytes) -> int:
    """Fila kana (0 = あ … 9 = わ) del primer carácter Shift-JIS, o -1."""
    if len(texto) < 2:
        return -1
    c = (texto[0] << 8) | texto[1]
    for fila, rangos in FILAS:
        if any(ini <= c < ini + n for ini, n in rangos):
            return fila
    return -1


def clave(nombre: bytes) -> str:
    """Clave de orden alfabético de un nombre en latín de 1 byte con portadores de tilde (sin acentos, mayúsculas)."""
    t, i = [], 0
    while i < len(nombre):
        b = nombre[i]
        if b == 0x83 and i + 1 < len(nombre) and 0 <= nombre[i + 1] - 0x9F < 16:
            t.append(PORTADOR[nombre[i + 1] - 0x9F])
            i += 2
        elif b >= 0x80:
            t.append("~")
            i += 2
        else:
            t.append(chr(b))
            i += 1
    return unicodedata.normalize("NFKD", "".join(t)).encode("ascii", "ignore").decode().replace("\0", "").upper()


def letra(nombre: bytes) -> int:
    """Índice de letra (1..46) que calcula 0x26b568 con la capa lista_registro_latina; no latino -> Z (44)."""
    if not nombre:
        return RESERVA
    b = nombre[0]
    if b == 0x83 and len(nombre) > 1:
        k = nombre[1] - 0x9F
        if not 0 <= k < 16 or PORTADOR[k] == "\0":
            return RESERVA
        b = ord(PORTADOR[k])
    c = (b & ~0x20) - 0x41
    return INDICE[chr(0x41 + c)] if 0 <= c < 26 else RESERVA


def visible(r: bytes) -> bool:
    """Registro que la lista muestra (id, +0x2A == 1 y bit 1 de +0x2B)."""
    return bool(struct.unpack_from("<H", r, 0x24)[0]) and r[0x2A] == 1 and bool(r[0x2B] & 2)


def _campo(b: bytes, o: int, n: int = 16) -> bytes:
    return b[o:o + n].split(b"\0", 1)[0]


def nombres(us_jp: bytes, u_jp: bytes, u_es: bytes) -> tuple[bytes, dict]:
    """usearch japonés con +0x00 = nombre corto español del jugador (+0x24) cuando el japonés coincide."""
    corto: dict[int, tuple[bytes, bytes]] = {}
    for i in range(len(u_jp) // R_UNITBASE):
        o = i * R_UNITBASE
        uid = struct.unpack_from("<H", u_jp, o + ID)[0]
        jp_c, es_c = _campo(u_jp, o + CORTO), _campo(u_es, o + CORTO)
        if uid and es_c != jp_c:
            corto.setdefault(uid, (jp_c, es_c))
    salida = bytearray(us_jp)
    inf = {"cambiados": 0, "sin_traduccion": 0, "nombre_distinto": 0}
    for k in range(len(us_jp) // R_USEARCH):
        o = k * R_USEARCH
        par = corto.get(struct.unpack_from("<H", us_jp, o + 0x24)[0])
        if par is None:
            inf["sin_traduccion"] += 1
        elif par[0] != _campo(us_jp, o):
            inf["nombre_distinto"] += 1
        else:
            # el último byte (+15) queda libre para la marca de fila de lista_registro_abc
            salida[o:o + 16] = par[1][:15].ljust(16, b"\0")
            inf["cambiados"] += 1
    return bytes(salida), inf


def ordenar(us_jp: bytes, us: bytes) -> bytes:
    """Orden alfabético global como el europeo, agrupado por el índice de letra de lista_registro_latina.

    Los registros ordenables (visibles o con inicial latina) ocupan sus mismas posiciones, rellenadas por
    (letra, latino antes que no latino, clave, nombre, id); los demás («？？？», 未定…) no se mueven. Las partidas no
    dependen de este orden (los registrados van por unitno.dat y los contadores se recalculan al abrir la lista)."""
    if len(us_jp) != len(us):
        raise ValueError("usearch con otro número de registros que el japonés")
    regs = [us[k * R_USEARCH:(k + 1) * R_USEARCH] for k in range(len(us) // R_USEARCH)]

    def ordenable(r: bytes) -> bool:
        n = _campo(r, 0)
        return visible(r) or (n[:1].isalpha() and n[:1].isascii()) or letra(n) != RESERVA

    def orden(r: bytes):
        n = _campo(r, 0)
        latina = letra(n) != RESERVA or clave(n)[:1] == "Z"
        return (letra(n), 0 if latina else 1, clave(n), n, struct.unpack_from("<H", r, 0x24)[0])

    pos = [k for k, r in enumerate(regs) if ordenable(r)]
    for k, r in zip(pos, sorted((regs[k] for k in pos), key=orden)):
        regs[k] = r
    return b"".join(regs)
