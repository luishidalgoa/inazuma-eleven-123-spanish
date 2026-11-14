"""usearch.dat de IE1 e IE2 (registros de 48 B) derivado del nombre actual de ``unitbase.dat``.

Es la base del «hook» de nombres: ``usearch.dat`` es un dato DERIVADO del ``unitbase.dat`` final. La búsqueda
por nombre de Ojear/Fichar (comparador de la CRO: IE2 0xf628 en la 1.4, IE1 0xf98c JP / 0xfab8 EU) compara por
PREFIJO, byte a byte y distinguiendo mayúsculas, lo que teclea el jugador con:

* ``+0x10`` (lectura kana en el japonés): si casa, acepta;
* ``+0x00`` (nombre), solo si el bit 0 de ``+0x2b`` está a 0 (a 1 el comparador SALTA ``+0x00``).

DISPOSICIÓN DE LOS DATOS (decidida con el análisis H5 de la CRO instalada, ronda 2). Hay otro consumidor de
``+0x00``: el clasificador de filas kana de la lista «Por nombre» del Registro (IE1 0xd6334, IE2 0x10ae10, llamado con
la base del registro desde IE1 0x1b72c/0x1d770 e IE2 0x1c59c/0x1deb4/0x1fb20). Lee los 2 primeros bytes del registro
y devuelve -1 si no son hiragana/katakana: con letras latinas en ``+0x00`` el registro desaparece de esa lista (598
jugadores en IE1, 1080 en IE2, medido con la función real emulada). ``+0x10`` solo lo lee el comparador. Por eso:

* ``+0x10`` := nombre visible del registro de ``unitbase.dat`` con el mismo identificador (usearch ``+0x24`` =
  unitbase ``+0x42``), pasado a texto (se expanden los bigramas de FONT12) y recodificado como lo teclea el teclado
  latino del proyecto: una letra = 2 B de ancho completo (acentos = portadores griegos), como máximo 8 letras
  (16 B, sin NUL si llena el campo), relleno con ``00``. Se conservan las mayúsculas oficiales.
* ``+0x00`` (kana: lo ve el clasificador), ``+0x2b`` (flags, bit 0 incluido), el orden y el resto, SIN CAMBIOS.
  El comparador prueba ``+0x10`` primero y no mira el bit 0 para él, así que no hay que tocar ningún flag.

Lo único que se pierde es la lectura kana original de ``+0x10`` (el apellido), inútil con un teclado solo latino.

Solo se escriben los registros que el comparador puede devolver (:func:`es_buscable`). Funciones puras
(bytes -> bytes); la lectura y escritura del ``archive.fa`` la hace quien las llama.
"""
from __future__ import annotations

import struct
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

__all__ = [
    "ESQUEMAS",
    "EXCEPCIONES_VUELTO_A_KANA",
    "EXCLUIDOS",
    "MAX_LETRAS",
    "R_UNITBASE",
    "R_USEARCH",
    "TECLADO",
    "Decodificado",
    "Decodificador",
    "EsquemaUsearch",
    "Hallazgo",
    "Informe",
    "campo_busqueda",
    "en_lista_por_nombre",
    "es_buscable",
    "es_kana_inicial",
    "indice_unitbase",
    "lista_por_nombre",
    "nombre_unitbase",
    "simular_busqueda",
    "sincronizar",
    "tecleable",
    "verificar",
]

R_USEARCH = 48
R_UNITBASE = 96
OFF_NOMBRE = 0x00
#: campo donde el hook escribe el nombre latino (el comparador lo prueba primero y solo él lo lee)
OFF_BUSQUEDA = 0x10
OFF_NIVEL = 0x26
OFF_VALIDO = 0x2A
OFF_FLAGS = 0x2B
OFF_ID_USEARCH = 0x24
OFF_ID_UNITBASE = 0x42
#: letras que caben en el campo +0x00 (16 B de 2 B por letra); también el tope del buffer de entrada de la búsqueda
MAX_LETRAS = 8
#: ``+0x26``: el comparador nunca devuelve estos registros (0xC9 y 0xFF) ni usa +0x00 en los de código secreto (0xD7:
#: ScoutSpCode.dat, comparación exacta por id)
EXCLUIDOS = frozenset({0xC9, 0xFF, 0xD7})

