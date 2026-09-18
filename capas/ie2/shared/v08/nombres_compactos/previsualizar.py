"""IE2 v08 · vistas previas x4 (antes = probe_ie2_v05, después = esta capa) con los mapas de bits reales.

- previews/nombres_*.png: 20 pestañas (FONT8, paso 10; x = lápiz + trunc((11 - advance)/2) + left), cada
  imagen con la pestaña de Silvia (después) como referencia. Además la misma fila a paso 9 (pantalla inferior).
- previews/rotulos.png: 10 rótulos (FONT8, paso 10, placa de 165 px con el origen del texto en su borde).
- previews/descripciones_*.png: 15 fichas (FONT12, paso 15, 2 líneas de hasta 18 casillas = 270 px).
Solapes: se informa en previews/solapes.json (núcleos a < 1 px entre casillas distintas).
Uso: python -X utf8 previsualizar.py
"""
from __future__ import annotations

import json
import struct
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import comun08 as K  # noqa: E402

A88, A89 = K.A88, K.A89
F12, F8, F12T = K.F12, K.F8, K.F12T
ESC = 4
OUT = HERE / 'previews'
NOMBRES = [('ie1', 9), ('ie1', 0), ('ie1', 1), ('ie1', 13), ('ie1', 1029), ('ie2', 1058), ('ie1', 14), ('ie1', 2),
           ('ie1', 1153), ('ie1', 1167), ('ie1', 3), ('ie1', 4), ('ie1', 5), ('ie1', 6), ('ie1', 7), ('ie1', 8),
           ('ie1', 10), ('ie1', 11), ('ie2', 278), ('ie1', 521)]
SILVIA = ('ie1', 14)
DESCS = [('ie1', 0), ('ie1', 2), ('ie1', 9), ('ie1', 1), ('ie1', 5), ('ie1', 14), ('ie1', 1029), ('ie1', 3),
         ('ie1', 4), ('ie1', 31), ('ie2', 0), ('ie2', 1), ('ie2', 2), ('ie2', 9), ('ie2', 14)]
STR = {'ie1': 'inazuma1/data_iz/logic/unitbase.STR', 'ie2': 'inazuma2/data_iz/logic/unitbase.STR'}


def fuentes_antes():
    tmp = Path(tempfile.mkdtemp(prefix='ie2_v08p_'))
    out = {}
    for f in K.FUENTES:
        p = tmp / Path(f).name
        p.write_bytes(K.FUENTE_ORIGEN[f].read_bytes() if f != F12 else
                      (K.W / 'ie1/capas/v90/cro_restantes/extra/font/FONT12.bcfnt').read_bytes())
        out[f] = A88.cargar(p)
    return out


def fuentes_despues():
    tmp = Path(tempfile.mkdtemp(prefix='ie2_v08p_'))
    out = {}
    for f in K.FUENTES:
        src = HERE / 'extra' / f
        if not src.exists():
            src = K.FUENTE_ORIGEN[f]
        p = tmp / Path(f).name
        p.write_bytes(src.read_bytes())
        out[f] = A88.cargar(p)
    return out


def codepoints(body):
    out, i = [], 0
    while i < len(body):
        b = body[i]
        if 0x81 <= b <= 0x9F or 0xE0 <= b <= 0xFC:
            out.append(ord(body[i:i + 2].decode('cp932')))
            i += 2
        else:
            out.append(None if b == 0x0A else b)
            i += 1
    return out


def colocar(F, cps, paso, caja):
    """[(px absolutos)] por casilla; None = salto de línea (y += 16)."""
    celdas, pen, y0 = [], 0, 0
    for cp in cps:
        if cp is None:
            pen, y0 = 0, y0 + 17
            celdas.append(None)
            continue
        gi = F.gi(cp)
        if gi is None:
            celdas.append({})
            pen += paso
            continue
        left, _, adv = F.metrics[gi]
        x0 = pen + int((caja - adv) / 2) + left
        celdas.append({(x0 + x, y0 + y): v for y, row in enumerate(F.bitmap(gi)) for x, v in enumerate(row) if v})
        pen += paso
    return celdas


