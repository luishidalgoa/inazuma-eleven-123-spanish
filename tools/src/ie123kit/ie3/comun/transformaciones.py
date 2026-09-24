"""Cambios de bytecode DECLARADOS que aceptan todas las capas de diálogo del IE3 (visto bueno del usuario, 2026-09-24).

La emisión (ie3.fase3.emitir_perfil) parte siempre del SSD japonés y exige que el eve heredado tenga su mismo
bytecode. Estos cambios lo alteran a propósito, así que se declaran aquí con dos funciones:

- ``revertir(ssd, evet)``: devuelve el eve/evet heredado a la forma japonesa (si el cambio está aplicado);
- ``aplicar(ssd, evet)``: vuelve a aplicarlo sobre el resultado de la emisión.

Así cualquier capa que reemite (restantes, espacio_estrecho, nombres_jugador, saltos_eu, restantes_2…) conserva los
cambios en cada pasada. Tipos:

1. ``intercambio``: en un 0x301D con operandos (texto, lectura, nombre 0x4002, lectura), el español lleva %s sin la
   marca de furigana que el japonés pone delante; se intercambian los operandos 1 y 2 (tipo y valor) y el slot de la
   lectura movida en la tabla SSD. El orden de los operandos de texto no cambia, así que el tramo @ se consume igual.
2. ``insercion``: una frase oficial que no cabe en un registro (u8, ≤ 252 B) se reparte en dos cajas: la primera parte
   va en el registro del 0x301D original y la segunda en un registro nuevo al final del evet, que lee un 0x301D nuevo
   insertado justo detrás (ID original + 1). Se renumeran los IDs posteriores, los operandos tipo 4 (IDs), los
   propietarios de la tabla de textos y los contadores de la cabecera.

Los datos (qué eventos y los cuerpos codificados, que son texto del juego) viven fuera del paquete: quien los tenga
llama a :func:`cargar` (lista de declaraciones o ruta a un JSON ``{"declaraciones": [...]}``). Sin declaraciones
registradas no se aplica nada.
"""

from __future__ import annotations

import json
import struct
from pathlib import Path

from ie123kit.ie3.comun.referencias import instrucciones, leer_referencias, reconstruir_evento
from ie123kit.ie3.comun.ssd import parse_flat_text, parse_ssd
from ie123kit.ie3.comun.text import TextTable

_REGISTRO: dict[tuple[str, int], list[dict]] = {}


def cargar(fuente) -> int:
    """Registra declaraciones (lista de dicts o ruta a JSON). Sustituye las anteriores. Devuelve cuántas."""
    if isinstance(fuente, (str, Path)):
        ruta = Path(fuente)
        lista = json.loads(ruta.read_text(encoding="utf-8"))["declaraciones"] if ruta.exists() else []
    else:
        lista = list(fuente)
    _REGISTRO.clear()
    for d in lista:
        if d["tipo"] not in ("intercambio", "insercion"):
            raise ValueError(f"tipo de declaración desconocido: {d['tipo']}")
        _REGISTRO.setdefault((d["perfil"], int(d["evento"])), []).append(d)
    for ds in _REGISTRO.values():
        # aplicar va de la instrucción más alta a la más baja (una inserción no desplaza a las anteriores) y
        # revertir, al revés
        ds.sort(key=lambda d: -int(d["instruccion"]))
    return len(lista)


def declaraciones() -> dict:
    """{(perfil, evento): [declaración, ...]} registradas con :func:`cargar`."""
    return _REGISTRO


# ------------------------------------------------------------------------------------------ utilidades SSD

def _tabla(ssd: bytes):
    _info, recs = parse_ssd(ssd, TextTable.identity())
    return [(r.instruction, r.argument, ssd[r.offset:r.offset + r.size]) for r in recs]


