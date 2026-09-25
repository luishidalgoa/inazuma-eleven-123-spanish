#!/usr/bin/env python3
"""
Pipeline unico de extraccion y alineamiento de textos de Inazuma Eleven 3.

    ROM / CIA
      -> CXI / RomFS                     (3dstool, ctrtool)
      -> contenedor Level-5 B123 (.fa)   (ie3lib.b123)
      -> eve.pkb+pkh / evet.pkb+pkh      (ie3lib.pack)
      -> LZ10                            (ie3lib.lz)
      -> SSD / tabla plana               (ie3lib.ssd)
      -> textos                          (ie3lib.text)
      -> CSV                             (este script)
      -> CSV alineado JP <-> ES          (ie3lib.align)

Ordenes:

    run        hace el proyecto entero (extraer los tres juegos + alinear)
    extract    procesa una sola ROM/CIA/RomFS
    align      cruza japones y espanol a partir de los CSV ya extraidos
    validate   vuelve a comprobar los CSV generados
    info       identifica una ROM/CIA sin extraer nada

Ejemplos:

    python -m ie123kit.ie3.pipeline run
    python -m ie123kit.ie3.pipeline extract roms/IE123_JP.3ds --lang jp --tag jp
    python -m ie123kit.ie3.pipeline extract CIAS/rayo.3ds --lang es --tag rayo
    python -m ie123kit.ie3.pipeline align
"""

import argparse
import csv
import hashlib
import json
import sys
import time
from pathlib import Path

from ie123kit.ie3.comun import align as aligner
from ie123kit.ie3.comun import sheet as sheetlib
from ie123kit.ie3.comun.b123 import B123Archive, B123Error
from ie123kit.ie3.comun.pack import Pack, PackError
from ie123kit.ie3.comun.rom import (
    RomError,
    detect_kind,
    prepare_romfs,
    product_code,
    title_id,
)
from ie123kit.ie3.comun.ssd import (
    SSDError,
    group_ruby,
    is_ssd,
    parse_flat_text,
    parse_ssd,
)
from ie123kit.ie3.comun.text import TextTable, clean_for_csv
from ie123kit.nucleo.config.raiz import find_root

# --------------------------------------------------------------------------
# Rutas y configuracion del proyecto
# --------------------------------------------------------------------------

ROOT = find_root()

TOOLS = ROOT / "tools" / "bin"
WORK = ROOT / "work"

# Nada de lo que sale de aqui puede subirse a git (Norma 2 de CLAUDE.md): son
# textos extraidos de la ROM. Por eso vive dentro de work/, que .gitignore ya
# excluye entero. A translation/ie3/ solo va el CSV final de traduccion.
OUTPUT = WORK / "ie3" / "shared" / "salida"
PACKS = WORK / "ie3" / "shared" / "packs"
EXTRACTED = WORK / "ie3" / "shared" / "eventos"

# Las dos mitades de IE3 con texto propio. Bomber (data_iz_bomber) NO tiene
# script propio: comparte eve/evet con Spark, asi que no es un objetivo aparte.
GAMES = {
    "spark": "inazuma3",       # IE3 Spark  / Lightning Bolt / Rayo Celeste
    "ogre": "inazuma3_ogre",   # IE3 Ogre   / Team Ogre Attacks / Amenaza del Ogro
}

PACK_NAMES = ("eve", "evet")

# Donde se extrae cada juego, siguiendo docs/ARQUITECTURA.md.
WORKDIRS = {
    "jp": WORK / "shared" / "base_3ds",
    "rayo": WORK / "ie3" / "rayo_celeste" / "fuentes" / "3ds_eu",
    "fuego": WORK / "ie3" / "shared" / "fuego",
    "ogro": WORK / "ie3" / "amenaza_del_ogro" / "fuentes" / "3ds_eu",
}

# Que hay que extraer de cada juego en la orden `run`.
TARGETS = [
    # tag     entrada                                                 idioma  juegos
    ("jp",   "Roms/shared/IE123_JP_CTR-P-AETJ.3ds",                   "jp",  ("spark", "ogre")),
    ("rayo", "Roms/ie3/rayo_celeste/00040000000F7E00_v00.trim.3ds",   "es",  ("spark",)),
    ("fuego", ("Roms/ie3/fuego_explosivo/00040000000F7C00 Inazuma Eleven 3 "
               "Bomb Blast (CTR-P-AXBZ) (v0.1.0) (E).piratelegit.cia"), "es", ("spark",)),
    ("ogro", ("Roms/ie3/amenaza_del_ogro/00040000000F8000 IE3 Team "
              "Ogre Attacks! (CTR-P-AXGZ) (W) (v0.0.0).standar.cia"), "es", ("ogre",)),
]

# Cruces finales: (nombre, juego, tag japones, tag espanol)
ALIGNMENTS = [
    ("spark_rayo", "spark", "jp", "rayo"),
    ("spark_fuego", "spark", "jp", "fuego"),
    ("ogre_ogro", "ogre", "jp", "ogro"),
]

# Carpeta de translation/ para cada mitad. Spark cubre TAMBIEN a Bomber
# (fuego_explosivo): data_iz_bomber no trae script propio, comparte eve/evet
# con data_iz, asi que su dialogo es este mismo.
TRANSLATION_DIR = {
    "spark": "rayo_celeste",
    "ogre": "amenaza_del_ogro",
}

LANG_DIR = {"jp": "japanese", "es": "spanish"}


# --------------------------------------------------------------------------
# Utilidades
# --------------------------------------------------------------------------

class Log:
    def __init__(self):
        self.t0 = time.time()

    def __call__(self, msg=""):
        print(f"[{time.time() - self.t0:7.1f}s] {msg}", flush=True)

    def section(self, title):
        print()
        print("=" * 74, flush=True)
        print(f"  {title}", flush=True)
        print("=" * 74, flush=True)


log = Log()


def die(msg):
    raise SystemExit(f"\nERROR: {msg}\n")


def tool_path(name, override=None):
    if override:
        p = Path(override).resolve()
    else:
        p = TOOLS / name
        if not p.exists():
            p = ROOT / name
    if not p.exists():
        die(
            f"No encuentro {name}. Deberia estar en {TOOLS}. "
            f"Usa --{name.split('.')[0]} para indicar otra ruta."
        )
    return p.resolve()


