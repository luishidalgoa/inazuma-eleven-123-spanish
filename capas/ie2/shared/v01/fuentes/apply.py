"""IE2 v01 · capa de fuentes: las mejoras tipográficas de IE1 aplicadas a IE2 (issue #69).

Autorización del usuario (2026-09-16): dar a IE2 los mismos glifos latinos europeos y métricas
(v74/v75) y los mismos bigramas (registro v87, mismos códigos) que IE1.

Qué hay que hacer y qué no (comprobado aquí, no supuesto):

1. BCFNT (font/FONT12.bcfnt, font/FONT8.bcfnt, font/FONT12T.bcfnt). Están en la raíz de archive.fa y
   las comparten IE1, IE2 e IE3 (el motor de texto está en code.bin; ina_main2.cro crea los mismos
   cuatro gestores FONT8/RUBI8/FONT12/FONT12T en 0x25b8-0x25d8, ver informe.json). La base IE1 (v87)
   ya lleva v74 + v75 (FONT12) y los bigramas v87 (FONT12 + FONT8); FONT12T sigue en v20 igual que en
   IE1. Aquí solo se verifica su sha256: no se copia nada (se heredan de la base).
2. NFTR propias de IE2 (inazuma2/data_iz/font/FONT12.NFTR y FONT8.NFTR). La v20 de IE1 solo tocó el
   CWDH de sus NFTR (52 códigos en FONT12, 1 en FONT8; bitmaps, CMAP y tamaño intactos). Las NFTR de
   IE2 parten de las MISMAS métricas en esos códigos, así que se aplica el mismo cambio, código a
   código, y se exige que el valor de partida coincida. FONT12T.NFTR y RUBI8.NFTR: IE1 no los tocó.
   No hay copias de fuentes en data_iz_blizzard (Ventisca usa las de data_iz).
3. Bigramas: los 13 códigos del registro v87 (y los que añada v88, si existe) no pueden aparecer como
   kanji en texto de IE2. Se reutiliza el escaneo de toda la recopilación de v88 (escaneo_base_v87.json,
   sobre probe_ie1_v87, los cuatro juegos y las CRO) y se filtran las apariciones en inazuma2/ y
   ina_main2.cro.

Uso: python -X utf8 work/ie2/shared/capas/v01/fuentes/apply.py
Escribe extra/inazuma2/data_iz/font/{FONT12,FONT8}.NFTR e informe.json. No toca IE1 ni el registro.
"""
from __future__ import annotations

import hashlib
import json
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[5]
sys.path.insert(0, str(ROOT / 'tools/src'))
from ie123kit.nucleo.contenedores.fa import FaArchive  # noqa: E402
from ie123kit.nucleo.fuentes.nftr import read_metrics  # noqa: E402

BASE_JP = ROOT / 'work/shared/base_3ds/romfs/archive.fa'
IE1_V87 = ROOT / 'work/shared/candidatas/probe_ie1_v87/archive.fa'
REGISTROS = [ROOT / 'work/ie1/capas/v88/bigramas_total/registro.json',
             ROOT / 'work/ie1/capas/v87/bigramas_fuentes/registro.json']
ESCANEO = ROOT / 'work/ie1/capas/v88/bigramas_total/escaneo_base_v87.json'

# bcfnt esperadas en la base (v87): FONT12 = v74+v75+bigramas, FONT8 = v20+bigramas, FONT12T = v20
BCFNT = {
    'font/FONT12.bcfnt': 'c453cf105984db168a6dac8f3c06d8a93408b76068e608462e83a32b2ca6720b',
    'font/FONT8.bcfnt': '535bd59a10f6f052de7ac097129a32143d53b58055872c1af7353a5555dd51b5',
    'font/FONT12T.bcfnt': '71c37509f0eec6c092ea75f373667b0bf1f19389c45b1741a89a8f53270164ab',
}
NFTR = ['FONT12', 'FONT8']
NFTR_IE1_V20 = {   # tools/dialogue_lock.py
    'FONT12': 'b43cfc73407c928272a001f04b85380976348e30da528b5938a3e45b87ea85c7',
    'FONT8': '6f683a8cef209d6e9eb9b31be5cadaad5eb90bf5ccd5e5c01c40afdf89984865',
}


def lector(ruta):
    arc = FaArchive(str(ruta))
    idx = {p: (o, s) for p, o, s in arc.entries}
    return lambda k: bytes(arc.d[idx[k][0]:idx[k][0] + idx[k][1]]), idx


