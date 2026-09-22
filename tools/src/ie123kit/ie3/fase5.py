"""Corrección de la candidata visual rechazada: datos, colocación, UI y medios.

Compone sobre fase4, pero reconstruye descripciones desde originales y reflujo
desde fase3. No atribuye a la build traducción completa ni validación en juego.
"""
from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path

from ie123kit.ie3.comun.b123 import B123Archive
from ie123kit.ie3.comun.casos_visibles import paquete_mision_intro, recursos_ficha_y_titulo
from ie123kit.ie3.comun.cobertura import huella, sha
from ie123kit.ie3.comun.colocacion_visible import parchear
from ie123kit.ie3.comun.emision import guardar
from ie123kit.ie3.comun.geometria_dialogo import Medidor, render_casos
from ie123kit.ie3.comun.literales_visibles import parchear_submenus
from ie123kit.ie3.comun.medios_es import leer_video, planificar_audio, planificar_videos
from ie123kit.ie3.comun.perfiles import cargar_perfil
from ie123kit.ie3.comun.rectangulo_menu import parchear_rectangulo_menu
from ie123kit.ie3.comun.tablas_ui import (
    recursos_tablas_ui,
    verificar_consumidor,
    verificar_consumidor_europeo,
)
from ie123kit.ie3.comun.text import load_text_table
from ie123kit.ie3.comun.tipografia import FuenteBCFNT
from ie123kit.ie3.comun.ui_visibles import ATLAS_VISIBLES, construir_payloads_visibles
from ie123kit.ie3.comun.revision_visual import leer_codigo, revisar_dialogos, verificar_revision
from ie123kit.nucleo.config.raiz import find_root
from ie123kit.nucleo.contenedores.fa import FaArchive, reemplazar_entrada

ARCHIVE4 = "4aba963e3f2d499cc2fe10c48ed469f0cea7e5251a3c8f44a8f5927f2957e193"
ARCHIVE3 = "98618a5aa51229bd3a6e8f31dfd301729ee327751d6048f54b2b28784afb244b"


def bases(root):
    shared = root / "work/ie3/shared/candidatas"
    return (root / "work/shared/base_3ds", shared / "spark_ogre_integrada_fase3",
            shared / "spark_ogre_integrada_fase4")


def componer_cro(root):
    _, _, reference = bases(root)
    source = (reference / "romfs/cro/ina_main3ogre.cro").read_bytes()
    cro, placement = parchear(source)
    cro, rectangle = parchear_rectangulo_menu(cro)
    proofs = {}
    outputs = []
    for name in ("spark", "ogre"):
        profile = cargar_perfil(name)
        romfs = (root / profile.oficial).parent
        with B123Archive(root / profile.oficial) as archive:
            data, report = parchear_submenus(
                cro, leer_codigo(romfs.parent / "exefs.bin"), (romfs / "cro/static.crs").read_bytes(),
                (romfs / "cro/ina_main3ogre.cro").read_bytes(), archive.read("font/CodeTable.bin"))
        outputs.append(data)
        proofs[name] = report
    if outputs[0] != outputs[1]:
        raise ValueError("submenús compartidos exigen distintas salidas Spark/Ogre")
    return outputs[0], {"placement": placement, "rectangle": rectangle, "submenus": proofs}