def write_csv(path, header, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
            w.writerow(header)
            w.writerows(rows)
    except PermissionError:
        die(
            f"No se puede escribir {path.relative_to(ROOT)} porque otro "
            f"programa lo tiene abierto.\n"
            f"Suele ser Excel: cierra el fichero y vuelve a ejecutar la orden."
        )
    return path


def read_csv(path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


# --------------------------------------------------------------------------
# Localizar los packs dentro del contenedor
# --------------------------------------------------------------------------

def find_archive(romfs):
    """El contenedor B123 del juego: archive.fa, archive_sz.fa, archive_op.fa..."""
    candidates = sorted(
        p for p in Path(romfs).glob("*.fa") if B123Archive.looks_like(p)
    )

    if not candidates:
        others = sorted(p.name for p in Path(romfs).glob("*.fa"))
        die(
            f"No hay ningun contenedor B123 en {romfs}. "
            + (f"Archivos .fa encontrados: {others}" if others
               else "No hay ningun .fa; comprueba que el RomFS se extrajo bien.")
        )

    # El contenedor principal es el mayor.
    candidates.sort(key=lambda p: p.stat().st_size, reverse=True)
    return candidates[0]


def pack_paths(archive, game_dir, lang):
    """
    Rutas de eve/evet dentro del contenedor.

    En japones cuelgan de la raiz; en europeo hay una carpeta por idioma
    (en/, es/, it/) porque cada idioma trae su propio texto.
    """
    prefixes = ["es/", ""] if lang == "es" else ["", "es/"]

    for prefix in prefixes:
        base = f"{prefix}{game_dir}/data_iz/script/"
        wanted = {
            pack: (f"{base}{pack}.pkb".encode(), f"{base}{pack}.pkh".encode())
            for pack in PACK_NAMES
        }
        if all(
            pkb in archive._by_path and pkh in archive._by_path
            for pkb, pkh in wanted.values()
        ):
            return prefix, wanted

    return None, None


# --------------------------------------------------------------------------
# Extraccion de un juego
# --------------------------------------------------------------------------

EXTRACT_HEADER = [
    "tag", "lang", "game", "pack", "event_id", "event_index",
    "string_id", "instruction", "argument", "opcode", "offset", "text",
]


def extract_pack(archive, table, prefix, pkb_rel, pkh_rel, tag, lang, game,
                 pack, dump_dir, stats):
    """Un pack (eve o evet) -> filas de CSV."""
    tmp = PACKS
    tmp.mkdir(parents=True, exist_ok=True)

    pkb = tmp / f"{tag}_{game}_{pack}.pkb"
    pkh = tmp / f"{tag}_{game}_{pack}.pkh"
    archive.extract(archive._by_path[pkb_rel], pkb)
    archive.extract(archive._by_path[pkh_rel], pkh)

    p = Pack(pkb, pkh)

    rows = []
    n_events = n_ssd = n_flat = n_compressed = 0
    n_strings = n_ruby = 0
    problems = []

    for entry in p:
        data, compressed = p.data(entry)
        n_events += 1
        n_compressed += int(compressed)

        if dump_dir is not None:
            dest = dump_dir / f"eve{entry.event_id}.ssd"
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)

        try:
            if is_ssd(data):
                n_ssd += 1
                _info, strings = parse_ssd(data, table)
                items = [(s, s.string_id) for s in strings]
            else:
                n_flat += 1
                flat = parse_flat_text(data, table)
                grouped = group_ruby(flat)
                n_ruby += sum(len(r) for _, r in grouped)
                items = [
                    (head, f"m{index:04d}")
                    for index, (head, _readings) in enumerate(grouped)
                ]
        except SSDError as exc:
            problems.append(f"evento {entry.event_id:08x}: {exc}")
            continue

        for s, string_id in items:
            n_strings += 1
            rows.append([
                tag, lang, game, pack,
                str(entry.event_id), entry.index,
                string_id, s.instruction, s.argument,
                f"0x{s.opcode:04x}" if s.opcode >= 0 else "",
                f"0x{s.offset:X}",
                clean_for_csv(s.text),
            ])

    stats.update(
        events=n_events, ssd=n_ssd, flat=n_flat, compressed=n_compressed,
        strings=n_strings, ruby=n_ruby, problems=problems,
        duplicate_ids=len(p.duplicate_ids),
    )

    return rows


def cmd_extract(args):
    dstool = tool_path("3dstool.exe", args.dstool)
    ctrtool = tool_path("ctrtool.exe", args.ctrtool)

    source = Path(args.input)
    if not source.is_absolute():
        source = (ROOT / source).resolve()
    if not source.exists():
        die(f"No existe la entrada: {source}")

    tag = args.tag or source.stem.split(".")[0].lower()
    work = WORKDIRS.get(tag, WORK / "ie3" / "shared" / tag)

    log.section(f"EXTRAER  {tag}  ({args.lang})")

    romfs = prepare_romfs(source, work, dstool, ctrtool, log, force=args.force)
    log(f"RomFS: {romfs}")

    archive_path = find_archive(romfs)
    log(f"Contenedor: {archive_path.name} ({archive_path.stat().st_size:,} bytes)")

    try:
        archive = B123Archive(archive_path)
    except B123Error as exc:
        die(f"No se pudo leer el contenedor: {exc}")

    log(f"  {archive.file_count:,} archivos / {archive.dir_count} directorios, "
        f"todos los CRC verificados")

    table = TextTable.identity()
    if args.lang == "es":
        try:
            table = TextTable.from_codetable(archive.read("font/CodeTable.bin"))
            log(f"  tabla de caracteres europea: {len(table)} sustituciones "
                f"(font/CodeTable.bin)")
        except (B123Error, KeyError, UnicodeError, ValueError) as exc:
            die(
                f"La version europea deberia traer font/CodeTable.bin con la "
                f"tabla de caracteres y no se pudo leer: {exc}"
            )

    games = args.games or [g for g in GAMES if g in _default_games(tag)]
    report = {}

    for game in games:
        game_dir = GAMES[game]
        prefix, wanted = pack_paths(archive, game_dir, args.lang)

        if wanted is None:
            log(f"  {game}: no hay eve/evet para {game_dir} en este contenedor, se salta")
            continue

        log(f"  {game}: {prefix or '<raiz>'}{game_dir}/data_iz/script/")

        for pack in PACK_NAMES:
            pkb_rel, pkh_rel = wanted[pack]
            dump_dir = (
                EXTRACTED / tag / f"{game}_{pack}" if args.dump_events else None
            )
            stats = {}

            try:
                rows = extract_pack(
                    archive, table, prefix, pkb_rel, pkh_rel,
                    tag, args.lang, game, pack, dump_dir, stats,
                )
            except PackError as exc:
                die(f"{tag}/{game}/{pack}: {exc}")

            out = OUTPUT / LANG_DIR[args.lang] / f"{tag}_{game}_{pack}.csv"
            write_csv(out, EXTRACT_HEADER, rows)

            log(
                f"     {pack:4} -> {out.relative_to(ROOT)} | "
                f"{stats['events']:5} eventos "
                f"({stats['ssd']} SSD / {stats['flat']} planos, "
                f"{stats['compressed']} LZ10) | "
                f"{stats['strings']:6} textos"
                + (f" | {stats['ruby']} furigana" if stats["ruby"] else "")
            )

            for problem in stats["problems"][:5]:
                log(f"        AVISO {problem}")
            if len(stats["problems"]) > 5:
                log(f"        ... y {len(stats['problems']) - 5} avisos mas")

            report[f"{game}_{pack}"] = {
                k: v for k, v in stats.items() if k != "problems"
            } | {"problems": len(stats["problems"]), "csv": str(out.relative_to(ROOT))}

    archive.close()

    meta = {
        "tag": tag,
        "lang": args.lang,
        "source": str(source),
        "kind": detect_kind(source),
        "title_id": title_id(source),
        "archive": archive_path.name,
        "charset_substitutions": len(table),
        "packs": report,
    }
    meta_path = work / "extract.json"
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), "utf-8")

    return meta


