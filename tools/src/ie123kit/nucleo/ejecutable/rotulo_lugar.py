"""Rótulo de lugar (barra superior, 0x4037 argumento 3) con más de 10 baldosas: búfer y sprites reubicados.

Medido en ``ina_main3ogre.cro`` (IE3) e ``ina_main2.cro`` (IE2), 2026-09-24. El mismo código en los dos:

- El objeto de la pantalla superior tiene en obj+8 una VRAM de OBJ emulada (vtable+0x28 = base + 0x90000:
  banco F de la DS, 16 KB; vtable+0x24 = su tamaño). Reparto (tabla de piezas del minimapa, 16 B por
  pieza: id, tamaño, offset, paleta; se busca por contenido):
  0x0000 pieza 4 · 0x0300 pieza 3 · 0x1300 pieza 2 · **0x1500 rótulo (0x140 = 10 baldosas)** ·
  0x1640 objetivo (0x800) · 0x1e40 rótulo de 32×8 (0x80) · 0x1ec0 pieza 1 · 0x2040 pieza 5 ·
  0x2140 pieza 7 · 0x2940 pieza 8 (hasta 0x2c40). **De 0x2c40 a 0x4000 no lo usa nada de este objeto.**
- Dibujo del rótulo (IE3 0x83bf8, IE2 0x8a548): ``add r5, r0, #0x1500`` + ``mov r2, #0x140`` (limpieza),
  ancho 0x50 × alto 8 al dibujo del sistema de texto (``mov r2, #0x50`` / ``mov r1, #8``), y al salir
  ``mov r1, #0x140`` + ``b`` (vaciado de caché). Ancho HD de la línea: ``vstr s2, [rN]`` con el tercer valor
  de ``CSubAdventureScreen_locale_*`` del ITX (``locale_Width`` = 160 = 10 baldosas × 16); se sustituye por
  ``str r2, [rN]`` con el r2 = 0xFF que la función acaba de cargar (255 ≥ 15 × 16).
- Registro del búfer en el sistema de texto (IE3 0x8474c, IE2 0x8af6c): ``add r4, r0, #0x1500``.
- Sprites (IE3 0x84d2c, IE2 0x8b478): 5 OAM de 16×8, baldosa 0xA8 + 2k, x = 0x10 + 16k
  (``mov r0, #0xa8`` … ``cmp r1, #5``) tras comprobar que caben (``add r1, r6, #0x28`` = 5 × 8 B).

El parche mueve el búfer a ``desplazamiento`` (por defecto 0x3e00: las baldosas 0x1f0-0x1ff, al final del
banco) y amplía coherentemente limpieza, vaciado, ancho de dibujo, ancho HD, número de sprites y su
comprobación. El texto sigue limitado a 31 B por la copia del manejador (``STD_CopyLString(.., 0x20)``):
15 caracteres de 2 B. ❌ v76 (IE1): alargar el rótulo en el búfer de 10 baldosas deja la placa vacía; aquí el
búfer nuevo no toca el del objetivo. Sin probar en el emulador: es una SONDA.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from ie123kit.nucleo.ejecutable import parches_cro as PC
from ie123kit.nucleo.errores import ValidacionError

__all__ = [
    "BALDOSAS_ORIGINAL",
    "DESPLAZAMIENTO_ORIGINAL",
    "TAM_VRAM",
    "ParchesRotulo",
    "aplicar",
    "codificar_inmediato",
    "localizar",
    "parches",
    "reparto_vram",
]

BALDOSAS_ORIGINAL = 10
DESPLAZAMIENTO_ORIGINAL = 0x1500
TAM_VRAM = 0x4000                    # banco F
MAX_CARACTERES = 15                  # STD_CopyLString(estado+0x44, arg3, 0x20) -> 31 B + NUL

MOV_R2_140, MOV_R1_140 = 0xE3A02D05, 0xE3A01D05
MOV_R2_50, MOV_R1_8 = 0xE3A02050, 0xE3A01008
MOV_R2_FF = 0xE3A020FF
MOV_R0_A8, MOV_R1_0, CMP_R1_5 = 0xE3A000A8, 0xE3A01000, 0xE3510005
ADD_R1_R6_28 = 0xE2861028
PIEZAS = struct.pack("<4I", 1, 0x180, 0x1EC0, 1)


def codificar_inmediato(valor: int) -> int:
    """Campo de 12 bits (rotación + 8 bits) de un inmediato ARM; ValidacionError si no se puede."""
    for rot in range(16):
        v = ((valor << (2 * rot)) | (valor >> (32 - 2 * rot))) & 0xFFFFFFFF if rot else valor
        if v < 0x100:
            return (rot << 8) | v
    raise ValidacionError("inmediato_no_codificable", detalle=hex(valor))


def _con_inmediato(palabra: int, valor: int) -> int:
    return (palabra & 0xFFFFF000) | codificar_inmediato(valor)


def _u32(d, o):
    return struct.unpack_from("<I", d, o)[0]


def _palabras(d, ini, fin):
    for a in range(ini, min(fin, len(d) - 3), 4):
        yield a, _u32(d, a)


@dataclass(frozen=True)
class ParchesRotulo:
    """Direcciones (offsets de fichero) de las palabras del rótulo en una CRO."""

    limpieza_add: int      # add rX, r0, #0x1500 (dibujo)
    limpieza_tam: int      # mov r2, #0x140
    ancho_dibujo: int      # mov r2, #0x50
    ancho_hd: int          # vstr s2, [rN]
    vaciado_tam: int       # mov r1, #0x140 (antes del b final)
    registro_add: int      # add rX, r0, #0x1500 (registro en el sistema de texto)
    oam_comprobacion: int  # add r1, r6, #0x28
    oam_baldosa: int       # mov r0, #0xa8
    oam_cuenta: int        # cmp r1, #5


def _es_add_1500(w: int) -> bool:
    return (w & 0xFFFF0FFF) == 0xE2800C15


def localizar(d: bytes) -> ParchesRotulo:
    """Busca por contenido las palabras del rótulo; exige una sola coincidencia de cada una."""
    # tras pedir la VRAM: ldr r1,[r0,#0x28] · add r0,rX,#8 · blx r1 · add rY,r0,#0x1500 (otras hay muchas)
    adds = [a for a, w in _palabras(d, 20, len(d)) if _es_add_1500(w)
            and any(_u32(d, a - 4 * k) == 0xE12FFF31 and _u32(d, a - 4 * k - 8) == 0xE5901028 for k in (1, 2, 3))]
    dibujo = [a for a in adds if _u32(d, a + 4) == MOV_R2_140]
    registro = [a for a in adds if a not in dibujo]
    if len(dibujo) != 1 or len(registro) != 1:
        raise ValidacionError("rotulo_no_localizado", detalle=f"add #0x1500: dibujo {dibujo}, registro {registro}")
    ini = dibujo[0]
    fin = next((a for a, w in _palabras(d, ini, ini + 0x400) if w == MOV_R1_140 and (_u32(d, a + 4) >> 24) == 0xEA),
               None)
    if fin is None:
        raise ValidacionError("rotulo_no_localizado", detalle="vaciado mov r1,#0x140 + b")
    ancho = [a for a, w in _palabras(d, ini, fin) if w == MOV_R2_50
             and MOV_R1_8 in (_u32(d, a + 4), _u32(d, a + 8), _u32(d, a + 12))]
    vstr = [a for a, w in _palabras(d, ini, fin) if (w & 0xFFF0FFFF) == 0xED801A00]
    ff = [a for a, w in _palabras(d, ini, fin) if w == MOV_R2_FF]
    if len(ancho) != 1 or len(vstr) != 1 or not ff or ff[0] > vstr[0]:
        raise ValidacionError("rotulo_no_localizado", detalle=f"ancho {ancho}, vstr {vstr}, mov r2,#0xff {ff}")
    _r2_intacto(d, ff[0], vstr[0])
    oam = [a for a, w in _palabras(d, 0, len(d)) if w == MOV_R0_A8 and _u32(d, a + 4) == MOV_R1_0
           and any(_u32(d, a + 4 * k) == CMP_R1_5 for k in range(2, 12))
           and any(_u32(d, a - 4 * k) == ADD_R1_R6_28 for k in range(1, 8))]
    if len(oam) != 1:
        raise ValidacionError("rotulo_no_localizado", detalle=f"OAM: {oam}")
    o = oam[0]
    cuenta = next(o + 4 * k for k in range(2, 12) if _u32(d, o + 4 * k) == CMP_R1_5)
    compr = next(o - 4 * k for k in range(1, 8) if _u32(d, o - 4 * k) == ADD_R1_R6_28)
    return ParchesRotulo(ini, ini + 4, ancho[0], vstr[0], fin, registro[0], compr, o, cuenta)


def _r2_intacto(d, desde: int, hasta: int) -> None:
    """Entre ``mov r2,#0xff`` y el vstr nadie escribe r2 (se comprueba con capstone si está)."""
    try:
        from capstone import CS_ARCH_ARM, CS_MODE_ARM, Cs
        from capstone.arm import ARM_REG_R2
    except ImportError:
        return
    md = Cs(CS_ARCH_ARM, CS_MODE_ARM)
    md.detail = True
    for i in md.disasm(bytes(d[desde + 4:hasta]), desde + 4):
        if ARM_REG_R2 in i.regs_access()[1] or i.mnemonic in ("b", "bl", "blx", "bx"):
            raise ValidacionError("rotulo_r2_modificado", detalle=f"{i.address:#x} {i.mnemonic} {i.op_str}")


