"""Capacidad de comandos de títulos de la clase175614, sin cambiar su tinta."""
import struct

from ie123kit.ie3.comun.ancho_ventana import direcciones_de_tablas
from ie123kit.ie3.comun.literales_visibles import _adr_target
from ie123kit.nucleo.ejecutable.cro import Cro
from ie123kit.nucleo.registros.rangos import assert_only_changed

CAMBIOS_TITULO = {
    0x175758: (0xE3A01003, 0xE3A01004),  # 1818CC: 64→128, altura sigue8.
    0x269DF4: (0xE3A00040, 0xE3A00080),  # Límite lógico en generador.
    0x269FDC: (0xE3A03040, 0xE3A03080),  # Rectángulo de selección UV.
}
LLAMADORES = {
    0x175614: (0x165D5C, 0x165DDC, 0x165E04, 0x165F20, 0x165F8C,
               0x166010, 0x166128, 0x1661B0, 0x166320),
    0x175608: (0x165D7C, 0x165E20, 0x165F3C, 0x165FA8,
               0x16602C, 0x166144, 0x1661D0, 0x16633C),
    0x269D70: (0x1750E8,),
    0x269F0C: (0x1751EC,),
}
ANCLAS = {
    0x175608: 0xE3A0200F, 0x17560C: 0xE28000F0, 0x175610: 0xEAFA2B7A,
    0x175754: 0xE3A02000, 0x17575C: 0xE2800004, 0x175760: 0xEB003059,
    0x175764: 0xE5870110, 0x269D84: 0xE5941110,
    0x269DD8: 0xE3A01001, 0x269DEC: 0xE8820082,
    0x269DFC: 0xE88100C1, 0x269E00: 0xE28400F0, 0x269E18: 0xEBFC5A98,
    0x269FB8: 0xE5950110, 0x269FD0: 0xE3A00008, 0x269FD4: 0xE58D0000,
    0x269FE8: 0xEBFC6044, 0x269FEC: 0xE3A09000, 0x269FF0: 0xE58D9000,
    0x269FF8: 0xE1A03009, 0x26A004: 0xEBFC606A,
    0x26A008: 0xE3A00006, 0x26A014: 0xE3A0300C, 0x26A020: 0xEBFC608E,
}


def _u32(data, offset):
    return struct.unpack_from("<I", data, offset)[0]


def cota_titulo(literal):
    """Cota por bytes: no usa otro encoder ni supone un carácter por byte SJIS."""
    try:
        length = literal[:15].index(0)
    except ValueError as exc:
        raise ValueError("título sin NUL antes de copia15") from exc
    commands = length + 1  # Conservador: cada byte podría representar un glifo.
    capacity = 128 * 8 // 2
    if commands * 32 > capacity:
        raise ValueError("título supera reserva de comandos")
    return {"bytes_before_nul": length, "glyphs_upper_bound": length,
            "command_bytes_upper_bound": commands * 32, "buffer_bytes": capacity}


def _comprobar_clase(cro, view):
    if view.imports().get(0x400) != "strncpy":
        raise ValueError("copiador de título no corresponde a strncpy")
    for offset, expected in ANCLAS.items():
        if _u32(cro, offset) != expected:
            raise ValueError(f"ancla de títulos distinta {offset:#x}")
    found = {target: [] for target in LLAMADORES}
    segment = view.segments[0]
    for pc in range(segment.offset, segment.offset + segment.size, 4):
        word = _u32(cro, pc)
        if word & 0x0E000000 != 0x0A000000:
            continue
        delta = word & 0xFFFFFF
        if delta & 0x800000:
            delta -= 1 << 24
        target = pc + 8 + delta * 4
        if target in found:
            found[target].append(pc)
    if {k: tuple(v) for k, v in found.items()} != LLAMADORES:
        raise ValueError("llamadores de la clase de títulos distintos")
    if any(r.value in LLAMADORES for r in view.relocations):
        raise ValueError("referencia indirecta adicional a la clase de títulos")
    titles = []
    for caller in LLAMADORES[0x175608]:
        reference = caller - 4
        word = _u32(cro, reference)
        if (word >> 12) & 15 != 1:
            raise ValueError("ADR de título no usa argumento r1")
        target = _adr_target(word, reference)
        if not 0 <= target <= len(cro) - 15:
            raise ValueError("literal de título fuera del CRO")
        titles.append({"caller": caller, "literal_offset": target,
                       **cota_titulo(cro[target:target+15])})
    return titles


def parchear_titulos(cro):
    """Tres constantes coordinadas; admite otros parches fuera de las anclas.

    Requiere la clase original y títulos terminados dentro de la copia15. No
    supone que strncpy termine entradas largas. No repara listas ni ordenación.
    """
    view = Cro(cro)
    titles = _comprobar_clase(cro, view)
    if set(CAMBIOS_TITULO) & direcciones_de_tablas(cro):
        raise ValueError("título intersecta destino de relocación")
    output = bytearray(cro)
    for offset, (old, new) in CAMBIOS_TITULO.items():
        if _u32(cro, offset) != old:
            raise ValueError(f"constante de título distinta {offset:#x}")
        struct.pack_into("<I", output, offset, new)
    result = bytes(output)
    changed = assert_only_changed(cro, result, [(x, x+4) for x in CAMBIOS_TITULO])
    for offset, (_, expected) in CAMBIOS_TITULO.items():
        if _u32(result, offset) != expected:
            raise AssertionError("relectura de geometría de título distinta")
    return result, {"title_width_commands_before": 64, "title_width_commands_after": 128,
                    "height_unchanged": 8, "buffer_bytes_before": 256,
                    "buffer_bytes_after": 512, "title_copy_limit_unchanged": 15,
                    "titles": titles, "constructor_callers": LLAMADORES[0x175614],
                    "title_selection_uv_width": 128, "selection_origin": [0, 0],
                    "text_position_unchanged": [12, 6], "changed_ranges": changed,
                    "fonts_metrics_buttons_other_lists_unchanged": True,
                    "no_cave_no_segment_growth": True, "runtime_verified": False}
