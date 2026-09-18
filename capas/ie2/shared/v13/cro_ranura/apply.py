"""IE2 v13 · cro_ranura: caja de ranura de guardado de la pantalla de título.

Qué se vio en probe_ie2_v10: «Equipo 12 j.» (unidad cortada), «ライモン» y «0V» + «V i c t o r i o .».

De dónde sale cada cosa (comprobado; detalle en informe.json):
- Los rótulos NO están en ina_main2.cro: son la textura ie02_slot_b_font01 de a_menu/menu_slot.arc
  (celdas japonesas チームレベル | プレイタイム | なかま 人 時間 分 勝 | チーム名 | オプション ×2). El QNA
  de la ranura (partes 34-41, repetidas en 100-107, 136-143, 171-178 y 204-211) las coloca así:
    fila 1: チームレベル (96 px) ... なかま (48 px) + cifras + 人 (16 px)
    fila 2: プレイタイム (96 px) ... cifras + 時間 (32 px) + cifras + 分 (16 px)
    fila 3: チーム名 (64 px) + nombre del equipo
    fila 4: cifras + 勝 (16 px) + título del equipo (rpgtitle.STR)
  v03 pintó なかま como «Equipo» (significa compañeros/jugadores), 人 como «j.» (no cabe en 16 px con
  esa fuente: sale cortado), 勝 como «V» y チーム名 como «Nombre».
- «V i c t o r i o .» no es la etiqueta de victorias: es el título del equipo (rpgtitle.STR n.º 37,
  ゆうしょうイレブン; NDS oficial «Equipo Victorioso»), recortado por v03 tablas_a a 9 caracteres de
  ancho completo (búfer de 18 B). La línea es «<victorias> 勝 <título>».
- «ライモン»: el único origen es el literal 0x216528 de ina_main2.cro, que la función de partida nueva
  del título (0x15d9d0; carga pic2d/title/nedn_bg04 y RPG_SCRIPT_NO) copia en 0x15db54 al nombre del
  equipo de la partida. Es dato del juego, no lo escribe el jugador. v04 ya lo cambió a «Raimon»
  (bigramas R|ai|m|on, 8 B como el japonés) y está en v09/v10; team.pkb y PracticeGame*.dat solo tienen
  «ウラ・ライモン» (otro equipo) y ningún evento lo fija. Una ranura que aún dice «ライモン» se creó con
  una candidata anterior a v05: hay que empezar partida nueva.
- ina_main2.cro: sin cambios en esta capa (la de v09 sirve tal cual).

Qué hace: repinta ie02_slot_b_font01 desde el japonés con el pintor de v03 (mismas celdas, metadata
CTPK, tamaño y tabla ARCV; SSZL recomprimido) sobre el menu_slot.arc de v06 (el instalado en v10):
  チームレベル «Nivel equipo» y プレイタイム «Tiempo» (igual que v03), なかま «Jugadores» (Bahnschrift
  Light Condensed 12/11, 1 px de margen), 人 vacío (el rótulo ya dice jugadores; como IE1, que deja 人 en
  blanco en su caja del CRO), 時間 «h», 分 «m» (igual que v03; NDS «%3dh%2dm»), 勝 «vic.» (16 px: no
  cabe «Victorias»; en la línea de las cifras), チーム名 «Equipo», オプション «Opciones» ×2.
Salida: extra/inazuma2/data_iz/a_menu/menu_slot.arc, informe.json, previews/.
Uso: python -X utf8 apply.py
"""
from __future__ import annotations

import hashlib
import json
import shutil
import struct
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[5]
V06 = ROOT / 'work/ie2/shared/capas/v06/graficos'
sys.path.insert(0, str(V06))
import base as B  # noqa: E402  (añade v03/graficos al path)
import pintado_menus as PM  # noqa: E402

C = B.C
RUTA = 'inazuma2/data_iz/a_menu/menu_slot.arc'
TEX = 'ie02_slot_b_font01.tga'
BASE_ARC = V06 / 'extra' / RUTA
CAND = ROOT / 'work/shared/candidatas/probe_ie2_v10/archive.fa'
CRO_V09 = ROOT / 'work/ie2/shared/capas/v09/cofres/romfs/cro/ina_main2.cro'
CRO_JP = ROOT / 'work/shared/base_3ds/romfs/cro/ina_main2.cro'
SALIDA = HERE / 'extra' / RUTA
PREVIEWS = HERE / 'previews'