#: Registros (id de usearch/unitbase) a los que se admite que su nombre de unitbase vuelva a kana mientras usearch
#: ``+0x10`` conserva el latín anterior, como AVISO en vez de error. Por juego (``ie1``, ``ie2``) ->
#: ``{id: motivo documentado y revisado}``. Vacía a propósito: hoy no hay ningún caso (0 en las candidatas medidas) y
#: cada entrada nueva debe llevar el motivo y haber sido revisada por una persona; ver docs/BACKLOG.md, «Hook de nombres».
EXCEPCIONES_VUELTO_A_KANA: dict[str, dict[int, str]] = {"ie1": {}, "ie2": {}}

#: caracteres que el teclado latino de la búsqueda puede producir (celdas de fcode0/1/2): sin apóstrofo ni guion
TECLADO = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.,!?():+/=@&;[] "
    "áéíóúüñÁÉÍÓÚÑ"
)


@dataclass(frozen=True)
class EsquemaUsearch:
    """Dónde viven el par usearch/unitbase de un juego dentro del ``archive.fa``."""

    juego: str
    ruta_usearch: str
    ruta_unitbase: str
    #: ScoutSpCode.dat (solo IE2): sus ids deben coincidir con los registros 0xD7 de usearch
    ruta_scout: str | None = None
    #: campos de unitbase donde mirar el nombre, por orden: +0x10 (corto visible), +0x00 (principal)
    campos_nombre: tuple[int, ...] = (0x10, 0x00)


ESQUEMAS: dict[str, EsquemaUsearch] = {
    "ie1": EsquemaUsearch("ie1", "inazuma1/data_iz/logic/usearch.dat", "inazuma1/data_iz/logic/unitbase.dat"),
    "ie2": EsquemaUsearch(
        "ie2",
        "inazuma2/data_iz/logic/usearch.dat",
        "inazuma2/data_iz/logic/unitbase.dat",
        ruta_scout="inazuma2/data_iz/logic/ScoutSpCode.dat",
    ),
}


# --------------------------------------------------------------------------- decodificación del nombre


@dataclass(frozen=True)
class Decodificado:
    texto: str
    #: códigos de 2 B sin entrada en los registros de bigramas ni valor Shift-JIS
    desconocidos: tuple[int, ...] = ()
    #: había caracteres que no son letras latinas (kana, kanji…): el nombre sigue sin traducir
    no_latino: bool = False

    @property
    def traducido(self) -> bool:
        return bool(self.texto.strip()) and not self.desconocidos and not self.no_latino


class Decodificador:
    """Campo de nombre de unitbase (ASCII, ancho completo, portadores y bigramas de FONT12) -> texto.

    ``registros`` son los ``registro.json`` de bigramas ya leídos (dicts con la lista ``bigramas``: ``sjis`` y
    ``par``), por orden de prioridad. Si un mismo código tiene dos significados gana el primero y queda en
    :attr:`conflictos`.
    """

    def __init__(self, registros: Iterable[Mapping]):
        self.pares: dict[int, str] = {}
        self.conflictos: list[tuple[int, str, str]] = []
        for registro in registros:
            for entrada in registro["bigramas"]:
                codigo, par = int(entrada["sjis"], 16), entrada["par"]
                previo = self.pares.setdefault(codigo, par)
                if previo != par:
                    self.conflictos.append((codigo, previo, par))
        from ie123kit.nucleo.texto import ancho_completo  # perezoso: carga el módulo congelado al usarlo

        self._inverso = {portador: letra for letra, portador in ancho_completo.ACCENTS.items()}

    def decodificar(self, campo: bytes) -> Decodificado:
        datos = campo.split(b"\0", 1)[0]
        texto: list[str] = []
        desconocidos: list[int] = []
        no_latino = False
        i = 0
        while i < len(datos):
            b = datos[i]
            if b < 0x80:
                texto.append(chr(b))
                i += 1
                continue
            if i + 1 >= len(datos):
                desconocidos.append(b << 8)
                break
            codigo = (b << 8) | datos[i + 1]
            i += 2
            par = self.pares.get(codigo)
            if par is not None:
                texto.append(par)
                continue
            try:
                letra = bytes((codigo >> 8, codigo & 0xFF)).decode("shift_jis")
            except UnicodeDecodeError:
                desconocidos.append(codigo)
                continue
            cp = ord(letra)
            if cp == 0x3000:
                texto.append(" ")
            elif 0xFF01 <= cp <= 0xFF5E:
                texto.append(chr(cp - 0xFEE0))
            elif letra in self._inverso:
                texto.append(self._inverso[letra])
            else:
                texto.append(letra)
                no_latino = True
        return Decodificado("".join(texto), tuple(desconocidos), no_latino)


