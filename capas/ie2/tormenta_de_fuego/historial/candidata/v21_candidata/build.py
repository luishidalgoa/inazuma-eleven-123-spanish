"""IE2 Fuego v21 · candidata probe_ie2_v21 = probe_ie2_v18 + v20 teclado/textos/graficos/voces + Fuego v21 tutorial.

archive.fa: el de v18 con estas capas de ficheros (la última gana; no se solapan):
  1. ie2/shared/capas/teclado/teclado/extra   (MMName.SPF_, MMProfd.SPF_)
  2. ie2/shared/capas/historial/nombres/v20_textos/extra    (unitbase.dat, item.dat, FONT12/FONT8.bcfnt)
  3. ie2/shared/capas/historial/graficos/v20_graficos/extra  (bocadillos, Valor, Límite, afinidades...)
  4. ie2/tormenta_de_fuego/capas/graficos/tutorial/extra (MASTutorial.SPF_ de la NDS ES)
  Sin eventos: eve/mch quedan como en v18.
CRO: ina_main1 de v18; ina_main2 de v20/textos (con los tres parches de ancho de v15).
romfs/: el de v18 SIN los fcode*/dakuten/handaku/ngword/fcodeck .txt sueltos (no se leen) y con
sound.pb/.ph/.ph_ de v20/voces/romfs_mod.
No instala nada.
Uso: python -X utf8 work/ie2/tormenta_de_fuego/capas/historial/candidata/v21_candidata/build.py
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[6]
sys.path.insert(0, str(ROOT / 'tools/src'))
from ie123kit.nucleo.construir import candidata as C  # noqa: E402
from ie123kit.nucleo.contenedores.fa import FaArchive  # noqa: E402

W = ROOT / 'work'
V18 = W / 'shared/candidatas/probe_ie2_v18'
BASE = V18 / 'archive.fa'
SALIDA_DIR = W / 'shared/candidatas/probe_ie2_v21'
SALIDA = SALIDA_DIR / 'archive.fa'
CAPAS_SH = W / 'ie2/shared/capas'
CAPAS = [CAPAS_SH / 'teclado/teclado/extra', CAPAS_SH / 'historial/nombres/v20_textos/extra', CAPAS_SH / 'historial/graficos/v20_graficos/extra',
         W / 'ie2/tormenta_de_fuego/capas/graficos/tutorial/extra']
CRO1 = V18 / 'romfs/cro/ina_main1.cro'
CRO2 = CAPAS_SH / 'historial/nombres/v20_textos/romfs/cro/ina_main2.cro'
VOZ = CAPAS_SH / 'historial/media/v20_voces/romfs_mod'
SOBRAN = {'fcode0.txt', 'fcode1.txt', 'fcode2.txt', 'fcodeck.txt', 'dakuten.txt', 'handaku.txt', 'ngword.txt'}
ANCHO = {0x66a24: 0xE3A01E1A, 0x4cabc: 0xE3A02E1A, 0x4d6a0: 0xE3A02D07}   # v15 ancho_dialogo
PK = ('inazuma2/data_iz/script/eve.pkh', 'inazuma2/data_iz/script/eve.pkb',
      'inazuma2/data_iz/script/mch.pkh', 'inazuma2/data_iz/script/mch.pkb')


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    d = CRO2.read_bytes()
    for a, w in ANCHO.items():
        assert int.from_bytes(d[a:a + 4], 'little') == w, hex(a)
    if SALIDA_DIR.exists():
        shutil.rmtree(SALIDA_DIR)
    declarados = set()
    for c in CAPAS:
        for p in c.rglob('*'):
            if p.is_file():
                rel = p.relative_to(c).as_posix()
                assert rel not in declarados, rel
                declarados.add(rel)
    rep = C.construir(BASE, SALIDA, capas=CAPAS, cro=[CRO1, CRO2])
    # romfs
    romfs = SALIDA_DIR / 'romfs'
    copiados, quitados = 0, []
    for p in sorted((V18 / 'romfs').rglob('*')):
        rel = p.relative_to(V18 / 'romfs')
        if not p.is_file() or rel.parts[0] == 'cro':
            continue
        if rel.parts[:2] == ('inazuma2', 'data_iz') and len(rel.parts) == 3 and rel.name in SOBRAN:
            quitados.append(rel.as_posix())
            continue
        dst = romfs / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p, dst)
        copiados += 1
    assert len(quitados) == len(SOBRAN), quitados
    voz = []
    for p in sorted(VOZ.rglob('*')):
        if p.is_file():
            rel = p.relative_to(VOZ)
            assert rel.parts[:3] == ('inazuma2', 'data_iz', 'sound'), rel
            assert (romfs / rel).exists(), rel
            shutil.copyfile(p, romfs / rel)
            voz.append(rel.as_posix())
    # comprobaciones
    cro = romfs / 'cro'
    assert sorted(x.name for x in cro.iterdir()) == ['ina_main1.cro', 'ina_main2.cro']
    assert sha(cro / 'ina_main1.cro') == sha(CRO1) and sha(cro / 'ina_main2.cro') == sha(CRO2)
    d = (cro / 'ina_main2.cro').read_bytes()
    assert all(int.from_bytes(d[a:a + 4], 'little') == w for a, w in ANCHO.items())
    sad = sum(1 for p in romfs.rglob('*') if p.is_file() and p.suffix.lower() == '.sad')
    assert sad == 547, sad
    a, b = FaArchive(str(BASE)), FaArchive(str(SALIDA))
    pa = {p: (o, s) for p, o, s in a.entries}
    pb = {p: (o, s) for p, o, s in b.entries}
    assert set(pa) == set(pb)
    cambiados = sorted(p for p in pa if pa[p][1] != pb[p][1]
                       or bytes(a.d[pa[p][0]:pa[p][0] + pa[p][1]]) != bytes(b.d[pb[p][0]:pb[p][0] + pb[p][1]]))
    no_decl = sorted(set(cambiados) - declarados)
    assert not no_decl, no_decl
    assert not set(PK) & set(cambiados)
    rep['base_v18'] = str(BASE)
    rep['capas_v21'] = [str(c) for c in CAPAS]
    rep['archive_cambiados'] = cambiados
    rep['declarados_sin_cambio'] = sorted(declarados - set(cambiados))
    rep['romfs_v18_copiados'] = copiados
    rep['romfs_quitados'] = quitados
    rep['romfs_voces'] = voz
    rep['romfs_sad'] = sad
    rep['sha256'] = {'archive.fa': sha(SALIDA),
                     'romfs/cro/ina_main1.cro': sha(cro / 'ina_main1.cro'),
                     'romfs/cro/ina_main2.cro': sha(cro / 'ina_main2.cro'),
                     **{'romfs/' + v: sha(romfs / v) for v in voz}}
    SALIDA.with_suffix('.build.json').write_text(
        json.dumps(rep, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    print(json.dumps(dict(sha256=rep['sha256'], cambiados=len(cambiados),
                          declarados_sin_cambio=rep['declarados_sin_cambio'], romfs=copiados,
                          quitados=quitados, sad=sad), ensure_ascii=False, indent=1))


if __name__ == '__main__':
    sys.exit(main())