PM.CADENAS['v13_cond'] = [(('bahn', b'Light Condensed', s), None) for s in (12, 11, 10)]
_G = dict(borrar='transparente', fuente='fina16')
OPS = [
    dict(caja=(0, 0, 96, 16), texto='Nivel equipo', **_G),
    dict(caja=(0, 16, 96, 32), texto='Tiempo', **_G),
    dict(caja=(0, 32, 48, 48), texto='Jugadores', borrar='transparente', fuente='v13_cond', x=1, dy=2),
    dict(caja=(48, 32, 64, 48), texto='', borrar='transparente'),
    dict(caja=(64, 32, 96, 48), texto='h', **_G),
    dict(caja=(96, 32, 112, 48), texto='m', **_G),
    dict(caja=(112, 32, 128, 48), texto='vic.', borrar='transparente', fuente='v13_cond', dy=1),
    dict(caja=(0, 48, 64, 64), texto='Equipo', **_G),
    dict(caja=(0, 64, 80, 80), texto='Opciones', **_G),
    dict(caja=(0, 80, 80, 96), texto='Opciones', **_G),
]
# celdas que se repintan igual que v03 (deben quedar idénticas a v10)
IGUALES_V10 = [(0, 0, 96, 16), (0, 16, 96, 32), (64, 32, 96, 48), (96, 32, 112, 48), (0, 64, 80, 80),
               (0, 80, 80, 96)]
CAMBIADAS = [(0, 32, 48, 48), (48, 32, 64, 48), (112, 32, 128, 48), (0, 48, 64, 64)]
GRUPO_QNA = range(30, 46)          # primera ranura (las otras repiten las mismas celdas)


def texturas(raw):
    return {n: (o, s, b) for n, o, s, b in C.texturas(raw)}


def qna_partes(raw):
    """[(índice, textura, uv, tamaño, centro)] del QNA que usa la textura de la ranura."""
    for off, ln, _ in C.U.entries(raw):
        b = raw[off:off + ln]
        if b[:8] != b' QNA 051':
            continue
        n_tex, _, n_partes = struct.unpack_from('<III', b, 8)
        noff, _, poff = struct.unpack_from('<III', b, 36)
        nombres = [b[noff + i * 32:noff + (i + 1) * 32].split(b'\0')[0].decode() for i in range(n_tex)]
        if TEX[:-4] not in nombres:
            continue
        out = []
        for i in range(n_partes):
            o = poff + i * 128
            u0, v0, u1, v1, w, h, _, _, x, y = struct.unpack_from('<10f', b, o)
            t = struct.unpack_from('<I', b, o + 88)[0]
            if t < n_tex:
                out.append((i, nombres[t], (u0, v0, u1, v1), (w, h), (x, y)))
        return out
    raise ValueError('QNA de la ranura no encontrado')


def maqueta(raw, grupo=GRUPO_QNA):
    """Caja de la ranura compuesta con las partes QNA (sin cifras ni textos del programa)."""
    tex = {n[:-4]: C.decodificar(b) for n, (_, _, b) in texturas(raw).items()}
    lienzo = Image.new('RGBA', (272, 160), (40, 44, 70, 255))
    for i, n, uv, wh, xy in qna_partes(raw):
        if i not in grupo or n not in tex:
            continue
        pieza = tex[n].crop(tuple(int(v) for v in uv)).resize((int(wh[0]), int(wh[1])))
        lienzo.alpha_composite(pieza, (int(136 + xy[0] - wh[0] / 2), int(80 - xy[1] - wh[1] / 2)))
    return lienzo


