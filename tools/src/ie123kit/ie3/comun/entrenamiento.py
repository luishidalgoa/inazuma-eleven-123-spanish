"""Resultado del entrenamiento del IE3 («Markはコントロールが1上がった！») con los mensajes oficiales europeos.

Análisis (``ina_main3ogre.cro`` japonesa 1.0, función 0xb52d8, pantalla ``tokkun_result``). La función:

1. ``switch ([r7+0x60])`` (tabla de 10 saltos con relocación en 0xb53b4; 0 y >= 10 van a 0xb54a8): cada caso
   (6 palabras en 0xb53dc + 24·k, k = 0..8, el último de 3) hace ``sprintf(sp+0xa0, "キック")`` con el nombre de la
   característica (búfer de 16 B);
2. pasa la subida ``r6 = [r7+0x6c] − [r7+0x68]`` a cifras (``powf``, 0xb54a8..0xb5558) y a ancho completo
   (``0x175cb8`` → ``sp+0xb8``);
3. ``sprintf(sp+0x20, fmt, nombre, stat, cifras[, nombre, stat])`` con «%sは%sが%s[上/あ]がった！» o, si
   ``[r7+0x7c] != 0``, la misma frase + «\\n%sの%sは[最大/さいだい]になった» (búfer de 128 B, borrado antes);
4. lo pinta en la ventana de mensaje (0x181370, que ya deja pasar el latín de 1 byte: capa ``copia_1byte``).

El europeo (0xba2a0..) no compone: cada característica tiene su frase completa (``GetString`` 169/170 Tiro,
336-347 Físico/Control/Defensa/Rapidez/Aguante/Valor y 770-773 PE/PT) y llama a
``sprintf(buf, frase, nombre, subida, nombre)``. La frase «normal» es siempre el principio de la de «máximo» hasta
el «\\n». No cabe copiar las 18 frases en los huecos japoneses (930 B), así que:

- cada caso deja en registros el formato de su **familia** y sus argumentos: la frase oficial con la palabra de
  la característica sustituida por ``%s`` (4 familias: «ha mejorado su», «ha aumentado su», Tiro y PE/PT) y
  ``r1 = formato``, ``r2, r3 = argumentos 1 y 2``, ``r5 = argumento 4``, ``r4 = característica`` (argumento 5);
- el mensaje: ``sprintf(sp+0x20, r1, r2, r3, r6 (la subida, %d), r5, r4)`` con el formato de «máximo» y, si no se
  ha llegado al máximo, se corta en el primer «\\n». El texto resultante es exactamente el oficial;
- se quitan la conversión a cifras y la copia del nombre de la característica (ya no hacen falta; ``r4``, ``r5``,
  ``sl``, ``fp`` y ``s16`` no se leen después sin volver a escribirse) y los textos se guardan en ese código y en
  el pool de literales japonés 0xb56e4..0xb579c (nombres de característica y formatos japoneses, más dos
  constantes que solo usaba el código quitado). La tabla de saltos y sus relocaciones no cambian.

Codificación: latín de 1 byte con portadores (``es_encode``), como el resto del IE3.
"""
from __future__ import annotations

import hashlib
import struct
from collections.abc import Callable, Sequence

from ie123kit.nucleo.texto.sjis_portador import es_encode

__all__ = [
    "CASOS", "ESPERADO_SHA256", "LITERALES", "REGION_CODIGO", "REGION_DATOS", "Familia",
    "aplicar_entrenamiento", "aplicar_literal", "codificar", "construir_region", "familias",
    "simular", "textos_bomber",
]

#: Código reescrito: casos del switch (0xb53dc) hasta el código que sigue al sprintf (0xb55c0, exclusivo).
REGION_CODIGO = (0xB53DC, 0xB55C0)
#: Pool de literales que queda libre (0xb56e0 = 0x1ea, usado en 0xb5370; 0xb579c.. palabras con relocación).
REGION_DATOS = (0xB56E4, 0xB579C)
#: SHA-256 del japonés 1.0 en REGION_CODIGO + REGION_DATOS (se comprueba antes de reescribir).
ESPERADO_SHA256 = "8cef667827b3afbefaf1a33d5c35aa856b9f2640778f4bceb4a04de49bccf43e"
_POR_DEFECTO = 0xB54A8           # destino de los casos 0 y >= 10 (tabla y «b» de 0xb53b0): se conserva
_FIN = 0xB55C0                   # continuación tras el sprintf (ldr r6, [pc, #0x114])
_SPRINTF = 0x530                 # thunk de __2sprintf
_CASO0, _PASO = 0xB53DC, 24
_NOP = 0xE320F000