def _default_games(tag):
    for t, _src, _lang, games in TARGETS:
        if t == tag:
            return games
    return tuple(GAMES)


# --------------------------------------------------------------------------
# Alineamiento
# --------------------------------------------------------------------------

ALIGN_HEADER = [
    "version", "pack", "event_id", "string_id", "opcode",
    "jp_offset", "es_offset", "jp_text", "es_text", "status",
]


def load_extract(tag, game, pack, lang):
    path = OUTPUT / LANG_DIR[lang] / f"{tag}_{game}_{pack}.csv"
    if not path.exists():
        die(
            f"Falta {path.relative_to(ROOT)}. "
            f"Ejecuta primero:  python -m ie123kit.ie3.pipeline run"
        )
    return read_csv(path)


class Row:
    """Fila de CSV con la misma interfaz minima que ScriptString."""
    __slots__ = (
        "argument",
        "instruction",
        "offset",
        "opcode",
        "string_id",
        "text",
    )

    def __init__(self, d):
        self.instruction = int(d["instruction"])
        self.argument = int(d["argument"])
        self.offset = d["offset"]
        self.text = d["text"]
        self.string_id = d["string_id"]
        self.opcode = d.get("opcode", "")

    @property
    def key(self):
        return (self.instruction, self.argument)


def group_by_event(rows):
    events = {}
    for d in rows:
        events.setdefault(d["event_id"], []).append(Row(d))
    return events


def align_pack(game, jp_tag, es_tag, pack, stats):
    jp_events = group_by_event(load_extract(jp_tag, game, pack, "jp"))
    es_events = group_by_event(load_extract(es_tag, game, pack, "es"))

    jp_ids = list(jp_events)
    es_ids = set(es_events)
    common = [e for e in jp_ids if e in es_ids]

    stats["events_jp"] = len(jp_events)
    stats["events_es"] = len(es_events)
    stats["events_matched"] = len(common)
    stats["events_only_jp"] = len(set(jp_ids) - es_ids)
    stats["events_only_es"] = len(es_ids - set(jp_ids))

    rows = []
    counts = {s: 0 for s in (
        aligner.STATUS_EXACT, aligner.STATUS_STRUCTURAL,
        aligner.STATUS_PROBABLE, aligner.STATUS_UNMATCHED,
    )}

    dropped = [0]

    # evet no tiene claves internas, asi que primero se resuelven los eventos
    # en los que el numero de dialogos cuadra (emparejamiento por posicion,
    # sin heuristica) y con ellos se monta una memoria japones -> espanol.
    # Esa memoria sirve de ancla para los eventos que NO cuadran.
    memory = None
    if pack != "eve":
        memory = aligner.flat_memory(
            (jp.text, es.text)
            for event_id in common
            for jp, es in zip(jp_events[event_id], es_events[event_id])
            if len(jp_events[event_id]) == len(es_events[event_id])
        )
        stats["memoria_anclas"] = len(memory)

    def emit(event_id, jp, es, status):
        # Los SSD tienen huecos de texto vacios. Una fila sin texto en
        # NINGUNO de los dos idiomas no le sirve de nada al traductor, asi
        # que no la escribimos (se cuenta aparte para no ocultarla).
        if not (jp and jp.text) and not (es and es.text):
            dropped[0] += 1
            return

        counts[status] += 1
        rows.append([
            game, pack, event_id,
            (jp or es).string_id,
            # El opcode manda el japones, que es el original; solo se coge
            # del espanol cuando la fila no tiene pareja japonesa.
            (jp or es).opcode,
            jp.offset if jp else "",
            es.offset if es else "",
            jp.text if jp else "",
            es.text if es else "",
            status,
        ])

    for event_id in jp_ids:
        jp_rows = jp_events[event_id]
        es_rows = es_events.get(event_id)

        if es_rows is None:
            for jp in jp_rows:
                emit(event_id, jp, None, aligner.STATUS_UNMATCHED)
            continue

        if pack == "eve":
            same = len(jp_rows) == len(es_rows)
            paired = aligner.align_script_strings(jp_rows, es_rows, same)
        else:
            paired = aligner.align_flat_strings(jp_rows, es_rows, memory)

        for jp, es, status in paired:
            emit(event_id, jp, es, status)

    for event_id in es_events:
        if event_id in jp_events:
            continue
        for es in es_events[event_id]:
            emit(event_id, None, es, aligner.STATUS_UNMATCHED)

    stats["strings_jp"] = sum(len(v) for v in jp_events.values())
    stats["strings_es"] = sum(len(v) for v in es_events.values())
    stats.update(counts)

    matched = counts[aligner.STATUS_EXACT] + counts[aligner.STATUS_STRUCTURAL] \
        + counts[aligner.STATUS_PROBABLE]
    stats["strings_matched"] = matched
    stats["alignment_pct"] = 100.0 * matched / max(stats["strings_jp"], 1)

    # Los SSD japoneses tienen muchos huecos de texto vacios; medir sobre
    # ellos hunde el porcentaje y no dice nada util al traductor.
    jp_filled = sum(1 for r in rows if r[6])
    jp_filled_matched = sum(1 for r in rows if r[6] and r[8] != aligner.STATUS_UNMATCHED)
    stats["strings_jp_nonempty"] = jp_filled
    stats["strings_jp_nonempty_matched"] = jp_filled_matched
    stats["alignment_pct_nonempty"] = 100.0 * jp_filled_matched / max(jp_filled, 1)
    stats["rows_dropped_empty_both"] = dropped[0]

    return rows


