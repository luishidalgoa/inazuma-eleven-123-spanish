"""Operaciones compartidas de revisión visual: reflujo e integridad de registros."""
import json
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

from ie123kit.ie3.comun.b123 import B123Archive
from ie123kit.ie3.comun.cobertura import huella, sha
from ie123kit.ie3.comun.emision import cargar_pares, guardar
from ie123kit.ie3.comun.paquetes import reconstruir_paquete
from ie123kit.ie3.comun.perfiles import cargar_perfil
from ie123kit.ie3.comun.referencias import leer_referencias, reconstruir_evento
from ie123kit.ie3.comun.tipografia import FuenteBCFNT
from ie123kit.nucleo.compresion.blz import decompress
from ie123kit.nucleo.contenedores.exefs import leer
from ie123kit.nucleo.texto.sjis_portador import es_encode


def leer_codigo(exefs):
    blob = exefs.read_bytes()
    items = [x for x in leer(blob) if x[0] == ".code"]
    if len(items) != 1:
        raise ValueError("ExeFS sin .code único")
    _, off, length = items[0]
    return decompress(blob[512+off:512+off+length])


def revisar_dialogos(profile, reference, archive, medidor, *, medidor_anterior=None):
    """Solo nuevas posiciones de saltos, referencias actuales y contenido literal."""
    rows = json.loads((reference/profile.nombre/"messages.json").read_text("utf-8"))
    pairs = cargar_pares(archive, profile.recurso)
    grouped, counts, pending, changed = defaultdict(list), Counter(), [], []
    for row in rows:
        if row["blockers"]:
            counts["pendiente_previo_literal"] += 1
            continue
        text = row["formatted"]
        if "%" in text:
            counts["control_admitido_previo_literal"] += 1
            continue
        if es_encode(text, 1 << 30).hex() != row["encoded_hex"]:
            raise ValueError("plan fase3 no coincide con encoder protegido")
        try:
            replacement = medidor.maquetar(text)
            measures = [medidor.medir(s) for s in text.split("\\n")]
        except ValueError as exc:
            replacement, measures = None, []
            pending.append({"key": row["key"], "reason": str(exc), "preserved": True})
        counts["estaticos_examinados"] += 1
        if replacement is None:
            counts["colocacion_pendiente_literal"] += 1
            if measures:
                pending.append({"key": row["key"], "reason": "no_cabe_en_tres_filas_sin_cambiar_contenido",
                                "text": text, "measures": measures, "preserved": True})
            continue
        counts["colocacion_estatica_comprobada"] += 1
        if replacement == text:
            continue
        if replacement.replace("\\n", " ") != text.replace("\\n", " "):
            raise ValueError("reflujo modificó contenido distinto de salto/espacio")
        record = {"key": row["key"], "instruction": row["instruction"],
                  "before": text, "after": replacement, "source": row["source"],
                  "before_hex": row["encoded_hex"],
                  "after_hex": es_encode(replacement, 1 << 30).hex(),
                  "measures_before": [(medidor_anterior or medidor).medir(s, 12) for s in text.split("\\n")],
                  "measures_after": [medidor.medir(s) for s in replacement.split("\\n")]}
        changed.append(record)
        grouped[row["event"]].append(record)
        counts["mensajes_recolocados"] += 1
    blocks, checks = {"eve": {}, "evet": {}}, []
    for event, ssd in pairs["eve"][2].items():
        evet = pairs["evet"][2].get(event)
        if evet is None:
            checks.append({"event": event, "missing_evet_original_preserved": True})
            continue
        refs, _, records, _, _ = leer_referencias(ssd, evet)
        by_ins = {r.instruccion.ident: r for r in refs}
        replacements = {}
        for row in grouped[event]:
            ref = by_ins[row["instruction"]]
            current = records[ref.registros[0]].raw
            if current.hex() != row["before_hex"]:
                raise ValueError(f"candidata distinta del plan actual: {row['key']}")
            payload = bytes.fromhex(row["after_hex"])
            if ref.inicio in replacements and replacements[ref.inicio] != payload:
                raise ValueError("referencia compartida contradictoria")
            replacements[ref.inicio] = payload
        if replacements:
            ns, ne, trace = reconstruir_evento(ssd, evet, replacements)
            nr, _, nrecords, _, _ = leer_referencias(ns, ne)
            if [(r.instruccion, r.registros) for r in refs] != [(r.instruccion, r.registros) for r in nr]:
                raise ValueError("identidad de consumidores modificada")
            for a, b in zip(records, nrecords):
                if a.offset in replacements:
                    if b.raw != replacements[a.offset]:
                        raise ValueError("reextracción no coincide")
                elif evet[a.offset:a.offset+a.size] != ne[b.offset:b.offset+b.size]:
                    raise ValueError("registro pendiente/secundario modificado")
            blocks["eve"][event], blocks["evet"][event] = ns, ne
            checks.append({"event": event, "references": len(nr), "records": len(nrecords),
                           "references_updated": trace["references_changed"],
                           "bytecode_secondary_pending_intact": True})
        counts["eventos_referencias_validados"] += 1
    payloads, pack_reports = {}, {}
    for kind in ("eve", "evet"):
        h, b, _, _ = pairs[kind]
        if reconstruir_paquete(h, b, kind, {})[:2] != (h, b):
            raise ValueError("roundtrip de paquete no literal")
        nh, nb, report = reconstruir_paquete(h, b, kind, blocks[kind])
        payloads[profile.recurso+"/"+kind+".pkh"] = nh
        payloads[profile.recurso+"/"+kind+".pkb"] = nb
        pack_reports[kind] = report
    return payloads, {"counts": dict(counts), "changed": changed, "pending": pending,
                      "events": checks, "packs": pack_reports, "no_truncation": True,
                      "new_translation_count": 0, "runtime_verified": False}


