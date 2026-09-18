"""IE2 v14 · candidata probe_ie2_v14 = probe_ie2_v10 + eventos IE2 de esta capa + ina_main2.cro parcheada.

- archive.fa: el de probe_ie2_v10 con SOLO el PackNum inazuma2 eve reempaquetado (candidata._reempaquetar,
  como el build.py de Fuego v10) con 22500101 y 22500102 de ie2/events.
- romfs/: copia del romfs de probe_ie2_v10 (SAD IE1/IE2 y ina_main1.cro), con ina_main2.cro sustituida
  por la parcheada de romfs/cro.
probe_ie2_v10 no se toca. No instala nada.
Uso: python -X utf8 work/ie2/shared/capas/v14/ancho_dialogo/build.py
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[5]
sys.path.insert(0, str(ROOT / 'tools/src'))
from ie123kit.nucleo.construir import candidata as C  # noqa: E402
from ie123kit.nucleo.contenedores.fa import FaArchive  # noqa: E402

W = ROOT / 'work'
V10 = W / 'shared/candidatas/probe_ie2_v10'
BASE = V10 / 'archive.fa'
SALIDA_DIR = W / 'shared/candidatas/probe_ie2_v14'
SALIDA = SALIDA_DIR / 'archive.fa'
EVENTOS = HERE / 'ie2/events'
CRO2 = HERE / 'romfs/cro/ina_main2.cro'
PK_EVE = ('inazuma2/data_iz/script/eve.pkh', 'inazuma2/data_iz/script/eve.pkb')


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    assert SALIDA_DIR != V10
    if SALIDA_DIR.exists():
        shutil.rmtree(SALIDA_DIR)
    arc = FaArchive(str(BASE))
    tmp = Path(tempfile.mkdtemp(prefix='ie2_v14_'))
    try:
        extra = tmp / 'extra_eventos'
        pkh, pkb, rep_ev = C._reempaquetar(arc, C._ssd_preparados(EVENTOS), PK_EVE)
        for rel, b in zip(PK_EVE, (pkh, pkb)):
            (extra / rel).parent.mkdir(parents=True, exist_ok=True)
            (extra / rel).write_bytes(b)
        del arc
        rep = C.construir(BASE, SALIDA, capas=[extra],
                          cro=[V10 / 'romfs/cro/ina_main1.cro', CRO2])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    # romfs de v10 (SAD y demás), sin pisar las CRO que ya dejó construir
    copiados = 0
    for p in sorted((V10 / 'romfs').rglob('*')):
        rel = p.relative_to(V10 / 'romfs')
        if p.is_file() and rel.parts[0] != 'cro':
            dst = SALIDA_DIR / 'romfs' / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(p, dst)
            copiados += 1
    cro_out = SALIDA_DIR / 'romfs/cro'
    assert sorted(x.name for x in cro_out.iterdir()) == ['ina_main1.cro', 'ina_main2.cro']
    assert sha(cro_out / 'ina_main2.cro') == sha(CRO2)
    assert sha(cro_out / 'ina_main1.cro') == sha(V10 / 'romfs/cro/ina_main1.cro')
    rep['events_repack'] = {'ie2_eve': rep_ev}
    rep['base_v10'] = str(BASE)
    rep['romfs_v10_copiados'] = copiados
    rep['sha256'] = {'archive.fa': rep['archive_sha256'],
                     'romfs/cro/ina_main1.cro': sha(cro_out / 'ina_main1.cro'),
                     'romfs/cro/ina_main2.cro': sha(cro_out / 'ina_main2.cro')}
    SALIDA.with_suffix('.build.json').write_text(json.dumps(rep, ensure_ascii=False, indent=2, default=str),
                                                 encoding='utf-8')
    print(json.dumps(dict(sha256=rep['sha256'], reemplazos=rep['archive_replacements'], romfs=copiados,
                          eventos=rep_ev), ensure_ascii=False, indent=1, default=str)[:3000])


if __name__ == '__main__':
    sys.exit(main())