def cmd_align(args):
    log.section("ALINEAR JAPONES <-> ESPANOL")

    everything = []
    report = {}

    for name, game, jp_tag, es_tag in ALIGNMENTS:
        all_rows = []
        for pack in PACK_NAMES:
            stats = {}
            rows = align_pack(game, jp_tag, es_tag, pack, stats)
            all_rows.extend(rows)
            report[f"{name}_{pack}"] = stats

            log(f"{name} / {pack}")
            log(f"    eventos   JP {stats['events_jp']:5}  ES {stats['events_es']:5}  "
                f"emparejados {stats['events_matched']:5}  "
                f"solo JP {stats['events_only_jp']:3}  solo ES {stats['events_only_es']:3}")
            log(f"    textos    JP {stats['strings_jp']:6}  ES {stats['strings_es']:6}  "
                f"emparejados {stats['strings_matched']:6}  "
                f"({stats['alignment_pct']:.2f}% del japones)")
            log(f"    sin huecos vacios: JP {stats['strings_jp_nonempty']:6}  "
                f"emparejados {stats['strings_jp_nonempty_matched']:6}  "
                f"({stats['alignment_pct_nonempty']:.2f}%)")
            if stats.get("memoria_anclas"):
                log(f"    anclas de memoria para los eventos descuadrados: "
                    f"{stats['memoria_anclas']}")
            log(f"    estados   exact {stats['exact']:6}  structural {stats['structural']:6}  "
                f"probable {stats['probable']:5}  unmatched {stats['unmatched']:6}")
            log(f"    huecos vacios en los dos idiomas, no escritos: "
                f"{stats['rows_dropped_empty_both']}")

        out = OUTPUT / "aligned" / f"{name}.csv"
        write_csv(out, ALIGN_HEADER, all_rows)
        log(f"    -> {out.relative_to(ROOT)}  ({len(all_rows):,} filas)")
        everything.extend(all_rows)

    combined = OUTPUT / "aligned" / "all_ie3.csv"
    write_csv(combined, ALIGN_HEADER, everything)
    log(f"\nCSV combinado -> {combined.relative_to(ROOT)}  ({len(everything):,} filas)")

    path = OUTPUT / "aligned" / "alignment_report.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), "utf-8")
    log(f"Informe        -> {path.relative_to(ROOT)}")

    return report


# --------------------------------------------------------------------------
# Hoja de traduccion
# --------------------------------------------------------------------------

def cmd_sheet(args):
    """CSV alineado -> hoja de traduccion (event_id, japones, es_final, estado)."""
    log.section("HOJA DE TRADUCCION")

    dest = OUTPUT / "traduccion"
    everything = []
    report = {}
    report_rows = {}

    for name, game, _jp_tag, _es_tag in ALIGNMENTS:
        src = OUTPUT / "aligned" / f"{name}.csv"
        if not src.exists():
            die(
                f"Falta {src.relative_to(ROOT)}. Ejecuta primero:  "
                f"python -m ie123kit.ie3.pipeline align"
            )

        rows = read_csv(src)
        if rows and "opcode" not in rows[0]:
            die(
                f"{src.relative_to(ROOT)} es de una version anterior del "
                f"pipeline y no trae la columna `opcode`, que es lo que "
                f"distingue el texto real de los nombres de recurso. "
                f"Vuelve a generarlo con: "
                f"python -m ie123kit.ie3.pipeline run --force"
            )

        sheet_rows, technical, glossary, stats = sheetlib.build(rows, game)

        write_csv(dest / f"{game}.csv", sheetlib.SHEET_HEADER, sheet_rows)
        write_csv(dest / f"{game}_glosario.csv",
                  sheetlib.GLOSSARY_HEADER, glossary)
        write_csv(dest / "descartado" / f"{game}_tecnico.csv",
                  sheetlib.TECHNICAL_HEADER, technical)

        pending = [r for r in sheet_rows if r[3] in
                   (sheetlib.UNTRANSLATED, sheetlib.NO_MATCH)]
        review = [r for r in sheet_rows if r[3] == sheetlib.REVIEW]
        write_csv(dest / f"{game}_revisar.csv", sheetlib.SHEET_HEADER, review)
        write_csv(dest / f"{game}_pendiente.csv",
                  sheetlib.SHEET_HEADER, pending)

        everything.extend([game] + r for r in sheet_rows)
        report_rows[game] = sheet_rows
        report[game] = stats

        total = stats["texto_real"]
        log(f"{game}")
        log(f"    alineadas {stats['filas_alineadas']:7}  ->  texto real "
            f"{total:6}  |  tecnico {stats['tecnico']:6}  |  "
            f"solo en europeo {stats['descartadas_sin_japones']:5}")
        for kind in ("dialogo", "texto"):
            b = stats[kind]
            if not b:
                continue
            n = sum(b.values())
            log(f"    {kind:8} {n:6}  "
                + "  ".join(f"{k} {v}" for k, v in sorted(b.items())))
        oficial = stats["por_estado"].get(sheetlib.OFFICIAL, 0)
        log(f"    con traduccion oficial: {oficial:6} de {total} "
            f"({100.0 * oficial / max(total, 1):.2f}%)")
        log(f"    rellenadas con memoria: {stats['memoria_rellenadas']:6}  "
            f"| heuristicas confirmadas {stats['heuristicas_confirmadas']}")
        log(f"    pendiente de traducir:  {len(pending):6}  "
            f"| a revisar a mano {len(review)}")
        log(f"    textos japoneses distintos: {stats['glosario_unicos']:6} "
            f"({stats['glosario_con_oficial']} ya tienen version oficial)")
        log(f"    -> {(dest / f'{game}.csv').relative_to(ROOT)}")

    # --- CSV en el formato del repo: event_id, japones, es_final, estado ---
    # Es texto oficial de Nintendo sacado de las ROMs europeas, asi que se
    # llama dialogo_oficial.csv y .gitignore lo excluye (Norma 2 de CLAUDE.md),
    # igual que los de IE1 e IE2. A git solo va dialogo.csv, con lo que
    # traduzca el proyecto.
    for game, carpeta in TRANSLATION_DIR.items():
        filas = [r[:4] for r in report_rows[game]]
        out = ROOT / "translation" / "ie3" / carpeta / "dialogo_oficial.csv"
        write_csv(out, ["event_id", "japones", "es_final", "estado"], filas)
        log(f"{game} -> {out.relative_to(ROOT)}  ({len(filas):,} filas)")

    write_csv(dest / "todo_ie3.csv",
              ["version"] + sheetlib.SHEET_HEADER, everything)
    log("")
    log(f"Hoja combinada -> {(dest / 'todo_ie3.csv').relative_to(ROOT)}  "
        f"({len(everything):,} filas)")

    path = dest / "sheet_report.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), "utf-8")
    log(f"Informe        -> {path.relative_to(ROOT)}")

    return report


# --------------------------------------------------------------------------
# Reinsercion del espanol en el recopilatorio japones
# --------------------------------------------------------------------------