def caja_tinta(arr, caja):
    x0, y0, x1, y1 = caja
    a = arr[y0:y1, x0:x1, 3]
    filas, cols = np.where(a.any(1))[0], np.where(a.any(0))[0]
    if not len(filas):
        return None
    return [int(cols[0]), int(filas[0]), int(cols[-1]), int(filas[-1])]


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    jp_arc = C.jp().get(RUTA)
    base = BASE_ARC.read_bytes()
    assert C.Archivo(CAND).get(RUTA) == base, 'menu_slot.arc de v06 != el instalado en probe_ie2_v10'
    raw_jp, raw = C.U.unwrap(jp_arc), bytearray(C.U.unwrap(base))
    tj, tb = texturas(raw_jp), texturas(bytes(raw))
    antes = np.array(C.decodificar(tj[TEX][2]))
    arr = PM.pintar(antes.copy(), OPS)
    off, ln, blob = tb[TEX]
    nuevo = C.codificar(blob, Image.fromarray(arr, 'RGBA'))
    raw[off:off + ln] = nuevo
    raw = bytes(raw)
    assert C.U.entries(raw) == C.U.entries(raw_jp)
    datos = C.reenvolver(jp_arc, raw)
    if SALIDA.parent.exists():
        shutil.rmtree(HERE / 'extra')
    SALIDA.parent.mkdir(parents=True)
    SALIDA.write_bytes(datos)

    final = np.array(C.decodificar(nuevo))
    v10 = np.array(C.decodificar(blob))
    PREVIEWS.mkdir(exist_ok=True)
    s = 4
    fila = [C.ampliar(Image.fromarray(x, 'RGBA'), s) for x in (antes, v10, final)]
    hoja = Image.new('RGBA', (fila[0].width * 3 + 24, fila[0].height + 16), (16, 16, 24, 255))
    d = ImageDraw.Draw(hoja)
    for k, (im, t) in enumerate(zip(fila, ('japonés', 'v10 (v03/v06)', 'v13'))):
        hoja.alpha_composite(im, (k * (im.width + 12), 16))
        d.text((k * (im.width + 12) + 2, 2), t, fill=(230, 230, 230, 255))
    hoja.save(PREVIEWS / 'font01_jp_v10_v13.png')
    cajas = [C.ampliar(maqueta(r), 3) for r in (raw_jp, C.U.unwrap(base), raw)]
    hoja = Image.new('RGBA', (cajas[0].width, (cajas[0].height + 16) * 3), (16, 16, 24, 255))
    d = ImageDraw.Draw(hoja)
    for k, (im, t) in enumerate(zip(cajas, ('japonés', 'v10', 'v13 (cifras, nombre y título los pone el programa)'))):
        y = k * (im.height + 16)
        d.text((2, y + 2), t, fill=(230, 230, 230, 255))
        hoja.alpha_composite(im, (0, y + 16))
    hoja.save(PREVIEWS / 'caja_ranura.png')

    cro9 = CRO_V09.read_bytes()
    informe = dict(
        archivo=RUTA, textura=TEX, base=str(BASE_ARC.relative_to(ROOT)),
        sha256=hashlib.sha256(datos).hexdigest(), bytes=len(datos), bytes_base=len(base),
        ops=[{k: (list(v) if isinstance(v, tuple) else v) for k, v in o.items()} for o in OPS],
        tinta={str(o['caja']): caja_tinta(final, o['caja']) for o in OPS},
        qna=[dict(parte=i, uv=uv, tam=wh, centro=xy) for i, n, uv, wh, xy in qna_partes(raw_jp)
             if n == TEX[:-4] and i in GRUPO_QNA],
        origen=dict(
            rotulos='textura ie02_slot_b_font01 (a_menu/menu_slot.arc), no ina_main2.cro',
            victorio='rpgtitle.STR n.º 37 ゆうしょうイレブン = NDS «Equipo Victorioso» (título del equipo; '
                     'v03 tablas_a lo dejó en «Victorio.», 9 caracteres de ancho completo)',
            raimon=dict(literal='ina_main2.cro 0x216528', jp=CRO_JP.read_bytes()[0x216528:0x216530].hex(),
                        v09=cro9[0x216528:0x216530].hex(), uso='0x15db54 (función 0x15d9d0, partida nueva '
                        'desde el título) copia el literal al nombre del equipo; traducido en v04',
                        conclusion='ranura creada antes de v05: empezar partida nueva'),
            cro='sin cambios: usar work/ie2/shared/capas/v09/cofres/romfs/cro/ina_main2.cro'),
        pendiente=['«Victorias» no cabe en la celda de 16 px de 勝: «vic.»; ampliarla exige tocar el QNA '
                   '(partes 35/101/137/172/205) y no se sabe dónde empieza el título que pinta el programa',
                   'título del equipo «Victorio.»: decidir si se reescribe (p. ej. «Victorioso» con un bigrama) '
                   'en rpgtitle.STR; esta capa no lo toca'],
        runtime_verified=False)
    (HERE / 'informe.json').write_text(json.dumps(informe, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(dict(bytes=len(datos), tinta=informe['tinta']), ensure_ascii=False))


if __name__ == '__main__':
    main()
