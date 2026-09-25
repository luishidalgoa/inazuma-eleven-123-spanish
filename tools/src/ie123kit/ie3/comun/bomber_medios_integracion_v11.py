"""Complemento de medios Bomber sobre una candidata Fase 5 ya verificada.

No vuelve a emitir textos, no parchea CRO y no altera las fases anteriores.
Reutiliza lectores/repacker/SADL/build del repositorio. La validación textual
se hereda SOLO después de demostrar identidad de todo recurso no multimedia.
Los hashes de las seis transiciones proceden del diagnóstico local aportado.
v1.1 permite conservar la pareja completa del opening, explícitamente pendiente,
sin relajar comparar_pareja ni falsificar resultados de decodificación.
"""
from __future__ import annotations

import copy
import hashlib
import json
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from .bomber_video_qa import comparar_pareja, decodificar, escribir_json, validar_resultado

SCHEMA = "ie3_bomber_media_extension_v1_1"
OPENING_MODES = ("estricto", "conservar-base")
CRO_PATH = "cro/ina_main3ogre.cro"
MOVIE_PREFIX = "inazuma3/data_iz/movie/"
SOUND_PREFIX = "inazuma3/data_iz/sound/"
# nombre: (SHA JP, SHA ES, bytes JP, bytes ES). No son ROMs/recursos incluidos.
VIDEOS = {
    "a3y01b": ("816186478e88b5859e13a05dba9b90dcc5287a130b44dd359d3a2df79801ac5e",
               "09f0e5d227455eec6840c348638665126d15818b80ef5e68a2c791a7ed3084b3", 274235, 283168),
    "a3y02b": ("2daf583708876dff7f34f4b10a7ac1de07f0115d9ea44bdb082bf2014ed879c1",
               "e7a0668bef08b653ce42fdfe659b5a40825053aa351c34f63b3b964380a8c5b3", 340703, 280653),
    "a3y03b": ("8c6025d10594081dc2d56702a7384286d7b72404190960bf3d572f641cf4a2a8",
               "0d7ed8e8371ec6f439a973ef8f0df039ff774a7734584078a454144016468acd", 322476, 290343),
    "op00b": ("74da594f665771dc3f6629c472c4ee9497272a49a7a6a3776d4a5a8bd0eb0463",
              "76fff5a2581081271c4a6aaca5b29895212bbfb6912873aa04941936fb980579", 9112472, 8517262),
}
CANCIONES = {
    "op00b": ("be0d74b460ff56a572eef0bab58456a5c9a1bad1495ea89e51e4477faee31bc7",
              "271895c48e70919c6dbc3def115d124a44b42148b2bb6336d7402e67aa548f11", 3167872, 3216384),
    "end00b": ("421bc66df6110fe7849cea009b5dcc2ebbc6ec51612dadd9fd642371ead2c808",
               "d9348846cf01de6982ae071357a27400614bebdcdf3309ab0bfbb483d1324a9e", 8095648, 10015840),
}
PENDIENTES = [
    "Los nueve SAD a3y (eyecatches) conservan la pista de la candidata base: categoría no auditada.",
    "Las cuatro promociones pv_b/pv_f/pv_o1/pv_o2 siguen sin fuente ES en las rutas examinadas.",
    "Subtítulos DAT, bancos de sonido, UI y textos no se modifican; conservan sus pendientes.",
    "Frames/fps iguales no prueban montaje, idioma ni sincronía de audio en el juego.",
    "La igualdad de corpus no certifica toda la campaña de Bomber ni sus otros recursos exclusivos.",
]


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def leer_json(path: Path) -> dict:
    def sin_duplicados(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Clave JSON duplicada {key!r} en {path}")
            result[key] = value
        return result
    value = json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=sin_duplicados)
    if not isinstance(value, dict):
        raise ValueError(f"Se esperaba objeto JSON: {path}")  # noqa: TRY004 (error de contenido del JSON)
    return value


def huella_local(path: Path) -> dict:
    """Fingerprint sencillo para logs/estado; los manifiestos usan huella del repo."""
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return {"path": str(path.resolve()), "size": path.stat().st_size, "sha256": h.hexdigest()}


