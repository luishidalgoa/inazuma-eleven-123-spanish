"""Revisión acotada de colocación y UI sobre la candidata fase3 exacta.

Reutiliza reconstructores SSD/PackNum, adaptadores de campos y constructor ROM.
No modifica las fuentes, el encoder ni los controles pendientes.
"""
from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path

from ie123kit.ie3.comun.b123 import B123Archive
from ie123kit.ie3.comun.cobertura import huella, sha
from ie123kit.ie3.comun.emision import guardar
from ie123kit.ie3.comun.geometria_dialogo import Medidor, parchear_origen, render_casos
from ie123kit.ie3.comun.limite_nombre import parchear_limite_nombre
from ie123kit.ie3.comun.perfiles import cargar_perfil
from ie123kit.ie3.comun.revision_visual import leer_codigo, revisar_dialogos, verificar_revision
from ie123kit.ie3.comun.tablas_ui import recursos_tablas_ui, verificar_consumidor
from ie123kit.ie3.comun.tipografia import FuenteBCFNT
from ie123kit.ie3.comun.ui_graficos import construir_payloads_graficos
from ie123kit.nucleo.config.raiz import find_root
from ie123kit.nucleo.contenedores.fa import FaArchive, reemplazar_entrada

REF_ARCHIVE = "98618a5aa51229bd3a6e8f31dfd301729ee327751d6048f54b2b28784afb244b"
REF_ROM = "34c2e9a3e79d7561ece763e41909f06db97601c98dbcd1d879100b38ddf4bc6e"
PROTEGIDOS = ("tipografia.py", "ancho_ventana.py", "sjis_portador.py", "reinsert.py",
              "referencias.py", "paquetes.py", "controles.py")




