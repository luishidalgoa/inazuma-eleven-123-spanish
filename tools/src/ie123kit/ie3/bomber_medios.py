"""Construye Fase 5 + cuatro vídeos y dos canciones de Bomber sin reemitir texto.

Ejecutar desde el repositorio. Solo usa Python/herramientas y recursos locales.
No hace llamadas de IA, git push, instalaciones ni borrados de candidatas.
"""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import sys
import traceback
from pathlib import Path

from .comun.bomber_medios_integracion import (
    SCHEMA,
    exigir_huella,
    huella_local,
    leer_json,
    preparar,
    verificar,
)
from .comun.bomber_video_qa import escribir_json

DEFAULT_BASE = "work/ie3/shared/candidatas/spark_ogre_revision_fase5"
DEFAULT_OUTPUT = "work/ie3/shared/candidatas/spark_bomber_ogre_fase5_medios"
DEFAULT_ROM = "work/build/inazuma123_fase5_con_bomber.3ds"


class _Tee:
    def __init__(self, screen, logfile):
        self.screen, self.logfile = screen, logfile

    def write(self, text):
        self.screen.write(text)
        self.logfile.write(text)
        self.logfile.flush()
        return len(text)

    def flush(self):
        self.screen.flush()
        self.logfile.flush()

    def isatty(self):
        return False


def _inside_work(root: Path, path: str, label: str) -> Path:
    value = (root / path).resolve()
    if not value.is_relative_to((root / "work").resolve()):
        raise ValueError(f"{label} debe estar dentro de work/ del repositorio")
    return value


def _free_output(path: Path) -> Path:
    if not path.exists():
        return path
    for i in range(2, 10000):
        candidate = path.with_name(f"{path.stem}_{i}{path.suffix}")
        if not candidate.exists():
            return candidate
    raise FileExistsError("Demasiadas salidas existentes; no se sobrescribe ninguna")


def ejecutar(root: Path, args) -> None:
    from ie123kit.ie3.comun.perfiles import cargar_perfil

    base = _inside_work(root, args.base_candidate, "Base")
    output = _inside_work(root, args.salida, "Salida")
    if not output.is_relative_to((root / "work/ie3/shared/candidatas").resolve()):
        raise ValueError("La candidata nueva debe estar bajo work/ie3/shared/candidatas/")
    if output.is_relative_to(base) or base.is_relative_to(output):
        raise ValueError("La salida debe ser distinta y no estar dentro de la candidata base")
    source = (root / (args.fuente or cargar_perfil("bomber").oficial)).resolve()
    print(f"Base que se conserva: {base}")
    print(f"Fuente Fuego: {source}")
    print(f"Nueva candidata: {output}")
    print("No se cambian diálogos, UI, fuentes, encoder, CRO ni guardados.\n", flush=True)

    if output.exists():
        if not (output / "revision.json").is_file():
            raise ValueError(
                "La carpeta de salida es parcial o ajena (falta revision.json). No se borra. "
                "Conserva el log; para otra salida utiliza --salida con una carpeta NUEVA."
            )
        rev = leer_json(output / "revision.json")
        if rev.get("schema") != SCHEMA or Path(rev["media_base"]["candidate"]).resolve() != base:
            raise ValueError("La carpeta de salida no corresponde a este complemento y esta base")
        exigir_huella(huella_local(source), rev["bomber_source"], "fuente Fuego")
        print("La candidata ya existe: comprobar, sin regenerar ni duplicar archivos...", flush=True)
        result = verificar(root, output)
    else:
        if args.verificar:
            raise FileNotFoundError("No existe la candidata a verificar")
        result = preparar(root, base, source, output)
    print(f"\nVerificación: {result['bomber_video_targets']} vídeos y {result['bomber_song_targets']} canciones destino.")
    print("Los demás recursos son idénticos a la candidata base; sus pendientes se conservan.")
    if args.solo_preparar or args.verificar:
        print(f"Candidata preparada, NO ROM completa: {output}")
        return

    receipt = output / "build_complemento.json"
    manifest_path = output / "manifest.json"
    if receipt.is_file():
        saved = leer_json(receipt)
        exigir_huella(huella_local(manifest_path), saved["manifest"], "manifiesto de ROM existente")
        path = Path(saved["rom"]["path"])
        exigir_huella(huella_local(path), saved["rom"], "ROM existente")
        print(f"\nROM ya creada con estos mismos recursos. Se reutiliza, no se duplica:\n{path}")
        print("PENDIENTE DE PRUEBA MANUAL; no se ha instalado en la consola.")
        return
    if manifest_path.exists():
        raise ValueError(
            "El builder ya creó manifest.json pero falta el recibo del complemento. "
            "No se mueve ni se elimina el manifiesto. Revisa la ROM indicada en ese manifiesto."
        )
    rom = _inside_work(root, args.rom, "ROM de salida")
    if rom.suffix.lower() != ".3ds" or not rom.is_relative_to((root / "work/build").resolve()):
        raise ValueError("La ROM de salida debe ser .3ds y estar bajo work/build/")
    rom.parent.mkdir(parents=True, exist_ok=True)
    rom = _free_output(rom)
    reference = Path(leer_json(output / "revision.json")["reference_manifest"]["path"])
    print(f"\nConstruyendo UNA ROM y reextrayendo el artefacto final:\n{rom}", flush=True)
    # Constructor existente: conserva todas sus comprobaciones y readback.
    from ie123kit.ie3.comun.build_piloto import construir

    construir(output, reference, rom, revision=True)
    saved = {"schema": SCHEMA, "rom": huella_local(rom),
             "manifest": huella_local(manifest_path), "runtime_verified": False}
    escribir_json(receipt, saved)
    print(f"\nROM CONSTRUIDA: {rom}")
    print(f"Tamaño: {saved['rom']['size']:,} bytes")
    print(f"SHA-256: {saved['rom']['sha256']}")
    print("Pendiente de prueba en juego. DAT, bancos y nueve eyecatches de audio no se han localizado aquí.")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-candidate", default=DEFAULT_BASE,
                        help="candidata Fase 5 con revision, verification y manifest coherentes")
    parser.add_argument("--salida", default=DEFAULT_OUTPUT,
                        help="carpeta nueva o candidata de ESTE complemento que se desea reutilizar")
    parser.add_argument("--fuente", help="archive_bz.fa extraído; por defecto el perfil bomber actual")
    parser.add_argument("--rom", default=DEFAULT_ROM)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--solo-preparar", action="store_true", help="no construir los 2 GiB de ROM")
    mode.add_argument("--verificar", action="store_true", help="solo verificar la candidata ya preparada")
    args = parser.parse_args(argv)
    from ie123kit.nucleo.config.raiz import find_root

    root = find_root().resolve()
    logs = root / "work/informes/complemento_bomber"
    logs.mkdir(parents=True, exist_ok=True)
    log = logs / (dt.datetime.now().strftime("%Y%m%d_%H%M%S_%f") + ".log")  # noqa: DTZ005 (hora local para el nombre del registro)
    with log.open("w", encoding="utf-8") as handle, contextlib.redirect_stdout(_Tee(sys.stdout, handle)), \
                contextlib.redirect_stderr(_Tee(sys.stderr, handle)):
        print(f"Log: {log}", flush=True)
        try:
            ejecutar(root, args)
        except (Exception, KeyboardInterrupt):  # noqa: BLE001 (se registra la traza y se sigue)
            traceback.print_exc()
            print("\nDETENIDO. No se ha declarado una nueva ROM válida. Los originales se conservan.")
            print(f"Comparte este log si necesitas revisar el fallo: {log}")
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
