"""IE3 · logic/PracticeGame*.dat (cadena de pachangas): texto oficial europeo en la geometría japonesa.

Registros de tamaño fijo, emparejados por índice (mismo número de registros en las dos versiones):

| campo | japonés | europeo |
|---|---|---|
| cabecera (datos) | [0:12] | [0:12] |
| nombre (equipo / premio) | [12:36] | [12:46] |
| dato u16 | [36:38] | [46:48] |
| segundo texto (premio, entrenador, técnica) | [38:60] | [48:80] |
| cola (datos) | [60:74] | [80:94] |
| paso | 74 | 94 |

Límite real de ambos textos: 21 B + NUL. ``ina_main3ogre.cro`` (japonés) 0x24dee4-0x24df2c indexa el
registro con ``i * 74`` y copia 0x16 B (22) de +0xC y de +0x26 a dos ranuras contiguas del objeto de la
pantalla (+0xC18 y +0xC2E, y +0xC44 ya es otro dato): sin NUL dentro de esos 22 B el texto se une al siguiente.
El lector de progreso 0x1c1d2c usa +0x3C (+60) como dato, lo que fija el comienzo de la cola.

API sin E/S: la codificación y la decodificación del europeo se inyectan (las de la capa textos_logic).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

PASO_JP = 74
PASO_EU = 94
#: (texto JP, texto EU) de cada campo de texto: (inicio, fin) dentro del registro
CAMPOS = {"nombre": ((12, 36), (12, 46)), "segundo": ((38, 60), (48, 80))}
#: rangos de datos que deben coincidir entre JP y EU para aceptar el emparejado
DATOS = (((0, 12), (0, 12)), ((36, 38), (46, 48)), ((60, 74), (80, 94)))
#: bytes de texto sin el NUL (copia de 0x16 B en 0x24df18 / 0x24df2c)
LIMITE = 21

Codificador = Callable[[str, int], "tuple[bytes | None, str]"]


@dataclass
class Resultado:
    datos: bytes
    traducidos: int = 0
    modos: dict = field(default_factory=dict)
    conservados: list = field(default_factory=list)  # (registro, campo, motivo, texto_es, bytes, límite)


def _texto(b: bytes) -> bytes:
    return b.split(b"\0", 1)[0]


def registros(n_bytes: int, paso: int) -> int:
    if n_bytes % paso:
        raise ValueError(f"tamaño {n_bytes} no es múltiplo del paso {paso}")
    return n_bytes // paso


def traducir(jp: bytes, eu: bytes, decodificar: Callable[[bytes], str], codificar: Codificador,
             limite: int = LIMITE, medir: Callable[[str], int] | None = None) -> Resultado:
    """Escribe en `jp` el texto europeo de cada campo; solo cambian los bytes de los campos de texto.

    `codificar(texto, limite)` devuelve (bytes, modo) o (None, motivo). Un texto que no cabe se deja en
    japonés (nunca se recorta); `medir(texto)` da su tamaño mínimo para el informe. Idempotente: si `jp` ya lleva el texto, el resultado es el mismo."""
    n = registros(len(jp), PASO_JP)
    if registros(len(eu), PASO_EU) != n:
        raise ValueError(f"número de registros distinto: {n} / {len(eu) // PASO_EU}")
    out = bytearray(jp)
    res = Resultado(b"")
    for i in range(n):
        oj, oe = i * PASO_JP, i * PASO_EU
        if any(jp[oj + a:oj + b] != eu[oe + c:oe + d] for (a, b), (c, d) in DATOS):
            for nombre, ((a, b), _) in CAMPOS.items():
                if _texto(jp[oj + a:oj + b]):
                    res.conservados.append((i, nombre, "datos_distintos", "", 0, limite))
            continue
        for nombre, ((a, b), (c, d)) in CAMPOS.items():
            tj, te = _texto(jp[oj + a:oj + b]), _texto(eu[oe + c:oe + d])
            if not tj or not te or tj == te:
                continue
            texto = decodificar(te)
            lim = min(limite, b - a - 1)
            cod, modo = codificar(texto, lim)
            if cod is None:
                largo = medir(texto) if medir else 0
                res.conservados.append((i, nombre, modo, texto, largo, lim))
                continue
            out[oj + a:oj + b] = cod.ljust(b - a, b"\0")
            res.traducidos += 1
            res.modos[modo] = res.modos.get(modo, 0) + 1
    res.datos = bytes(out)
    return res


def solo_texto_cambiado(antes: bytes, despues: bytes) -> bool:
    """True si `despues` solo difiere de `antes` dentro de los campos de texto JP."""
    if len(antes) != len(despues):
        return False
    texto = set()
    for i in range(len(antes) // PASO_JP):
        for (a, b), _ in CAMPOS.values():
            texto.update(range(i * PASO_JP + a, i * PASO_JP + b))
    return all(x == y or k in texto for k, (x, y) in enumerate(zip(antes, despues)))
