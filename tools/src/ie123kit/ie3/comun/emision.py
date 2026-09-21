"""Reinserción IE3 por referencias verificadas; piloto explícito, no --crecer.

auditar: round-trip y planificación offline de todo un perfil.
piloto: aplica solo claves seleccionadas sobre una referencia, conserva el resto.
La activación general autorizada tras el piloto vive en ``ie3.fase3``.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from collections import Counter, defaultdict
from pathlib import Path

from ie123kit.ie3.comun.b123 import B123Archive
from ie123kit.ie3.comun.cobertura import huella, leer_corpus, sha
from ie123kit.ie3.comun.identidades import resolver_overrides_por_identidad
from ie123kit.ie3.comun.maqueta import maquetar_una_caja
from ie123kit.ie3.comun.paquetes import leer_paquete, reconstruir_paquete
from ie123kit.ie3.comun.perfiles import cargar_perfil
from ie123kit.ie3.comun.referencias import leer_referencias, reconstruir_evento
from ie123kit.ie3.comun.reinsert import MARCA_FURIGANA, _codificable
from ie123kit.ie3.comun.ssd import group_ruby, parse_flat_text
from ie123kit.ie3.comun.text import TextTable, clean_for_csv
from ie123kit.nucleo.config.raiz import find_root
from ie123kit.nucleo.texto.sjis_portador import es_encode


def guardar(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def cargar_pares(archive, prefix):
    pairs = {}
    for kind in ("eve", "evet"):
        h, b = archive.read(prefix + "/" + kind + ".pkh"), archive.read(prefix + "/" + kind + ".pkb")
        blocks, metadata = leer_paquete(h, b, kind)
        pairs[kind] = (h, b, blocks, metadata)
    return pairs


def resolver(japanese, eligible, aligned, official, reverse=None):
    """Primero identidad original; memoria solo si es unívoca y reextraída."""
    alternatives = {r["es_final"] for r in eligible}
    matched = []
    for row in aligned:
        if row["jp_text"] != japanese or not row["es_offset"]:
            continue
        if len(alternatives) > 1 and row["status"] not in ("exact", "structural"):
            continue
        es = row["es_text"]
        source = (int(row["event_id"]), int(row["es_offset"], 16))
        if es in alternatives and official.get(source) == es:
            matched.append((es, source, row))
    if len({es for es, _, _ in matched}) == 1:
        es, source, row = matched[0]
        return es, {
            "event": source[0],
            "offset": source[1],
            "string_id": row["string_id"],
            "method": "offset_identity_and_official_reextraction",
            "alignment_status": row["status"],
        }
    if len(alternatives) == 1:
        es = next(iter(alternatives))
        sources = reverse.get(es, []) if reverse is not None else [k for k, v in official.items() if v == es]
        if sources:
            return es, {
                "method": "unanimous_curated_memory_and_official_reextraction",
                "occurrences": len(sources),
                "event": sources[0][0],
                "offset": sources[0][1],
            }
    return None, None


def compilar(japanese, spanish, record_sizes):
    """Mantiene configuración aprobada. Sin truncar ni inventar páginas.

    Esta etapa solo emite mensajes sin sustituciones/control de argumentos ES.
    Ruby JP puede quedar como registros secundarios no usados (no se elimina).
    El relocator sí conserva controles arbitrarios en todos los no modificados.
    """
    reasons = []
    if "%" in MARCA_FURIGANA.sub("", japanese) or "%" in spanish:
        reasons.append("estructura_controles_argumentos_pendiente")
    unsupported = sorted({c for c in spanish if not _codificable(c)})
    if unsupported:
        reasons.append("caracter_no_soportado")
    formatted = maquetar_una_caja(spanish)
    if formatted is None:
        reasons.append("layout_paginacion")
    encoded = None if unsupported or formatted is None else es_encode(formatted, 1 << 30)
    needed = None if encoded is None else (len(encoded) + 8) & ~3
    if needed is not None and needed > 252:
        reasons.append("limite_real_registro_u8")
    if encoded is not None and len(encoded) + 1 > 512:
        reasons.append("limite_real_buffer_expandido")
    span = None if needed is None else max(record_sizes[0], needed) + sum(record_sizes[1:])
    if span is not None and span > 1024:
        reasons.append("limite_real_grupo_1024")
    return {
        "formatted": formatted,
        "encoded_hex": None if encoded is None else encoded.hex(),
        "bytes_needed_record": needed,
        "new_group_size": span,
        "blockers": reasons,
        "unsupported": unsupported,
    }


def auditar(root, profile, base, compiler=None, resolver_identidades=False):
    base_fingerprint = huella(base)
    if base_fingerprint["sha256"] != profile.base_sha256:
        raise ValueError("base JP distinta de la revisión del perfil")
    consumer = huella(root / "work/shared/base_3ds/romfs/cro/ina_main3ogre.cro")
    if consumer["sha256"] != profile.consumer_sha256:
        raise ValueError("consumidor JP distinto de la revisión auditada")
    corpus = leer_corpus(root / profile.corpus)
    alignment = defaultdict(list)
    with (root / profile.alineado).open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            if row["pack"] == "evet" and row["jp_offset"]:
                alignment[(int(row["event_id"]), int(row["jp_offset"], 16))].append(row)
    with B123Archive(base) as jp, B123Archive(root / profile.oficial) as es:
        pairs = cargar_pares(jp, profile.recurso)
        epairs = cargar_pares(es, "es/" + profile.recurso)
        table = TextTable.from_codetable(es.read("font/CodeTable.bin"))
        official = {
            (eid, r.offset): clean_for_csv(r.text)
            for eid, block in epairs["evet"][2].items()
            for r in parse_flat_text(block, table)
        }
        reverse = defaultdict(list)
        for key, value in official.items():
            reverse[value].append(key)
        input_hashes = {
            f"{lang}/{kind}.{suffix}": sha(pair[i])
            for lang, p in (("jp", pairs), ("es", epairs))
            for kind, pair in p.items()
            for i, suffix in enumerate(("pkh", "pkb"))
        }
    rows, exceptions, orphans = [], [], []
    stats = Counter()
    for event, block in pairs["evet"][2].items():
        for head, _ in group_ruby(parse_flat_text(block, TextTable.identity())):
            stats["legacy_groups_including_secondary_orphans"] += 1
            stats["legacy_official_available"] += any(
                r["estado"] in ("oficial", "memoria") and r["es_final"]
                for r in corpus.get((event, clean_for_csv(head.text)), [])
            )
    for lang, p in (("jp", pairs), ("es", epairs)):
        for kind, (h, b, blocks, _) in p.items():
            nh, nb, _ = reconstruir_paquete(h, b, kind, blocks)
            if (nh, nb) != (h, b):
                raise ValueError("round-trip PackNum no literal")
            stats[f"{lang}_pack_roundtrips"] += 1
        for event, ssd in p["eve"][2].items():
            evet = p["evet"][2].get(event)
            try:
                refs, inline, records, _, _ = leer_referencias(ssd, evet)
            except ValueError as exc:
                # Ausencia conocida en originales: catalogar cada instrucción,
                # nunca emitir ni considerar el evento estructuralmente válido.
                if evet is not None:
                    raise
                exceptions.append(
                    {
                        "language": lang,
                        "event": event,
                        "reason": str(exc),
                        "key": f"{profile.nombre}:eve:{event}",
                        "action": "resolver recurso ausente antes de emitir",
                    }
                )
                stats[f"{lang}_events_missing_evet"] += 1
                continue
            stats[f"{lang}_references_validated"] += len(refs)
            if evet is not None:
                ns, ne, _ = reconstruir_evento(ssd, evet, {})
                if (ns, ne) != (ssd, evet):
                    raise ValueError("round-trip evento no literal")
                stats[f"{lang}_event_roundtrips"] += 1
            for item in inline:
                exceptions.append(
                    {
                        "language": lang,
                        "event": event,
                        **item,
                        "key": f"{profile.nombre}:eve:{event}:{item['instruction']}",
                        "reason": "dialogo_inline_sin_plan_de_correspondencia",
                    }
                )
                stats[f"{lang}_inline_dialogues"] += 1
            if lang != "jp":
                continue
            covered = {i for ref in refs for i in ref.registros}
            for i, r in enumerate(records):
                if i not in covered:
                    orphans.append(
                        {
                            "key": f"{profile.nombre}:evet:{event}:{r.offset:08X}",
                            "sha256": sha(evet[r.offset : r.offset + r.size]),
                            "reason": "registro_sin_consumidor_301D_conservado",
                        }
                    )
            simulation = {}
            simulated_rows = []
            identities = {}
            if resolver_identidades and event in epairs["eve"][2] and event in epairs["evet"][2]:
                erefs = leer_referencias(epairs["eve"][2][event], epairs["evet"][2][event])[0]
                identities = resolver_overrides_por_identidad(event, refs, erefs)
            for ref in refs:
                head = records[ref.registros[0]]
                japanese = clean_for_csv(head.text)
                candidates = corpus.get((event, japanese), [])
                eligible = [r for r in candidates if r["estado"] in ("oficial", "memoria") and r["es_final"]]
                spanish, origin = resolver(japanese, eligible, alignment[(event, head.offset)], official, reverse)
                if spanish is None and eligible and (event, head.offset) in identities:
                    evidence = identities[event, head.offset]
                    source = evidence["source"]
                    candidate = official.get((source["event_id"], source["offset"]))
                    if candidate in {r["es_final"] for r in eligible}:
                        spanish = candidate
                        origin = {"event": source["event_id"], "offset": source["offset"],
                                  "method": "consumer_identity_and_official_reextraction", "evidence": evidence}
                        stats["corpus_collisions_resolved_by_consumer"] += 1
                sizes = [records[i].size for i in ref.registros]
                row = {
                    "key": f"{profile.nombre}:evet:{event}:{head.offset:08X}",
                    "version": profile.nombre,
                    "pack": "evet",
                    "event": event,
                    "instruction": ref.instruccion.ident,
                    "offset": head.offset,
                    "japanese": japanese,
                    "official_available": bool(eligible),
                    "official_verified": spanish is not None,
                    "span_original": ref.longitud,
                    "record_sizes": sizes,
                    "head_sha256": sha(head.raw),
                    "source": origin,
                    "span_sha256": sha(evet[ref.inicio : ref.inicio + ref.longitud]),
                    "csv_lines": [r["csv_line"] for r in eligible],
                }
                if spanish is None:
                    reason = (
                        "correspondencia_contradictoria_o_no_reextraida"
                        if eligible
                        else "correspondencia_ambigua"
                        if any(r["es_final"] for r in candidates)
                        else "correspondencia_ausente"
                    )
                    row.update(reason=reason, blockers=[reason])
                else:
                    compiled = (compilar(japanese, spanish, sizes) if compiler is None else
                                compiler(japanese, spanish, sizes, ref, ssd, records))
                    row.update(spanish=spanish, **compiled)
                    row["reason"] = row["blockers"][0] if row["blockers"] else "emitible_referencias"
                    if not row["blockers"]:
                        payload = bytes.fromhex(row["encoded_hex"])
                        simulation[ref.inicio] = payload
                        simulated_rows.append((ref.registros[0], payload))
                        row["offline_reextracted"] = True
                        row["needs_growth"] = row["bytes_needed_record"] > head.size
                stats["messages_referenced"] += 1
                stats["official_available"] += bool(eligible)
                stats["official_verified"] += spanish is not None
                stats[row["reason"]] += 1
                stats["offline_reextracted"] += bool(row.get("offline_reextracted"))
                stats["emitible_with_growth"] += bool(row.get("needs_growth"))
                rows.append(row)
            if simulation:
                ns, ne, _ = reconstruir_evento(ssd, evet, simulation)
                rafter = leer_referencias(ns, ne)[2]
                if any(rafter[index].raw != payload for index, payload in simulated_rows):
                    raise ValueError("reextracción de simulación fallida")
                stats["jp_events_simulated"] += 1
        # Entradas evet sin evento eve tampoco desaparecen del inventario.
        if lang == "jp":
            for eid, block in p["evet"][2].items():
                if eid not in p["eve"][2]:
                    for r in parse_flat_text(block, TextTable.identity()):
                        orphans.append(
                            {
                                "key": f"{profile.nombre}:evet:{eid}:{r.offset:08X}",
                                "reason": "evento_sin_eve_conservado",
                                "sha256": sha(block[r.offset : r.offset + r.size]),
                            }
                        )
    stats["unreferenced_records"] = len(orphans)
    stats["inserted_this_run"] = 0
    stats["runtime_tested_this_run"] = 0
    stats["coverage_plan_percent"] = round(100 * stats["emitible_referencias"] / max(1, stats["official_available"]), 4)
    stats["coverage_plan_over_legacy_denominator_percent"] = round(
        100 * stats["emitible_referencias"] / max(1, stats["legacy_official_available"]), 4
    )
    manifest = {
        "schema": 1,
        "profile": profile.datos(),
        "base": base_fingerprint,
        "consumer": consumer,
        "official": huella(root / profile.oficial),
        "corpus": huella(root / profile.corpus),
        "alignment": huella(root / profile.alineado),
        "pack_hashes": input_hashes,
        "denominator": "all JP 301D @ consumers; inline and missing resources in exceptions, orphan records separately, no silent exclusions",
        "code": {
            p.name: huella(p)
            for p in [
                *sorted(Path(__file__).parent.glob("*.py")),
                *sorted(Path(__file__).parent.parent.glob("fase*.py")),
                root / "tools/src/ie123kit/nucleo/texto/sjis_portador.py",
            ]
        },
        "runtime_verified": False,
        "stage": "A offline; no corpus-wide activation",
    }
    return manifest, rows, dict(stats), exceptions, orphans


def piloto(root, profile, plan_dir, reference, keys, output):
    """Selección explícita + manifiesto fijado; no permite activar todo el corpus."""
    manifest = json.loads((plan_dir / "manifest.json").read_text(encoding="utf-8"))
    rows = json.loads((plan_dir / "messages.json").read_text(encoding="utf-8"))
    if sha(json.dumps(rows, ensure_ascii=False, indent=2).encode("utf-8")) != manifest["messages_sha256"]:
        raise ValueError("filas del plan modificadas tras auditoría")
    if manifest["profile"] != profile.datos():
        raise ValueError("perfil del plan no coincide")
    for item in [
        manifest["base"],
        manifest["consumer"],
        manifest["official"],
        manifest["corpus"],
        manifest["alignment"],
        *manifest["code"].values(),
    ]:
        if huella(Path(item["path"]))["sha256"] != item["sha256"]:
            raise ValueError(f"entrada/código cambió desde auditoría: {item['path']}")
    selected = {r["key"]: r for r in rows if r["key"] in keys}
    if len(selected) != len(set(keys)) or not 1 <= len(selected) <= 5:
        raise ValueError("piloto requiere entre 1 y 5 claves conocidas explícitas")
    if any(r["reason"] != "emitible_referencias" for r in selected.values()):
        raise ValueError("selección contiene pendientes: no se omiten silenciosamente")
    grouped = defaultdict(list)
    for r in selected.values():
        grouped[r["event"]].append(r)
    refhash = huella(reference)
    replacements = {"eve": {}, "evet": {}}
    traces = {}
    with B123Archive(reference) as arc:
        pairs = cargar_pares(arc, profile.recurso)
        for event, selection in grouped.items():
            s, e = pairs["eve"][2][event], pairs["evet"][2][event]
            refs, _, records, _, _ = leer_referencias(s, e)
            by_ins = {ref.instruccion.ident: ref for ref in refs}
            changes = {}
            for row in selection:
                ref = by_ins[row["instruction"]]
                record = records[ref.registros[0]]
                body = bytes.fromhex(row["encoded_hex"])
                if sha(record.raw) != row["head_sha256"]:
                    raise ValueError("conflicto con referencia actual: mensaje ya modificado; no sobrescribir")
                changes[ref.inicio] = body
            ns, ne, trace = reconstruir_evento(s, e, changes)
            replacements["eve"][event] = ns
            replacements["evet"][event] = ne
            traces[event] = trace
        resources = {}
        for kind, changes in replacements.items():
            h, b, _, _ = pairs[kind]
            nh, nb, _report = reconstruir_paquete(h, b, kind, changes)
            resources[profile.recurso + "/" + kind + ".pkh"] = nh
            resources[profile.recurso + "/" + kind + ".pkb"] = nb
        before = {entry.path.decode(): sha(arc.read(entry)) for entry in arc.entries}
    output.mkdir(parents=True, exist_ok=False)
    target = output / "archive.fa"
    shutil.copyfile(reference, target)
    # Utiliza el escritor B123 existente; no hay otro repacker.
    from ie123kit.nucleo.contenedores.fa import FaArchive, reemplazar_entrada

    archive = FaArchive(str(target))
    with target.open("r+b") as f:
        for path, data in resources.items():
            reemplazar_entrada(f, archive, path, data)
    del archive
    with B123Archive(target) as arc:
        after = {entry.path.decode(): sha(arc.read(entry)) for entry in arc.entries}
        if set(after) != set(before):
            raise ValueError("inventario B123 cambió")
        changed = [p for p in before if before[p] != after[p]]
        if set(changed) - set(resources):
            raise ValueError("recursos ajenos modificados")
        for path, payload in resources.items():
            if arc.read(path) != payload:
                raise ValueError("reextracción B123 difiere")
    result = {
        "label": f"{profile.nombre.title()} Fase 2 — piloto de referencias — pendiente de validación visual",
        "runtime_verified": False,
        "reference": refhash,
        "plan": huella(plan_dir / "manifest.json"),
        "archive": huella(target),
        "selected": list(selected.values()),
        "traces": traces,
        "changed_resources": changed,
        "resources_before": before,
        "resources_after": after,
        "inserted_this_run": len(selected),
        "reextracted_this_run": len(selected),
        "runtime_tested_this_run": 0,
        "warning": "no activación masiva; recursos Spark compartidos con Bomber, que no queda validado",
    }
    guardar(output / "pilot.json", result)
    return result


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=("auditar", "piloto"))
    p.add_argument("--perfil", required=True)
    p.add_argument("--perfil-json", type=Path)
    p.add_argument("--base", type=Path)
    p.add_argument("--salida", type=Path, required=True)
    p.add_argument("--plan", type=Path)
    p.add_argument("--referencia", type=Path)
    p.add_argument("--clave", action="append", default=[])
    a = p.parse_args(argv)
    root = find_root()
    profile = cargar_perfil(a.perfil, a.perfil_json)
    if a.salida.exists():
        p.error("salida existente; conservar y utilizar otra carpeta")
    if a.action == "auditar":
        result = auditar(root, profile, a.base or root / "work/shared/base_3ds/romfs/archive.fa")
        result[0]["messages_sha256"] = sha(json.dumps(result[1], ensure_ascii=False, indent=2).encode("utf-8"))
        a.salida.mkdir(parents=True)
        for name, data in zip(("manifest", "messages", "summary", "exceptions", "unreferenced"), result):
            guardar(a.salida / (name + ".json"), data)
        print(json.dumps(result[2], ensure_ascii=False, indent=2))
    else:
        if a.plan is None or a.referencia is None:
            p.error("piloto requiere --plan, --referencia y --clave")
        r = piloto(root, profile, a.plan, a.referencia, a.clave, a.salida)
        print(
            json.dumps(
                {k: r[k] for k in ("label", "archive", "inserted_this_run", "changed_resources")},
                ensure_ascii=False,
                indent=2,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
