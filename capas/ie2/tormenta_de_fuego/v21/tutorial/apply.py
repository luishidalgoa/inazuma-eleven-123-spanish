"""IE2 Fuego v21 · tutorial: MASTutorial.SPF_ japonés -> paquete de la NDS española (texto oficial).

inazuma2/data_iz/pic2d/menu/MASTutorial.SPF_ (archive.fa) es un SFP comprimido en LZ10, igual que en la NDS.
El paquete de la NDS española (fuentes/nds_es/data_iz/pic2d/menu/sp/MASTutorial.SPF_) tiene el MISMO formato:
LZ10 -> SFP con 5/0x20/0x140 de cabecera y las mismas 9 entradas (SYDN_B00..T00.PAC), cada una un PAC de 3 partes
(paleta 32 B, mapa, teselas). Paletas y mapas tienen el mismo tamaño (mismas dimensiones); solo cambia el número
de teselas (el texto). Por eso se copia tal cual, ya comprimido; comprobaciones en ``comprobar``.

Vive en tormenta_de_fuego porque la fuente (NDS ES) está en tormenta_de_fuego/fuentes, aunque el archive.fa de
3DS tiene un único inazuma2/ para las dos versiones.
Base de comparación: el archive.fa japonés (work/shared/base_3ds). No construye ni instala.
Uso: python -X utf8 work/ie2/tormenta_de_fuego/capas/v21/tutorial/apply.py
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
from ie123kit.nucleo.compresion import lz10  # noqa: E402
from ie123kit.nucleo.contenedores.fa import FaArchive  # noqa: E402

RUTA = 'inazuma2/data_iz/pic2d/menu/MASTutorial.SPF_'
BASE = ROOT / 'work/shared/base_3ds/romfs/archive.fa'
FUENTE = ROOT / 'work/ie2/tormenta_de_fuego/fuentes/nds_es/data_iz/pic2d/menu/sp/MASTutorial.SPF_'
SALIDA = HERE / 'extra' / RUTA


def sfp(d: bytes) -> dict:
    assert d[:4] == b'SFP\0', d[:4]
    blq, datos = struct.unpack_from('<2I', d, 0x0c)
    out, i, fin = {}, 0, datos
    while 0x20 + 16 * i < fin:   # la tabla termina donde empiezan los nombres
        no, sz, bl, _ = struct.unpack_from('<4I', d, 0x20 + 16 * i)
        i += 1
        if no == 0:
            break
        fin = min(fin, no)
        nombre = d[no:d.index(0, no)].decode('ascii')
        out[nombre] = d[datos + bl * blq:datos + bl * blq + sz]
    return out


def pac(b: bytes):
    h = struct.unpack_from('<7I', b, 0)
    assert h[0] == 3, h
    # (paleta, mapa) tamaños; teselas variable
    return dict(paleta=b[h[1]:h[1] + h[2]], tam_mapa=h[4], tam_teselas=h[6])


def comprobar(base_c: bytes, nds_c: bytes) -> list:
    fallos = []
    if base_c[:1] != b'\x10' or nds_c[:1] != b'\x10':
        fallos.append('no es LZ10')
        return fallos
    b, n = lz10.decompress(base_c), lz10.decompress(nds_c)
    if b[:0x20] != n[:0x20]:
        fallos.append('cabecera SFP distinta')
    eb, en = sfp(b), sfp(n)
    if list(eb) != list(en):
        fallos.append(f'entradas distintas: {list(eb)} / {list(en)}')
    for k in eb:
        if k not in en:
            continue
        pb, pn = pac(eb[k]), pac(en[k])
        if pb['paleta'] != pn['paleta']:
            fallos.append(f'{k}: paleta distinta')
        if pb['tam_mapa'] != pn['tam_mapa']:
            fallos.append(f'{k}: mapa de otro tamaño (dimensiones)')
    return fallos


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    base_c = FaArchive(str(BASE)).read(RUTA)
    nds_c = FUENTE.read_bytes()
    fallos = comprobar(base_c, nds_c)
    if fallos:
        print(fallos)
        return 1
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_bytes(nds_c)
    en = sfp(lz10.decompress(nds_c))
    inf = dict(ruta=RUTA, fuente=str(FUENTE), entradas=len(en), nombres=list(en),
               bytes_base=len(base_c), bytes_nuevo=len(nds_c),
               sha256=hashlib.sha256(nds_c).hexdigest())
    (HERE / 'informe.json').write_text(json.dumps(inf, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(inf, ensure_ascii=False, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