#: Orden de los casos 1..9 del switch japonés y sus textos europeos: (característica, max, normal).
#: (キック, ボディ, コントロール, ガード, スピード, スタミナ, ガッツ, ＧＰ, ＴＰ) — el europeo sigue el mismo orden.
CASOS = (
    (130, 169, 170), (131, 336, 337), (134, 338, 339), (132, 340, 341), (133, 342, 343),
    (136, 344, 345), (135, 346, 347), (137, 770, 772), (138, 771, 773),
)

#: Literales sueltos de la misma pantalla y de la selección de jugador del entrenamiento:
#: (offset, texto japonés, capacidad en B con el NUL, GetString europeo, consumidor).
LITERALES = (
    (0x24FB1C, "ひつようねっけつＰ", 20, 171,
     "0x24f9c0: sprintf(sp+0x18 [32 B], lit) y 0x24eac0 lo pinta (EU 0x260ac4: GetString(171) en la misma llamada)"),
    (0x2B3A08, "ねっけつＰがたりません。", 32, 172,
     "campo char[32] en 0x2b38f4+0x114, copiado con vldm en 0x24f744 (EU 0x260864: GetString(172))"),
)

NOMBRE, STAT, SUBIDA = "nombre", "stat", "subida"


class Familia:
    """Formato común de varias características: plantilla y orden de argumentos."""

    def __init__(self, plantilla: str, args: tuple[str, ...]):
        self.plantilla, self.args = plantilla, args

    def __repr__(self) -> str:
        return f"Familia({self.plantilla!r}, {self.args})"


def _plantilla(frase: str, stat: str) -> tuple[str, tuple[str, ...]]:
    """Frase oficial -> (plantilla con la característica como %s, argumentos en orden)."""
    marca = "\x01"
    if stat not in frase:
        raise ValueError(f"{stat!r} no aparece en {frase!r}")
    t = frase.replace(stat, marca)
    args, i = [], 0
    while i < len(t):
        if t[i] == marca:
            args.append(STAT)
        elif t.startswith("%s", i):
            args.append(NOMBRE)
            i += 1
        elif t.startswith("%d", i):
            args.append(SUBIDA)
            i += 1
        elif t[i] == "%":
            raise ValueError(f"formato no previsto en {frase!r}")
        i += 1
    return t.replace(marca, "%s"), tuple(args)


def familias(textos: dict[int, str]) -> tuple[list[Familia], list[tuple[int, str]]]:
    """Agrupa los 9 casos: ``([familias], [(índice de familia, característica) por caso])``.

    Comprueba que la frase normal es el principio de la de máximo hasta «\\n» y que los argumentos caben en
    el esquema del código (1.º y 2.º nombre/característica, 3.º la subida, 4.º nombre/característica, 5.º la
    característica)."""
    fams: list[Familia] = []
    casos = []
    for id_stat, id_max, id_normal in CASOS:
        stat, maximo, normal = textos[id_stat], textos[id_max], textos[id_normal]
        if "\n" not in maximo or maximo.split("\n", 1)[0] != normal:
            raise ValueError(f"{id_normal} no es el principio de {id_max}")
        plantilla, args = _plantilla(maximo, stat)
        if not (3 <= len(args) <= 5 and args[2] == SUBIDA and SUBIDA not in args[:2] + args[3:]
                and (len(args) < 5 or args[4] == STAT)):
            raise ValueError(f"{id_max}: argumentos {args} fuera del esquema")
        for k, f in enumerate(fams):
            if f.plantilla == plantilla:
                if f.args != args:
                    raise ValueError(f"{id_max}: misma plantilla con otros argumentos")
                break
        else:
            fams.append(Familia(plantilla, args))
            k = len(fams) - 1
        casos.append((k, stat))
    return fams, casos


def codificar(texto: str) -> bytes:
    """Latín de 1 byte con portadores; «%s», «%d» y «\n» quedan en ASCII. ValueError si algo no se codifica."""
    b = es_encode(texto, 1 << 30)
    if b"\0" in b or b.count(b"?") != texto.count("?"):
        raise ValueError(f"carácter sin codificar en {texto!r}")
    return b


# ------------------------------------------------------------------------------------------ ensamblador mínimo
def _rotimm(valor: int) -> int:
    for rot in range(16):
        v = ((valor << (2 * rot)) | (valor >> (32 - 2 * rot))) & 0xFFFFFFFF if rot else valor
        if v < 256:
            return rot << 8 | v
    raise ValueError(f"{valor:#x} no es un inmediato ARM")


def _adr(rd: int, pc: int, destino: int) -> int:
    d = destino - (pc + 8)
    if d < 0:
        raise ValueError("adr hacia atrás no previsto")
    return 0xE28F0000 | rd << 12 | _rotimm(d)