def preparar(root, output):
    if output.exists():
        raise ValueError("salida existente: no sobrescribir")
    base, phase3, reference = bases(root)
    for path, expected in ((phase3 / "archive.fa", ARCHIVE3), (reference / "archive.fa", ARCHIVE4)):
        if huella(path)["sha256"] != expected:
            raise ValueError("referencia distinta de la revisión auditada")
    previous = json.loads((reference / "revision.json").read_text("utf-8"))
    for item in previous["protected_code"].values():
        if huella(Path(item["path"])) != item:
            raise ValueError("componente protegido modificado")
    profiles = [cargar_perfil(name) for name in ("spark", "ogre")]
    roots = [(root / profile.oficial).parent for profile in profiles]
    cro, cro_report = componer_cro(root)
    output.mkdir(parents=True)
    payloads = {}
    with B123Archive(reference / "archive.fa") as current, \
            B123Archive(phase3 / "archive.fa") as dialogue_base, \
            B123Archive(base / "romfs/archive.fa") as jp, \
            B123Archive(root / profiles[0].oficial) as spark, \
            B123Archive(root / profiles[1].oficial) as ogre:
        before = {e.path.decode(): sha(current.read(e)) for e in current.entries}
        consumers = {"jp": verificar_consumidor((base / "romfs/cro/ina_main3ogre.cro").read_bytes())}
        with tempfile.TemporaryDirectory(prefix="ie3_revision_font_readonly_") as td:
            fp = Path(td) / "FONT12.bcfnt"
            fp.write_bytes(current.read("font/FONT12.bcfnt"))
            font = FuenteBCFNT(fp)
            measure = Medidor(font, word_spacing=3, extra_line=1, vertical_percent=100)
            for profile, official, romfs in zip(profiles, (spark, ogre), roots, strict=True):
                print(f"Recomponiendo textos completos: {profile.nombre}", flush=True)
                consumers[profile.nombre] = verificar_consumidor_europeo((romfs / "cro/ina_main3ogre.cro").read_bytes())
                dialogue, report = revisar_dialogos(profile, phase3, dialogue_base, measure,
                                                    medidor_anterior=Medidor(font))
                tables, tables_report = recursos_tablas_ui(profile, jp, official)
                cards, cards_report = recursos_ficha_y_titulo(profile, jp, official, current)
                payloads.update(dialogue)
                payloads.update(tables)
                payloads.update(cards)
                prefix = profile.recurso + "/eve"
                header, body, mission = paquete_mision_intro(
                    jp.read(prefix + ".pkh"), jp.read(prefix + ".pkb"),
                    official.read("es/" + prefix + ".pkh"), official.read("es/" + prefix + ".pkb"),
                    payloads[prefix + ".pkh"], payloads[prefix + ".pkb"], load_text_table(official))
                payloads[prefix + ".pkh"], payloads[prefix + ".pkb"] = header, body
                guardar(output / (profile.nombre + ".json"), {
                    "dialogues": report, "tables": tables_report, "cards": cards_report,
                    "mission": mission, "incorrect_phase4_unitbase_discarded": True})
                print(json.dumps(report["counts"], ensure_ascii=False), flush=True)
            rows = json.loads((phase3 / "spark/messages.json").read_text("utf-8"))
            cases = [(row["key"], row["formatted"]) for row in rows if row["key"] in {
                "spark:evet:32010100:00000000", "spark:evet:32500100:00000000",
                "spark:evet:32500100:00000104", "spark:evet:32500100:000001DC"}]
            image, report = render_casos(cases, measure)
            image.save(output / "colocacion_simulacion.png")
            guardar(output / "colocacion_simulacion.json", report)
        print("Componiendo gráficos oficiales sin cambiar geometría", flush=True)
        paths = [f"inazuma3_ogre/data_iz/a_menu/{family}.arc" for family in ATLAS_VISIBLES]
        graphics, graphics_report = construir_payloads_visibles(
            jp, spark, ogre, leer_codigo(base / "exefs.bin"),
            actuales={path: current.read(path) for path in paths})
        payloads.update(graphics)
        guardar(output / "graphics.json", graphics_report)
        mediaqa = root / "work/ie3/shared/fase5_media"
        videos, video_report = planificar_videos(
            jp, spark, ogre, cro,
            json.loads((mediaqa / "decode_videos_jp.json").read_text("utf-8")),
            json.loads((mediaqa / "decode_videos.json").read_text("utf-8")))
        guardar(output / "videos.json", video_report)
        # Vídeos se leen al escribir; no duplicar cientos de MB en payloads.
        target = output / "archive.fa"
        shutil.copyfile(reference / "archive.fa", target)
        arc = FaArchive(str(target))
        emitted = {path: sha(data) for path, data in payloads.items()}
        with target.open("r+b") as stream:
            for path, data in payloads.items():
                reemplazar_entrada(stream, arc, path, data)
            for path, entry in videos.items():
                print(f"Vídeo oficial: {path}", flush=True)
                data = leer_video(entry, spark, ogre)
                reemplazar_entrada(stream, arc, path, data)
                emitted[path] = sha(data)
        del arc
    with B123Archive(target) as arc:
        after = {e.path.decode(): sha(arc.read(e)) for e in arc.entries}
        if before.keys() != after.keys() or any(before[p] != after[p] for p in before if p not in emitted):
            raise ValueError("recurso ajeno modificado")
        if any(after[path] != digest for path, digest in emitted.items()):
            raise ValueError("payload reextraído distinto")
    fonts = {p: {"before": before[p], "after": after[p]} for p in before if p.startswith("font/")}
    if any(item["before"] != item["after"] for item in fonts.values()):
        raise ValueError("fuente o codificación modificada")
    audio, audio_report = planificar_audio(base / "romfs", *roots)
    guardar(output / "audio.json", audio_report)
    external = {}
    for relative, source in audio.items():
        dst = output / "romfs" / relative
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, dst)
        a, b = huella(source), huella(dst)
        if (a["sha256"], a["size"]) != (b["sha256"], b["size"]):
            raise ValueError("medio externo no idéntico a oficial")
        external[relative] = {"sha256": b["sha256"], "size": b["size"], "source": a}
    cro_path = output / "romfs/cro/ina_main3ogre.cro"
    cro_path.parent.mkdir(parents=True, exist_ok=True)
    cro_path.write_bytes(cro)
    result = {
        "label": "Spark + Ogre — revisión de textos, interfaz y medios — pendiente de prueba manual",
        "runtime_verified": False, "complete_spanish_localization": False,
        "reference": huella(reference / "archive.fa"), "reference_manifest": huella(reference / "manifest.json"),
        "archive": huella(target), "cro": huella(cro_path), "cro_patches": cro_report,
        "dialogue_source": huella(phase3 / "manifest.json"),
        "protected_code": previous["protected_code"], "protected_fonts": fonts, "protected_hashes_match": True,
        "resources_before": before, "resources_after": after, "emitted_payloads": emitted,
        "changed_resources": [p for p in before if before[p] != after[p]],
        "external_romfs": external, "table_consumers": consumers,
        "warnings": ["Pendiente de validación visual y escucha en juego.",
                     "Localización incompleta: textos rechazados y controles pendientes conservados.",
                     "Subtítulos DAT, bancos de sonido no auditados y exclusivos sin fuente ES conservados.",
                     "No se certifica Bomber ni los juegos IE1/IE2."]}
    guardar(output / "revision.json", result)
    return result