# --------------------------------------------------------------------------- codificación del campo de búsqueda (+0x10)


def tecleable(texto: str) -> tuple[str, str]:
    """(texto con solo lo que el teclado escribe, caracteres descartados)."""
    return "".join(c for c in texto if c in TECLADO), "".join(c for c in texto if c not in TECLADO)


def campo_busqueda(texto: str) -> tuple[bytes, bool, str]:
    """(16 B del campo de búsqueda, ¿truncado a 8 letras?, caracteres descartados por no tener tecla).

    Se quitan los espacios finales del nombre completo y, ya recortado, NO se tocan: un prefijo que acaba en espacio
    sigue siendo tecleable (tecla ESP).
    """
    from ie123kit.nucleo.texto import ancho_completo

    limpio, descartados = tecleable(texto)
    limpio = limpio.rstrip(" ")
    codificado = b"".join(ancho_completo.encode_fullwidth(c) for c in limpio[:MAX_LETRAS])
    if len(codificado) != 2 * min(len(limpio), MAX_LETRAS):
        raise ValueError(f"una letra no ocupa 2 B en ancho completo: {limpio!r}")
    return codificado.ljust(16, b"\0"), len(limpio) > MAX_LETRAS, descartados


# --------------------------------------------------------------------------- relación usearch <-> unitbase


def _u16(datos: bytes, off: int) -> int:
    return struct.unpack_from("<H", datos, off)[0]