def _b(pc: int, destino: int, cond: int = 0xE, enlace: bool = False) -> int:
    return cond << 28 | (0x0B000000 if enlace else 0x0A000000) | ((destino - pc - 8) >> 2) & 0xFFFFFF


def _nombre(rd: int) -> int:
    return 0xE288001C | rd << 12        # add rd, r8, #0x1c (nombre corto del jugador)


def _alcanza(pc: int, destino: int) -> bool:
    try:
        _adr(0, pc, destino)
        return True
    except ValueError:
        return False


# ------------------------------------------------------------------------------------------ construcción
def construir_region(textos: dict[int, str]) -> tuple[dict[int, bytes], dict]:
    """Bytes nuevos de REGION_CODIGO y REGION_DATOS: ``({inicio: bytes}, informe)``."""
    fams, casos = familias(textos)
    cadenas: list[bytes] = [codificar(f.plantilla) for f in fams]
    stats = sorted({s for _k, s in casos}, key=[s for _k, s in casos].index)
    cadenas += [codificar(s) for s in stats]
    cadenas.append(b"")                                    # cadena vacía (caso por defecto)
    ref_stat = {s: len(fams) + i for i, s in enumerate(stats)}
    vacia = len(cadenas) - 1

    # código: casos (0..7 en su sitio, el 8 salta fuera), por defecto, mensaje, caso 8
    caso8 = 0xB54EC
    msg = 0xB54AC
    codigo: dict[int, int | tuple] = {}                    # pc -> palabra o ("adr", rd, cadena)

    def caso(pc: int, k_fam: int, stat: str, salto: int) -> None:
        f = fams[k_fam]
        args = f.args + (STAT,) * (5 - len(f.args))

        def carga(rd: int, arg: str):
            return _nombre(rd) if arg == NOMBRE else ("adr", rd, ref_stat[stat])
        codigo[pc] = ("adr", 1, k_fam)
        codigo[pc + 4] = carga(2, args[0])
        codigo[pc + 8] = carga(3, args[1])
        codigo[pc + 12] = carga(5, args[3])
        codigo[pc + 16] = ("adr", 4, ref_stat[stat])
        codigo[pc + 20] = _b(pc + 20, salto)

    for k, (k_fam, stat) in enumerate(casos[:8]):
        caso(_CASO0 + _PASO * k, k_fam, stat, msg)
    codigo[_CASO0 + _PASO * 8] = _b(_CASO0 + _PASO * 8, caso8)
    codigo[_CASO0 + _PASO * 8 + 4] = _NOP
    codigo[_CASO0 + _PASO * 8 + 8] = _NOP
    codigo[_POR_DEFECTO] = ("adr", 1, vacia)
    bucle = msg + 36
    for i, w in enumerate((
        0xE58D6000,                         # str r6, [sp]        (3.º: subida, %d)
        0xE58D5004,                         # str r5, [sp, #4]    (4.º)
        0xE58D4008,                         # str r4, [sp, #8]    (5.º: característica)
        0xE28D0020,                         # add r0, sp, #0x20
        _b(msg + 16, _SPRINTF, enlace=True),  # bl __2sprintf
        0xE597007C,                         # ldr r0, [r7, #0x7c] (¿al máximo?)
        0xE3500000,                         # cmp r0, #0
        _b(msg + 28, _FIN, cond=0x1),       # bne fin (frase entera)
        0xE28D001F,                         # add r0, sp, #0x1f
        0xE5F01001,                         # bucle: ldrb r1, [r0, #1]!
        0xE351000A,                         # cmp r1, #10
        0x13510000,                         # cmpne r1, #0
        _b(bucle + 12, bucle, cond=0x1),    # bne bucle
        0xE3A01000,                         # mov r1, #0
        0xE5C01000,                         # strb r1, [r0]       (corta en el «\n»)
        _b(msg + 60, _FIN),                 # b fin
    )):
        codigo[msg + 4 * i] = w
    caso(caso8, *casos[8], msg)
    fin_codigo = caso8 + 24

    # datos: huecos libres; cada cadena alineada a 4 y al alcance de todas sus ADR
    huecos = [[fin_codigo, REGION_CODIGO[1]], list(REGION_DATOS)]
    refs: dict[int, list[int]] = {}
    for pc, w in codigo.items():
        if isinstance(w, tuple):
            refs.setdefault(w[2], []).append(pc)
    sitio: dict[int, int] = {}
    for i in sorted(range(len(cadenas)), key=lambda j: -len(cadenas[j])):
        n = len(cadenas[i]) + 1
        for h in huecos:
            pos = h[0] + (-h[0]) % 4
            if pos + n <= h[1] and all(_alcanza(pc, pos) for pc in refs.get(i, [])):
                sitio[i] = pos
                h[0] = pos + n
                break
        else:
            raise ValueError(f"no cabe la cadena {cadenas[i]!r}")

    salida = {REGION_CODIGO[0]: bytearray(REGION_CODIGO[1] - REGION_CODIGO[0]),
              REGION_DATOS[0]: bytearray(REGION_DATOS[1] - REGION_DATOS[0])}

    def poner(off: int, datos: bytes) -> None:
        for ini, buf in salida.items():
            if ini <= off and off + len(datos) <= ini + len(buf):
                buf[off - ini:off - ini + len(datos)] = datos
                return
        raise ValueError(f"{off:#x} fuera de las regiones")

    for pc in range(REGION_CODIGO[0], fin_codigo, 4):
        w = codigo.get(pc, _NOP)
        if isinstance(w, tuple):
            w = _adr(w[1], pc, sitio[w[2]])
        poner(pc, struct.pack("<I", w))
    for i, pos in sitio.items():
        poner(pos, cadenas[i] + b"\0")
    informe = {
        "familias": [{"plantilla": f.plantilla, "argumentos": list(f.args), "offset": hex(sitio[k])}
                     for k, f in enumerate(fams)],
        "casos": [{"caso": k + 1, "stat": s, "familia": kf} for k, (kf, s) in enumerate(casos)],
        "libre": [h[1] - h[0] for h in huecos],
    }
    return {k: bytes(v) for k, v in salida.items()}, informe