def solapes(celdas, solido):
    malos, prev = [], None
    for c in celdas:
        if c is None:
            prev = None
            continue
        xs = [x for (x, _), v in c.items() if v >= solido]
        if not xs:
            continue
        if prev is not None and min(xs) - prev - 1 < 1:
            malos.append(min(xs) - prev - 1)
        prev = max(xs)
    return malos


def dibujar(d, celdas, ox, oy, ancho_fondo=None, fondo=(222, 232, 248)):
    if ancho_fondo:
        d.rectangle([ox, oy - 2 * ESC, ox + ancho_fondo * ESC - 1, oy + 15 * ESC], fill=fondo)
    for c in celdas:
        if not c:
            continue
        for (x, y), v in c.items():
            g = int(255 - v * 255 / 15)
            d.rectangle([ox + x * ESC, oy + y * ESC, ox + (x + 1) * ESC - 1, oy + (y + 1) * ESC - 1], fill=(g, g, g))


def main():
    OUT.mkdir(exist_ok=True)
    antes, despues = fuentes_antes(), fuentes_despues()
    get = K.comun88.abrir(K.CAND)
    ub_a = {j: get(K.UNIT[j]) for j in K.UNIT}
    ub_d = {j: (HERE / 'extra' / K.UNIT[j]).read_bytes() if (HERE / 'extra' / K.UNIT[j]).exists() else ub_a[j]
            for j in K.UNIT}
    reg = json.loads((HERE / 'registro.json').read_text(encoding='utf-8'))
    codec = A89.Codec(reg['bigramas'])
    informe = {'nombres': [], 'rotulos': [], 'descripciones': []}

    def nombre(ub, j, i):
        return ub[j][96 + i * 96 + 16:96 + i * 96 + 32].split(bytes(1))[0]

    # ---- nombres ---------------------------------------------------------------------------------------
    silvia = colocar(despues[F8], codepoints(nombre(ub_d, *SILVIA)), 10, 11)
    for lote in range(2):
        filas = NOMBRES[lote * 10:(lote + 1) * 10]
        img = Image.new('RGB', (600 * ESC // 2, (len(filas) * 20 + 30) * ESC), 'white')
        d = ImageDraw.Draw(img)
        dibujar(d, silvia, 10 * ESC, 6 * ESC, 30)
        d.text((4, 2), 'referencia: Silvia (v08)', fill=(200, 0, 0))
        for k, (j, i) in enumerate(filas):
            ba, bd = nombre(ub_a, j, i), nombre(ub_d, j, i)
            ca = colocar(antes[F8], codepoints(ba), 10, 11)
            cd = colocar(despues[F8], codepoints(bd), 10, 11)
            c9 = colocar(despues[F8], codepoints(bd), 9, 11)
            ct = colocar(despues[F12T], codepoints(bd), 15, 16)
            y = (30 + k * 20) * ESC
            dibujar(d, ca, 10 * ESC, y, 10 * len(ca))
            dibujar(d, cd, 90 * ESC, y, 10 * len(cd))
            dibujar(d, silvia, 170 * ESC, y, 30, (248, 232, 222))
            dibujar(d, c9, 210 * ESC, y, 9 * len(c9))
            txt = codec.texto(bd)
            d.text((4, y - 2 * ESC), f'{j} #{i} {txt}', fill=(0, 0, 160))
            informe['nombres'].append(dict(juego=j, registro=i, texto=txt, antes=codec.texto(ba),
                                           solapes_10=solapes(cd, 8), solapes_9=solapes(c9, 8),
                                           solapes_12T_15=solapes(ct, 15)))
        d.text((10 * ESC, 16 * ESC), 'v05 (antes)', fill=(0, 120, 0))
        d.text((90 * ESC, 16 * ESC), 'v08 (después)', fill=(0, 120, 0))
        d.text((170 * ESC, 16 * ESC), 'Silvia', fill=(0, 120, 0))
        d.text((210 * ESC, 16 * ESC), 'v08 a paso 9', fill=(0, 120, 0))
        img.save(OUT / f'nombres_{lote + 1}.png')

    # ---- rótulos --------------------------------------------------------------------------------------
    inf = json.loads((HERE / 'informe.json').read_text(encoding='utf-8'))
    cambios = {(c['juego'], c['evento'], c['indice']): c for c in inf['rotulos'] if isinstance(c, dict)} \
        if isinstance(inf.get('rotulos'), list) else {}
    filas = ([c for c in inf['cambios_rotulos'] if c['despues'] != c['antes']] +
             [c for c in inf['cambios_rotulos'] if c['despues'] == c['antes'] and c['bytes'] != 0])
    vistos, elegidas = set(), []
    for c in filas:
        if not any(x['evento'] == c['evento'] and x['indice'] == c['indice'] for x in json.loads(
                (HERE / 'cambios_registros.json').read_text(encoding='utf-8'))['registros']):
            continue
        if c['despues'] not in vistos:
            vistos.add(c['despues'])
            elegidas.append(c)
    elegidas = elegidas[:10]
    img = Image.new('RGB', (380 * ESC, (len(elegidas) * 22 + 10) * ESC), 'white')
    d = ImageDraw.Draw(img)
    for k, c in enumerate(elegidas):
        ev = HERE / c['juego'] / 'events' / f"{c['evento']}.ssd"
        data = ev.read_bytes()
        _, ops, recs = A88.S.parse(data)
        bd = recs[c['indice']].body
        ba = bytes.fromhex(next(x['cuerpo_antes'] for x in json.loads((HERE / 'cambios_registros.json').read_text(
            encoding='utf-8'))['registros'] if x['evento'] == c['evento'] and x['indice'] == c['indice']))
        ca = colocar(antes[F8], codepoints(ba), 10, 11)
        cd = colocar(despues[F8], codepoints(bd), 10, 11)
        y = (8 + k * 22) * ESC
        dibujar(d, ca, 4 * ESC, y, 165)
        dibujar(d, cd, 190 * ESC, y, 165)
        d.text((4, y - 2 * ESC), f"{c['juego']} {c['evento']}#{c['indice']}: {c['antes']} -> {c['despues']}",
               fill=(0, 0, 160))
        informe['rotulos'].append(dict(c, solapes=solapes(cd, 8)))
    img.save(OUT / 'rotulos.png')

    # ---- descripciones ---------------------------------------------------------------------------------
    st_d = {j: (HERE / 'extra' / STR[j]).read_bytes() if (HERE / 'extra' / STR[j]).exists() else get(STR[j])
            for j in STR}
    st_a = {j: get(STR[j]) for j in STR}
    for lote in range(3):
        filas = DESCS[lote * 5:(lote + 1) * 5]
        img = Image.new('RGB', (570 * ESC, (len(filas) * 44 + 8) * ESC), 'white')
        d = ImageDraw.Draw(img)
        for k, (j, i) in enumerate(filas):
            p = struct.unpack_from('<H', ub_a[j], 96 + i * 96 + 94)[0] * 32
            ba = st_a[j][p:st_a[j].index(bytes(1), p)]
            bd = st_d[j][p:st_d[j].index(bytes(1), p)]
            ca = colocar(antes[F12], codepoints(ba), 15, 15)
            cd = colocar(despues[F12], codepoints(bd), 15, 15)
            y = (10 + k * 44) * ESC
            dibujar(d, ca, 4 * ESC, y, 270, (240, 236, 220))
            dibujar(d, cd, 290 * ESC, y, 270, (240, 236, 220))
            d.text((4, y - 3 * ESC), f'{j} #{i}', fill=(0, 0, 160))
            informe['descripciones'].append(dict(juego=j, registro=i, antes=codec.texto(ba), despues=codec.texto(bd),
                                                 solapes=solapes(cd, 5)))
        img.save(OUT / f'descripciones_{lote + 1}.png')
    (OUT / 'solapes.json').write_text(json.dumps(informe, ensure_ascii=False, indent=1), encoding='utf-8')
    print('nombres con solape', [x['texto'] for x in informe['nombres'] if x['solapes_10'] or x['solapes_9']])
    print('rótulos con solape', [x['despues'] for x in informe['rotulos'] if x['solapes']])
    print('descripciones con solape', [x['registro'] for x in informe['descripciones'] if x['solapes']])


if __name__ == '__main__':
    main()
