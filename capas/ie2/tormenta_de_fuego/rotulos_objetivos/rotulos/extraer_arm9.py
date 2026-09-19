"""IE2 Fuego v03 · vuelca ARM9 y overlays de la NDS ES y genera bin/strings.txt (falta señalada en el plan §1).

No hay ndstool en tools/bin: se leen la cabecera NDS, la FAT y la tabla de overlays directamente.
ARM9 y overlays van en BLZ (ie123kit.nucleo.compresion.blz). strings.txt: cadenas imprimibles
(ASCII/latín del DS/Shift-JIS) de >= 3 caracteres, «fichero\toffset\ttexto», como el de IE1.
Salida (work/, no se sube): work/ie2/tormenta_de_fuego/fuentes/nds_es/bin/
Uso: python -X utf8 extraer_arm9.py
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[5]
sys.path.insert(0, str(ROOT / 'tools/src'))
from ie123kit.nucleo.compresion.blz import decompress  # noqa: E402

ROM = next((ROOT / 'Roms/ie2/tormenta_de_fuego').glob('*.nds'))
OUT = ROOT / 'work/ie2/tormenta_de_fuego/fuentes/nds_es/bin'


def cadenas(nombre, d):
    out, i, n = [], 0, len(d)
    while i < n:
        j, s = i, []
        while j < n:
            c = d[j]
            if (0x81 <= c <= 0x9F or 0xE0 <= c <= 0xEF) and j + 1 < n:
                try:
                    s.append(d[j:j + 2].decode('cp932'))
                    j += 2
                    continue
                except UnicodeDecodeError:
                    break
            if 0x20 <= c < 0x7F or c in (0x0A,):
                s.append(chr(c) if c != 0x0A else '\\n')
                j += 1
                continue
            break
        if j < n and d[j] == 0 and len(s) >= 3:
            out.append(f'{nombre}\t{hex(i)}\t{"".join(s)}')
            i = j + 1
        else:
            i = max(j, i + 1)
    return out


def main():
    rom = ROM.read_bytes()
    OUT.mkdir(parents=True, exist_ok=True)
    a9o, a9e, a9r, a9s = struct.unpack_from('<4I', rom, 0x20)
    fat_o, fat_s = struct.unpack_from('<2I', rom, 0x48)
    ov_o, ov_s = struct.unpack_from('<2I', rom, 0x50)
    arm9 = rom[a9o:a9o + a9s]
    (OUT / 'arm9.bin').write_bytes(arm9)
    # module params: +0x14 = compressed_static_end (dirección absoluta), justo antes de la versión SDK y 0xDEC00621
    p = arm9.find(struct.pack('<I', 0xDEC00621))
    comp_end = struct.unpack_from('<I', arm9, p - 8)[0] if p > 0 else 0
    dec = arm9
    if comp_end:
        fin = comp_end - a9r
        dec = decompress(arm9[:fin]) + arm9[fin:]
    (OUT / 'arm9.dec').write_bytes(dec)
    lineas = cadenas('arm9.bin', dec)
    fat = [struct.unpack_from('<2I', rom, fat_o + k * 8) for k in range(fat_s // 8)]
    for k in range(ov_s // 32):
        ov_id, _, _, _, _, _, fid, flags = struct.unpack_from('<8I', rom, ov_o + k * 32)
        a, b = fat[fid]
        raw = rom[a:b]
        (OUT / f'overlay9_{ov_id:03d}.bin').write_bytes(raw)
        d = decompress(raw) if (flags >> 24) & 1 else raw
        (OUT / f'overlay9_{ov_id:03d}.dec').write_bytes(d)
        lineas += cadenas(f'overlay9_{ov_id:03d}.bin', d)
    (OUT / 'strings.txt').write_text('\n'.join(lineas) + '\n', encoding='utf-8')
    print('arm9', len(arm9), '->', len(dec), 'comp_end', hex(comp_end), 'overlays', ov_s // 32, 'cadenas', len(lineas))


if __name__ == '__main__':
    main()
