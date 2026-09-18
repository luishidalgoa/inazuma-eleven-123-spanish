"""Validación de Fuego v21/tutorial: extra/MASTutorial.SPF_ == paquete NDS ES y compatible con el japonés.
Uso: python -X utf8 work/ie2/tormenta_de_fuego/capas/v21/tutorial/validate.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import apply as A  # noqa: E402


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    nuevo = A.SALIDA.read_bytes()
    fallos = []
    if nuevo != A.FUENTE.read_bytes():
        fallos.append('extra distinto del paquete NDS ES')
    fallos += A.comprobar(A.FaArchive(str(A.BASE)).read(A.RUTA), nuevo)
    en = A.sfp(A.lz10.decompress(nuevo))
    if len(en) != 9:
        fallos.append(f'{len(en)} entradas, se esperaban 9')
    sal = dict(ok=not fallos, fallos=fallos, entradas=list(en))
    (HERE / 'validacion.json').write_text(json.dumps(sal, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(sal, ensure_ascii=False, indent=1))
    sys.exit(0 if not fallos else 1)


if __name__ == '__main__':
    main()