def exigir_huella(actual: dict, expected: dict, label: str) -> None:
    if (actual.get("sha256"), actual.get("size")) != (expected.get("sha256"), expected.get("size")):
        raise ValueError(f"Hash/tamaño modificado: {label}")
    if not isinstance(actual.get("sha256"), str) or not isinstance(actual.get("size"), int):
        raise ValueError(f"Huella sin SHA/tamaño: {label}")  # noqa: TRY004 (error de contenido del JSON)


def ruta_interna(base: Path, relative: str) -> Path:
    """Rechaza escape, rutas absolutas, alias Windows y enlaces fuera de base."""
    if not isinstance(relative, str) or "\\" in relative or ":" in relative:
        raise ValueError(f"Ruta interna inválida: {relative!r}")
    rel = PurePosixPath(relative)
    if rel.is_absolute() or not rel.parts or any(p in ("..", ".") for p in rel.parts):
        raise ValueError(f"Ruta interna fuera del contenedor: {relative!r}")
    path = base.joinpath(*rel.parts)
    if not path.resolve().is_relative_to(base.resolve()):
        raise ValueError(f"Enlace/ruta fuera de base: {relative}")
    return path


@dataclass(frozen=True)
class Motor:
    """Adaptadores de producción; los tests inyectan contenedores sintéticos."""
    archivo: Callable
    repack: Callable
    huella: Callable
    sad: Callable
    descriptor: Callable
    consumidor: Callable


def motor_real() -> Motor:
    # Imports perezosos: --help y tests puros no dependen de las ROMs.
    from ie123kit.ie3.comun.b123 import B123Archive
    from ie123kit.ie3.comun.cobertura import huella
    from ie123kit.ie3.comun.medios_es import _sad, comprobar_consumidores, descriptor_moflex
    from ie123kit.nucleo.contenedores.fa import FaArchive, reemplazar_entrada

    def repack(path: Path, payloads: dict[str, bytes]) -> None:
        arc = FaArchive(str(path))
        try:
            with path.open("r+b") as handle:
                for relative, data in payloads.items():
                    reemplazar_entrada(handle, arc, relative, data)
        finally:
            del arc
    return Motor(B123Archive, repack, huella, _sad, descriptor_moflex, comprobar_consumidores)


def inventario(arc: Any) -> dict[str, str]:
    result = {}
    for entry in arc.entries:
        name = entry.path.decode("utf-8") if isinstance(entry.path, bytes) else entry.path
        if name in result:
            raise ValueError(f"Entrada de archivo duplicada: {name}")
        result[name] = digest(arc.read(entry))
    return result


def ficheros_overlay(root: Path) -> set[str]:
    result = set()
    for path in root.rglob("*"):
        if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
            raise ValueError(f"Overlay con enlace/junction no admitido: {path}")
        if path.is_file():
            result.add(path.relative_to(root).as_posix())
    return result


def comprobar_protegidos(revision: dict, motor: Motor) -> None:
    if revision.get("protected_hashes_match") is not True:
        raise ValueError("La candidata no tiene protecciones satisfechas")
    for item in revision["protected_code"].values():
        # Se conserva incluso la comprobación de identidad de ruta de la API original.
        if motor.huella(Path(item["path"])) != item:
            raise ValueError(f"Código protegido cambiado: {item['path']}")


