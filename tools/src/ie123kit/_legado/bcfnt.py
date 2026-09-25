#!/usr/bin/env python3
"""Parser del formato de fuente BCFNT (CFNT v3) de Nintendo 3DS.

Lee cabecera + bloques FINF / TGLP / CWDH / CMAP. Sirve para inspeccionar la
fuente del juego (FONT12T.bcfnt) y, despues, anadir glifos del espanol (etapa 6).
Los offsets internos apuntan al CUERPO del bloque (block_start + 8).
"""
import sys

from ie123kit.nucleo.fuentes.bcfnt import *  # noqa: F401,F403


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    f = sys.argv[1] if len(sys.argv) > 1 else r"work\shared\fa_extract\font\FONT12T.bcfnt"
    b = BCFNT(open(f, "rb").read())
    print(f"{f}: version=0x{b.version:08X} file_size={b.file_size} blocks={b.nblocks}")
    print(f"FINF: type={b.font_type} line_feed={b.line_feed} alter={b.alter_char} "
          f"enc={b.encoding} height={b.height} width={b.width} ascent={b.ascent}")
    t = b.tglp()
    print(f"TGLP: cell={t['cell_w']}x{t['cell_h']} baseline={t['baseline']} maxw={t['max_w']} "
          f"sheets={t['nsheets']} fmt={t['fmt']} grid={t['ncols']}x{t['nrows']} "
          f"sheet={t['sheet_w']}x{t['sheet_h']} sheet_size={t['sheet_size']} data@{t['sheet_data']}")
    cms = b.cmaps()
    total = sum(c["n"] for c in cms)
    print(f"CMAP: {len(cms)} bloques, {total} codepoints mapeados")
    for c in cms[:8]:
        print(f"   begin=0x{c['begin']:04X} end=0x{c['end']:04X} method={c['method']} n={c['n']}")
    if len(cms) > 8:
        print(f"   ... (+{len(cms)-8} bloques)")
    # comprobar acentos latinos y signos
    allmap = {}
    for c in cms:
        allmap.update(c["entries"])
    print("\nGlifos para caracteres del espanol (codepoint Unicode):")
    for ch in "ñÑáéíóúüÁÉÍÓÚ¡¿":
        cp = ord(ch)
        print(f"   {ch} U+{cp:04X}: {'SI glifo='+str(allmap[cp]) if cp in allmap else 'NO'}")
    print(f"\nrango total de codepoints: 0x{min(allmap):04X}..0x{max(allmap):04X}")


if __name__ == "__main__":
    main()
