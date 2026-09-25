"""Comparacion controlada de las fuentes oficiales Spark/Bomber.

Parte de los CSV ya extraidos por :mod:`ie123kit.ie3.pipeline`; no interpreta
binarios ni reimplementa formatos.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from ie123kit.ie3.comun import sheet as sheetlib
from ie123kit.nucleo.config.raiz import find_root

ROOT = find_root()
SALIDA = ROOT / "work" / "ie3" / "shared" / "salida"
INFORME = ROOT / "work" / "informes" / "fuego_vs_rayo"
CORPUS_FUEGO = ROOT / "translation" / "ie3" / "fuego_explosivo" / "dialogo_oficial.csv"
PACKS = ("eve", "evet")


@dataclass(frozen=True)
class FuenteRom:
    ruta: str
    formato: str
    title_id: str
    product_code: str
    sha256: str
    size: int


IDENTITY_FIELDS = ("pack", "event_id", "instruction", "argument", "opcode", "string_id")
COMPARE_HEADER = [
    "classification",
    *IDENTITY_FIELDS,
    "rayo_text",
    "fuego_text",
]
THREE_WAY_HEADER = [
    "jp_identity",
    "jp_text",
    "rayo_text",
    "fuego_text",
    "classification",
    "selected_translation",
    "selection_reason",
]


def leer_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def escribir_csv(path: Path, header: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=header, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def identidad(row: dict[str, str]) -> tuple[str, ...]:
    return tuple(row.get(field, "") for field in IDENTITY_FIELDS)


def identidad_texto(key: tuple[str, ...]) -> str:
    return ":".join(key)


def cargar(version: str, pack: str, lang: str = "spanish") -> dict[tuple[str, ...], dict[str, str]]:
    path = SALIDA / lang / f"{version}_spark_{pack}.csv"
    rows = {}
    for row in leer_csv(path):
        key = identidad(row)
        if key not in rows or not rows[key].get("text"):
            rows[key] = row
    return rows


def clasificar_par(rayo: dict[str, str] | None, fuego: dict[str, str] | None) -> tuple[str, str, str]:
    if rayo and fuego:
        if rayo.get("text", "") == fuego.get("text", ""):
            return "COMUN_IDENTICO", rayo.get("text", ""), fuego.get("text", "")
        return "COMUN_DISTINTO", rayo.get("text", ""), fuego.get("text", "")
    if fuego:
        return "SOLO_FUEGO", "", fuego.get("text", "")
    if rayo:
        return "SOLO_RAYO", rayo.get("text", ""), ""
    return "AMBIGUO", "", ""


def comparar_rayo_fuego() -> tuple[list[dict[str, str]], dict[str, dict[str, int]]]:
    rows: list[dict[str, str]] = []
    stats: dict[str, dict[str, int]] = {}
    for pack in PACKS:
        rayo = cargar("rayo", pack)
        fuego = cargar("fuego", pack)
        counts: Counter[str] = Counter()
        for key in sorted(set(rayo) | set(fuego)):
            classification, rayo_text, fuego_text = clasificar_par(rayo.get(key), fuego.get(key))
            counts[classification] += 1
            row = dict(zip(IDENTITY_FIELDS, key, strict=True))
            row.update(
                classification=classification,
                rayo_text=rayo_text,
                fuego_text=fuego_text,
            )
            rows.append(row)
        stats[pack] = dict(counts)
    total: Counter[str] = Counter()
    for pack_stats in stats.values():
        total.update(pack_stats)
    stats["total"] = dict(total)
    return rows, stats


def vista_tres_vias(comparacion: list[dict[str, str]]) -> list[dict[str, str]]:
    jp_rows = {}
    for pack in PACKS:
        jp_rows.update(cargar("jp", pack, "japanese"))
    out: list[dict[str, str]] = []
    for row in comparacion:
        key = tuple(row[field] for field in IDENTITY_FIELDS)
        jp = jp_rows.get(key, {})
        classification = row["classification"]
        rayo_text = row["rayo_text"]
        fuego_text = row["fuego_text"]
        if classification == "COMUN_IDENTICO":
            selected, reason = rayo_text, "Rayo y Fuego coinciden"
        elif classification == "SOLO_FUEGO":
            selected, reason = fuego_text, "Solo Fuego aporta texto oficial para esta identidad"
        elif classification == "SOLO_RAYO":
            selected, reason = rayo_text, "Solo Rayo aporta texto oficial para esta identidad"
        elif classification == "COMUN_DISTINTO":
            selected, reason = "", "Conflicto oficial: no se selecciona automaticamente"
        else:
            selected, reason = "", "Sin correspondencia segura"
        out.append(
            {
                "jp_identity": identidad_texto(key),
                "jp_text": jp.get("text", ""),
                "rayo_text": rayo_text,
                "fuego_text": fuego_text,
                "classification": classification,
                "selected_translation": selected,
                "selection_reason": reason,
            }
        )
    return out


def generar_corpus_fuego() -> dict[str, object]:
    """Construye el corpus oficial Bomber desde el alineado JP<->Fuego."""
    rows = leer_csv(SALIDA / "aligned" / "spark_fuego.csv")
    sheet_rows, technical, glossary, stats = sheetlib.build(rows, "bomber")
    CORPUS_FUEGO.parent.mkdir(parents=True, exist_ok=True)
    escribir_csv(
        CORPUS_FUEGO,
        ["event_id", "japones", "es_final", "estado"],
        [
            {
                "event_id": row[0],
                "japones": row[1],
                "es_final": row[2],
                "estado": row[3],
            }
            for row in sheet_rows
        ],
    )
    destino = SALIDA / "traduccion"
    escribir_csv(destino / "spark_fuego.csv", sheetlib.SHEET_HEADER, [
        dict(zip(sheetlib.SHEET_HEADER, row, strict=True)) for row in sheet_rows
    ])
    escribir_csv(destino / "spark_fuego_glosario.csv", sheetlib.GLOSSARY_HEADER, [
        dict(zip(sheetlib.GLOSSARY_HEADER, row, strict=True)) for row in glossary
    ])
    escribir_csv(destino / "descartado" / "spark_fuego_tecnico.csv", sheetlib.TECHNICAL_HEADER, [
        dict(zip(sheetlib.TECHNICAL_HEADER, row, strict=True)) for row in technical
    ])
    return {"path": str(CORPUS_FUEGO.relative_to(ROOT)), "rows": len(sheet_rows), "stats": stats}


def generar_informe(fuente: FuenteRom | None = None, destino: Path = INFORME) -> dict[str, object]:
    comparacion, stats = comparar_rayo_fuego()
    corpus = generar_corpus_fuego()
    destino.mkdir(parents=True, exist_ok=True)

    por_clase: dict[str, list[dict[str, str]]] = {
        "COMUN_IDENTICO": [],
        "COMUN_DISTINTO": [],
        "SOLO_FUEGO": [],
        "SOLO_RAYO": [],
        "AMBIGUO": [],
    }
    for row in comparacion:
        por_clase.setdefault(row["classification"], []).append(row)

    for pack in PACKS:
        escribir_csv(destino / f"{pack}.csv", COMPARE_HEADER, [r for r in comparacion if r["pack"] == pack])
    escribir_csv(destino / "conflictos.csv", COMPARE_HEADER, por_clase["COMUN_DISTINTO"])
    escribir_csv(destino / "solo_fuego.csv", COMPARE_HEADER, por_clase["SOLO_FUEGO"])
    escribir_csv(destino / "solo_rayo.csv", COMPARE_HEADER, por_clase["SOLO_RAYO"])
    escribir_csv(destino / "comunes.csv", COMPARE_HEADER, por_clase["COMUN_IDENTICO"])
    escribir_csv(destino / "tres_vias_jp_rayo_fuego.csv", THREE_WAY_HEADER, vista_tres_vias(comparacion))

    summary = {
        "source_rom": fuente.__dict__ if fuente else None,
        "identity_fields": IDENTITY_FIELDS,
        "stats": stats,
        "bomber_corpus": corpus,
        "fail_closed": {
            "conflicts": stats["total"].get("COMUN_DISTINTO", 0),
            "policy": "no seleccionar traduccion automaticamente para identidades con Rayo y Fuego distintos",
        },
    }
    (destino / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", required=True)
    parser.add_argument("--formato", default="cia")
    parser.add_argument("--title-id", required=True)
    parser.add_argument("--product-code", required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--size", required=True, type=int)
    parser.add_argument("--salida", type=Path, default=INFORME)
    args = parser.parse_args(argv)
    fuente = FuenteRom(args.rom, args.formato, args.title_id, args.product_code, args.sha256, args.size)
    print(json.dumps(generar_informe(fuente, args.salida), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