def comprobar_base(root: Path, candidate: Path, motor: Motor) -> dict:
    """Comprueba lo que se heredará SIN reescribir verification.json de la base."""
    rev = leer_json(candidate / "revision.json")
    verified = leer_json(candidate / "verification.json")
    built = leer_json(candidate / "manifest.json")
    for name, expected in (("revision.json", built["emission_manifest"]),
                           ("verification.json", built["independent_verification"])):
        exigir_huella(motor.huella(candidate / name), expected, name)
    for key, relative in (("archive", "archive.fa"), ("cro", "romfs/" + CRO_PATH)):
        actual = motor.huella(candidate / relative)
        exigir_huella(actual, rev[key], relative)
        exigir_huella(actual, built[key], "manifest: " + relative)
        if verified[key] != rev[key]:
            raise ValueError("Verificación heredada no corresponde a la candidata")
    if verified.get("no_truncations_accepted") is not True:
        raise ValueError("La base no tiene verificación textual utilizable")
    comprobar_protegidos(rev, motor)
    exigir_huella(motor.huella(root / "work/shared/base_3ds/exefs.bin"), built["exefs"], "ExeFS")
    readback = built["readback"]
    if (readback.get("exefs_unchanged") is not True
            or readback.get("archive.fa", {}).get("sha256") != rev["archive"]["sha256"]
            or readback.get(CRO_PATH, {}).get("sha256") != rev["cro"]["sha256"]):
        raise ValueError("La base carece de readback final compatible con archive/CRO/ExeFS")
    print("Comprobando inventario íntegro de la candidata base...", flush=True)
    with motor.archivo(candidate / "archive.fa") as arc:
        current = inventario(arc)
    if current != rev["resources_after"] or readback.get("all_archive_entries_verified") != len(current):
        raise ValueError("El inventario de la base no coincide con su ROM verificada")
    expected_overlay = set(rev["external_romfs"]) | {CRO_PATH}
    if ficheros_overlay(candidate / "romfs") != expected_overlay:
        raise ValueError("La base tiene un overlay ausente o no inventariado; no se copiará a ciegas")
    for relative, info in rev["external_romfs"].items():
        exigir_huella(motor.huella(ruta_interna(candidate / "romfs", relative)), info, relative)
    if readback.get("external_media_verified") != len(rev["external_romfs"]):
        raise ValueError("El readback heredado no cubre el overlay completo")
    return {"revision": rev, "verification": verified, "built": built, "inventory": current,
            "snapshot": {name: motor.huella(candidate / name) for name in
                         ("revision.json", "verification.json", "manifest.json", "audio.json", "videos.json")}}


def contrato_bytes(data: bytes, sha: str, size: int, label: str) -> None:
    if len(data) != size or digest(data) != sha:
        raise ValueError(f"Recurso distinto de la extracción auditada: {label}. No se aplica por parecido.")


def comprobar_transicion(current: str, before: str, after: str, label: str) -> None:
    if current not in (before, after):
        raise ValueError(f"{label}: el recurso actual no es ni el JP auditado ni el ES esperado")



def evidencia_opening(jp: dict, es: dict) -> dict:
    """Registra la discrepancia sin transformarla en un resultado válido."""
    validar_resultado(jp, VIDEOS["op00b"][0])
    validar_resultado(es, VIDEOS["op00b"][1])
    return {
        "target": MOVIE_PREFIX + "op00b.moflex",
        "audio_target": SOUND_PREFIX + "op00b.SAD",
        "reason": ("duracion_distinta_par_opening_conservado"
                   if jp["frames"] != es["frames"] else
                   "par_opening_conservado_por_politica_explicita"),
        "qa_jp": jp, "qa_es": es,
        "frames_jp": jp["frames"], "frames_es": es["frames"],
        "delta_frames_es_menos_jp": es["frames"] - jp["frames"],
        "delta_seconds_es_menos_jp": (es["frames"] - jp["frames"]) / 24,
        "timeline_counts_match": jp["frames"] == es["frames"],
        "selected": False, "runtime_verified": False,
        "action": "conservar_video_y_audio_JP_de_la_base_sin_recortar_ni_estirar",
    }


def comprobar_opening_base(root: Path, base: Path, state: dict) -> dict:
    """Impide conservar por descuido una mezcla JP/ES ya presente en la base."""
    video = MOVIE_PREFIX + "op00b.moflex"
    audio = SOUND_PREFIX + "op00b.SAD"
    if state["inventory"].get(video) != VIDEOS["op00b"][0]:
        raise ValueError("Conservar opening requiere el vídeo JP auditado en la base")
    path = ruta_interna(base / "romfs", audio)
    if not path.is_file():
        path = ruta_interna(root / "work/shared/base_3ds/romfs", audio)
    data = path.read_bytes()
    contrato_bytes(data, CANCIONES["op00b"][0], CANCIONES["op00b"][2],
                   "opening JP que se conserva")
    return {"video_sha256": VIDEOS["op00b"][0],
            "audio_sha256": digest(data), "audio_size": len(data)}


