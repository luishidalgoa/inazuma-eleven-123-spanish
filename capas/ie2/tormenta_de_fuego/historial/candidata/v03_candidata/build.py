"""IE2 Fuego v03 · paso 2: candidata probe_ie2_v03 = probe_ie2_v02 + tandas de texto v03 (#70, #71, #72).

Mismo envoltorio que v02 (work/ie2/tormenta_de_fuego/capas/dialogo/dialogo/build.py): nucleo.construir.candidata
con RUTA_MCH apuntando a inazuma2/.../eve.pk{h,b}; el mch de IE2 se reempaqueta antes con `_reempaquetar`
y entra como capa de ficheros. No se edita nada de tools/. Los gráficos v03 (otra tanda) NO entran.

Capas de ficheros (la última gana; ninguna repite fichero, se comprueba):
  work/ie2/shared/capas/historial/nombres/v03_textos/{nombres,tablas_a,tablas_b}/extra, extra_mch (mch reempaquetado)
CRO: ina_main1.cro de probe_ie2_v02 (sin cambios) + ina_main2.cro de textos/cro/romfs/cro.
Uso: python -X utf8 build.py
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[6]
sys.path.insert(0, str(ROOT / 'work/ie2/shared/capas/historial/nombres/v03_textos'))
import comun_v03 as K  # noqa: E402
from ie123kit.nucleo.construir import candidata as C  # noqa: E402

M = K.M
TEXTOS = ROOT / 'work/ie2/shared/capas/historial/nombres/v03_textos'
BASE_DIR = M.CAND / 'probe_ie2_v02'
SALIDA_DIR = M.CAND / 'probe_ie2_v03'
SALIDA = SALIDA_DIR / 'archive.fa'
EXTRA_MCH = HERE / 'extra_mch'
CAPAS = [TEXTOS / 'nombres/extra', TEXTOS / 'tablas_a/extra', TEXTOS / 'tablas_b/extra']
CRO2 = TEXTOS / 'cro/romfs/cro/ina_main2.cro'
# Conflicto: tablas_a y tablas_b escriben logic/gamerule.dat. Gana tablas_b (más texto NDS literal:
# «¡Juega un partidillo!», «¡Que no te metan gol!», «¡Mete el primer gol!»); la copia de tablas_a se excluye.
EXCLUIR = {(TEXTOS / 'tablas_a/extra', 'inazuma2/data_iz/logic/gamerule.dat')}
CAPA_TABLAS = HERE / 'extra_tablas'


def sha(p):
    with open(p, 'rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    base = BASE_DIR / 'archive.fa'
    if CAPA_TABLAS.exists():
        shutil.rmtree(CAPA_TABLAS)
    for c in CAPAS:
        for p in (c.rglob('*') if c.is_dir() else []):
            rel = p.relative_to(c).as_posix()
            if p.is_file() and (c, rel) not in EXCLUIR:
                dst = CAPA_TABLAS / rel
                assert not dst.exists(), f'fichero en varias capas: {rel}'
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(p, dst)
    capas = [CAPA_TABLAS]
    vistos = Counter(p.relative_to(c).as_posix() for c in capas for p in c.rglob('*') if p.is_file())
    dobles = [k for k, v in vistos.items() if v > 1]
    assert not dobles, f'ficheros en varias capas: {dobles}'
    assert not any(k.startswith(('inazuma2/data_iz/script/eve.', 'inazuma2/data_iz/script/mch.', 'font/'))
                   for k in vistos), 'una capa de tablas no puede traer eve/mch ni fuentes BCFNT'
    b = M.Archivo(base)
    if EXTRA_MCH.exists():
        shutil.rmtree(EXTRA_MCH)
    prep = C._ssd_preparados(HERE / 'events_mch')
    rep_mch = []
    if prep:
        pkh, pkb, rep_mch = C._reempaquetar(b.arc, prep, M.PK_MCH)
        for rel, datos in zip(M.PK_MCH, (pkh, pkb)):
            dst = EXTRA_MCH / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(datos)
        capas.append(EXTRA_MCH)
    cros = [BASE_DIR / 'romfs/cro/ina_main1.cro']
    if CRO2.is_file():
        cros.append(CRO2)
    if SALIDA_DIR.exists():
        shutil.rmtree(SALIDA_DIR)
    antes = C.RUTA_MCH
    C.RUTA_MCH = M.PK_EVE
    try:
        rep = C.construir(base, SALIDA, capas=capas, cro=cros,
                          aportaciones=[{'objetivo': 'ie2_tormenta_textos_v03', 'eventos': {'mch': HERE / 'events'}}])
    finally:
        C.RUTA_MCH = antes
    rep['nota_ie2'] = ('events_mch = inazuma2/data_iz/script/eve.pk{h,b} (RUTA_MCH redirigida); mch de IE2 '
                       'reempaquetado en extra_mch (work/ie2/tormenta_de_fuego/capas/historial/candidata/v03_candidata/build.py)')
    rep['base_ie2'] = 'probe_ie2_v02'
    rep['capas_v03'] = [str(c) for c in capas]
    rep['mch_ie2'] = rep_mch
    SALIDA.with_suffix('.build.json').write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding='utf-8')
    print('base', rep['base_sha256'])
    print('archive', rep['archive_sha256'], 'reemplazos', rep['archive_replacements'],
          'eve', len(rep['events_mch']), 'mch', len(rep_mch), 'cros', [c['nombre'] for c in rep['cros']])


if __name__ == '__main__':
    main()
