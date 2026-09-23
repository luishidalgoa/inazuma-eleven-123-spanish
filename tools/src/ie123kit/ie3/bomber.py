"""Integracion reproducible de Fuego/Bomber como fuente logica IE3.

Bomber comparte el recurso fisico ``inazuma3/data_iz/script`` con Spark. Este
modulo compara fuentes oficiales europeas antes de crear el corpus Bomber, para
que una discrepancia no acabe como escritura silenciosa sobre el mismo slot.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

from ie123kit.nucleo.config.raiz import find_root

PACKS = ("eve", "evet")
IDENTITY_FIELDS = ("pack", "event_id", "instruction", "argument", "opcode", "string_id")


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_rows(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def identity(row: dict[str, str]) -> tuple[str, ...]:
    return tuple(row.get(field, "") for field in IDENTITY_FIELDS)


def compare_rows(rayo: list[dict[str, str]], fuego: list[dict[str, str]]) -> tuple[list[dict[str, str]], Counter]:
    rayo_by_id = {identity(row): row for row in rayo}
    fuego_by_id = {identity(row): row for row in fuego}
    rows: list[dict[str, str]] = []
    counts: Counter = Counter()
    for key in sorted(set(rayo_by_id) | set(fuego_by_id)):
        rayo_row = rayo_by_id.get(key)
        fuego_row = fuego_by_id.get(key)
        if rayo_row is None:
            classification = "SOLO_FUEGO"
        elif fuego_row is None:
            classification = "SOLO_RAYO"
        elif rayo_row["text"] == fuego_row["text"]:
            classification = "COMUN_IDENTICO"
        else:
            classification = "COMUN_DISTINTO"
        counts[classification] += 1
        rows.append(
            dict(
                zip(IDENTITY_FIELDS, key, strict=True),
                classification=classification,
                rayo_text="" if rayo_row is None else rayo_row["text"],
                fuego_text="" if fuego_row is None else fuego_row["text"],
            )
        )
    return rows, counts


def comparar(root: Path, salida: Path) -> dict:
    base = root / "work/ie3/shared/salida/spanish"
    salida.mkdir(parents=True, exist_ok=True)
    summary: dict[str, dict] = {}
    buckets = {"conflictos": [], "solo_fuego": [], "solo_rayo": [], "comunes": []}
    fields = [*IDENTITY_FIELDS, "classification", "rayo_text", "fuego_text"]
    for pack in PACKS:
        rayo = read_rows(base / f"rayo_spark_{pack}.csv")
        fuego = read_rows(base / f"fuego_spark_{pack}.csv")
        rows, counts = compare_rows(rayo, fuego)
        write_rows(salida / f"{pack}.csv", rows, fields)
        for row in rows:
            match row["classification"]:
                case "COMUN_DISTINTO":
                    buckets["conflictos"].append(row)
                case "SOLO_FUEGO":
                    buckets["solo_fuego"].append(row)
                case "SOLO_RAYO":
                    buckets["solo_rayo"].append(row)
                case "COMUN_IDENTICO":
                    buckets["comunes"].append(row)
        summary[pack] = {
            "rayo_rows": len(rayo),
            "fuego_rows": len(fuego),
            "common": counts["COMUN_IDENTICO"] + counts["COMUN_DISTINTO"],
            **{name: counts[name] for name in ("COMUN_IDENTICO", "COMUN_DISTINTO", "SOLO_FUEGO", "SOLO_RAYO")},
        }
    for name, rows in buckets.items():
        write_rows(salida / f"{name}.csv", rows, fields)
    keys = {key for data in summary.values() for key in data}
    summary["total"] = {key: sum(data.get(key, 0) for data in summary.values()) for key in sorted(keys)}
    (salida / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return summary


def crear_corpus(root: Path, informe: Path) -> dict:
    summary = json.loads((informe / "summary.json").read_text(encoding="utf-8"))
    total = summary["total"]
    if total.get("COMUN_DISTINTO", 0) or total.get("SOLO_FUEGO", 0) or total.get("SOLO_RAYO", 0):
        raise ValueError("Fuego y Rayo difieren; no se puede derivar corpus Bomber comun sin resolver conflictos")
    source = root / "translation/ie3/rayo_celeste/dialogo_oficial.csv"
    target = root / "translation/ie3/fuego_explosivo/dialogo_oficial.csv"
    target.parent.mkdir(parents=True, exist_ok=True)
    rows = read_rows(source)
    write_rows(target, rows, ["event_id", "japones", "es_final", "estado"])
    meta = {
        "source": str(source),
        "target": str(target),
        "derivation": "Rayo y Fuego oficiales son identicos por identidad estructural eve/evet",
        "comparison": str(informe / "summary.json"),
        "rows": len(rows),
        "classification": total,
    }
    (target.parent / "bomber_corpus.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    return meta


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("comparar")
    p.add_argument("--salida", type=Path, default=Path("work/informes/fuego_vs_rayo"))
    p = sub.add_parser("corpus")
    p.add_argument("--informe", type=Path, default=Path("work/informes/fuego_vs_rayo"))
    args = parser.parse_args(argv)
    root = find_root()
    if args.cmd == "comparar":
        result = comparar(root, root / args.salida)
    else:
        result = crear_corpus(root, root / args.informe)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
