"""Static verification of a layered IE1 candidate against its base candidate.

Every entry provided by a layer must match that layer (later layers win); every
other archive entry, including fonts, must be byte-identical to the base. Only
staged SSD events may differ after decompression, and the CRO may differ only in
the declared literal slots. The v20 typography lock must pass.

Example:
  python tools/verify_candidate.py --base work/shared/candidatas/probe_ie1_v29 --candidate work/shared/candidatas/probe_ie1_v30 \
      --layer work/ie1/legacy/menu_revision/extra --layer work/ie1/legacy/submenu_revision/extra
"""
import argparse
import hashlib
import json
from pathlib import Path

from ie123kit.nucleo.config.congelados import preparar
from ie123kit.nucleo.config.raiz import find_root

ROOT = find_root()
preparar(ROOT)
from dialogue_lock import validate  # noqa: E402
from build_ie1_probe import layout  # noqa: E402
from ie123kit.nucleo.contenedores.fa import FaArchive  # noqa: E402,F401
from ie123kit.nucleo.eventos.packnum import parse_index  # noqa: E402,F401
from ie123kit.nucleo.compresion.lz10 import decompress  # noqa: E402,F401
from ie123kit.nucleo.errores import ValidacionError  # noqa: E402
from ie123kit.nucleo.validar.candidata import sha256_fichero as digest  # noqa: E402,F401
from ie123kit.ie1.verificar import EVE, verificar_candidata  # noqa: E402,F401


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', type=Path, required=True)
    ap.add_argument('--candidate', type=Path, required=True)
    ap.add_argument('--layer', type=Path, action='append', default=[])
    ap.add_argument('--events', type=Path, help='directory of staged <event>.ssd files')
    ap.add_argument('--literals', type=Path, help='JSON with entries[offset,capacity] allowed to differ in the CRO')
    args = ap.parse_args()

    if (ROOT / 'work/probe_ie1_v14_inputs/extra_ascii').exists():  # capa antigua de v14, ya no se conserva
        validate(True, ROOT / 'work/probe_ie1_v14_inputs/extra_ascii', layout)
    try:
        report = verificar_candidata(args.base, args.candidate, args.layer, args.events, args.literals)
    except ValidacionError as exc:
        raise SystemExit(exc.detalle)
    (args.candidate / 'verify.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