def preparar(root, reference, output):
    if output.exists():
        raise ValueError("salida existente: no sobrescribir")
    manifest = reference/"manifest.json"
    previous = json.loads(manifest.read_text("utf-8"))
    if previous["rom"]["sha256"] != REF_ROM or huella(reference/"archive.fa")["sha256"] != REF_ARCHIVE:
        raise ValueError("referencia distinta de fase3 solicitada")
    plan = json.loads((reference/"spark/plan.json").read_text("utf-8"))
    protected = {}
    for key in PROTEGIDOS:
        record = plan["code"][key]
        actual = huella(Path(record["path"]))
        if actual["sha256"] != record["sha256"]:
            raise ValueError(f"componente protegido modificado: {key}")
        protected[key] = actual
    base = root/"work/shared/base_3ds"
    jp_cro = (base/"romfs/cro/ina_main3ogre.cro").read_bytes()
    cro = (reference/"romfs/cro/ina_main3ogre.cro").read_bytes()
    cro, names_report = parchear_limite_nombre(cro)
    cro, origin_report = parchear_origen(cro)
    consumer = verificar_consumidor(jp_cro)
    output.mkdir(parents=True)
    payloads, reports = {}, {}
    profiles = [cargar_perfil(x) for x in ("spark", "ogre")]
    with B123Archive(reference/"archive.fa") as current, B123Archive(base/"romfs/archive.fa") as jp, \
            B123Archive(root/profiles[0].oficial) as spark, B123Archive(root/profiles[1].oficial) as ogre:
        before = {e.path.decode(): sha(current.read(e)) for e in current.entries}
        with tempfile.TemporaryDirectory(prefix="ie3_fase4_font_readonly_") as td:
            font_path = Path(td)/"FONT12.bcfnt"
            font_path.write_bytes(current.read("font/FONT12.bcfnt"))
            measure = Medidor(FuenteBCFNT(font_path))
            for profile, official in zip(profiles, (spark, ogre)):
                print(f"Colocación y tablas {profile.nombre}", flush=True)
                dialogue, dialogue_report = revisar_dialogos(profile, reference, current, measure)
                tables, tables_report = recursos_tablas_ui(profile, jp, official)
                for path in tables:
                    if current.read(path) != jp.read(path):
                        raise ValueError(f"tabla con cambios heredados no previstos: {path}")
                payloads.update(dialogue)
                payloads.update(tables)
                reports[profile.nombre] = {"dialogues": dialogue_report, "tables": tables_report}
                guardar(output/(profile.nombre+".json"), reports[profile.nombre])
                print(json.dumps(dialogue_report["counts"], ensure_ascii=False), flush=True)
            rows = json.loads((reference/"spark/messages.json").read_text("utf-8"))
            cases = [(r["key"], r["formatted"]) for r in rows if r["key"] in {
                "spark:evet:32010100:00000000", "spark:evet:32500100:00000000",
                "spark:evet:32500100:00000104", "spark:evet:32500100:000001DC"}]
            preview, preview_report = render_casos(cases, measure)
            preview.save(output/"colocacion_simulacion.png")
            guardar(output/"colocacion_simulacion.json", preview_report)
        print("Gráficos oficiales compatibles", flush=True)
        esbase = root/"work/ie3/rayo_celeste/fuentes/3ds_eu"
        es_cro = (esbase/"romfs/cro/ina_main3ogre.cro").read_bytes()
        graphics, graphics_report = construir_payloads_graficos(
            jp, spark, ogre, leer_codigo(base/"exefs.bin"), jp_cro, es_cro)
        for path, data in graphics.items():
            if path in payloads or current.read(path) != jp.read(path):
                raise ValueError(f"conflicto gráfico/heredado: {path}")
            payloads[path] = data
        guardar(output/"graphics.json", graphics_report)
        # Literales oficiales del ejecutable: adaptador independiente, sin fuentes.
        from ie123kit.ie3.comun.ui_literales import parchear_literales_ie3
        cro, literals_report = parchear_literales_ie3(
            cro, leer_codigo(esbase/"exefs.bin"), (esbase/"romfs/cro/static.crs").read_bytes(),
            es_cro, spark.read("font/CodeTable.bin"))
        guardar(output/"literals.json", literals_report)
    target = output/"archive.fa"
    shutil.copyfile(reference/"archive.fa", target)
    arc = FaArchive(str(target))
    with target.open("r+b") as stream:
        for path, data in payloads.items():
            reemplazar_entrada(stream, arc, path, data)
    del arc
    with B123Archive(target) as arc:
        after = {e.path.decode(): sha(arc.read(e)) for e in arc.entries}
        if before.keys() != after.keys() or any(before[p] != after[p] for p in before if p not in payloads):
            raise ValueError("recurso ajeno cambiado")
        if any(arc.read(p) != data for p, data in payloads.items()):
            raise ValueError("payload reextraído diferente")
    fonts = {p: {"before": before[p], "after": after[p]} for p in before if p.startswith("font/")}
    if any(x["before"] != x["after"] for x in fonts.values()):
        raise ValueError("fuente o tabla de códigos modificada")
    cro_path = output/"romfs/cro/ina_main3ogre.cro"
    cro_path.parent.mkdir(parents=True)
    cro_path.write_bytes(cro)
    result = {"label": "Spark + Ogre Fase 4 — pendiente de validación manual del conjunto",
              "runtime_verified": False, "reference": huella(reference/"archive.fa"),
              "reference_manifest": huella(manifest), "archive": huella(target),
              "cro": huella(cro_path), "cro_patches": {"name": names_report, "body_origin": origin_report},
              "protected_code": protected, "protected_fonts": fonts, "protected_hashes_match": True,
              "resources_before": before, "resources_after": after,
              "changed_resources": [p for p in before if before[p] != after[p]],
              "reports": {p.name: huella(p) for p in output.glob("*.json")},
              "table_consumers": consumer,
              "warnings": ["Sin ejecución del artefacto: la simulación no es validación visual.",
                           "Bomber sin corpus ni validación; conserva exclusivos sin correspondencia.",
                           "Diálogos y controles geométricamente pendientes se conservan literales; véanse reports."]}
    guardar(output/"revision.json", result)
    return result




def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--referencia", type=Path, required=True)
    p.add_argument("--salida", type=Path, required=True)
    p.add_argument("--verificar", action="store_true", help="releer la candidata existente, sin reconstruirla")
    a = p.parse_args(argv)
    if a.verificar:
        result = verificar_revision(find_root(), a.referencia.resolve(), a.salida.resolve())
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        result = preparar(find_root(), a.referencia.resolve(), a.salida.resolve())
        print(json.dumps({k: result[k] for k in ("label", "archive", "cro", "changed_resources")}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
