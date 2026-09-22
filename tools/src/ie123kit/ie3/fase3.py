"""Emisión general Spark/Ogre desde originales y transición heredada declarada.

El núcleo de crecimiento sigue siendo reconstruir_evento de la fase 2.
Nunca usa paquetes transformados como si fueran originales ni --crecer.
"""

from __future__ import annotations

import argparse
import json
import shutil
from collections import Counter, defaultdict
from functools import partial
from pathlib import Path

from ie123kit.ie3.comun.b123 import B123Archive
from ie123kit.ie3.comun.cobertura import huella, sha
from ie123kit.ie3.comun.controles import compilar_contexto, cota_pool
from ie123kit.ie3.comun.emision import auditar, cargar_pares, guardar
from ie123kit.ie3.comun.items import construir_items
from ie123kit.ie3.comun.paquetes import leer_paquete, reconstruir_paquete
from ie123kit.ie3.comun.perfiles import cargar_perfil
from ie123kit.ie3.comun.presentacion_nombres import recursos_nombres
from ie123kit.ie3.comun.referencias import REFERENCIA, leer_referencias, reconstruir_evento, sustituir_tabla
from ie123kit.ie3.comun.ssd import parse_ssd
from ie123kit.ie3.comun.text import TextTable
from ie123kit.ie3.comun.texto_visible import PerfilTextoVisible, construir_payloads_texto_visible
from ie123kit.nucleo.config.raiz import find_root


def fusionar_textos_ssd(original, inherited, rebuilt, visible=None):
    """Fusiona por owner/slot sin tocar código, referencias ni debug original.

    Las fuentes de cada capa deben compartir bytecode, no solo cardinalidad.
    El SSD reconstruido aporta las nuevas @; el resto conserva el estado
    heredado salvo un campo visible explícitamente distinto del original.
    """
    layers = [original, inherited, rebuilt] + ([] if visible is None else [visible])
    parsed = [parse_ssd(data, TextTable.identity()) for data in layers]
    end = 32 + parsed[0][0]["code_len"]
    if any(data[32:end] != original[32:end] or info["code_len"] != end - 32
           for data, (info, _) in zip(layers, parsed)):
        raise ValueError("transición SSD con bytecode diferente")
    owners = [[r.key for r in records] for _, records in parsed]
    if any(keys != owners[0] for keys in owners):
        raise ValueError("transición SSD con propietarios diferentes")
    changes = {}
    for i, source in enumerate(parsed[0][1]):
        if REFERENCIA.fullmatch(source.raw) or source.opcode == 0x3070:
            continue
        body = parsed[1][1][i].raw
        if visible is not None and parsed[3][1][i].raw != source.raw:
            body = parsed[3][1][i].raw
        if body != parsed[2][1][i].raw:
            changes[i] = body
    return sustituir_tabla(rebuilt, changes)