def cmd_reinsert(args):
    """Mete el dialogo espanol de IE3 en archive.fa.

    Los bloques de evet conservan tamano y numero de registros. La evidencia de
    Spark descarta crecerlos: desplazar registros hace que el motor pierda el
    comienzo del dialogo.
    """
    import shutil
    import struct as _struct

    from ie123kit.ie3.comun.reinsert import parchear_bloque, parchear_ssd
    from ie123kit.ie3.comun.sheet import TEXT_OPCODES
    from ie123kit.nucleo.config.congelados import cargar
    from ie123kit.nucleo.contenedores.fa import FaArchive, reemplazar_entrada
    from ie123kit.nucleo.eventos import packnum
    if args.crecer:
        die("--crecer esta deshabilitado: corrompe offsets de evet; ver docs/IE3_RE_DIALOGO.md")

    log.section("REINSERTAR IE3 EN archive.fa  (mismo tamano)")

    origen = Path(args.entrada) if args.entrada else WORK / "archive_es.fa"
    if not origen.is_file():
        origen = WORK / "shared" / "base_3ds" / "romfs" / "archive.fa"
    destino = Path(args.salida) if args.salida else WORK / "archive_es.fa"

    if not origen.is_file():
        die(f"No existe {origen}. Ejecuta antes: python -m ie123kit._legado.reinsert")

    log(f"Base:    {origen.name}")
    if destino.resolve() != origen.resolve():
        shutil.copyfile(origen, destino)

    total = 0

    with destino.open("r+b") as fh:
        arc = FaArchive(str(destino))

        # sjis_portador no guarda á/¡ literalmente: emite sus portadores
        # griegos. La fuente debe llevar el mismo parche que los renderiza;
        # partir del archive JP sin este paso muestra los glifos griegos.
        patch_font_bytes = cargar("font_patch").patch_font_bytes
        fuentes_parcheadas = {}
        for rel in ("font/FONT12.bcfnt", "font/FONT12T.bcfnt", "font/FONT8.bcfnt"):
            fuente = arc.read(rel)
            origen_fuente = WORK / "shared" / "fa_extract" / Path(rel)
            if not origen_fuente.is_file():
                die(f"falta la fuente de referencia para parchear: {origen_fuente}")
            if origen_fuente.read_bytes() != fuente:
                die(f"la fuente base no coincide con {origen_fuente}; no se parchea a ciegas")
            # FONT12/FONT8 se adaptan desde el original con coordenadas BCFNT
            # correctas. No ejecutar antes el escritor histórico: dejaría
            # residuos en el margen de las celdas portadoras.
            parcheada = (patch_font_bytes(origen_fuente)
                         if rel == "font/FONT12T.bcfnt" else fuente)
            if len(parcheada) != len(fuente):
                die(f"{rel}: font_patch cambio el tamano ({len(fuente)} -> {len(parcheada)})")
            reemplazar_entrada(fh, arc, rel, parcheada)
            fuentes_parcheadas[rel] = parcheada
            log(f"  fuente ES {rel}: {hashlib.sha256(parcheada).hexdigest()[:12]}")

        # FONT12 recibe raster y CWDH europeos como una unidad coherente, con
        # el píxel general de respiración del proyecto. FONT8 adapta glifos
        # individuales de nombres; los bigramas v5 se retiraron porque la
        # prueba visual demostró que fusionaban trazos.
        from ie123kit.ie3.comun.nombres import caracteres_cortos
        from ie123kit.ie3.comun.tipografia import adaptar_font8_nombres, adaptar_font12

        oficial_archive = WORK / "ie3" / "rayo_celeste" / "fuentes" / "3ds_eu" / "romfs" / "archive_sz.fa"
        if not oficial_archive.is_file():
            die(f"falta referencia ES para tipografía/nombres: {oficial_archive}")
        oficial_fuente = FaArchive(str(oficial_archive))
        try:
            tabla_es = TextTable.from_codetable(oficial_fuente.read("font/CodeTable.bin"))
            unitbase = "inazuma3/data_iz/logic/unitbase.dat"
            unitbase_jp = arc.read(unitbase)
            unitbase_es = oficial_fuente.read(f"es/{unitbase}")
            caracteres_nombres = caracteres_cortos(
                unitbase_jp, unitbase_es, tabla_es
            )
            font12, informe_fuente = adaptar_font12(
                fuentes_parcheadas["font/FONT12.bcfnt"],
                oficial_fuente.read("font/FONT12.bcfnt"),
                tabla_es,
            )
            font8, informe_font8 = adaptar_font8_nombres(
                fuentes_parcheadas["font/FONT8.bcfnt"],
                oficial_fuente.read("font/FONT8.bcfnt"), tabla_es,
                caracteres_nombres,
            )
        finally:
            cerrar = getattr(oficial_fuente, "close", None)
            if callable(cerrar):
                cerrar()
        reemplazar_entrada(fh, arc, "font/FONT12.bcfnt", font12)
        reemplazar_entrada(fh, arc, "font/FONT8.bcfnt", font8)
        log("  FONT12 latina oficial con tracking: "
            f"{informe_fuente['glifos']} glifos | "
            f"È {informe_fuente['portador_E_grave']} | "
            f"{hashlib.sha256(font12).hexdigest()[:12]}")
        log("  FONT8 nombres oficiales por carácter: "
            f"{informe_font8['glifos']} glifos | "
            f"{hashlib.sha256(font8).hexdigest()[:12]}")

        # 0x301A resuelve el rótulo en unitbase.dat, no en evet. La rutina
        # conserva registros y solo acepta la correspondencia física que la
        # referencia ES confirma también fuera de los campos de nombre.
        from ie123kit.ie3.comun.nombres import localizar_cortos

        oficial = FaArchive(str(oficial_archive))
        try:
            tabla_es = TextTable.from_codetable(oficial.read("font/CodeTable.bin"))
            tabla_unidades, informe_nombres = localizar_cortos(
                unitbase_jp, oficial.read(f"es/{unitbase}"), tabla_es,
            )
        finally:
            cerrar = getattr(oficial, "close", None)
            if callable(cerrar):
                cerrar()
        reemplazar_entrada(fh, arc, unitbase, tabla_unidades)
        log("  unitbase.dat: "
            f"{informe_nombres['applied']} nombres cortos ES verificados | "
            f"estructura {informe_nombres['skipped_structure']} | "
            f"encoding {informe_nombres['skipped_encoding']} | "
            f"tamaño {informe_nombres['skipped_size']} | "
            f"{informe_nombres['characters']} caracteres FONT8")

        for game in (args.games or tuple(TRANSLATION_DIR)):
            carpeta = TRANSLATION_DIR[game]
            csv_path = ROOT / "translation" / "ie3" / carpeta / "dialogo_oficial.csv"
            if not csv_path.exists():
                log(f"  {carpeta}: falta {csv_path.relative_to(ROOT)}, se salta")
                continue

            trad = {}
            for row in read_csv(csv_path):
                if row["es_final"] and row["estado"] in ("oficial", "memoria"):
                    trad.setdefault(int(row["event_id"]), {})[row["japones"]] =                         row["es_final"]

            folder = GAMES[game]
            ruta_pkb = f"{folder}/data_iz/script/evet.pkb"
            ruta_pkh = f"{folder}/data_iz/script/evet.pkh"

            def leer(ruta):
                try:
                    return arc.read(ruta)
                except KeyError:
                    die(f"no encontrado en el contenedor: {ruta}")

            pkb = leer(ruta_pkb)
            pkh = leer(ruta_pkh)

            reemplazos = {}
            aplicadas = no_caben = 0
            for eid, off, size in packnum.parse_index(pkh):
                if eid == 0xFFFFFFFF or eid not in trad:
                    continue
                try:
                    nuevo, n, fuera = parchear_bloque(
                        pkb[off:off + size], trad[eid])
                except ValueError as exc:
                    log(f"     AVISO evento {eid}: {exc}")
                    continue
                if n:
                    reemplazos[eid] = nuevo
                aplicadas += n
                no_caben += fuera

            nuevo_pkh, nuevo_pkb, _informe = packnum.rebuild(
                pkh, pkb, reemplazos, comprimir=False, align="auto",
            )

            # 0x1C del .pkh es el tamano del bloque MAS GRANDE. Si el motor
            # reserva el bufer con ese numero y un bloque crece por encima, se
            # sale. Se recalcula siempre.
            mayor = max(
                (sz for _e, _o, sz in packnum.parse_index(nuevo_pkh)), default=0
            )
            nuevo_pkh = bytearray(nuevo_pkh)
            _struct.pack_into("<I", nuevo_pkh, 0x1C, mayor)
            nuevo_pkh = bytes(nuevo_pkh)

            reemplazar_entrada(fh, arc, ruta_pkb, nuevo_pkb)
            reemplazar_entrada(fh, arc, ruta_pkh, nuevo_pkh)

            total += aplicadas
            log(f"  {carpeta:18} evet  {len(reemplazos):5} eventos | {aplicadas:6} lineas ES"
                + (f" | {no_caben:6} no caben" if no_caben else " | todo cabe")
                + f" | pkb {len(pkb):,} -> {len(nuevo_pkb):,}")

            # --- eve: rotulos de objetivo y nombres de sitio ---------------
            # Es lo que sale en la barra de objetivo y en la placa del mapa;
            # sin esto siguen en japones aunque el dialogo este traducido.
            ruta_epkb = f"{folder}/data_iz/script/eve.pkb"
            ruta_epkh = f"{folder}/data_iz/script/eve.pkh"
            epkb = leer(ruta_epkb)
            epkh = leer(ruta_epkh)

            rem_eve = {}
            ap_eve = 0
            for eid, off, size in packnum.parse_index(epkh):
                if eid == 0xFFFFFFFF:
                    continue
                if eid not in trad:
                    continue
                try:
                    dec = packnum.entry_data(epkb, off, size)
                    if dec[:4] != b"SSD" + bytes(1):
                        continue
                    # NO se recolocan offsets. La hipotesis de que 0x301a
                    # arg2 fuese un offset a evet quedo DESMENTIDA (❌#17 de
                    # FURIGANA_LECCIONES: correlacion del 95% que era ruido de
                    # valores pequenos; los valores reales son 0, 2, 8 y los
                    # registros estan en 204, 216, 228). Ademas 0x301a ni
                    # siquiera es el opcode del dialogo: lo es 0x301d, y sus
                    # argumentos son indices de la tabla de textos del propio
                    # SSD, no offsets a evet. Tocarlos corrompe operandos.
                    # 2) traducir los rotulos de objetivo y nombres de sitio
                    n = 0
                    if eid in trad:
                        dec, n = parchear_ssd(dec, trad[eid], set(TEXT_OPCODES))
                except (ValueError, Exception) as exc:
                    if isinstance(exc, KeyboardInterrupt):
                        raise
                    log(f"     AVISO eve {eid}: {exc}")
                    continue
                if n:
                    rem_eve[eid] = dec
                    ap_eve += n

            if rem_eve:
                n_epkh, n_epkb, _inf = packnum.rebuild(
                    epkh, epkb, rem_eve, comprimir=True, align="auto",
                )
                mayor_e = max(
                    (sz for _e, _o, sz in packnum.parse_index(n_epkh)), default=0
                )
                n_epkh = bytearray(n_epkh)
                _struct.pack_into("<I", n_epkh, 0x1C, mayor_e)
                reemplazar_entrada(fh, arc, ruta_epkb, n_epkb)
                reemplazar_entrada(fh, arc, ruta_epkh, bytes(n_epkh))
                total += ap_eve
                log(f"  {carpeta:18} eve   {len(rem_eve):5} eventos | {ap_eve:6} rotulos ES"
                    f" | pkb {len(epkb):,} -> {len(n_epkb):,}")

        cerrar = getattr(arc, "close", None)
        if callable(cerrar):
            cerrar()

    log(f"-> {destino}  ({destino.stat().st_size:,} bytes)")
    log(f"Total IE3: {total:,} lineas en espanol")
    return total