def _montar(ssd: bytes, codigo: bytes, tabla: list, n_ins: int) -> bytes:
    cuerpo = b"".join(t[2] if t[2][:3] == struct.pack("<HB", t[0], t[1]) else
                      struct.pack("<HB", t[0], t[1]) + t[2][3:] for t in tabla)
    out = bytearray(ssd[:32]) + codigo + cuerpo
    struct.pack_into("<I", out, 8, len(out))
    struct.pack_into("<HH", out, 12, n_ins, len(tabla))
    struct.pack_into("<II", out, 16, len(codigo), len(cuerpo))
    return bytes(out)


def _entrada(ins: int, slot: int, cuerpo: bytes) -> tuple:
    size = (len(cuerpo) + 8) & ~3
    return (ins, slot, struct.pack("<HBB", ins, slot, size) + cuerpo + bytes(size - 4 - len(cuerpo)))


def _renumerar(ssd: bytes, desde: int, delta: int, quitar: int | None = None, meter: bytes | None = None,
               tras: int | None = None) -> tuple[bytes, list]:
    """IDs > desde (+delta) en código, operandos tipo 4 y tabla; opcionalmente quita la instrucción `quitar` o mete
    `meter` (bytes de instrucción ya numerada) detrás de la instrucción `tras`."""
    ins = instrucciones(ssd)
    codigo = bytearray()
    for i in ins:
        size = struct.unpack_from("<H", ssd, i.offset + 2)[0]
        b = bytearray(ssd[i.offset:i.offset + size])
        if i.ident == quitar:
            continue
        if i.ident > desde:
            struct.pack_into("<H", b, 0, i.ident + delta)
        words = (len(i.tipos) + 7) // 8
        for k, (t, v) in enumerate(zip(i.tipos, i.valores)):
            if t == 4 and v > desde:
                struct.pack_into("<I", b, 8 + 4 * words + 4 * k, v + delta)
        codigo += b
        if meter is not None and i.ident == tras:
            codigo += meter
    tabla = [(t[0] + delta if t[0] > desde else t[0], t[1], t[2]) for t in _tabla(ssd)]
    return bytes(codigo), tabla


# ------------------------------------------------------------------------------------------ intercambio

def _es_intercambiado(i) -> bool:
    return len(i.tipos) >= 4 and i.tipos[1] == 4 and i.tipos[2] == 3


def _intercambiar(ssd: bytes, ident: int) -> bytes:
    """Intercambia los operandos 1 y 2 (tipo y valor) y los slots de sus textos. Es su propia inversa."""
    ins = {i.ident: i for i in instrucciones(ssd)}[ident]
    if len(ins.tipos) < 4 or len(ins.tipos) > 8:
        raise ValueError("intercambio: se esperan de 4 a 8 operandos (texto, lectura, nombre, lectura, …)")
    b = bytearray(ssd)
    t = list(ins.tipos)
    t[1], t[2] = t[2], t[1]
    b[ins.offset + 8] = t[0] | (t[1] << 4)
    b[ins.offset + 9] = t[2] | (t[3] << 4)
    base = ins.offset + 12                      # 1 palabra de tipos (argc ≤ 8)
    v1, v2 = struct.unpack_from("<II", b, base + 4)
    struct.pack_into("<II", b, base + 4, v2, v1)
    s1, s2 = 2, 3                               # slots físicos = palabras de tipos (1) + índice del operando
    _info, recs = parse_ssd(bytes(b), TextTable.identity())
    for r in recs:
        if r.instruction == ident and r.argument in (s1, s2):
            b[r.offset + 2] = s2 if r.argument == s1 else s1
    return bytes(b)


# ------------------------------------------------------------------------------------------ inserción

def _insercion_aplicada(ssd: bytes, d: dict) -> bool:
    ins = {i.ident: i for i in instrucciones(ssd)}
    nuevo = ins.get(d["instruccion"] + 1)
    return bool(nuevo and nuevo.opcode == 0x301D and len(nuevo.tipos) == 1 and d.get("marca") and
                nuevo.valores[0] == d["marca"])