def sha(b):
    return hashlib.sha256(b).hexdigest()


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    jp, idx_jp = lector(BASE_JP)
    v87, _ = lector(IE1_V87)
    informe = {'base_ie1': str(IE1_V87), 'bcfnt': {}, 'nftr': {}, 'bigramas': {}}

    # 1. bcfnt compartidas
    for rel, esperado in BCFNT.items():
        real = sha(v87(rel))
        assert real == esperado, (rel, real)
        informe['bcfnt'][rel] = {'sha256': real, 'origen': 'heredada de la base IE1 (compartida)'}
    assert not any(p.startswith('inazuma2/data_iz_blizzard/font/') for p in idx_jp), 'Ventisca con fuentes propias'

    # 2. NFTR de IE2: mismo cambio de CWDH que la v20 de IE1
    for f in NFTR:
        ie1_jp = jp(f'inazuma1/data_iz/font/{f}.NFTR')
        ie1_v20 = v87(f'inazuma1/data_iz/font/{f}.NFTR')
        assert sha(ie1_v20) == NFTR_IE1_V20[f]
        dif = [i for i in range(len(ie1_jp)) if ie1_jp[i] != ie1_v20[i]]
        cwdh = struct.unpack_from('<I', ie1_jp, 36)[0] - 8
        assert all(cwdh <= i < cwdh + struct.unpack_from('<I', ie1_jp, cwdh + 4)[0] for i in dif), 'v20 tocó algo fuera de CWDH'
        a, b = read_metrics(ie1_jp), read_metrics(ie1_v20)
        cambios = {cp: (a[cp], b[cp]) for cp in a if a[cp] != b[cp]}

        ie2 = jp(f'inazuma2/data_iz/font/{f}.NFTR')
        assert sha(ie2) == sha(v87(f'inazuma2/data_iz/font/{f}.NFTR')), 'la base IE1 ya toca la NFTR de IE2'
        m2, off2 = read_metrics(ie2, with_offsets=True)
        nuevo = bytearray(ie2)
        filas = []
        for cp, (antes, despues) in sorted(cambios.items()):
            assert m2.get(cp) == antes, (f, hex(cp), m2.get(cp), antes)
            struct.pack_into('<bBB', nuevo, off2[cp], *despues)
            filas.append({'sjis': f'{cp:04X}', 'car': bytes([cp >> 8, cp & 255]).decode('cp932'),
                          'antes': list(antes), 'despues': list(despues)})
        nuevo = bytes(nuevo)
        assert len(nuevo) == len(ie2)
        assert read_metrics(nuevo) == {**m2, **{cp: d for cp, (_, d) in cambios.items()}}
        out = HERE / 'extra' / f'inazuma2/data_iz/font/{f}.NFTR'
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(nuevo)
        informe['nftr'][f] = {'sha256_antes': sha(ie2), 'sha256_despues': sha(nuevo),
                              'codigos_cambiados': len(filas), 'cambios': filas}
        print(f'inazuma2 {f}.NFTR: {len(filas)} anchos como la v20 de IE1 -> {sha(nuevo)}')

    # 3. bigramas: códigos del registro sin uso como kanji en IE2
    reg_path = next(p for p in REGISTROS if p.is_file())
    reg = json.loads(reg_path.read_text(encoding='utf-8'))
    esc = json.loads(ESCANEO.read_text(encoding='utf-8'))
    for e in reg['bigramas']:
        c = e['sjis']
        assert c in esc['codigos'], ('código sin escanear', c)
        ie2 = [x for x in esc['apariciones_textuales'].get(c, [])
               if x[0].startswith('inazuma2/') or 'ina_main2' in x[0]]
        informe['bigramas'][c] = {'par': e['par'], 'escaneo': esc['codigos'][c], 'apariciones_ie2': ie2}
        assert not ie2, (c, ie2)
    informe['registro'] = {'ruta': str(reg_path), 'version': reg.get('version'), 'codigos': len(reg['bigramas'])}
    informe['escaneo'] = str(ESCANEO)
    print(f"bigramas: {len(reg['bigramas'])} códigos ({reg_path.parent.name}) sin uso textual en IE2")
    (HERE / 'informe.json').write_text(json.dumps(informe, ensure_ascii=False, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()
