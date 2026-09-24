"""Extractor del contenedor 'archive.fa' (magic B123) de Inazuma Eleven 1-2-3 (3DS).

B123 es una variante del formato ARC0/XFSA de Level-5, con las TABLAS sin comprimir
y entradas de directorio de 24 bytes (ARC0 usa 20 y comprimidas). Las herramientas
de la comunidad (Pingouin / StudioElevenLib) NO lo abren porque rechazan el magic
y asumen tablas comprimidas -> de ahi este parser propio.

Descompresion Level-5 portada de StudioElevenLib (Tiniifan) / Kuriimu.

Uso:
    python -m ie123kit._legado.fa_unpack work/shared/base_3ds/romfs/archive.fa --tree            # listar todo
    python -m ie123kit._legado.fa_unpack work/shared/base_3ds/romfs/archive.fa --tree --filter sItx
    python -m ie123kit._legado.fa_unpack work/shared/base_3ds/romfs/archive.fa -o work/shared/fa_extract --filter inazuma1
    python -m ie123kit._legado.fa_unpack work/shared/base_3ds/romfs/archive.fa -o work/shared/fa_extract # extraer todo

NOTA: el contenido extraido tiene copyright; va a work/ (ignorado por git).
"""
import argparse
import os

from ie123kit.nucleo.contenedores.fa import *  # noqa: F401,F403
from ie123kit.nucleo.contenedores.fa import _huffman, _lz10, _rle  # noqa: F401


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("archive")
    ap.add_argument("-o", "--out", help="carpeta de salida (extrae)")
    ap.add_argument("--filter", help="solo rutas que contengan este texto")
    ap.add_argument("--tree", action="store_true", help="solo listar, no extraer")
    ap.add_argument("--raw", action="store_true", help="no descomprimir (volcar tal cual)")
    args = ap.parse_args()

    arc = FaArchive(args.archive)
    print(f"Contenedor: {os.path.basename(args.archive)}  archivos={len(arc.entries)}  "
          f"data_off=0x{arc.data_off:X}")

    files = arc.entries
    if args.filter:
        files = [f for f in files if args.filter.lower() in f[0].lower()]
        print(f"Filtro '{args.filter}': {len(files)} archivos")

    if args.tree or not args.out:
        ext_summary = {}
        for path, off, size in files:
            ext = os.path.splitext(path)[1].lower() or "(sin)"
            c, s = ext_summary.get(ext, (0, 0))
            ext_summary[ext] = (c + 1, s + size)
        for path, off, size in files[:400]:
            head = arc.file_bytes(off, min(size, 8))
            print(f"  [{describe(head):6}] {size:9} {path}")
        if len(files) > 400:
            print(f"  ... (+{len(files) - 400} mas; usa --filter para acotar)")
        print("\nResumen por extension:")
        for ext, (c, s) in sorted(ext_summary.items(), key=lambda x: -x[1][1]):
            print(f"  {ext:14} {c:6} archivos  {s/1024/1024:9.2f} MB")
        return

    os.makedirs(args.out, exist_ok=True)
    n_ok = 0
    for path, off, size in files:
        data = arc.file_bytes(off, size)
        if not args.raw:
            try:
                data = l5_decompress(data)
            except Exception as e:
                print(f"  WARN descomprimiendo {path}: {e}")
        dst = os.path.join(args.out, path.replace("/", os.sep))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, "wb") as f:
            f.write(data)
        n_ok += 1
    print(f"Extraidos {n_ok} archivos en {args.out}")


if __name__ == "__main__":
    main()
