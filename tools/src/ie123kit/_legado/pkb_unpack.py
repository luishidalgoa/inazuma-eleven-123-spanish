#!/usr/bin/env python3
"""Parser del paquete de scripts de evento Level-5 "PackNum" (eve.pkb + eve.pkh).

FORMATO RESUELTO del indice (.pkh):
  - 16 bytes: cabecera ASCII "PackNum YYYYMMDD"
  - +0x10 u32: tamaño total del .pkh
  - +0x30 en adelante: tabla de entradas de 12 bytes c/u:
        u32 event_id   (p.ej. 10010001 = mapa/capitulo 1001, evento 0001)
        u32 offset      (en el .pkb)
        u32 size
  Los offsets cubren el .pkb completo (verificado).

Cada entrada del .pkb es un SCRIPT DE EVENTO COMPILADO (bytecode) con el texto del
dialogo EMBEBIDO como operandos, usando plantillas tipo printf (`%s`, `\n`, `%2F`,
`$`) y codigos de control de 1 byte entrelazados con el Shift-JIS. Por eso el texto
no se extrae 100% limpio sin un parser del bytecode (PENDIENTE: catalogar los
codigos de control). Este modulo resuelve el INDICE y da un volcado best-effort.

Uso:
    python tools/pkb_unpack.py <pkh> <pkb> --list
    python tools/pkb_unpack.py <pkh> <pkb> --extract-dir work/eve_entries
    python tools/pkb_unpack.py <pkh> <pkb> --text work/eve_text.csv [--enc sjis|nds]
"""
import argparse
import csv
import os
import struct
import sys

from ie123kit.nucleo.texto.nds_latin import NDS_DEC, decode_cadena  # noqa: F401
from ie123kit.nucleo.eventos.packnum import parse_index, entry_data, lz10_decompress  # noqa: F401

_decode_string = decode_cadena


def is_furigana(s):
    """Una lectura furigana = cadena corta solo de hiragana/katakana."""
    core = [c for c in s if c not in " 　"]
    return bool(core) and all(0x3040 <= ord(c) <= 0x30FF for c in core)


def dialogue_runs(data, enc="sjis"):
    """Extrae las lineas de texto de un script de evento (descomprime LZ10 primero).

    Tras descomprimir, el contenido son cadenas separadas por NUL. Se devuelven las
    que contienen texto real (Shift-JIS con kana/kanji, o ES con letras). Las lecturas
    furigana (solo hiragana, cortas) se incluyen pero pueden filtrarse con is_furigana.
    """
    data = lz10_decompress(data)
    out = []
    for part in data.split(b"\x00"):
        if len(part) < 2:
            continue
        s = _decode_string(part, enc)
        if not s or s.count("�") > len(s) * 0.2:
            continue
        if enc == "sjis":
            # texto real: >=2 kana/kanji de ancho completo (descarta basura binaria)
            jp = sum(1 for c in s if 0x3040 <= ord(c) <= 0x30FF or 0x4E00 <= ord(c) <= 0x9FFF)
            if jp >= 2:
                out.append(s)
        else:
            if sum(ch.isalpha() for ch in s) >= 3 and " " in s.strip():
                out.append(s)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pkh"); ap.add_argument("pkb")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--extract-dir")
    ap.add_argument("--text")
    ap.add_argument("--enc", choices=["sjis", "nds"], default="sjis")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    pkh = open(args.pkh, "rb").read()
    pkb = open(args.pkb, "rb").read()
    idx = parse_index(pkh)
    print(f"{os.path.basename(args.pkb)}: {len(idx)} entradas (event scripts), "
          f"pkb={len(pkb)} B")

    if args.list:
        for eid, off, size in idx[:40]:
            print(f"  id={eid:>9}  off={off:>9}  size={size}")
        if len(idx) > 40:
            print(f"  ... (+{len(idx)-40})")

    if args.extract_dir:
        os.makedirs(args.extract_dir, exist_ok=True)
        for eid, off, size in idx:
            open(os.path.join(args.extract_dir, f"{eid}.evt"), "wb").write(pkb[off:off + size])
        print(f"Extraidas {len(idx)} entradas en {args.extract_dir}")

    if args.text:
        rows = []
        for eid, off, size in idx:
            for run in dialogue_runs(pkb[off:off + size], args.enc):
                rows.append([eid, run])
        with open(args.text, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f); w.writerow(["event_id", "texto_best_effort"]); w.writerows(rows)
        print(f"Volcado best-effort: {len(rows)} fragmentos -> {args.text}")
        print("AVISO: fragmentado por codigos de control (ver issue #3).")


if __name__ == "__main__":
    main()
