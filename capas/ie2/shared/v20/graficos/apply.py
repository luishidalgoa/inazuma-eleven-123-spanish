"""v20 · gráficos de partido de IE2 (issue #77). No construye candidata ni instala.

1. Sprites DS heredados de pic3d/ (sueltos en 3DS, empaquetados en la NDS española en
   pic3d/sp/common.pkb y pic3d/sp/mbd_s.pkb; el índice .pkh son registros de 16 B
   (crc32(nombre), offset, tamaño, cabecera LZ)). Se copian tal cual si ambos decodifican con las
   mismas medidas y el píxel cambia:
     ply_bkr01   burbujas de reacción (ナイス!/ミス!/ダイレクト!/とっぱ! -> ¡Buena!/¡Fallo!/…)
     mbd_w00/w01 rótulo テクニック bajo los números del duelo -> «Valor» (término oficial NDS)
     ply_num     iconos 風林火山 junto al dorsal de la ficha -> iconos de afinidad NDS
     mbd_s*      placas de equipo con «Valor total» y nombre europeo, gmdn_*, mln_*, yddn_w00…
2. «制限時間» (a_game/battle_start_t.arc, ie02_battle_start_time_plt_t01): no hay pieza NDS (textura
   3DS). Se pinta «Límite», el término oficial de la 3DS europea de IE1 (misma placa), reutilizando
   sus glifos recoloreados al amarillo de la placa de IE2. Parte del .arc de probe_ie2_v18.
Salida: extra/<ruta>, informe.json, previews/*_x4.png
"""
import json
import shutil
import struct
import sys
import zlib
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'v03' / 'graficos'))
import comun as C  # noqa: E402
from lz10 import compress as lz10_compress  # noqa: E402

CAND = C.ROOT / 'work/shared/candidatas/probe_ie2_v18/archive.fa'
EU = C.ROOT / 'work/ie1/fuentes/3ds_eu/romfs/archive.fa'
EXTRA, PREV = HERE / 'extra', HERE / 'previews'
PAQUETES = ['common', 'mbd_s']
ARC_T = 'inazuma2/data_iz/a_game/battle_start_t.arc'
TEX_T = 'ie02_battle_start_time_plt_t01.tga'


def paquete(nombre):
    d = C.NDS / 'data_iz/pic3d/sp'
    h, b = (d / f'{nombre}.pkh').read_bytes(), (d / f'{nombre}.pkb').read_bytes()
    out = {}
    for i in range(0, len(h), 16):
        k, o, s = struct.unpack_from('<III', h, i)
        out[k] = b[o:o + s]
    return out


def dec(d):
    return C.L.decode(C.ds_decomp(d))


def recortar(orig, es):
    """ES con más celdas al final (ply_bkr01: 9 celdas en 32x256 frente a 8 en 32x128): si las celdas
    japonesas coinciden con las primeras españolas y el ancho es igual, se monta un PAC con la cabecera,
    tamaño y celdas japoneses, los píxeles españoles de la parte usada y la paleta española; se recomprime en LZ10 como el original."""
    a, b = C.ds_decomp(orig), C.ds_decomp(es)
    ha, hb = struct.unpack_from('<7I', a), struct.unpack_from('<7I', b)
    ma, mb = a[ha[5]:ha[5] + ha[6]], b[hb[5]:hb[5] + hb[6]]
    if ma[2] != mb[2] or ma[4] != mb[4] or len(ma) > len(mb) or ma[8:] != mb[8:len(ma)]:
        return None
    out = bytearray(a)
    out[ha[1]:ha[1] + ha[2]] = b[hb[1]:hb[1] + ha[2]]
    out[ha[3]:ha[3] + ha[4]] = b[hb[3]:hb[3] + ha[4]]
    comp = lz10_compress(bytes(out))
    assert C.ds_decomp(comp) == bytes(out)
    return comp