def indice_unitbase(unitbase: bytes) -> dict[int, int]:
    """id de jugador (unitbase +0x42) -> posición del registro; el primero gana y 0 es «sin jugador»."""
    indice: dict[int, int] = {}
    for k in range(len(unitbase) // R_UNITBASE):
        ident = _u16(unitbase, k * R_UNITBASE + OFF_ID_UNITBASE)
        if ident:
            indice.setdefault(ident, k)
    return indice


def es_buscable(registro: bytes) -> bool:
    """¿Puede el comparador devolver este registro de usearch por su nombre?"""
    return (
        _u16(registro, OFF_ID_USEARCH) != 0
        and registro[OFF_VALIDO] == 1
        and registro[OFF_NIVEL] not in EXCLUIDOS
    )


def _seleccionado(registro: bytes, alcance: str) -> bool:
    """Registros que el hook escribe/comprueba: los alcanzables por el comparador o, con ``todos``, todo id != 0
    salvo los de código secreto (0xD7)."""
    if alcance == "alcanzables":
        return es_buscable(registro)
    if alcance == "todos":
        return _u16(registro, OFF_ID_USEARCH) != 0 and registro[OFF_NIVEL] != 0xD7
    raise ValueError(f"alcance desconocido: {alcance!r} (alcanzables | todos)")


def nombre_unitbase(registro: bytes, decodificador: Decodificador, campos: tuple[int, ...] = (0x10, 0x00)):
    """(texto, campo) del primer campo del registro de unitbase que ya está en latín; (None, None) si ninguno."""
    for off in campos:
        d = decodificador.decodificar(registro[off:off + 16])
        if d.traducido:
            return d.texto, off
    return None, None


@dataclass
class Informe:
    registros: int = 0
    escritos: int = 0
    cambiados: int = 0
    truncados: int = 0
    no_buscables: int = 0
    sin_unitbase: int = 0
    sin_traduccion: int = 0
    descartados: Counter = field(default_factory=Counter)
    ejemplos: list[dict] = field(default_factory=list)

    def a_json(self) -> dict:
        return {
            "registros": self.registros,
            "escritos": self.escritos,
            "cambiados": self.cambiados,
            "truncados_a_8_letras": self.truncados,
            "no_buscables_sin_tocar": self.no_buscables,
            "sin_unitbase": self.sin_unitbase,
            "sin_traduccion_sin_tocar": self.sin_traduccion,
            "caracteres_descartados": dict(self.descartados),
            "ejemplos": self.ejemplos,
        }


def sincronizar(
    esquema: EsquemaUsearch,
    usearch: bytes,
    unitbase: bytes,
    decodificador: Decodificador,
    *,
    ejemplos: int = 0,
    alcance: str = "alcanzables",
) -> tuple[bytes, Informe]:
    """usearch con el nombre actual de unitbase en +0x10 (+0x00 kana y flags intactos). Idempotente."""
    if len(usearch) % R_USEARCH or len(unitbase) % R_UNITBASE:
        raise ValueError("usearch/unitbase con un tamaño que no es múltiplo del registro")
    indice = indice_unitbase(unitbase)
    salida = bytearray(usearch)
    inf = Informe(registros=len(usearch) // R_USEARCH)
    for n in range(inf.registros):
        o = n * R_USEARCH
        r = usearch[o:o + R_USEARCH]
        if not _u16(r, OFF_ID_USEARCH):
            continue
        if not _seleccionado(r, alcance):
            inf.no_buscables += 1
            continue
        k = indice.get(_u16(r, OFF_ID_USEARCH))
        if k is None:
            inf.sin_unitbase += 1
            continue
        texto, _ = nombre_unitbase(unitbase[k * R_UNITBASE:(k + 1) * R_UNITBASE], decodificador, esquema.campos_nombre)
        if texto is None:
            inf.sin_traduccion += 1
            continue
        campo, truncado, descartados = campo_busqueda(texto)
        if not campo.strip(b"\0"):
            inf.sin_traduccion += 1
            continue
        nuevo = r[:OFF_BUSQUEDA] + campo + r[OFF_BUSQUEDA + 16:]
        inf.escritos += 1
        inf.truncados += truncado
        inf.descartados.update(descartados)
        if nuevo != r:
            inf.cambiados += 1
            salida[o:o + R_USEARCH] = nuevo
            if len(inf.ejemplos) < ejemplos:
                inf.ejemplos.append(
                    {"id": _u16(r, OFF_ID_USEARCH), "indice_usearch": n, "indice_unitbase": k, "nombre": texto,
                     "antes": r[OFF_BUSQUEDA:OFF_BUSQUEDA + 16].hex(" "), "despues": campo.hex(" "),
                     "campo_kana_intacto": r[:16].hex(" "), "flags_intactos": r[OFF_FLAGS]}
                )
    return bytes(salida), inf


# --------------------------------------------------------------------------- validación


@dataclass(frozen=True)
class Hallazgo:
    """Resultado de una comprobación: ``error`` = desincronizado, ``aviso`` = informativo."""

    codigo: str
    gravedad: str
    mensaje: str
    ident: int | None = None

    def __str__(self) -> str:
        return f"[{self.gravedad}] {self.codigo}: {self.mensaje}"


def _hay_letras_latinas(campo: bytes) -> bool:
    """¿Hay letras latinas (ASCII o A-Z a-z de ancho completo) en el campo?"""
    datos = campo.split(b"\0", 1)[0]
    i = 0
    while i < len(datos):
        b = datos[i]
        if b < 0x80:
            if chr(b).isalpha():
                return True
            i += 1
            continue
        if b == 0x82 and i + 1 < len(datos) and (0x60 <= datos[i + 1] <= 0x79 or 0x81 <= datos[i + 1] <= 0x9A):
            return True
        i += 2
    return False


def es_kana_inicial(registro: bytes) -> bool:
    """Réplica del clasificador de filas kana de la lista «Por nombre» (IE1 0xd6334, IE2 0x10ae10).

    Mira los 2 primeros bytes del REGISTRO (``+0x00``): hiragana 0x829F-0x82F1 o katakana 0x8340-0x8396 dan fila
    0..9; cualquier otra cosa (letra latina de ancho completo, portador, espacio) da -1 y el registro sale de la lista.
    """
    codigo = (registro[0] << 8) | registro[1]
    return 0x829F <= codigo <= 0x82F1 or 0x8340 <= codigo <= 0x8396


def en_lista_por_nombre(registro: bytes) -> bool:
    """¿Entra el registro en la lista «Por nombre» del Registro? (id, bit 1 de ``+0x2b`` y ``+0x2a`` == 1)."""
    return _u16(registro, OFF_ID_USEARCH) != 0 and bool(registro[OFF_FLAGS] & 2) and registro[OFF_VALIDO] == 1


def verificar(
    esquema: EsquemaUsearch,
    usearch: bytes,
    unitbase: bytes,
    decodificador: Decodificador,
    scout: bytes | None = None,
    *,
    alcance: str = "alcanzables",
) -> list[Hallazgo]:
    """Hallazgos de sincronía entre usearch y el nombre ACTUAL de unitbase (sin errores = en sincronía).

    Errores: tamaños, id sin unitbase, ``+0x10`` distinto del nombre actual (``USEARCH_DESINCRONIZADO``), ``+0x00`` que
    deja de ser kana en un registro de la lista «Por nombre» (``USEARCH_NOMBRE_NO_KANA``: lo rompería el clasificador),
    nombre de unitbase que VUELVE a kana mientras usearch ``+0x10`` guarda el latín anterior en un registro alcanzable
    (``USEARCH_NOMBRE_VUELTO_A_KANA``: la búsqueda encontraría un nombre que ya no se muestra; solo es aviso para los
    ids de :data:`EXCEPCIONES_VUELTO_A_KANA`), códigos sin bigrama y ScoutSpCode. Avisos: nombre aún en kana en ambos
    sitios (``USEARCH_SIN_TRADUCCION``: nada obsoleto, simplemente sin traducir), unitbase ``+0x00`` y ``+0x10`` con
    nombres distintos (``USEARCH_UNITBASE_NOMBRES_DISTINTOS``), truncados y caracteres sin tecla.
    """
    h: list[Hallazgo] = []
    if len(usearch) % R_USEARCH or len(usearch) == 0:
        h.append(Hallazgo("USEARCH_TAMANO", "error", f"usearch mide {len(usearch)} B (registros de {R_USEARCH})"))
        return h
    if len(unitbase) % R_UNITBASE or len(unitbase) == 0:
        h.append(Hallazgo("UNITBASE_TAMANO", "error", f"unitbase mide {len(unitbase)} B (registros de {R_UNITBASE})"))
        return h
    indice = indice_unitbase(unitbase)
    for n in range(len(usearch) // R_USEARCH):
        r = usearch[n * R_USEARCH:(n + 1) * R_USEARCH]
        ident = _u16(r, OFF_ID_USEARCH)
        if not ident:
            continue
        k = indice.get(ident)
        if k is None:
            h.append(Hallazgo("USEARCH_ID_HUERFANO", "error", f"usearch[{n}] id={ident}: no existe en unitbase", ident))
            continue
        if en_lista_por_nombre(r) and not es_kana_inicial(r):
            h.append(Hallazgo("USEARCH_NOMBRE_NO_KANA", "error",
                              f"usearch[{n}] id={ident}: +0x00={r[:4].hex()}… ya no empieza por kana (el "
                              "clasificador de la lista «Por nombre» lo dejaría fuera)", ident))
        if not _seleccionado(r, alcance):
            continue
        registro = unitbase[k * R_UNITBASE:(k + 1) * R_UNITBASE]
        texto, _ = nombre_unitbase(registro, decodificador, esquema.campos_nombre)
        if texto is None:
            d = [decodificador.decodificar(registro[o:o + 16]) for o in esquema.campos_nombre]
            if any(x.desconocidos for x in d):
                h.append(Hallazgo("UNITBASE_CODIGO_SIN_BIGRAMA", "error",
                                  f"unitbase[{k}] id={ident}: códigos sin entrada en los registros de bigramas "
                                  f"{[hex(c) for x in d for c in x.desconocidos][:3]}", ident))
            elif _hay_letras_latinas(r[OFF_BUSQUEDA:OFF_BUSQUEDA + 16]):
                motivo = EXCEPCIONES_VUELTO_A_KANA.get(esquema.juego, {}).get(ident)
                h.append(Hallazgo("USEARCH_NOMBRE_VUELTO_A_KANA", "aviso" if motivo else "error",
                                  f"unitbase[{k}] id={ident}: el nombre ha vuelto a kana pero usearch +0x10 conserva "
                                  "el latín anterior (no hay kana que restaurar sin el japonés original: la búsqueda "
                                  "encontraría un nombre que ya no se muestra)"
                                  + (f"; excepción revisada: {motivo}" if motivo else ""), ident))
            else:
                h.append(Hallazgo("USEARCH_SIN_TRADUCCION", "aviso", f"unitbase[{k}] id={ident}: nombre aún en kana", ident))
            continue
        traducidos = [x.texto.rstrip() for o in esquema.campos_nombre
                      if (x := decodificador.decodificar(registro[o:o + 16])).traducido]
        if len(set(traducidos)) > 1:
            h.append(Hallazgo("USEARCH_UNITBASE_NOMBRES_DISTINTOS", "aviso",
                              f"unitbase[{k}] id={ident}: +0x{esquema.campos_nombre[0]:02x} y "
                              f"+0x{esquema.campos_nombre[1]:02x} tienen nombres distintos {traducidos!r}; "
                              f"usearch sigue a +0x{esquema.campos_nombre[0]:02x}", ident))
        esperado, truncado, descartados = campo_busqueda(texto)
        if descartados:
            h.append(Hallazgo("USEARCH_NO_TECLEABLE", "aviso",
                              f"unitbase[{k}] id={ident} {texto!r}: sin tecla {descartados!r}, se descarta", ident))
        if truncado:
            h.append(Hallazgo("USEARCH_TRUNCADO", "aviso", f"unitbase[{k}] id={ident} {texto!r}: solo 8 letras", ident))
        if r[OFF_BUSQUEDA:OFF_BUSQUEDA + 16] != esperado:
            h.append(Hallazgo("USEARCH_DESINCRONIZADO", "error",
                              f"usearch[{n}] id={ident}: +0x10={r[OFF_BUSQUEDA:OFF_BUSQUEDA + 16].hex()} esperado "
                              f"{esperado.hex()} ({texto!r})", ident))
    if scout is not None:
        ids_scout = {_u16(scout, j * 22) for j in range(len(scout) // 22)} - {0}
        ids_d7 = {
            _u16(usearch, n * R_USEARCH + OFF_ID_USEARCH)
            for n in range(len(usearch) // R_USEARCH)
            if usearch[n * R_USEARCH + OFF_NIVEL] == 0xD7 and _u16(usearch, n * R_USEARCH + OFF_ID_USEARCH)
        }
        if ids_scout != ids_d7:
            h.append(Hallazgo("SCOUTSPCODE_IDS", "error",
                              f"ids de ScoutSpCode {sorted(ids_scout)} != registros 0xD7 de usearch {sorted(ids_d7)}"))
    return h


# --------------------------------------------------------------------------- réplica del comparador (tests)


def simular_busqueda(usearch: bytes, tecleado: bytes) -> list[int]:
    """Posiciones que casan con la cadena tecleada según el comparador (rama de nombre, sin filtros de progreso).

    Réplica estática de IE2 0xf628 / IE1 0xf98c: prefiltro u16 con los dos primeros bytes, comparación por prefijo
    (STD_CompareNString, sensible a mayúsculas) con +0x10 y, solo si el bit 0 de +0x2b es 0, con +0x00.
    """
    if not tecleado:
        return []
    n = len(tecleado)
    previo = _u16(tecleado + b"\0", 0)
    encontrados = []
    for k in range(len(usearch) // R_USEARCH):
        r = usearch[k * R_USEARCH:(k + 1) * R_USEARCH]
        if not es_buscable(r):
            continue
        por_busqueda = _u16(r, OFF_BUSQUEDA) == previo and r[OFF_BUSQUEDA:OFF_BUSQUEDA + n] == tecleado
        por_nombre = (
            not r[OFF_FLAGS] & 1 and _u16(r, OFF_NOMBRE) == previo and r[OFF_NOMBRE:OFF_NOMBRE + n] == tecleado
        )
        if por_busqueda or por_nombre:
            encontrados.append(k)
    return encontrados


def lista_por_nombre(usearch: bytes) -> list[int]:
    """Posiciones que el clasificador de filas kana deja en la lista «Por nombre» (réplica de ``es_kana_inicial``)."""
    return [
        k for k in range(len(usearch) // R_USEARCH)
        if en_lista_por_nombre(usearch[k * R_USEARCH:(k + 1) * R_USEARCH])
        and es_kana_inicial(usearch[k * R_USEARCH:(k + 1) * R_USEARCH])
    ]