def reparto_vram(d: bytes) -> list[tuple[int, int, int]]:
    """``[(id, offset, tamaño)]`` de la tabla de piezas del minimapa (primera tabla de la CRO)."""
    i = d.find(PIEZAS)
    if i < 0:
        raise ValidacionError("rotulo_sin_tabla_piezas")
    out = []
    while True:
        pid, tam, off, _pal = struct.unpack_from("<4I", d, i)
        if pid == 0 or tam == 0 or off + tam > TAM_VRAM or (out and pid <= out[-1][0]):
            break
        out.append((pid, off, tam))
        i += 16
    return out


def _libre(d: bytes, desp: int, tam: int) -> None:
    ocupado = [(off, off + t, f"pieza {p}") for p, off, t in reparto_vram(d)]
    ocupado += [(0x1640, 0x1E40, "objetivo"), (0x1E40, 0x1EC0, "rótulo 32×8")]
    for a, b, que in ocupado:
        if desp < b and a < desp + tam:
            raise ValidacionError("rotulo_vram_ocupada", detalle=f"{desp:#x}+{tam:#x} pisa {que} {a:#x}-{b:#x}")
    if desp % 32 or desp + tam > TAM_VRAM:
        raise ValidacionError("rotulo_vram_fuera", detalle=f"{desp:#x}+{tam:#x}")