def emitir_perfil(profile, original_arc, reference_arc, rows, visible_resources):
    """Emisión pura: prueba original→heredado→nuevo por instrucción y hash JP."""
    original = cargar_pares(original_arc, profile.recurso)
    inherited = cargar_pares(reference_arc, profile.recurso)
    visible = {}
    if profile.recurso + "/eve.pkh" in visible_resources:
        visible, _ = leer_paquete(visible_resources[profile.recurso + "/eve.pkh"],
                                 visible_resources[profile.recurso + "/eve.pkb"], "eve")
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["event"]].append(row)
    replacements = {"eve": {}, "evet": {}}
    stats, transitions, event_checks = Counter(), [], []
    for event, ssd in original["eve"][2].items():
        legacy_ssd = inherited["eve"][2][event]
        evet = original["evet"][2].get(event)
        if evet is None:
            # Ausencia original conocida: no fabricar el recurso ni interpretar @.
            replacements["eve"][event] = fusionar_textos_ssd(ssd, legacy_ssd, ssd, visible.get(event))
            continue
        refs, _, records, _, _ = leer_referencias(ssd, evet)
        legacy_evet = inherited["evet"][2][event]
        oldrefs, _, oldrecords, _, _ = leer_referencias(legacy_ssd, legacy_evet)
        if [r.instruccion for r in refs] != [r.instruccion for r in oldrefs]:
            raise ValueError(f"{event}: consumidores heredados diferentes")
        if len(records) != len(oldrecords):
            raise ValueError(f"{event}: número de registros heredados diferente")
        by_ins = {r.instruccion.ident: r for r in refs}
        old_by_ins = {r.instruccion.ident: r for r in oldrefs}
        changes = {}
        for row in grouped[event]:
            ref = by_ins[row["instruction"]]
            oldref = old_by_ins[row["instruction"]]
            head = records[ref.registros[0]]
            legacy = oldrecords[oldref.registros[0]]
            if ref.registros != oldref.registros or head.offset != row["offset"]:
                raise ValueError("identidad original/heredada cambió")
            if sha(head.raw) != row["head_sha256"] or sha(evet[ref.inicio:ref.inicio + ref.longitud]) != row["span_sha256"]:
                raise ValueError("hash JP original no coincide: no sobrescribir")
            supported = not row["blockers"]
            body = bytes.fromhex(row["encoded_hex"]) if supported else legacy.raw
            if ref.inicio in changes and changes[ref.inicio] != body:
                raise ValueError("consumidor compartido con traducciones contradictorias")
            changes[ref.inicio] = body
            if not supported:
                state = "pending_inherited_preserved" if legacy.raw != head.raw else "pending_japanese_intact"
            elif body == head.raw:
                state = "original_already_official"
            elif body == legacy.raw:
                state = "inherited_official_retained"
            elif legacy.raw == head.raw:
                state = "new_official_inserted"
            else:
                state = "inherited_translation_corrected"
            stats[state] += 1
            stats["official_reextracted"] += supported
            transitions.append({"key": row["key"], "instruction": row["instruction"], "state": state,
                                "original_sha256": sha(head.raw), "inherited_sha256": sha(legacy.raw),
                                "output_sha256": sha(body), "source": row["source"],
                                "blockers": row["blockers"],
                                **({"inherited_hex": legacy.raw.hex(), "new_hex": body.hex(),
                                    "official": row["spanish"]} if state == "inherited_translation_corrected" else {})})
        ns, ne, trace = reconstruir_evento(ssd, evet, changes)
        ns = fusionar_textos_ssd(ssd, legacy_ssd, ns, visible.get(event))
        nrefs, _, nrecords, _, _ = leer_referencias(ns, ne)
        # Independiente del mapa del escritor: orden de consumidores, bytes de
        # todos los registros y secundarios según las posiciones reextraídas.
        heads = {ref.registros[0] for ref in refs}
        for index, (before, after) in enumerate(zip(records, nrecords)):
            if index in heads:
                if after.raw != changes.get(before.offset, before.raw):
                    raise ValueError("reextracción de principal diferente de la transición")
            elif ne[after.offset:after.offset + after.size] != evet[before.offset:before.offset + before.size]:
                raise ValueError("registro secundario/huérfano alterado")
        if [(r.instruccion.ident, r.registros) for r in refs] != [(r.instruccion.ident, r.registros) for r in nrefs]:
            raise ValueError("orden de registros consumidores modificado")
        event_checks.append({"event": event, "records": len(records), "references": len(refs),
                             "references_updated": trace["references_changed"], "secondary_literal": True,
                             "bytecode_unchanged": True, "reextracted": True})
        replacements["eve"][event], replacements["evet"][event] = ns, ne
    resources, pack_reports = {}, {}
    for kind, blocks in replacements.items():
        h, b, _, _ = original[kind]
        nh, nb, report = reconstruir_paquete(h, b, kind, blocks)
        resources[profile.recurso + "/" + kind + ".pkh"] = nh
        resources[profile.recurso + "/" + kind + ".pkb"] = nb
        pack_reports[kind] = report
    return resources, {"summary": dict(stats), "transitions": transitions,
                       "events": event_checks, "packs": pack_reports}


