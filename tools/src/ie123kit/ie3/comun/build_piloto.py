"""ROM piloto con CRO congelado y comprobación de recursos dentro de la ROM."""

import argparse
import json
import shutil
import tempfile
from pathlib import Path

from ie123kit.ie3.comun.b123 import B123Archive
from ie123kit.ie3.comun.cobertura import huella, sha
from ie123kit.ie3.comun.rom import prepare_romfs
from ie123kit.nucleo.config.herramientas import exigir
from ie123kit.nucleo.config.raiz import find_root
from ie123kit.nucleo.construir.rom import build_3ds


def construir(candidate, visual_manifest, output, integration=False, revision=False):
    if integration and revision:
        raise ValueError("seleccionar una sola transición")
    emission_manifest = candidate / ("revision.json" if revision else "integration.json" if integration else "pilot.json")
    pilot = json.loads(emission_manifest.read_text(encoding="utf-8"))
    reference = json.loads(visual_manifest.read_text(encoding="utf-8"))
    if output.exists() or (candidate / "manifest.json").exists():
        raise ValueError("salida existente: no sobrescribir")
    if not integration and pilot["reference"]["sha256"] != reference["archive"]["sha256"]:
        raise ValueError("el piloto no deriva de la referencia visual indicada")
    if integration:
        # La fase 3 parte del piloto aprobado, que a su vez deriva de v7.
        approved_manifest = Path(pilot["runtime_approval_scope"]["manifest"]["path"])
        if huella(approved_manifest)["sha256"] != pilot["runtime_approval_scope"]["manifest"]["sha256"]:
            raise ValueError("manifiesto aprobado modificado")
        approved = json.loads(approved_manifest.read_text(encoding="utf-8"))
        if approved["archive"]["sha256"] != pilot["reference"]["sha256"]:
            raise ValueError("transición no deriva del piloto aprobado")
        if approved["visual_reference"]["sha256"] != huella(visual_manifest)["sha256"]:
            raise ValueError("referencia tipográfica diferente de la aprobada")
    if huella(candidate / "archive.fa")["sha256"] != pilot["archive"]["sha256"]:
        raise ValueError("archive del piloto modificado después de validarlo")
    cro = visual_manifest.parent / "romfs/cro/ina_main3ogre.cro"
    crohash = huella(cro)
    if crohash["sha256"] != reference["cro"]["sha256" if revision else "sha256_after"]:
        raise ValueError("CRO de referencia no coincide")
    root = find_root()
    base = root / "work/shared/base_3ds"
    if shutil.disk_usage(candidate).free < 8 * 1024**3:
        raise ValueError("se requieren 8 GiB libres para ROM y temporales de lectura")
    dst = candidate / "romfs/cro/ina_main3ogre.cro"
    dst.parent.mkdir(parents=True, exist_ok=True)
    names_patch = None
    if revision:
        if huella(visual_manifest) != pilot["reference_manifest"]:
            raise ValueError("manifiesto de referencia modificado")
        if huella(dst) != pilot["cro"]:
            raise ValueError("CRO integrado modificado después de comprobarlo")
        if not pilot["protected_hashes_match"]:
            raise ValueError("protecciones de la revisión no satisfechas")
        verification = json.loads((candidate / "verification.json").read_text(encoding="utf-8"))
        if verification["archive"] != pilot["archive"] or verification["cro"] != pilot["cro"]:
            raise ValueError("verificación independiente desactualizada")
        if not verification["no_truncations_accepted"]:
            raise ValueError("verificación de integridad incompleta")
        for record in pilot["protected_code"].values():
            if huella(Path(record["path"])) != record:
                raise ValueError("código protegido cambió antes de construir")
        names_patch = pilot["cro_patches"]
    elif integration:
        from ie123kit.ie3.comun.presentacion_nombres import parchear_font8_ie3
        data, names_patch = parchear_font8_ie3(cro.read_bytes())
        dst.write_bytes(data)
    else:
        shutil.copyfile(cro, dst)
    external = pilot.get("external_romfs", {})
    for relative, expected in external.items():
        path = candidate / "romfs" / relative
        if not path.resolve().is_relative_to((candidate / "romfs").resolve()):
            raise ValueError("overlay externo fuera de RomFS")
        actual = huella(path)
        if (actual["sha256"], actual["size"]) != (expected["sha256"], expected["size"]):
            raise ValueError(f"overlay externo modificado: {relative}")
    result = {
        "label": pilot["label"],
        "runtime_verified": False,
        "visual_reference": huella(visual_manifest),
        "emission_manifest": huella(emission_manifest),
        "archive": pilot["archive"],
        "cro": huella(dst),
        "cro_visual_reference": crohash,
        "names_patch": names_patch,
        "exefs": huella(base / "exefs.bin"),
        "rom": build_3ds(candidate, output),
        "readback": {},
    }
    if revision:
        result["independent_verification"] = huella(candidate / "verification.json")
    # Reextraer el artefacto final, no confiar solamente en intermedios.
    with tempfile.TemporaryDirectory(prefix="ie3_fase2_readback_") as td:
        temporary = Path(td)
        romfs = prepare_romfs(output, temporary, exigir("3dstool"), None, print)
        for relative, expected in (
            ("archive.fa", pilot["archive"]["sha256"]),
            ("cro/ina_main3ogre.cro", result["cro"]["sha256"]),
        ):
            actual = huella(romfs / relative)
            if actual["sha256"] != expected:
                raise ValueError(f"ROM readback difiere: {relative}")
            result["readback"][relative] = {"sha256": actual["sha256"], "size": actual["size"]}
        for relative, expected in external.items():
            actual = huella(romfs / relative)
            if (actual["sha256"], actual["size"]) != (expected["sha256"], expected["size"]):
                raise ValueError(f"medio externo ROM readback difiere: {relative}")
        result["readback"]["external_media_verified"] = len(external)
        if huella(temporary / "exefs.bin")["sha256"] != result["exefs"]["sha256"]:
            raise ValueError("ExeFS modificado en ROM")
        with B123Archive(romfs / "archive.fa") as arc:
            actual = {e.path.decode(): sha(arc.read(e)) for e in arc.entries}
        if actual != pilot["resources_after"]:
            raise ValueError("inventario interno ROM no coincide con piloto")
        result["readback"]["all_archive_entries_verified"] = len(actual)
        result["readback"]["exefs_unchanged"] = True
    (candidate / "manifest.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--candidate", type=Path, required=True)
    p.add_argument("--visual-manifest", type=Path, required=True)
    p.add_argument("--rom", type=Path, required=True)
    p.add_argument("--integrated", action="store_true")
    p.add_argument("--revision", action="store_true", help="revisión validada con CRO ya compuesto; no rehacer parches")
    a = p.parse_args(argv)
    result = construir(a.candidate.resolve(), a.visual_manifest.resolve(), a.rom.resolve(), a.integrated, a.revision)
    print(json.dumps({k: result[k] for k in ("label", "rom", "readback")}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