def validar_politica_plan(root: Path, base: Path, state: dict, plan: dict) -> str:
    """La omisión solo admite el opening completo y una evidencia ligada a hashes."""
    mode = plan.get("opening_policy")
    if mode not in OPENING_MODES:
        raise ValueError("Política de opening ausente o no reconocida")
    pending = plan.get("pending")
    if mode == "estricto":
        if pending != []:
            raise ValueError("Un plan estricto no puede omitir medios")
    else:
        if not isinstance(pending, list) or len(pending) != 1:
            raise ValueError("Solo se puede dejar pendiente la pareja op00b")
        row = pending[0]
        expected = evidencia_opening(row["qa_jp"], row["qa_es"])
        expected["preserved_pair"] = comprobar_opening_base(root, base, state)
        if row != expected:
            raise ValueError("Evidencia de opening pendiente alterada")
    return mode


def planificar(root: Path, base: Path, source: Path, state: dict, motor: Motor, cache: Path,
               *, decoder: Callable = decodificar, opening: str = "estricto") -> dict:
    """Plan acotado; el opening solo puede conservarse como pareja completa."""
    if opening not in OPENING_MODES:
        raise ValueError("Política de opening no reconocida")
    original = root / "work/shared/base_3ds/romfs"
    audio_report = leer_json(base / "audio.json")
    audio_rows = {}
    for row in audio_report["rows"]:
        if row["target"] in audio_rows:
            raise ValueError("Informe de audio heredado con destino duplicado")
        audio_rows[row["target"]] = row
    plan = {"schema": SCHEMA, "video": [], "audio": [], "warnings": list(PENDIENTES),
            "runtime_verified": False, "subtitle_localized": False,
            "opening_policy": opening, "pending": []}
    with motor.archivo(original / "archive.fa") as jp, motor.archivo(source) as fuego:
        for name, (oldhash, newhash, oldsize, newsize) in VIDEOS.items():
            target = MOVIE_PREFIX + name + ".moflex"
            relative = "es/" + target
            before, after = jp.read(target), fuego.read(relative)
            contrato_bytes(before, oldhash, oldsize, "JP " + target)
            contrato_bytes(after, newhash, newsize, "Fuego " + relative)
            before_desc, after_desc = motor.descriptor(before), motor.descriptor(after)
            comprobar_transicion(state["inventory"][target], oldhash, newhash, target)
            print(f"QA secuencial JP/ES: {name} (caché por SHA-256)", flush=True)
            qa_jp, qa_es = decoder(before, cache), decoder(after, cache)
            validar_resultado(qa_jp, oldhash)
            validar_resultado(qa_es, newhash)
            if name == "op00b":
                evidence = evidencia_opening(qa_jp, qa_es)
                # Informe real aunque la política estricta detenga la construcción.
                escribir_json(cache.parent / "comparacion_op00b.json", evidence)
                print(f"Opening: JP={qa_jp['frames']}, ES={qa_es['frames']} frames; "
                      f"delta={(qa_es['frames'] - qa_jp['frames']) / 24:+.6f} s", flush=True)
                if opening == "conservar-base":
                    evidence["preserved_pair"] = comprobar_opening_base(root, base, state)
                    plan["pending"].append(evidence)
                    plan["warnings"].append(
                        "OPENING BOMBER PENDIENTE: vídeo op00b y canción op00b conservados "
                        "en japonés como pareja. No se autoriza la sustitución ES con duración distinta."
                    )
                    print("PENDIENTE: se conserva el opening JP completo (vídeo + canción).",
                          flush=True)
                    continue
            # La igualdad de duración continúa siendo obligatoria para cada vídeo emitido.
            proof = comparar_pareja(qa_jp, qa_es)
            plan["video"].append({"target": target, "source": relative, "edition": "bomber",
                                  "before": before_desc, "after": after_desc,
                                  "qa_jp": qa_jp, "qa_es": qa_es, "proof": proof,
                                  "paired_audio": "op00b.SAD" if name == "op00b" else "JP heredado (eyecatch no auditado)"})
    for name, (oldhash, newhash, oldsize, newsize) in CANCIONES.items():
        if name == "op00b" and opening == "conservar-base":
            continue  # No sustituir solo la canción mientras se conserva su vídeo JP.
        target = SOUND_PREFIX + name + ".SAD"
        src = ruta_interna(source.parent / "es", target)
        before, jpinfo = motor.sad(ruta_interna(original, target))
        after, esinfo = motor.sad(src)
        contrato_bytes(before, oldhash, oldsize, "JP " + target)
        contrato_bytes(after, newhash, newsize, "Fuego " + target)
        for key in ("channels", "sample_rate", "codec_flag", "loop", "start_offset"):
            if jpinfo[key] != esinfo[key]:
                raise ValueError(f"{target}: cambia {key}; no se copia")
        # Corroboración independiente con el recurso ya seleccionado para Spark.
        common = SOUND_PREFIX + name[:-1] + "f.SAD"
        inherited = audio_rows[common]
        if inherited.get("state") != "preparado" or inherited["after"]["sha256"] != newhash:
            raise ValueError(f"La canción {target} no coincide con la fuente ES común documentada")
        common_path = ruta_interna(base / "romfs", common)
        contrato_bytes(common_path.read_bytes(), newhash, newsize, "canción ES heredada " + common)
        names = (before[0x20:0x30].split(b"\0", 1)[0], after[0x20:0x30].split(b"\0", 1)[0])
        # Excepción acotada por ruta, pareja de etiquetas Y ambos hashes auditados.
        known_alias = name == "op00b" and names == (b"OP00B.SAD", b"OP00F.SAD")
        if names[0] != names[1] and not known_alias:
            raise ValueError(f"Identidad SADL inesperada {target}: {names!r}; se conserva la base")
        existing = base / "romfs" / target
        current = digest(existing.read_bytes()) if existing.is_file() else oldhash
        comprobar_transicion(current, oldhash, newhash, target)
        plan["audio"].append({"target": target, "source": str(src.resolve()), "before": jpinfo,
                              "after": esinfo, "before_sha256": oldhash, "after_sha256": newhash,
                              "source_size": newsize, "common_es_target": common,
                              "internal_names": [n.decode("ascii", errors="backslashreplace") for n in names],
                              "hash_bound_internal_alias": known_alias, "audio_decoded": False})
    plan["consumer"] = motor.consumidor((base / "romfs" / CRO_PATH).read_bytes())
    return plan


