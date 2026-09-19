"""IE2 v19 · candidata probe_ie2_v18 = probe_ie2_v17 con todos los saltos del diálogo rehechos.

archive.fa: el de v17 con los PackNum inazuma2 eve y mch reempaquetados con ie2/eve y ie2/mch de
esta capa. Nada más cambia: ni CRO, ni sonidos, ni vídeos (los moflex subtitulados ya están en la
base v17 y no se vuelven a superponer).
romfs/: el de v17 tal cual (las dos CRO parcheadas, SAD y voz del título).
No instala nada.
Uso: python -X utf8 work/ie2/shared/capas/dialogo/saltos37/build.py
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
V17 = W / 'shared/candidatas/probe_ie2_v17'
BASE = V17 / 'archive.fa'
SALIDA_DIR = W / 'shared/candidatas/probe_ie2_v18'
SALIDA = SALIDA_DIR / 'archive.fa'
PK = {'eve': ('inazuma2/data_iz/script/eve.pkh', 'inazuma2/data_iz/script/eve.pkb'),
      'mch': ('inazuma2/data_iz/script/mch.pkh', 'inazuma2/data_iz/script/mch.pkb')}


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    if SALIDA_DIR.exists():
        shutil.rmtree(SALIDA_DIR)
    arc = FaArchive(str(BASE))
    tmp = Path(tempfile.mkdtemp(prefix='ie2_v19_'))
    rep_ev = {}
    try:
        extra = tmp / 'extra_eventos'
        for pk, rutas in PK.items():
            pkh, pkb, rep_ev[pk] = C._reempaquetar(arc, C._ssd_preparados(HERE / 'ie2' / pk), rutas)
            for rel, b in zip(rutas, (pkh, pkb)):
                (extra / rel).parent.mkdir(parents=True, exist_ok=True)
                (extra / rel).write_bytes(b)
        del arc
        rep = C.construir(BASE, SALIDA, capas=[extra],
                          cro=[V17 / 'romfs/cro/ina_main1.cro', V17 / 'romfs/cro/ina_main2.cro'])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    copiados = 0
    for p in sorted((V17 / 'romfs').rglob('*')):
        rel = p.relative_to(V17 / 'romfs')
        if p.is_file() and rel.parts[0] != 'cro':
            dst = SALIDA_DIR / 'romfs' / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(p, dst)
            copiados += 1
    for n in ('ina_main1.cro', 'ina_main2.cro'):
        assert sha(SALIDA_DIR / 'romfs/cro' / n) == sha(V17 / 'romfs/cro' / n)
    rep['events_repack'] = rep_ev
    rep['base_v17'] = str(BASE)
    rep['capas_v19'] = ['(temporal) eve/mch IE2 de ie2/shared/capas/dialogo/saltos37']
    rep['romfs_v17_copiados'] = copiados
    rep['sha256'] = {'archive.fa': rep['archive_sha256'],
                     **{f'romfs/cro/{n}': sha(SALIDA_DIR / 'romfs/cro' / n)
                        for n in ('ina_main1.cro', 'ina_main2.cro')}}
    SALIDA.with_suffix('.build.json').write_text(
        json.dumps(rep, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    print(json.dumps(dict(sha256=rep['sha256'], reemplazos=rep['archive_replacements'], romfs=copiados,
                          eventos={k: len(v) for k, v in rep_ev.items()}), ensure_ascii=False, indent=1))


if __name__ == '__main__':
    sys.exit(main())