def _aplicar_insercion(ssd: bytes, evet: bytes, d: dict) -> tuple[bytes, bytes]:
    x = d["instruccion"]
    refs = leer_referencias(ssd, evet)[0]
    ref = next(r for r in refs if r.instruccion.ident == x)
    ssd, evet, _ = reconstruir_evento(ssd, evet, {ref.inicio: bytes.fromhex(d["parte1_hex"])})
    parte2 = bytes.fromhex(d["parte2_hex"])
    size = (len(parte2) + 8) & ~3
    if size > 252:
        raise ValueError("inserción: la segunda parte no cabe en un registro")
    inicio = len(evet)
    evet = evet + struct.pack("<HBB", 0, 0, size) + parte2 + bytes(size - 4 - len(parte2))
    orig = {i.ident: i for i in instrucciones(ssd)}[x]
    flags = ssd[orig.offset + 7]
    nueva = struct.pack("<HHHBB", x + 1, 16, 0x301D, 1, flags) + struct.pack("<II", 3, d["marca"])
    codigo, tabla = _renumerar(ssd, x, +1, meter=nueva, tras=x)
    pos = max(k for k, t in enumerate(tabla) if t[0] == x) + 1
    tabla.insert(pos, _entrada(x + 1, 1, f"@{inicio},{size}".encode("ascii")))
    n = struct.unpack_from("<H", ssd, 12)[0] + 1
    return _montar(ssd, codigo, tabla, n), evet


def _revertir_insercion(ssd: bytes, evet: bytes, d: dict) -> tuple[bytes, bytes]:
    x = d["instruccion"]
    codigo, _ = _renumerar(ssd, x + 1, -1, quitar=x + 1)
    tabla = [t for t in _tabla(ssd) if t[0] != x + 1]
    tabla = [(t[0] - 1 if t[0] > x + 1 else t[0], t[1], t[2]) for t in tabla]
    n = struct.unpack_from("<H", ssd, 12)[0] - 1
    recs = parse_flat_text(evet, TextTable.identity())
    return _montar(ssd, codigo, tabla, n), evet[:recs[-1].offset]


# ------------------------------------------------------------------------------------------ API para fase3

def revertir(perfil: str | None, evento: int, ssd: bytes, evet: bytes | None):
    for d in reversed(declaraciones().get((perfil, evento), [])):
        if d["tipo"] == "insercion" and evet is not None and _insercion_aplicada(ssd, d):
            ssd, evet = _revertir_insercion(ssd, evet, d)
        elif d["tipo"] == "intercambio":
            i = {i.ident: i for i in instrucciones(ssd)}.get(d["instruccion"])
            if i is not None and _es_intercambiado(i):
                ssd = _intercambiar(ssd, d["instruccion"])
    return ssd, evet


def _con_marca(ssd: bytes, ds: list) -> bool:
    marcas = {d.get("marca") for d in ds if d["tipo"] == "insercion"}
    return any(i.opcode == 0x301D and len(i.tipos) == 1 and i.valores[0] in marcas for i in instrucciones(ssd))


def aplicar(perfil: str | None, evento: int, ssd: bytes, evet: bytes | None):
    ds = declaraciones().get((perfil, evento), [])
    ya = _con_marca(ssd, ds)            # inserciones ya aplicadas (los IDs ya no son los japoneses)
    for d in ds:
        if d["tipo"] == "insercion" and ya:
            continue
        if d["tipo"] == "intercambio":
            i = {i.ident: i for i in instrucciones(ssd)}[d["instruccion"]]
            if not _es_intercambiado(i):
                if i.tipos[:4] != (3, 3, 4, 3):
                    raise ValueError(f"intercambio {evento}/{d['instruccion']}: operandos {i.tipos}")
                ssd = _intercambiar(ssd, d["instruccion"])
        elif d["tipo"] == "insercion" and evet is not None and not _insercion_aplicada(ssd, d):
            ssd, evet = _aplicar_insercion(ssd, evet, d)
    return ssd, evet
