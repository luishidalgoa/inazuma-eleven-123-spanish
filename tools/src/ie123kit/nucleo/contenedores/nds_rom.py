#!/usr/bin/env python3
"""Extractor minimo del sistema de archivos de una ROM NDS (sin dependencias).

Lee las tablas FNT/FAT de la cabecera NDS y vuelca todos los archivos
respetando la jerarquia de carpetas. Pensado para inspeccionar las ROMs de
referencia oficiales en castellano (IE1 / IE2 DS).

Uso:
    python tools/nds_unpack.py "roms/Inazuma Eleven.nds" work/ie1/fuentes/nds_es
    python tools/nds_unpack.py --tree-only "roms/Inazuma Eleven.nds"

NOTA: el contenido extraido tiene copyright; queda en work/ (ignorado por git).
"""
import os
import struct


def u16(b, o): return struct.unpack_from("<H", b, o)[0]
def u32(b, o): return struct.unpack_from("<I", b, o)[0]


def read_dir(data, fnt_off, dir_id, fat, names_only, out_dir, files_log):
    """Procesa recursivamente el subtable de un directorio (dir_id >= 0xF000)."""
    idx = dir_id & 0x0FFF
    entry = fnt_off + idx * 8
    sub_off = fnt_off + u32(data, entry)
    file_id = u16(data, entry + 4)

    p = sub_off
    while True:
        t = data[p]; p += 1
        if t == 0x00:
            break
        length = t & 0x7F
        name = data[p:p + length].decode("shift_jis", errors="replace")
        p += length
        if t & 0x80:  # subdirectorio
            sub_id = u16(data, p); p += 2
            child = os.path.join(out_dir, name) if out_dir else None
            if child:
                os.makedirs(child, exist_ok=True)
            read_dir(data, fnt_off, sub_id, fat, names_only, child, files_log)
        else:  # archivo
            start, end = fat[file_id]
            rel = os.path.join(out_dir, name) if out_dir else name
            files_log.append((rel, end - start))
            if not names_only and out_dir:
                with open(os.path.join(out_dir, name), "wb") as f:
                    f.write(data[start:end])
            file_id += 1