def actualizar_cro(root, candidate):
    """Recomponer solo la candidata aún NO publicada como ROM; evita otra copiaFA."""
    if (candidate / "manifest.json").exists():
        raise ValueError("ROM ya generada: no modificar su candidata")
    manifest = json.loads((candidate / "revision.json").read_text("utf-8"))
    path = candidate / "romfs/cro/ina_main3ogre.cro"
    if huella(path) != manifest["cro"] or huella(candidate / "archive.fa") != manifest["archive"]:
        raise ValueError("candidata cambió fuera del integrador")
    cro, report = componer_cro(root)
    path.write_bytes(cro)
    manifest.update(cro=huella(path), cro_patches=report)
    guardar(candidate / "revision.json", manifest)
    return manifest


def verificar(root, candidate):
    _, phase3, _ = bases(root)
    result = verificar_revision(root, phase3, candidate)
    manifest = json.loads((candidate / "revision.json").read_text("utf-8"))
    for relative, expected in manifest["external_romfs"].items():
        actual = huella(candidate / "romfs" / relative)
        if (actual["sha256"], actual["size"]) != (expected["sha256"], expected["size"]):
            raise ValueError("medio externo cambiado")
    result["external_media_verified"] = len(manifest["external_romfs"])
    guardar(candidate / "verification.json", result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--salida", required=True, type=Path)
    parser.add_argument("--verificar", action="store_true")
    parser.add_argument("--actualizar-cro", action="store_true")
    args = parser.parse_args(argv)
    if args.verificar and args.actualizar_cro:
        parser.error("seleccionar una operación")
    operation = verificar if args.verificar else actualizar_cro if args.actualizar_cro else preparar
    result = operation(find_root(), args.salida.resolve())
    print(json.dumps({key: result[key] for key in ("archive", "cro")}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