def comprobar_aislamiento(before: dict, after: dict, expected: dict) -> None:
    if set(before) != set(after):
        raise ValueError("Se han añadido o eliminado entradas del archive")
    for name, oldhash in before.items():
        target = expected.get(name, oldhash)
        if after[name] != target:
            raise ValueError(f"Recurso modificado fuera del plan o payload incorrecto: {name}")


def informes_combinados(base: Path, output: Path, plan: dict) -> None:
    """Conserva las filas heredadas; actualiza solo los seis destinos del plan."""
    audio = copy.deepcopy(leer_json(base / "audio.json"))
    videos = copy.deepcopy(leer_json(base / "videos.json"))
    for kind, report in (("audio", audio), ("video", videos)):
        targets = {row["target"] for row in plan[kind]}
        rows = [r for r in report["rows"] if r["target"] not in targets]
        for item in plan[kind]:
            row = {"target": item["target"], "source": item["source"], "edition": "bomber",
                   "source_editions": ["bomber"], "before": item["before"], "after": item["after"]}
            if kind == "audio":
                row.update(state="preparado", category="cancion",
                           official_internal_name_alias=item["hash_bound_internal_alias"])
            else:
                row.update(state="preparado_video_DAT_JP_preservado", frames=item["proof"]["frames"])
            rows.append(row)
        report["rows"] = sorted(rows, key=lambda r: r["target"])
        report["pending"] = [r for r in report.get("pending", []) if r["target"] not in targets]
        state = "preparado" if kind == "audio" else "preparado_video_DAT_JP_preservado"
        report["selected"] = sum(r.get("state") == state for r in rows)
        report["runtime_verified"] = False
        if kind == "video":
            report["compatible"] = len(rows)
            report["subtitle_localized"] = False
            report["audio_sync_runtime_verified"] = False
        for omission in plan.get("pending", []):
            excluded = omission["audio_target"] if kind == "audio" else omission["target"]
            if excluded in targets or any(r["target"] == excluded for r in rows):
                raise ValueError("El opening pendiente figura también como preparado")
            report["pending"] = [r for r in report["pending"] if r["target"] != excluded]
            report["pending"].append({
                "target": excluded, "reason": omission["reason"],
                "paired_video": omission["target"], "paired_audio": omission["audio_target"],
                "frames_jp": omission["frames_jp"], "frames_es": omission["frames_es"],
                "delta_seconds_es_menos_jp": omission["delta_seconds_es_menos_jp"],
                "state": "JP_conservado_no_localizado_por_este_complemento",
            })
        report["extension_bomber"] = {"targets": sorted(targets), "runtime_verified": False,
                                      "opening_policy": plan["opening_policy"],
                                      "pending": plan.get("pending", []),
                                      "warnings": list(plan["warnings"])}
        escribir_json(output / ("audio.json" if kind == "audio" else "videos.json"), report)