def parches(d: bytes, baldosas: int = 16, desplazamiento: int = 0x3E00) -> list[PC.ParchePalabra]:
    """Palabras a cambiar para un rótulo de ``baldosas`` (par) en ``desplazamiento`` de la VRAM de OBJ."""
    if baldosas % 2 or not BALDOSAS_ORIGINAL < baldosas <= 2 * (MAX_CARACTERES // 2 + 1):
        raise ValidacionError("rotulo_baldosas", detalle=str(baldosas))
    tam = 32 * baldosas
    _libre(d, desplazamiento, tam)
    p = localizar(d)
    w = lambda a: _u32(d, a)
    vstr = w(p.ancho_hd)
    return [
        PC.ParchePalabra(p.limpieza_add, w(p.limpieza_add), _con_inmediato(w(p.limpieza_add), desplazamiento),
                         f"búfer del rótulo en VRAM OBJ + {desplazamiento:#x}"),
        PC.ParchePalabra(p.limpieza_tam, w(p.limpieza_tam), _con_inmediato(w(p.limpieza_tam), tam),
                         f"limpieza {tam:#x} B ({baldosas} baldosas)"),
        PC.ParchePalabra(p.ancho_dibujo, w(p.ancho_dibujo), _con_inmediato(w(p.ancho_dibujo), 8 * baldosas),
                         f"ancho de dibujo {8 * baldosas} px DS"),
        PC.ParchePalabra(p.ancho_hd, vstr, 0xE5802000 | (vstr & 0x000F0000),
                         "ancho HD: str r2 (= 0xff) en lugar de locale_Width (160)"),
        PC.ParchePalabra(p.vaciado_tam, w(p.vaciado_tam), _con_inmediato(w(p.vaciado_tam), tam),
                         f"vaciado de caché {tam:#x} B"),
        PC.ParchePalabra(p.registro_add, w(p.registro_add), _con_inmediato(w(p.registro_add), desplazamiento),
                         "registro del búfer en el sistema de texto"),
        PC.ParchePalabra(p.oam_comprobacion, w(p.oam_comprobacion),
                         _con_inmediato(w(p.oam_comprobacion), 8 * (baldosas // 2)),
                         f"comprobación de {baldosas // 2} entradas OAM"),
        PC.ParchePalabra(p.oam_baldosa, w(p.oam_baldosa), _con_inmediato(w(p.oam_baldosa), desplazamiento // 32),
                         f"baldosa inicial {desplazamiento // 32:#x}"),
        PC.ParchePalabra(p.oam_cuenta, w(p.oam_cuenta), _con_inmediato(w(p.oam_cuenta), baldosas // 2),
                         f"{baldosas // 2} sprites de 16×8"),
    ]


def aplicar(cro: bytes, baldosas: int = 16, desplazamiento: int = 0x3E00) -> tuple[bytes, dict]:
    """CRO con el rótulo ampliado (ver módulo) e informe de ``parches_cro.aplicar``."""
    salida, inf = PC.aplicar(cro, parches(cro, baldosas, desplazamiento))
    inf["rotulo"] = {"baldosas": baldosas, "desplazamiento": hex(desplazamiento),
                     "max_caracteres": MAX_CARACTERES, "reparto_vram": [(p, hex(o), hex(t)) for p, o, t in
                                                                        reparto_vram(cro)]}
    return salida, inf
