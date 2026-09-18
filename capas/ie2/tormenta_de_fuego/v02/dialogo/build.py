"""IE2 Fuego v02 · paso 4: candidata probe_ie2_v02 = base IE1 (v89, o v88 si v89 no está) + capas IE2.

Capas (la última gana): fuentes IE2 v01, nombre de la sonda v01, diálogo v02 (eve + mch).
Mismo envoltorio que la sonda v01: `ie123kit.nucleo.construir.candidata.construir` con RUTA_MCH
apuntando a inazuma2/.../eve.pk{h,b} durante la llamada (build_ui_revision.py está congelado y fijo a
IE1). El mch de IE2 se reempaqueta antes con el mismo `_reempaquetar` (mismas comprobaciones) y entra
como capa de ficheros. No se edita nada de tools/.

Uso: python -X utf8 build.py --base v89|v88
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys

import comun_ie2 as M
from ie123kit.nucleo.construir import candidata as C

SALIDA = M.CAND / 'probe_ie2_v02/archive.fa'
EXTRA_MCH = M.HERE / 'extra_mch'


def sha(p):
    with open(p, 'rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', choices=['v89', 'v88'], required=True)
    args = ap.parse_args()
    base_dir = M.CAND / f'probe_ie1_{args.base}'
    base = base_dir / 'archive.fa'
    b = M.Archivo(base)
    jp = M.Archivo(M.JP)
    for rel in M.PK_EVE + M.PK_MCH:
        assert b.get(rel) == jp.get(rel), f'la base ya toca {rel}'
    # mch de IE2 -> capa de ficheros
    if EXTRA_MCH.exists():
        shutil.rmtree(EXTRA_MCH)
    prep = C._ssd_preparados(M.HERE / 'events_mch')
    pkh, pkb, rep_mch = C._reempaquetar(b.arc, prep, M.PK_MCH)
    for rel, datos in zip(M.PK_MCH, (pkh, pkb)):
        dst = EXTRA_MCH / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(datos)
    cros = sorted((base_dir / 'romfs/cro').glob('*.cro'))
    antes = C.RUTA_MCH
    C.RUTA_MCH = M.PK_EVE
    try:
        rep = C.construir(base, SALIDA, capas=[M.FUENTES_V01, M.NOMBRE_V01, EXTRA_MCH], cro=cros,
                          aportaciones=[{'objetivo': 'ie2_tormenta_dialogo_v02', 'eventos': {'mch': M.HERE / 'events'}}])
    finally:
        C.RUTA_MCH = antes
    rep['nota_ie2'] = ('events_mch = inazuma2/data_iz/script/eve.pk{h,b} (RUTA_MCH redirigida); '
                       'mch de IE2 reempaquetado en extra_mch (work/ie2/tormenta_de_fuego/capas/v02/dialogo/build.py)')
    rep['base_ie1'] = args.base
    rep['mch_ie2'] = rep_mch
    SALIDA.with_suffix('.build.json').write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding='utf-8')
    print('base', args.base, rep['base_sha256'])
    print('archive', rep['archive_sha256'], 'reemplazos', rep['archive_replacements'],
          'eve2', len(rep['events_mch']), 'mch2', len(rep_mch), 'cros', [c['nombre'] for c in rep['cros']])


if __name__ == '__main__':
    main()