def huellas_paquete(motor: Motor) -> dict:
    paths = [Path(__file__), Path(__file__).with_name("bomber_video_qa.py"),
             Path(__file__).parent.parent / "bomber_medios_v11.py"]
    return {p.name: motor.huella(p.resolve()) for p in paths}


def preparar(root: Path, base: Path, source: Path, output: Path, *, motor: Motor | None = None,
             decoder: Callable = decodificar, opening: str = "estricto") -> dict:
    motor = motor or motor_real()
    if output.exists():
        raise FileExistsError("Candidata de salida existente: no se sobrescribe; usa verificar o ejecutar")
    if output.is_relative_to(base) or base.is_relative_to(output):
        raise ValueError("La salida y la base no pueden contenerse entre sí")
    state = comprobar_base(root, base, motor)
    overlay_bytes = sum(p.stat().st_size for p in (base / "romfs").rglob("*") if p.is_file())
    needed = (base / "archive.fa").stat().st_size + overlay_bytes + 8 * 1024 ** 3 + 64 * 1024 ** 2
    if shutil.disk_usage(root).free < needed:
        raise ValueError(f"Faltan espacio para candidata y temporales: se requieren aproximadamente {needed / 1024**3:.1f} GiB libres")
    source_snapshot = motor.huella(source)
    cache = root / "work/ie3/shared/bomber_media_qa/cache"
    plan = planificar(root, base, source, state, motor, cache, decoder=decoder, opening=opening)
    validar_politica_plan(root, base, state, plan)
    # Nada grande se copia antes de superar las comprobaciones anteriores.
    exigir_huella(motor.huella(source), source_snapshot, "archive oficial Fuego durante el plan")
    comprobar_protegidos(state["revision"], motor)
    output.mkdir(parents=True)
    escribir_json(output / "medios_bomber.json", plan)
    shutil.copytree(base / "romfs", output / "romfs")  # Copia real; no enlaces duros.
    shutil.copyfile(base / "archive.fa", output / "archive.fa")
    payloads = {}
    with motor.archivo(source) as fuego:
        for row in plan["video"]:
            data = fuego.read(row["source"])
            contrato_bytes(data, row["after"]["sha256"], row["after"]["bytes"], row["source"])
            if state["inventory"][row["target"]] != digest(data):
                payloads[row["target"]] = data
    if payloads:
        motor.repack(output / "archive.fa", payloads)
    external = dict(state["revision"]["external_romfs"])
    for row in plan["audio"]:
        src, dst = Path(row["source"]), ruta_interna(output / "romfs", row["target"])
        contrato_bytes(src.read_bytes(), row["after_sha256"], row["source_size"], row["source"])
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        external[row["target"]] = {"sha256": row["after_sha256"], "size": row["source_size"],
                                   "source": motor.huella(src)}
    with motor.archivo(output / "archive.fa") as arc:
        after = inventario(arc)
    expected = {r["target"]: r["after"]["sha256"] for r in plan["video"]}
    comprobar_aislamiento(state["inventory"], after, expected)
    informes_combinados(base, output, plan)
    revision = {
        "schema": SCHEMA, "label": ("Fase 5 + medios Bomber — "
        + ("opening JP conservado — " if opening == "conservar-base" else "")
        + "pendiente de validación manual"),
        "runtime_verified": False, "complete_spanish_localization": False,
        "reference": motor.huella(base / "archive.fa"),
        "reference_manifest": motor.huella(base / "manifest.json"),
        "archive": motor.huella(output / "archive.fa"), "cro": motor.huella(output / "romfs" / CRO_PATH),
        "cro_patches": state["revision"]["cro_patches"],
        "protected_code": state["revision"]["protected_code"], "protected_hashes_match": True,
        "protected_fonts": {p: {"before": state["inventory"][p], "after": after[p]}
                            for p in after if p.startswith("font/")},
        "resources_before": state["inventory"], "resources_after": after,
        "changed_resources": [p for p in after if after[p] != state["inventory"][p]],
        "emitted_payloads": expected, "external_romfs": external,
        "dialogue_source": state["revision"].get("dialogue_source"),
        "table_consumers": state["revision"].get("table_consumers", {}),
        "media_base": {"candidate": str(base), "snapshots": state["snapshot"]},
        "bomber_source": source_snapshot, "media_plan": motor.huella(output / "medios_bomber.json"),
        "extension_code": huellas_paquete(motor),
        "media_reports": {n: motor.huella(output / n) for n in ("audio.json", "videos.json")},
        "warnings": list(plan["warnings"]), "opening_policy": opening,
        "media_pending": copy.deepcopy(plan["pending"]),
    }
    escribir_json(output / "revision.json", revision)
    return verificar(root, output, motor=motor)


