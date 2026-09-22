"""QA local de MOFLEX con OpenCV: cuenta lecturas reales, no transcodifica.

`read() == False` no distingue por sí solo EOF de todos los errores del backend.
El resultado registra esa limitación: no certifica CRC, idioma ni sincronía.
La caché se liga a los bytes y versión de este comprobador, nunca al nombre solo.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

QA_VERSION = "bomber-opencv-sequential-v1"
LIMITACION = (
    "OpenCV read=False termina la lectura; no prueba por sí solo ausencia de corrupción. "
    "Se comprueban frames decodificados, geometría, fps y pareja JP/ES; "
    "sin verificación de CRC, idioma, subtítulos ni sincronía en juego."
)


def escribir_json(path: Path, value: Any) -> None:
    """Escritura atómica de informes propios, sin sobrescribir originales."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.write("\n")
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)  # Solo nuestro temporal concreto.


def validar_resultado(row: dict, digest: str) -> None:
    """No acepta pruebas inventadas a partir del descriptor ni cero frames."""
    if (
        row.get("qa_version") != QA_VERSION
        or row.get("sha256") != digest
        or row.get("decode") != "sequential_eof"
        or row.get("termination") != "opencv_read_false"
        or type(row.get("frames")) is not int
        or row["frames"] <= 0
        or not isinstance(row.get("fps"), (int, float))
        or not math.isfinite(row["fps"])
        or not math.isclose(row["fps"], 24.0, abs_tol=1e-3)
        or (row.get("width"), row.get("height")) != (240, 320)
        or row.get("runtime_verified") is not False
    ):
        raise ValueError("QA de vídeo ausente, obsoleta o incompatible")
    declared = row.get("declared_frames")
    if declared is not None and declared != row["frames"]:
        raise ValueError("El número declarado y los frames realmente decodificados difieren")


def comparar_pareja(jp: dict, es: dict) -> dict:
    validar_resultado(jp, jp["sha256"])
    validar_resultado(es, es["sha256"])
    if jp["frames"] != es["frames"]:
        raise ValueError(
            f"Cambia la duración: JP={jp['frames']} frames, ES={es['frames']} frames. "
            "No se recorta, estira ni omite la comprobación."
        )
    return {"frames": jp["frames"], "fps": 24, "timeline_counts_match": True,
            "audio_sync_runtime_verified": False, "crc_verified": False}


def decodificar(data: bytes, cache: Path, *, cv: Any = None) -> dict:
    """Usa VideoCapture sobre un temporal privado y libera todos los recursos.

    El parámetro cv permite inyectar un backend simulado en tests. En producción
    se importa cv2 instalado en el MISMO Python que ejecuta la herramienta.
    """
    digest = hashlib.sha256(data).hexdigest()
    cached = cache / (digest + ".json")
    if cached.is_file():
        row = json.loads(cached.read_text(encoding="utf-8"))
        validar_resultado(row, digest)
        return row
    if cv is None:
        try:
            import cv2 as cv
        except ImportError as exc:
            raise RuntimeError(
                "Este Python no tiene OpenCV. La documentación del proyecto lo usa para QA. "
                "Comprueba el entorno; no se instalará nada automáticamente. "
                f'Instalación manual en este intérprete: "{sys.executable}" -m pip install opencv-python'
            ) from exc

    cache.mkdir(parents=True, exist_ok=True)
    # Nombre ASCII corto en TEMP para evitar problemas de backend en Windows.
    with tempfile.TemporaryDirectory(prefix="ie3_bomber_cv_") as tmp:
        movie = Path(tmp) / "video.moflex"
        movie.write_bytes(data)
        cap = cv.VideoCapture(str(movie))
        try:
            if not cap.isOpened():
                raise RuntimeError("OpenCV no puede abrir este MOFLEX; falta backend/codec compatible")
            if hasattr(cv, "CAP_PROP_ORIENTATION_AUTO"):
                cap.set(cv.CAP_PROP_ORIENTATION_AUTO, 0)
            fps = float(cap.get(cv.CAP_PROP_FPS))
            if not math.isfinite(fps) or not math.isclose(fps, 24.0, abs_tol=1e-3):
                raise ValueError(f"OpenCV informa fps incompatibles: {fps}")
            count = float(cap.get(cv.CAP_PROP_FRAME_COUNT))
            declared = None
            if math.isfinite(count) and count > 0:
                if not math.isclose(count, round(count), abs_tol=0.05):
                    raise ValueError(f"Contador de frames no entero: {count}")
                declared = round(count)
            try:
                backend = cap.getBackendName()
            except (AttributeError, RuntimeError):
                backend = "no_informado"
            frames = 0
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                if frame is None or getattr(frame, "size", 0) == 0:
                    raise ValueError("OpenCV devuelve un frame vacío con éxito=True")
                if tuple(frame.shape[:2]) != (320, 240):
                    raise ValueError(f"Geometría decodificada incompatible: {frame.shape}")
                frames += 1
                if frames > 24 * 60 * 60:
                    raise ValueError("Más de una hora decodificada: se detiene por límite de seguridad")
            row = {
                "qa_version": QA_VERSION, "sha256": digest, "bytes": len(data),
                "frames": frames, "fps": fps, "width": 240, "height": 320,
                "declared_frames": declared, "decode": "sequential_eof",
                "termination": "opencv_read_false", "backend": backend,
                "opencv_version": getattr(cv, "__version__", "no_informada"),
                "runtime_verified": False, "crc_verified": False,
                "limitation": LIMITACION,
            }
            validar_resultado(row, digest)
        finally:
            cap.release()
    escribir_json(cached, row)
    return row
