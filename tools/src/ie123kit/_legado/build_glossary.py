#!/usr/bin/env python3
"""Genera el glosario JP(3DS)<->ES(NDS oficial) del juego 1 de Inazuma Eleven.

Empareja por INDICE DE REGISTRO los ficheros de datos del 3DS (japones) con los
del NDS europeo en castellano, que comparten el mismo orden de entidades:

  - Jugadores:  data_iz/logic/unitbase.dat   (registro 96 B, nombre@+0, 16 B)  [ambas plataformas]
  - Objetos:    data_iz/logic/item.dat       (3DS: 16 B/reg, NDS: 48 B/reg, nombre@+0)
  - Equipos:    data_iz/logic/teamtitle.dat  (registro 16 B, nombre@+0)         [ambas]
  - Menus:      data_iz/logic/games.STR      (mismo nº de cadenas, empareja por indice)

El 3DS usa Shift-JIS; el NDS una codificacion Latin propia (ver NDS_DEC).

Uso (rutas por defecto a work/, ignorado por git):
    python tools/build_glossary.py
Salida: CSV en translation/shared/glossary/ (solo nombres/terminos, sin descripciones).
"""
import csv
import os
import struct  # noqa: F401
import sys

from ie123kit.nucleo.config.raiz import find_root
from ie123kit.nucleo.texto.nds_latin import NDS_DEC, NDS_SJIS, dec_es, dec_jp  # noqa: F401
from ie123kit.nucleo.registros.tabla_fija import names_from_dat, strings_from_str

REPO = str(find_root())
# valores por defecto (juego 1); main() los reasigna segun el juego
DS = os.path.join(REPO, "work", "shared", "fa_extract", "inazuma1", "data_iz", "logic")   # 3DS JP
ES = os.path.join(REPO, "work", "ie1", "fuentes", "nds_es", "data_iz", "logic", "sp")             # NDS ES
OUT = os.path.join(REPO, "translation", "shared", "glossary")

# config por juego: (carpeta 3DS, carpeta NDS ES, salida glosario)
GAME_CFG = {
    "game1": ("inazuma1", os.path.join("ie1", "fuentes", "nds_es", "data_iz", "logic", "sp"),
              os.path.join("translation", "shared", "glossary")),
    "game2": ("inazuma2", os.path.join("ie2", "tormenta_de_fuego", "fuentes", "nds_es", "data_iz", "logic", "sp"),
              os.path.join("translation", "ie2", "glossary")),
}


DUMMY = {"ダミー", "Dummy", "dummy", "-", "ー", "なし"}


def clean(s):
    return (s and any(ch.isalpha() for ch in s)
            and "<" not in s and "?" not in s and s not in DUMMY)


def write_csv(fname, header, rows):
    os.makedirs(OUT, exist_ok=True)
    p = os.path.join(OUT, fname)
    with open(p, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    print(f"  {fname}: {len(rows)} entradas -> {p}")


def pair_dat(name, jp_stride, es_stride, fname, header):
    jp = names_from_dat(os.path.join(DS, name), jp_stride, dec_jp)
    es = names_from_dat(os.path.join(ES, name), es_stride, dec_es)
    n = min(len(jp), len(es))
    rows = [[i, jp[i], es[i]] for i in range(n) if clean(jp[i]) and clean(es[i])]
    write_csv(fname, header, rows)
    return len(rows)


def main():
    global DS, ES, OUT
    game = sys.argv[1] if len(sys.argv) > 1 else "game1"
    folder, es_rel, out_rel = GAME_CFG[game]
    DS = os.path.join(REPO, "work", "shared", "fa_extract", folder, "data_iz", "logic")
    ES = os.path.join(REPO, "work", *es_rel.split(os.sep))
    OUT = os.path.join(REPO, out_rel)
    print(f"Generando glosario {game} (JP 3DS <-> ES NDS oficial)...")
    total = 0
    total += pair_dat("unitbase.dat", 96, 96, "jugadores.csv",
                      ["idx", "japones", "espanol_oficial"])
    total += pair_dat("teamtitle.dat", 16, 16, "titulos_equipo.csv",
                      ["idx", "japones", "espanol_oficial"])
    # Menus: games.STR por indice (NDS puede tenerlo en sp/ o en logic/)
    es_games = os.path.join(ES, "games.STR")
    if not os.path.exists(es_games):
        es_games = os.path.join(os.path.dirname(ES), "games.STR")
    jp = strings_from_str(os.path.join(DS, "games.STR"), dec_jp)
    es = strings_from_str(es_games, dec_es) if os.path.exists(es_games) else []
    if es and len(jp) == len(es):
        rows = [[i, jp[i], es[i]] for i in range(len(jp)) if clean(es[i])]
        write_csv("menus.csv", ["idx", "japones", "espanol_oficial"], rows)
        total += len(rows)
    else:
        print(f"  menus.csv: OMITIDO (jp={len(jp)} vs es={len(es)})")
    print(f"TOTAL: {total} parejas")


if __name__ == "__main__":
    main()