def simular(textos: dict[int, str], caso: int, nombre: str, subida: int, maximo: bool) -> str:
    """Texto que escribe el código nuevo (sprintf + corte), para comprobar que es el oficial."""
    fams, casos = familias(textos)
    k, stat = casos[caso]
    f = fams[k]
    valores = {NOMBRE: nombre, STAT: stat}
    it = iter(f.args)
    out, t, i = "", f.plantilla, 0
    while i < len(t):
        if t.startswith("%s", i) or t.startswith("%d", i):
            a = next(it)
            out += str(subida) if a == SUBIDA else valores[a]
            i += 2
            continue
        out += t[i]
        i += 1
    return out if maximo else out.split("\n", 1)[0]


# ------------------------------------------------------------------------------------------ aplicación
def _region_actual(cro: bytes) -> bytes:
    return bytes(cro[REGION_CODIGO[0]:REGION_CODIGO[1]]) + bytes(cro[REGION_DATOS[0]:REGION_DATOS[1]])


def aplicar_entrenamiento(cro: bytes, textos: dict[int, str]) -> tuple[bytes, dict]:
    """Reescribe el mensaje del resultado del entrenamiento (idempotente). ``textos``: GetString europeo."""
    nuevo, informe = construir_region(textos)
    objetivo = nuevo[REGION_CODIGO[0]] + nuevo[REGION_DATOS[0]]
    actual = _region_actual(cro)
    if actual == objetivo:
        return bytes(cro), {**informe, "ya_aplicado": True}
    if hashlib.sha256(actual).hexdigest() != ESPERADO_SHA256:
        raise ValueError("resultado del entrenamiento: la región no es la japonesa 1.0 ni la de esta capa")
    out = bytearray(cro)
    for ini, datos in nuevo.items():
        out[ini:ini + len(datos)] = datos
    return bytes(out), {**informe, "ya_aplicado": False}


def aplicar_literal(cro: bytes, offset: int, japones: str, capacidad: int, texto: str) -> tuple[bytes, dict]:
    """Escribe ``texto`` (1 byte) en el literal japonés de ``capacidad`` B (con el NUL), rellenando con ceros."""
    datos = codificar(texto)
    if len(datos) + 1 > capacidad:
        raise ValueError(f"{texto!r}: {len(datos) + 1} B > {capacidad} B en {offset:#x}")
    nuevo = datos + bytes(capacidad - len(datos))
    actual = bytes(cro[offset:offset + capacidad])
    jp = japones.encode("cp932")
    if actual == nuevo:
        return bytes(cro), {"offset": hex(offset), "texto": texto, "ya_aplicado": True}
    if actual[:len(jp)] != jp or any(actual[len(jp):]):
        raise ValueError(f"{offset:#x}: no es «{japones}» seguido de ceros")
    out = bytearray(cro)
    out[offset:offset + capacidad] = nuevo
    return bytes(out), {"offset": hex(offset), "texto": texto, "bytes": len(datos) + 1, "capacidad": capacidad,
                        "ya_aplicado": False}


def textos_bomber(leer: Callable[[int], str], ids: Sequence[int] | None = None) -> dict[int, str]:
    """Textos europeos que hacen falta (``leer(id)`` = GetString de la tabla española)."""
    todos = {i for c in CASOS for i in c} | {lit[3] for lit in LITERALES}
    return {i: leer(i) for i in sorted(ids or todos)}