def verificar_revision(root, reference, candidate, *, comprobar_literales=True):
    """Lectura independiente de recursos ensamblados antes de la ROM completa."""
    from ie123kit.ie3.comun.presentacion_nombres import auditar_presentacion, render_comparacion
    from ie123kit.ie3.comun.ui_literales import parchear_literales_ie3

    manifest = json.loads((candidate/"revision.json").read_text("utf-8"))
    if huella(candidate/"archive.fa") != manifest["archive"] or huella(candidate/"romfs/cro/ina_main3ogre.cro") != manifest["cro"]:
        raise ValueError("candidata cambió tras la emisión")
    cro = (candidate/"romfs/cro/ina_main3ogre.cro").read_bytes()
    esbase = root/"work/ie3/amenaza_del_ogro/fuentes/3ds_eu"
    with B123Archive(root/cargar_perfil("ogre").oficial) as es:
        checked_cro, ogre_source = parchear_literales_ie3(
            cro, leer_codigo(esbase/"exefs.bin"), (esbase/"romfs/cro/static.crs").read_bytes(),
            (esbase/"romfs/cro/ina_main3ogre.cro").read_bytes(), es.read("font/CodeTable.bin"))
        if comprobar_literales and checked_cro != cro:
            raise ValueError("fuente Ogre exige literales distintos de Spark")
    counts = {}
    with B123Archive(candidate/"archive.fa") as arc, B123Archive(reference/"archive.fa") as before:
        actual = {e.path.decode(): sha(arc.read(e)) for e in arc.entries}
        if actual != manifest["resources_after"]:
            raise ValueError("inventario B123 ensamblado distinto")
        with tempfile.TemporaryDirectory(prefix="ie3_nombre_final_") as td:
            fp = Path(td)/"FONT8.bcfnt"
            fp.write_bytes(arc.read("font/FONT8.bcfnt"))
            font = FuenteBCFNT(fp)
            names = auditar_presentacion(arc, font)
            guardar(candidate/"names.json", names)
            render_comparacion(["Bianchi", "Maserati", "Downtown", "¿Sra. Hob.?", "Mr. T"], font).save(
                candidate/"nombres_simulacion.png")
        for name in ("spark", "ogre"):
            profile = cargar_perfil(name)
            old, new = cargar_pares(before, profile.recurso), cargar_pares(arc, profile.recurso)
            changed = json.loads((candidate/(name+".json")).read_text("utf-8"))["dialogues"]["changed"]
            expected = {r["key"]: r for r in changed}
            by_event_instruction = {(int(r["key"].split(":")[2]), r["instruction"]): r for r in changed}
            if len(by_event_instruction) != len(expected):
                raise ValueError("identidad de sustitución duplicada")
            seen, records_count, refs_count = set(), 0, 0
            for event, ns in new["eve"][2].items():
                os = old["eve"][2][event]
                oe, ne = old["evet"][2].get(event), new["evet"][2].get(event)
                if oe is None:
                    if ne is not None or ns != os:
                        raise ValueError("excepción de recurso ausente modificada")
                    continue
                refs, _, records, _, _ = leer_referencias(os, oe)
                nrefs, _, nrecords, _, _ = leer_referencias(ns, ne)
                if len(records) != len(nrecords) or [(r.instruccion, r.registros) for r in refs] != [(r.instruccion, r.registros) for r in nrefs]:
                    raise ValueError("consumidores/registro cambiaron")
                changes_by_index = {}
                for ref in refs:
                    # La clave fase3 conserva offset ORIGINAL JP; usar ID de
                    # instrucción para encontrar su transición, no offset actual.
                    row = by_event_instruction.get((event, ref.instruccion.ident))
                    if row is not None:
                        seen.add(row["key"])
                        changes_by_index[ref.registros[0]] = bytes.fromhex(row["after_hex"])
                for i, (a, b) in enumerate(zip(records, nrecords)):
                    if i in changes_by_index:
                        if b.raw != changes_by_index[i]:
                            raise ValueError("texto completo reextraído no coincide")
                    elif oe[a.offset:a.offset+a.size] != ne[b.offset:b.offset+b.size]:
                        raise ValueError("pendiente o secundario no conservado")
                records_count += len(records)
                refs_count += len(refs)
            if seen != set(expected):
                raise ValueError("no se reextrajeron todas las sustituciones declaradas")
            counts[name] = {"references": refs_count, "records": records_count,
                            "reflows_reextracted": len(seen), "untouched_records_literal": True}
    result = {"runtime_verified": False, "archive": huella(candidate/"archive.fa"),
              "cro": huella(candidate/"romfs/cro/ina_main3ogre.cro"),
              "all_archive_entries": len(actual), "dialogues": counts,
              "names": huella(candidate/"names.json"), "ogre_literal_equivalence": ogre_source,
              "protected_fonts": manifest["protected_fonts"], "no_truncations_accepted": True}
    guardar(candidate/"verification.json", result)
    return result