def preparar(root, reference, approval_path, output, profiles=None, profile_files=None):
    if output.exists():
        raise ValueError("salida existente: no sobrescribir")
    approval = json.loads(approval_path.read_text(encoding="utf-8"))
    if approval.get("confirmed_by") != "user" or approval.get("general_qa") is not False:
        raise ValueError("aprobación acotada del usuario requerida")
    if huella(reference)["sha256"] != approval["archive"]["sha256"]:
        raise ValueError("referencia diferente del piloto aprobado")
    if huella(Path(approval["artifact"]["path"]))["sha256"] != approval["artifact"]["sha256"]:
        raise ValueError("ROM aprobada diferente")
    base = root / "work/shared/base_3ds/romfs/archive.fa"
    output.mkdir(parents=True)
    resources, reports = {}, {}
    for name in profiles or ("spark", "ogre"):
        profile = cargar_perfil(name, (profile_files or {}).get(name))
        plan_dir = output / name
        plan_dir.mkdir()
        print(f"Auditoría + emisión {name}", flush=True)
        logic = profile.recurso.rsplit("/", 1)[0] + "/logic/"
        name_path, item_path = logic + "unitbase.dat", logic + "item.dat"
        with B123Archive(base) as jp, B123Archive(root / profile.oficial) as es, B123Archive(reference) as inherited:
            table = TextTable.from_codetable(es.read("font/CodeTable.bin"))
            names, names_report = recursos_nombres(profile, {name_path: jp.read(name_path)},
                                                   {"es/" + name_path: es.read("es/" + name_path)}, table,
                                                   {name_path: inherited.read(name_path)})
            items, items_report = construir_items(jp.read(item_path), es.read("es/" + item_path), table)
        pools = {"item": cota_pool(items_report["pool"])}
        compiler = partial(compilar_contexto, pools=pools)
        manifest, rows, summary, exceptions, orphans = auditar(root, profile, base, compiler,
                                                           resolver_identidades=True)
        manifest["dynamic_pools"] = {"item": {"bound": pools["item"],
                                             "sha256": items_report["payload_sha256"], "path": item_path}}
        manifest["stage"] = "general emission authorized; overall manual QA pending"
        manifest["messages_sha256"] = sha(json.dumps(rows, ensure_ascii=False, indent=2).encode("utf-8"))
        for key, data in (("plan", manifest), ("messages", rows), ("summary_plan", summary),
                          ("exceptions", exceptions), ("unreferenced", orphans)):
            guardar(plan_dir / (key + ".json"), data)
        with B123Archive(base) as jp, B123Archive(root / profile.oficial) as es, B123Archive(reference) as inherited:
            visible, visible_report = construir_payloads_texto_visible(jp, es, PerfilTextoVisible(name, profile.recurso))
            payloads, report = emitir_perfil(profile, jp, inherited, rows, visible)
        for path, data in visible.items():
            if not path.startswith(profile.recurso + "/"):
                payloads[path] = data
        payloads.update(names)
        payloads[item_path] = items
        for path, data in payloads.items():
            if path in resources and resources[path] != data:
                raise ValueError(f"conflicto entre perfiles: {path}")
            resources[path] = data
        report["plan_summary"] = summary
        report["visible"] = visible_report
        report["names"] = names_report
        report["items"] = items_report
        guardar(plan_dir / "emission.json", report)
        reports[name] = {"summary": report["summary"], "plan_summary": summary,
                         "visible": visible_report, "names": names_report, "items": items_report,
                         "manifest": huella(plan_dir / "emission.json")}
        print(json.dumps(report["summary"], ensure_ascii=False), flush=True)
    with B123Archive(reference) as arc:
        before = {entry.path.decode(): sha(arc.read(entry)) for entry in arc.entries}
    target = output / "archive.fa"
    shutil.copyfile(reference, target)
    from ie123kit.nucleo.contenedores.fa import FaArchive, reemplazar_entrada
    archive = FaArchive(str(target))
    with target.open("r+b") as f:
        for path, data in resources.items():
            reemplazar_entrada(f, archive, path, data)
    del archive
    with B123Archive(target) as arc:
        after = {entry.path.decode(): sha(arc.read(entry)) for entry in arc.entries}
        if set(before) != set(after) or any(before[p] != after[p] for p in before if p not in resources):
            raise ValueError("recurso ajeno modificado")
        if any(arc.read(p) != data for p, data in resources.items()):
            raise ValueError("reextracción B123 diferente")
    result = {"label": "Spark + Ogre Fase 3 — pendiente de validación manual del conjunto",
              "runtime_verified": False, "runtime_approval_scope": approval,
              "reference": huella(reference), "archive": huella(target),
              "profiles": reports, "resources_before": before, "resources_after": after,
              "changed_resources": [p for p in before if before[p] != after[p]],
              "warning": "Bomber comparte recursos Spark; no tiene corpus ni validación propia"}
    guardar(output / "integration.json", result)
    return result


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--referencia", type=Path, required=True)
    p.add_argument("--aprobacion", type=Path, required=True)
    p.add_argument("--salida", type=Path, required=True)
    p.add_argument("--perfil", action="append", help="por defecto spark y después ogre")
    p.add_argument("--perfil-json", type=Path, action="append", default=[], help="perfil adicional con corpus verificado")
    a = p.parse_args(argv)
    profile_files = {}
    for path in a.perfil_json:
        data = json.loads(path.read_text(encoding="utf-8"))
        if data["nombre"] in profile_files:
            p.error("perfil configurado dos veces")
        profile_files[data["nombre"]] = path
    r = preparar(find_root(), a.referencia.resolve(), a.aprobacion.resolve(), a.salida.resolve(), a.perfil, profile_files)
    print(json.dumps({k: r[k] for k in ("label", "archive", "changed_resources")}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