def cmd_build(args):
    """Empaqueta una candidata IE3 junto al CRO que exige su maquetación.

    El archive lleva los textos; el ancho que usa ``maqueta`` vive en RomFS/CRO.
    Separarlos fue la causa de los cortes a 22 caracteres de la v2.  El builder
    general crea una copia temporal del RomFS, por lo que esta orden nunca toca
    la base extraída.
    """
    import shutil

    from ie123kit.ie3.comun import ancho_ventana
    from ie123kit.nucleo.construir.rom import build_3ds

    archive = Path(args.archive).resolve()
    destino = Path(args.candidate_dir).resolve()
    salida = Path(args.output).resolve()
    cro_base = WORK / "shared" / "base_3ds" / "romfs" / "cro" / "ina_main3ogre.cro"
    if not archive.is_file():
        die(f"no existe la candidata archive.fa: {archive}")
    if destino.exists():
        die(f"el directorio de candidata ya existe: {destino}")
    if salida.exists():
        die(f"la ROM de salida ya existe: {salida}")
    if not cro_base.is_file():
        die(f"falta el CRO base: {cro_base}")

    cro_original = cro_base.read_bytes()
    try:
        cro_parcheado, informe_cro = ancho_ventana.parchear(cro_original)
    except ancho_ventana.CROError as exc:
        die(f"CRO IE3 no verificable; no se construye: {exc}")

    (destino / "romfs" / "cro").mkdir(parents=True)
    shutil.copyfile(archive, destino / "archive.fa")
    (destino / "romfs" / "cro" / cro_base.name).write_bytes(cro_parcheado)
    manifiesto = {
        "label": "Spark conservadora — pendiente de validación visual",
        "archive": {"source": str(archive), "sha256": hashlib.sha256(archive.read_bytes()).hexdigest()},
        "cro": {
            "source": str(cro_base),
            "sha256_before": hashlib.sha256(cro_original).hexdigest(),
            "sha256_after": hashlib.sha256(cro_parcheado).hexdigest(),
            "verification": informe_cro,
        },
        "runtime_verified": False,
    }
    (destino / "manifest.json").write_text(
        json.dumps(manifiesto, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    informe_rom = build_3ds(destino, salida)
    manifiesto["rom"] = informe_rom
    (destino / "manifest.json").write_text(
        json.dumps(manifiesto, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    log(f"CRO verificado: {informe_cro['caracteres_por_linea']} caracteres/línea")
    log(f"Candidata ejecutable: {destino}")
    log(f"ROM: {salida} ({informe_rom['size']:,} bytes)")
    return manifiesto


# --------------------------------------------------------------------------
# Build de diagnostico
# --------------------------------------------------------------------------

#: Eventos del prologo en Italia, que es lo primero que se juega.
EVENTOS_DIAGNOSTICO = {32500100, 32500120, 32500130, 32010200, 32010300}


def cmd_diagnostico(args):
    """Mete reglas graduadas en los dialogos del prologo para MEDIR la caja."""
    import shutil
    import struct as _struct

    from ie123kit.ie3.comun import diagnostico as diag
    from ie123kit.nucleo.contenedores.fa import FaArchive, reemplazar_entrada
    from ie123kit.nucleo.eventos import packnum

    log.section("BUILD DE DIAGNOSTICO (reglas graduadas)")

    origen = Path(args.entrada) if args.entrada else (
        WORK / "shared" / "base_3ds" / "romfs" / "archive.fa")
    destino = Path(args.salida) if args.salida else WORK / "archive_diag.fa"

    shutil.copyfile(origen, destino)
    total = 0

    with destino.open("r+b") as fh:
        arc = FaArchive(str(destino))

        for game in ("spark",):
            folder = GAMES[game]
            ruta_pkb = f"{folder}/data_iz/script/evet.pkb"
            ruta_pkh = f"{folder}/data_iz/script/evet.pkh"

            def leer(ruta):
                for p_, o, sz in arc.entries:
                    if p_.endswith(ruta):
                        return bytes(arc.d[o:o + sz])
                die(f"no encontrado: {ruta}")

            pkb = leer(ruta_pkb)
            pkh = leer(ruta_pkh)

            reemplazos = {}
            for eid, off, size in packnum.parse_index(pkh):
                if eid == 0xFFFFFFFF:
                    continue
                nuevo, n = diag.parchear_bloque(
                    pkb[off:off + size], EVENTOS_DIAGNOSTICO, eid,
                    lineas=args.lineas, ancho=args.ancho,
                )
                if n:
                    reemplazos[eid] = nuevo
                    total += n
                    log(f"  evento {eid}: {n} dialogos con regla")

            if reemplazos:
                n_pkh, n_pkb, _i = packnum.rebuild(
                    pkh, pkb, reemplazos, comprimir=False, align="auto")
                mayor = max((sz for _e, _o, sz in packnum.parse_index(n_pkh)),
                            default=0)
                n_pkh = bytearray(n_pkh)
                _struct.pack_into("<I", n_pkh, 0x1C, mayor)
                reemplazar_entrada(fh, arc, ruta_pkb, n_pkb)
                reemplazar_entrada(fh, arc, ruta_pkh, bytes(n_pkh))

        cerrar = getattr(arc, "close", None)
        if callable(cerrar):
            cerrar()

    log(f"-> {destino}  ({total} dialogos con regla)")
    log("")
    log("QUE MIRAR EN EL EMULADOR:")
    log("  1. La primera linea DEBE empezar por 'A'. Si empieza por otra cosa,")
    log("     el motor lee desde un offset desplazado y el caracter por el que")
    log("     empieza dice cuanto se ha comido.")
    log("  2. El ultimo caracter visible de cada linea da los caracteres que")
    log("     caben: A=1, B=11, C=21, D=31, E=41.")
    log("  3. Cuantas lineas dibuja la caja.")
    return total


# --------------------------------------------------------------------------
# Validacion
# --------------------------------------------------------------------------

def _has_kana(text):
    return any(
        "぀" <= c <= "ヿ" or "ｦ" <= c <= "ﾟ"
        for c in text
    )


def cmd_validate(args):
    log.section("VALIDAR")

    problems = []
    notes = []

    # 1. Los CSV de extraccion existen y no estan vacios.
    for tag, _src, lang, games in TARGETS:
        for game in games:
            for pack in PACK_NAMES:
                p = OUTPUT / LANG_DIR[lang] / f"{tag}_{game}_{pack}.csv"
                if not p.exists():
                    problems.append(f"falta {p.relative_to(ROOT)}")
                    continue
                rows = read_csv(p)
                if not rows:
                    problems.append(f"{p.relative_to(ROOT)} esta vacio")
                    continue

                empty = sum(1 for r in rows if not r["text"].strip())
                dupes = len(rows) - len({
                    (r["event_id"], r["string_id"]) for r in rows
                })
                bad = sum(1 for r in rows if "�" in r["text"])

                notes.append(
                    f"{p.relative_to(ROOT)}: {len(rows):6} textos | "
                    f"vacios {empty:5} | claves repetidas {dupes:5} | "
                    f"caracteres ilegibles {bad}"
                )
                if bad:
                    problems.append(
                        f"{p.relative_to(ROOT)}: {bad} textos con caracteres "
                        f"que no se pudieron descodificar"
                    )

                if lang == "es":
                    kana = sum(1 for r in rows if _has_kana(r["text"]))
                    notes.append(
                        f"{p.relative_to(ROOT)}: {kana} textos siguen en "
                        f"japones (sin traducir en la version europea)"
                    )

    # 2. Los dos juegos europeos traen los mismos textos espanoles.
    for game in ("spark", "ogre"):
        for pack in PACK_NAMES:
            a = OUTPUT / "spanish" / f"rayo_{game}_{pack}.csv"
            b = OUTPUT / "spanish" / f"ogro_{game}_{pack}.csv"
            if a.exists() and b.exists():
                ta = [r["text"] for r in read_csv(a)]
                tb = [r["text"] for r in read_csv(b)]
                same = "IDENTICOS" if ta == tb else "DISTINTOS"
                notes.append(f"es/{game}/{pack}: Rayo vs Ogro -> {same}")
                if ta != tb:
                    problems.append(
                        f"los textos espanoles de {game}/{pack} difieren entre "
                        f"las dos ROMs europeas"
                    )

    # 3. Los CSV alineados.
    for name, _game, _jp, _es in ALIGNMENTS:
        p = OUTPUT / "aligned" / f"{name}.csv"
        if not p.exists():
            problems.append(f"falta {p.relative_to(ROOT)}")
            continue
        rows = read_csv(p)
        by_status = {}
        for r in rows:
            by_status[r["status"]] = by_status.get(r["status"], 0) + 1
        both = sum(1 for r in rows if r["jp_text"] and r["es_text"])
        notes.append(
            f"{p.relative_to(ROOT)}: {len(rows):6} filas | con los dos idiomas "
            f"{both:6} | {by_status}"
        )
        # Una fila emparejada tiene las dos partes; que el texto de una de
        # ellas sea la cadena vacia es legitimo (hay huecos de texto vacios
        # en los propios SSD), asi que comprobamos los offsets, no el texto.
        wrong = sum(
            1 for r in rows
            if r["status"] != "unmatched"
            and not (r["jp_offset"] and r["es_offset"])
        )
        if wrong:
            problems.append(
                f"{p.relative_to(ROOT)}: {wrong} filas marcadas como emparejadas "
                f"pero a las que les falta un idioma"
            )

        half_empty = sum(
            1 for r in rows
            if r["status"] != "unmatched"
            and bool(r["jp_text"]) != bool(r["es_text"])
        )
        if half_empty:
            notes.append(
                f"{p.relative_to(ROOT)}: {half_empty} parejas en las que un "
                f"idioma tiene el hueco de texto vacio"
            )

    for n in notes:
        log(f"  {n}")

    print()
    if problems:
        log(f"VALIDACION: {len(problems)} problema(s)")
        for p in problems:
            log(f"  - {p}")
    else:
        log("VALIDACION: todo correcto")

    report = OUTPUT / "validation_report.txt"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(
        "\n".join(notes)
        + "\n\nPROBLEMAS\n"
        + ("\n".join(f"- {p}" for p in problems) if problems else "ninguno")
        + "\n",
        "utf-8",
    )
    log(f"Informe -> {report.relative_to(ROOT)}")

    return problems


# --------------------------------------------------------------------------
# info / run
# --------------------------------------------------------------------------

def cmd_info(args):
    source = Path(args.input)
    if not source.is_absolute():
        source = (ROOT / source).resolve()
    if not source.exists():
        die(f"No existe: {source}")

    kind = detect_kind(source)
    print(f"{source.name}")
    print(f"  formato:  {kind}")
    print(f"  tamano:   {source.stat().st_size:,} bytes")
    tid = title_id(source)
    if tid:
        print(f"  title id: {tid}")
    if kind == "ncsd":
        import struct
        with source.open("rb") as f:
            f.seek(0x120)
            off = struct.unpack("<I", f.read(4))[0] * 0x200
            f.seek(off + 0x150)
            print(f"  producto: {f.read(16).split(bytes(1))[0].decode('ascii','replace')}")
    elif kind == "ncch":
        print(f"  producto: {product_code(source)}")


def cmd_run(args):
    log.section("PIPELINE COMPLETO DE INAZUMA ELEVEN 3")

    for tag, src, lang, games in TARGETS:
        source = ROOT / src
        if not source.exists():
            die(
                f"No encuentro {src}. Coloca la ROM/CIA en su sitio o usa la "
                f"orden `extract` indicando la ruta a mano."
            )
        sub = argparse.Namespace(
            input=str(source), lang=lang, tag=tag, games=list(games),
            force=args.force, dump_events=args.dump_events,
            dstool=args.dstool, ctrtool=args.ctrtool,
        )
        cmd_extract(sub)

    cmd_align(args)
    cmd_sheet(args)
    problems = cmd_validate(args)

    log.section("TERMINADO")
    log(f"CSV japones  -> {(OUTPUT / 'japanese').relative_to(ROOT)}")
    log(f"CSV espanol  -> {(OUTPUT / 'spanish').relative_to(ROOT)}")
    log(f"CSV alineado -> {(OUTPUT / 'aligned').relative_to(ROOT)}")
    log(f"HOJA A TRADUCIR -> {(OUTPUT / 'traduccion').relative_to(ROOT)}")
    if problems:
        log(f"Con {len(problems)} aviso(s); mira output/validation_report.txt")


# --------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--3dstool", dest="dstool", help="ruta a 3dstool.exe")
    parser.add_argument("--ctrtool", dest="ctrtool", help="ruta a ctrtool.exe")
    parser.add_argument("--force", action="store_true",
                        help="rehace pasos ya hechos en vez de reutilizarlos")
    parser.add_argument("--dump-events", action="store_true",
                        help="ademas del CSV, guarda cada evento suelto en extracted/")

    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("run", help="proyecto entero: extraer los tres juegos y alinear")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("extract", help="procesa una ROM/CIA/RomFS")
    p.add_argument("input", help=".3ds / .trim.3ds / .cci / .cxi / .cia / carpeta RomFS")
    p.add_argument("--lang", required=True, choices=("jp", "es"))
    p.add_argument("--tag", help="nombre corto de esta version (jp, rayo, ogro...)")
    p.add_argument("--games", nargs="*", choices=tuple(GAMES),
                   help="que mitades extraer (por defecto, las que correspondan)")
    p.set_defaults(func=cmd_extract)

    p = sub.add_parser("align", help="cruza los CSV japoneses y espanoles")
    p.set_defaults(func=cmd_align)

    p = sub.add_parser(
        "sheet",
        help="hoja de traduccion: event_id, japones, es_final, estado",
    )
    p.set_defaults(func=cmd_sheet)

    p = sub.add_parser(
        "reinsert",
        help="mete el dialogo espanol de IE3 en archive.fa (evet, mismo tamano)",
    )
    p.add_argument("--entrada", help="archive.fa de partida (por defecto work/archive_es.fa)")
    p.add_argument("--salida", help="archive.fa de salida (por defecto work/archive_es.fa)")
    p.add_argument("--games", nargs="+", choices=tuple(TRANSLATION_DIR),
                   help="mitades a reinsertar; para una prueba Spark usar --games spark")
    p.add_argument("--crecer", action="store_true",
                   help="obsoleto e inseguro; se rechaza para no desplazar evet")
    p.set_defaults(func=cmd_reinsert)

    p = sub.add_parser("build", help="empaqueta archive.fa y el CRO IE3 verificado en una ROM")
    p.add_argument("--archive", required=True, help="archive.fa conservador ya validado")
    p.add_argument("--candidate-dir", required=True, help="directorio nuevo para manifiesto y overlay CRO")
    p.add_argument("--output", required=True, help="ROM .3ds nueva; se niega a sobrescribir")
    p.set_defaults(func=cmd_build)

    p = sub.add_parser(
        "diagnostico",
        help="mete reglas graduadas en el prologo para medir la caja",
    )
    p.add_argument("--entrada", help="archive.fa de partida")
    p.add_argument("--salida", help="archive.fa de salida")
    p.add_argument("--lineas", type=int, default=3)
    p.add_argument("--ancho", type=int, default=45)
    p.set_defaults(func=cmd_diagnostico)

    p = sub.add_parser("validate", help="revalida los CSV generados")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("info", help="identifica una ROM/CIA")
    p.add_argument("input")
    p.set_defaults(func=cmd_info)

    args = parser.parse_args()

    if not getattr(args, "command", None):
        parser.print_help()
        return 1

    try:
        args.func(args)
    except (RomError, B123Error, PackError, SSDError) as exc:
        die(str(exc))

    return 0


if __name__ == "__main__":
    sys.exit(main())
