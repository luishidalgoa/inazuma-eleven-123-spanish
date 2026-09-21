"""Diagnóstico trazable IE3 con el layout vigente, sin modificar recursos.

Amplía el informe histórico de rechazos: no oculta ausencia/ambigüedad de
correspondencia, errores de encoding ni la diferencia entre previsión e inserción.
El denominador legado group_ruby queda explícito, no se confunde con el consumidor.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

from ie123kit.ie3.comun.b123 import B123Archive
from ie123kit.ie3.comun.maqueta import LINEAS, MAX_CAR, MAX_TINTA, maquetar_una_caja
from ie123kit.ie3.comun.perfiles import cargar_perfil
from ie123kit.ie3.comun.reinsert import (
    MARCA_FURIGANA,
    MAX_REGISTRO,
    MIN_REGISTRO,
    _codificable,
    _reparto,
)
from ie123kit.ie3.comun.ssd import group_ruby, parse_flat_text
from ie123kit.ie3.comun.text import TextTable
from ie123kit.nucleo.config.raiz import find_root
from ie123kit.nucleo.eventos import packnum
from ie123kit.nucleo.texto.sjis_portador import es_encode


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def huella(path: Path) -> dict:
    with path.open("rb") as handle:
        digest = hashlib.file_digest(handle, "sha256").hexdigest()
    return {"path": str(path.resolve()), "size": path.stat().st_size, "sha256": digest}


def leer_corpus(path: Path):
    """No sobreescribir silenciosamente traducciones contradictorias."""
    result = defaultdict(list)
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for number, row in enumerate(csv.DictReader(handle), 2):
            row = {**row, "csv_line": number}
            result[(int(row["event_id"]), row["japones"])].append(row)
    return dict(result)


def decidir(line, readings, rows):
    eligible = [r for r in rows if r["es_final"] and r["estado"] in ("oficial", "memoria")]
    alternatives = sorted({r["es_final"] for r in eligible})
    total = line.size + sum(r.size for r in readings)
    result = {
        "official_available": bool(eligible),
        "correspondence_states": sorted({r["estado"] for r in rows}),
        "csv_lines": [r["csv_line"] for r in eligible],
        "alternatives": alternatives,
        "bytes_available_group": total,
        "bytes_available_dialogue": min(MAX_REGISTRO, total - MIN_REGISTRO * len(readings)),
        "record_sizes": [line.size, *[r.size for r in readings]],
        "record_offsets": [line.offset, *[r.offset for r in readings]],
        "bytes_needed": None,
        "formatted": None,
    }
    if not eligible:
        result["reason"] = "correspondencia_ambigua" if any(r["es_final"] for r in rows) else "correspondencia_ausente"
        return result
    if len(alternatives) != 1:
        result["reason"] = "correspondencia_contradictoria"
        return result
    spanish = alternatives[0]
    cleaned = MARCA_FURIGANA.sub("", spanish)
    formatted = maquetar_una_caja(cleaned)
    unsupported = sorted({ch for ch in cleaned if not _codificable(ch)})
    result.update(
        spanish=spanish,
        formatted=formatted,
        unsupported=unsupported,
        explicit_pages=spanish.count("\\f") + spanish.count("\f"),
    )
    # Diagnostic independent dimensions: all causes are recorded, even if the
    # legacy reinserter returns early on a layout failure.
    encoded = es_encode(formatted if formatted is not None else cleaned, 1 << 30)
    needed = (len(encoded) + 8) & ~3
    result["bytes_needed"] = needed
    result["byte_excess"] = max(0, needed - result["bytes_available_dialogue"])
    result["blockers"] = []
    if formatted is None:
        result["blockers"].append("layout_paginacion")
    if unsupported:
        result["blockers"].append("caracter_no_soportado")
    if needed > MAX_REGISTRO:
        result["blockers"].append("limite_registro_u8")
    if _reparto(total, len(readings), needed) is None:
        result["blockers"].append("presupuesto_binario_heredado")
    result["reason"] = result["blockers"][0] if result["blockers"] else "insertable_conservador"
    return result


def diagnosticar(base: Path, perfil, root: Path, referencia: Path | None = None):
    corpus_path = root / perfil.corpus
    corpus = leer_corpus(corpus_path)
    origins = defaultdict(list)
    with (root / perfil.alineado).open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["pack"] == "evet" and row["jp_offset"]:
                origins[(int(row["event_id"]), int(row["jp_offset"], 16))].append(row)
    rows, stats = [], Counter()
    with B123Archive(base) as archive:
        prefix = perfil.recurso + "/evet"
        header, payload = archive.read(prefix + ".pkh"), archive.read(prefix + ".pkb")
        for event, offset, size in packnum.parse_index(header):
            if event == 0xFFFFFFFF:
                continue
            block = packnum.entry_data(payload, offset, size)
            for group, (line, readings) in enumerate(group_ruby(parse_flat_text(block, TextTable.identity()))):
                text = line.text.replace("\n", "\\n")
                row = decidir(line, readings, corpus.get((event, text), []))
                row.update(
                    key=f"{perfil.nombre}:evet:{event}:{line.offset:08X}",
                    version=perfil.nombre,
                    pack="evet",
                    event_id=event,
                    group_legacy=group,
                    record_offset=line.offset,
                    japanese=text,
                    original_group_sha256=sha(block[line.offset : line.offset + row["bytes_available_group"]]),
                    alignment=origins.get((event, line.offset), []),
                )
                stats["original_groups_legacy"] += 1
                stats["official_available"] += int(row["official_available"])
                stats[row["reason"]] += 1
                rows.append(row)
    manifest = {
        "schema": 1,
        "profile": perfil.datos(),
        "base": huella(base),
        "corpus": huella(corpus_path),
        "alignment": huella(root / perfil.alineado),
        "official": huella(root / perfil.oficial),
        "denominator": "all group_ruby heads; explicit legacy denominator, not yet consumer spans",
        "layout": {"max_characters": MAX_CAR, "max_ink": MAX_TINTA, "lines": LINEAS},
        "code": {
            str(p.relative_to(root)): huella(p)
            for p in (
                root / "tools/src/ie123kit/ie3/comun/reinsert.py",
                root / "tools/src/ie123kit/ie3/comun/maqueta.py",
                root / "tools/src/ie123kit/ie3/comun/tipografia.py",
                root / "tools/src/ie123kit/ie3/comun/ancho_ventana.py",
                root / "tools/src/ie123kit/nucleo/texto/sjis_portador.py",
            )
        },
        "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
        "git_branch": subprocess.check_output(["git", "branch", "--show-current"], cwd=root, text=True).strip(),
        "git_status": subprocess.check_output(["git", "status", "--short"], cwd=root, text=True),
    }
    if referencia:
        ref = json.loads(referencia.read_text(encoding="utf-8"))
        rom, archive_path = huella(Path(ref["rom"]["path"])), Path(ref["archive"]["source"])
        archive_hash = huella(archive_path)
        if rom["sha256"] != ref["rom"]["sha256"] or archive_hash["sha256"] != ref["archive"]["sha256"]:
            raise ValueError("la referencia visual no coincide con su manifiesto")
        with B123Archive(archive_path) as arc:
            fonts = {e.path.decode(): sha(arc.read(e)) for e in arc.entries if e.path.startswith(b"font/")}
        manifest["visual_reference"] = {
            "manifest": huella(referencia),
            "rom": rom,
            "archive": archive_hash,
            "fonts": fonts,
            "cro": ref["cro"],
            "acceptance": "usuario acepta legibilidad de casos probados; no QA global",
        }
    summary = dict(stats)
    summary["coverage_available_percent"] = round(
        100 * stats["insertable_conservador"] / max(1, stats["official_available"]), 4
    )
    summary["inserted_this_run"] = 0
    summary["runtime_tested_this_run"] = 0
    summary["note"] = "diagnóstico; no implica inserción ni validación dinámica"
    return manifest, rows, summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--perfil", required=True)
    parser.add_argument("--perfil-json", type=Path)
    parser.add_argument("--base", type=Path)
    parser.add_argument("--referencia", type=Path)
    parser.add_argument("--salida", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.salida.exists():
        parser.error("salida existente: preservar el manifiesto y usar otra carpeta")
    root = find_root()
    profile = cargar_perfil(args.perfil, args.perfil_json)
    manifest, rows, summary = diagnosticar(
        args.base or root / "work/shared/base_3ds/romfs/archive.fa", profile, root, args.referencia
    )
    args.salida.mkdir(parents=True)
    for name, data in (("manifest.json", manifest), ("messages.json", rows), ("summary.json", summary)):
        (args.salida / name).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