def sprites(informe, prev):
    jp, cand = C.jp(), C.Archivo(CAND)
    for pk in PAQUETES:
        ent = paquete(pk)
        for ruta in sorted(jp.rutas('inazuma2/data_iz/pic3d/')):
            nombre = ruta.split('/')[-1]
            k = zlib.crc32(nombre.encode())
            if ruta.count('/') != 3 or k not in ent:
                continue
            orig, es = jp.get(ruta), ent[k]
            assert cand.get(ruta) == orig, f'{ruta} ya cambiado en la base'
            if orig == es:
                continue
            a, b = dec(orig), dec(es)
            if a.size != b.size:
                es = recortar(orig, es)
                if es is None:
                    informe.append(dict(ruta=ruta, estado='medidas_distintas'))
                    continue
                b = dec(es)
            if a.tobytes() == b.tobytes():
                continue
            dst = EXTRA / ruta
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(es)
            informe.append(dict(ruta=ruta, clase='sprite_nds', paquete=pk, tam_jp=len(orig), tam_es=len(es)))
            prev.append(C.par(a, b, s=4, titulo=nombre))


def limite(informe):
    base = C.Archivo(CAND).get(ARC_T)
    raw = bytearray(C.U.unwrap(base))
    tex = {n: (o, l, b) for n, o, l, b in C.texturas(bytes(raw))}
    o, l, blob = tex[TEX_T]
    im = np.array(C.decodificar(blob))
    antes = Image.fromarray(im.copy(), 'RGBA')
    fondo = im[5, 50].copy()  # verde oliva de la placa
    tinta = np.array([213, 205, 65, 255], np.uint8)
    im[6:19, 38:93] = fondo                         # borra 制限時間 (el reloj queda en x<38)
    eu = C.Archivo(EU)
    raw_eu = C.U.unwrap(eu.get('es/inazuma1/data_iz/a_game/battle_start_t.arc'))
    e = np.array(C.decodificar({n: b for n, _, _, b in C.texturas(raw_eu)}['ie01_battle_start_time_plt_t01.tga']))
    zona = e[8:21, 58:96]
    mask = (zona[..., 0] > 150) & (zona[..., 1] < 100)   # glifos rojos «Límite»
    ys, xs = np.nonzero(mask)
    g = mask[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    gh, gw = g.shape
    x0 = 38 + (93 - 38 - gw) // 2
    y0 = 18 - gh + 1
    sub = im[y0:y0 + gh, x0:x0 + gw]
    sub[g] = tinta
    nuevo = C.codificar(blob, Image.fromarray(im, 'RGBA'))
    raw[o:o + l] = nuevo
    out = C.reenvolver(base, bytes(raw))
    assert C.U.unwrap(out) == bytes(raw)
    dst = EXTRA / ARC_T
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(out)
    despues = C.decodificar(nuevo)
    informe.append(dict(ruta=ARC_T, textura=TEX_T, clase='pintado', texto='Límite',
                        origen_glifos='3DS EU IE1 ie01_battle_start_time_plt_t01'))
    C.par(antes, despues, s=4, titulo=TEX_T).save(PREV / 'limite_x4.png')


def main():
    shutil.rmtree(EXTRA, ignore_errors=True)
    shutil.rmtree(PREV, ignore_errors=True)
    PREV.mkdir(parents=True)
    informe, prev = [], []
    sprites(informe, prev)
    clave = {'ply_bkr01.pac_': 'burbujas', 'mbd_w00.pac_': 'tecnica', 'mbd_w01.pac_': 'tecnica',
             'ply_num.pac_': 'dorsal'}
    # hojas: las de los puntos del issue aparte, el resto juntas
    sel = {}
    for r, im in zip([x for x in informe if x.get('clase') == 'sprite_nds'], prev):
        sel.setdefault(clave.get(r['ruta'].split('/')[-1], 'resto'), []).append(im)
    for g, ims in sel.items():
        for i in range(0, len(ims), 24):
            C.hoja(ims[i:i + 24], 2400).save(PREV / f'{g}_{i // 24:02d}_x4.png')
    limite(informe)
    (HERE / 'informe.json').write_text(json.dumps(informe, ensure_ascii=False, indent=1), encoding='utf-8')
    print(len(informe), 'cambios')


if __name__ == '__main__':
    main()
