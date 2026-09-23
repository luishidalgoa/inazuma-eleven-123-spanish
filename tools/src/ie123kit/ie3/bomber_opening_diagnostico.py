"""Extrae solo opening JP/ES para diagnosticar; no instala ningún recurso.

Incluye los MOFLEX y SADL originales y los resultados existentes de la caché.
No altera fotogramas, pistas, DAT, candidatas ni manifiestos de construcción.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import uuid
import zipfile
from pathlib import Path

from .comun.bomber_medios_integracion_v11 import (
    CANCIONES,
    MOVIE_PREFIX,
    SOUND_PREFIX,
    VIDEOS,
    contrato_bytes,
    digest,
    leer_json,
    motor_real,
    ruta_interna,
)
from .comun.bomber_video_qa import validar_resultado


def exportar(root: Path, source: Path, *, motor=None) -> Path:
    motor = motor or motor_real()
    original = root / "work/shared/base_3ds/romfs"
    movie = MOVIE_PREFIX + "op00b.moflex"
    song = SOUND_PREFIX + "op00b.SAD"
    buffers = {}
    origins = {}
    with motor.archivo(original / "archive.fa") as jp, motor.archivo(source) as es:
        for tag, archive, key, expected in (
            ("JP", jp, movie, (VIDEOS["op00b"][0], VIDEOS["op00b"][2])),
            ("ES", es, "es/" + movie, (VIDEOS["op00b"][1], VIDEOS["op00b"][3])),
        ):
            data = archive.read(key)
            contrato_bytes(data, *expected, tag + " opening")
            name = f"op00b_{tag}.moflex"
            buffers[name] = data
            origins[name] = {"resource": key, "sha256": digest(data), "bytes": len(data)}
        # DAT es opcional; se extrae solo para análisis, nunca se vacía/copia al mod.
        dat = MOVIE_PREFIX + "txt/op00b.dat"
        for tag, archive, key in (("JP", jp, dat), ("ES", es, "es/" + dat)):
            if archive.exists(key):
                data = archive.read(key)
                name = f"op00b_{tag}.dat"
                buffers[name] = data
                origins[name] = {"resource": key, "sha256": digest(data), "bytes": len(data)}

    for tag, path, expected in (
        ("JP", ruta_interna(original, song), (CANCIONES["op00b"][0], CANCIONES["op00b"][2])),
        ("ES", ruta_interna(source.parent / "es", song), (CANCIONES["op00b"][1], CANCIONES["op00b"][3])),
    ):
        data = path.read_bytes()
        contrato_bytes(data, *expected, tag + " audio")
        name = f"op00b_{tag}.SAD"
        buffers[name] = data
        origins[name] = {"source": str(path), "sha256": digest(data), "bytes": len(data)}

    qa = {}
    cache = root / "work/ie3/shared/bomber_media_qa/cache"
    for tag, hashed in (("JP", VIDEOS["op00b"][0]), ("ES", VIDEOS["op00b"][1])):
        path = cache / (hashed + ".json")
        if path.is_file():
            row = leer_json(path)
            validar_resultado(row, hashed)
            qa[tag] = row
        else:
            qa[tag] = {"state": "sin_QA_previa", "sha256": hashed}
    manifest = {
        "schema": "ie3_opening_export_diagnostic_v1",
        "purpose": "comparar diferencias reales de imagen, audio y duración; no autoriza inserción",
        "source_archive_jp": str(original / "archive.fa"),
        "source_archive_es": str(source), "files": origins, "qa_cache": qa,
        "no_media_modified": True, "runtime_verified": False,
        "warning": "El ZIP contiene recursos originales para análisis privado; no publicarlo en Git.",
    }
    token = dt.datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:8]  # noqa: DTZ005 (hora local para el nombre del registro)
    folder = root / "work/informes/bomber_opening" / token
    folder.mkdir(parents=True, exist_ok=False)
    output = folder / "op00b_originales_para_diagnostico.zip"
    partial = folder / "op00b_originales_para_diagnostico.zip.partial"
    # Solo se escriben ficheros nuevos en el directorio único de diagnóstico.
    with zipfile.ZipFile(partial, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=3) as z:
        for name, data in buffers.items():
            z.writestr(name, data)
        z.writestr("diagnostico.json",
                   json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"))
    if output.exists():
        raise FileExistsError("Salida de diagnóstico ya existente")
    partial.rename(output)
    return output


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fuente", help="archive_bz.fa; por defecto el perfil Bomber")
    args = parser.parse_args(argv)
    try:
        from ie123kit.ie3.comun.perfiles import cargar_perfil
        from ie123kit.nucleo.config.raiz import find_root
        root = find_root().resolve()
        source = (root / (args.fuente or cargar_perfil("bomber").oficial)).resolve()
        output = exportar(root, source)
        print(f"ZIP PARA DIAGNÓSTICO:\n{output}")
        print(f"Tamaño: {output.stat().st_size:,} bytes")
        print("No se ha modificado la ROM, ningún original ni la candidata base.")
        print("Este ZIP contiene los medios originales. Compártelo solo para diagnóstico privado.")
        return 0
    except (Exception, KeyboardInterrupt) as exc:  # noqa: BLE001 (se registra la traza y se sigue)
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
