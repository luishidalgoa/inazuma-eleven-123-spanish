"""Re-exports perezosos de los ficheros congelados v20 (F1.4, T2).

Cada comprobación corre en un subproceso con cwd en la raíz y entorno limpio, para
que ``sys.modules`` no arrastre módulos cargados por otras pruebas.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import textwrap

import pytest

from ie123kit.nucleo.config.raiz import find_root

RAIZ = find_root()


def _ejecutar(codigo: str) -> None:
    entorno = {k: v for k, v in os.environ.items() if not k.startswith("IE123_") and k != "PYTHONPATH"}
    r = subprocess.run([sys.executable, "-X", "utf8", "-c", textwrap.dedent(codigo)], cwd=RAIZ,
                       env=entorno, capture_output=True, text=True, encoding="utf-8", check=False)
    assert r.returncode == 0, r.stdout + r.stderr


def test_identidades():
    _ejecutar("""
        import sys
        from ie123kit.nucleo.texto import tipografia_v20, ancho_completo
        from ie123kit.nucleo.fuentes import glifos
        from ie123kit.nucleo.config.congelados import preparar
        preparar()  # F2.7: los congelados importan nombres planos que ya no son shims
        import build_ie1_probe, dialogue_typography, font_patch, dialogue_lock
        assert tipografia_v20.layout is build_ie1_probe.layout
        assert ancho_completo.encode_fullwidth is dialogue_typography.encode_fullwidth
        assert glifos.PLAN is font_patch.PLAN and glifos.Font is font_patch.Font
        assert glifos.modulo() is font_patch
        assert tipografia_v20.FUENTES_BLOQUEADAS == tuple(dialogue_lock.FONT_HASHES)
        assert tipografia_v20.LAYOUT_HASH == dialogue_lock.LAYOUT_HASH
        texto = 'texto de prueba largo para comprobar el ajuste aprobado de lineas en la caja v20 ' * 3
        assert tipografia_v20.approved_layout(texto) == dialogue_lock.approved_layout(texto, build_ie1_probe.layout)
    """)


def test_carga_perezosa():
    _ejecutar("""
        import sys
        import ie123kit.nucleo.texto.ancho_completo as a
        import ie123kit.nucleo.texto.tipografia_v20
        import ie123kit.nucleo.fuentes.glifos
        import ie123kit.nucleo.config.congelados
        for n in ('dialogue_typography', 'font_patch', 'dialogue_lock', 'build_ie1_probe'):
            assert n not in sys.modules, n
        a.ACCENTS
        assert 'dialogue_typography' in sys.modules
    """)


def test_build_ui_revision_no_importable():
    from ie123kit.nucleo.config import congelados
    with pytest.raises(ValueError):
        congelados.cargar("build_ui_revision")


def test_round_trip_ancho_completo():
    _ejecutar(r"""
        from ie123kit.nucleo.texto.ancho_completo import encode_fullwidth, decode_fullwidth, ACCENTS
        assert len(set(ACCENTS.values())) == len(ACCENTS)
        for x in ['¿Qué pasó, Mark? ¡Vamos!', 'Año 2024: niño, pingüino; 50% (sí).\\nOtra\\flínea %s y %1F',
                  'ÁÉÍÓÚáéíóúñÑü 0123456789 +*/=<>[]{}#&@', '']:
            assert decode_fullwidth(encode_fullwidth(x)) == x, x
    """)


def test_hashes_congelados():
    esperado = {}
    for linea in (RAIZ / "tools/tests/compat/golden/congelados.sha256").read_text(encoding="utf-8").splitlines():
        if linea.strip():
            h, ruta = linea.split(None, 1)
            esperado[ruta.strip()] = h
    assert len(esperado) == 5
    for ruta, h in esperado.items():
        assert hashlib.sha256((RAIZ / ruta).read_bytes()).hexdigest() == h, ruta