def verificar(root: Path, candidate: Path, *, motor: Motor | None = None) -> dict:
    motor = motor or motor_real()
    revision = leer_json(candidate / "revision.json")
    if revision.get("schema") != SCHEMA:
        raise ValueError("Esta CLI solo verifica candidatas del complemento Bomber, no otras fases")
    base = Path(revision["media_base"]["candidate"])
    for name, info in revision["media_base"]["snapshots"].items():
        exigir_huella(motor.huella(base / name), info, "base heredada " + name)
    for name, info in revision["extension_code"].items():
        exigir_huella(motor.huella(Path(info["path"])), info, "código de complemento " + name)
    state = comprobar_base(root, base, motor)
    if revision["reference_manifest"] != motor.huella(base / "manifest.json"):
        raise ValueError("Referencia de build distinta de la base")
    exigir_huella(motor.huella(base / "archive.fa"), revision["reference"], "archive base")
    comprobar_protegidos(revision, motor)
    if revision["protected_code"] != state["revision"]["protected_code"] or revision["cro_patches"] != state["revision"]["cro_patches"]:
        raise ValueError("Protecciones o parches heredados fueron sustituidos")
    for name, info in revision["media_reports"].items():
        exigir_huella(motor.huella(candidate / name), info, "informe combinado " + name)
    exigir_huella(motor.huella(candidate / "archive.fa"), revision["archive"], "archive nuevo")
    exigir_huella(motor.huella(candidate / "romfs" / CRO_PATH), revision["cro"], "CRO nuevo")
    if revision["cro"]["sha256"] != state["revision"]["cro"]["sha256"]:
        raise ValueError("El complemento no permite modificar el CRO")
    exigir_huella(motor.huella(candidate / "medios_bomber.json"), revision["media_plan"], "plan")
    plan = leer_json(candidate / "medios_bomber.json")
    opening = validar_politica_plan(root, base, state, plan)
    if (revision.get("opening_policy") != opening
            or revision.get("media_pending") != plan["pending"]
            or revision.get("warnings") != plan["warnings"]):
        raise ValueError("La revisión y el plan discrepan sobre el opening pendiente")
    expected_targets = {MOVIE_PREFIX + n + ".moflex" for n in VIDEOS
                        if not (n == "op00b" and opening == "conservar-base")}
    if len(plan["video"]) != len(expected_targets) or {r["target"] for r in plan["video"]} != expected_targets:
        raise ValueError("El plan de vídeos no coincide con los destinos de su política")
    expected = {}
    for row in plan["video"]:
        name = PurePosixPath(row["target"]).stem
        oldhash, newhash, _, _ = VIDEOS[name]
        if row["source"] != "es/" + row["target"] or row["before"]["sha256"] != oldhash or row["after"]["sha256"] != newhash:
            raise ValueError("Correspondencia de vídeo alterada")
        validar_resultado(row["qa_jp"], oldhash)
        validar_resultado(row["qa_es"], newhash)
        if row["proof"] != comparar_pareja(row["qa_jp"], row["qa_es"]):
            raise ValueError("Prueba temporal del vídeo emitido alterada")
        expected[row["target"]] = newhash
    with motor.archivo(candidate / "archive.fa") as arc:
        actual = inventario(arc)
        for row in plan["video"]:
            if motor.descriptor(arc.read(row["target"])) != row["after"]:
                raise ValueError("Descriptor/hash final de vídeo diferente")
    comprobar_aislamiento(state["inventory"], actual, expected)
    if actual != revision["resources_after"] or revision["resources_before"] != state["inventory"]:
        raise ValueError("Inventarios declarados no corresponden a la transición")
    expected_audio = {SOUND_PREFIX + n + ".SAD" for n in CANCIONES
                      if not (n == "op00b" and opening == "conservar-base")}
    if len(plan["audio"]) != len(expected_audio) or {r["target"] for r in plan["audio"]} != expected_audio:
        raise ValueError("Plan de canciones diferente de los destinos de su política")
    inherited = state["revision"]["external_romfs"]
    if set(revision["external_romfs"]) != set(inherited) | expected_audio:
        raise ValueError("Se ha añadido/eliminado audio fuera de los dos destinos")
    if ficheros_overlay(candidate / "romfs") != set(revision["external_romfs"]) | {CRO_PATH}:
        raise ValueError("Overlay final contiene archivos no inventariados o le faltan archivos")
    for relative, info in revision["external_romfs"].items():
        actual_info = motor.huella(ruta_interna(candidate / "romfs", relative))
        exigir_huella(actual_info, info, "overlay " + relative)
        if relative not in expected_audio:
            exigir_huella(actual_info, inherited[relative], "medio heredado " + relative)
    # Reinspección real de SADL, hash y etiquetas internas después de copiar.
    for row in plan["audio"]:
        name = PurePosixPath(row["target"]).stem
        _, newhash, _, newsize = CANCIONES[name]
        data, info = motor.sad(ruta_interna(candidate / "romfs", row["target"]))
        contrato_bytes(data, newhash, newsize, row["target"])
        if info != row["after"]:
            raise ValueError("La cabecera SADL final difiere de la inspección de su fuente")
    motor.consumidor((candidate / "romfs" / CRO_PATH).read_bytes())
    # No se finge reejecutar el verificador textual: todos sus bytes son idénticos
    # a una base cuya evidencia está ligada por hashes y reextraída arriba.
    result = {
        "schema": SCHEMA, "archive": revision["archive"], "cro": revision["cro"],
        "no_truncations_accepted": True,
        "text_proof": "herencia_de_base_verificada_mas_identidad_de_todo_recurso_no_multimedia",
        "base_verification": state["snapshot"]["verification.json"],
        "all_archive_entries_verified": len(actual),
        "non_media_resources_byte_identical": True, "cro_unchanged": True,
        "external_media_verified": len(revision["external_romfs"]),
        "bomber_video_targets": len(expected_targets), "bomber_song_targets": len(expected_audio),
        "runtime_verified": False, "subtitle_localized": False,
        "audio_decoded": False, "audio_sync_runtime_verified": False,
        "warnings": list(plan["warnings"]), "opening_policy": opening,
        "media_pending": copy.deepcopy(plan["pending"]),
        "all_requested_bomber_media_integrated": not plan["pending"],
    }
    dest = candidate / "verification.json"
    if (candidate / "manifest.json").exists():
        # Nunca invalidar el fingerprint usado por una ROM ya construida.
        if not dest.is_file() or leer_json(dest) != result:
            raise ValueError("La verificación cambiaría una candidata ya construida; no se sobrescribe")
    else:
        escribir_json(dest, result)
    return result
