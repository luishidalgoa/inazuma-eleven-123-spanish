"""verify_candidate (shim → ie123kit._legado.verify_candidate) sobre la candidata de referencia.

Sustituye al golden del par probe_ie1_v66/v67 (borradas). Se monta en un temporal una base con la
disposición de candidata (enlaces duros a work/shared/base_3ds/romfs) y la candidata de referencia
(base + capa titulo_logo con build_ui_revision.py); verify.json se escribe en ese temporal.
Del informe se compara todo salvo la ruta absoluta de la candidata.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from ie123kit.nucleo.compat import golden
from ie123kit.nucleo.config.raiz import find_root

pytestmark = pytest.mark.requiere_rom

RAIZ = find_root()
GOLDEN = Path(__file__).resolve().parent / "golden" / "verify_referencia.json"
BASE = RAIZ / golden.BASE_REFERENCIA


def _enlazar(origen: Path, destino: Path) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(origen, destino)
    except OSError:
        shutil.copyfile(origen, destino)


@pytest.mark.skipif(not (BASE / "archive.fa").is_file(), reason=f"falta {golden.BASE_REFERENCIA}/archive.fa")
def test_verify_candidate_igual_al_golden():
    g = json.loads(GOLDEN.read_text(encoding="utf-8"))
    tmp = Path(tempfile.mkdtemp(prefix="ie123_verify_"))
    try:
        base = tmp / "base"
        _enlazar(BASE / "archive.fa", base / "archive.fa")
        _enlazar(BASE / "cro" / "ina_main1.cro", base / "romfs" / "cro" / "ina_main1.cro")
        candidata = tmp / "referencia"
        assert golden._reconstruir(RAIZ, base / "archive.fa", golden.CAPA, candidata / "archive.fa",
                                   base / "romfs" / "cro" / "ina_main1.cro") == 0
        env = dict(os.environ)
        env.pop("IE123_ROOT", None)
        r = subprocess.run([sys.executable, "-X", "utf8", "tools/verify_candidate.py", "--base", str(base),
                            "--candidate", str(candidata), "--layer", f"{golden.CAPA}/extra"],
                           cwd=RAIZ, env=env, capture_output=True, text=True, encoding="utf-8", check=False)
        assert r.returncode == g["returncode"], r.stderr
        assert r.stderr == g["stderr"]
        verify = candidata / "verify.json"
        obtenido = json.loads(verify.read_text(encoding="utf-8")) if verify.is_file() else None
        if obtenido is not None:
            obtenido.pop("candidate", None)
        assert obtenido == g["verify_json"]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
