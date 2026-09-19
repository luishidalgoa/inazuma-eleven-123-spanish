"""v85 · previsualización y comprobación de solapes de la sonda de bigramas con el modelo real del motor
(work/ie1/capas/fuentes/espaciado_fuente/motor.py): x_tinta = base + trunc((15 - advance)/2) + left.

Fuentes: antes = FONT12 de probe_ie1_v84 (= v75/glifos_eu), después = extra/font/FONT12.bcfnt de la sonda.
Modelos de lápiz (base):
  proporcional   base += advance (diálogo, CSprMenuCtrl, listas)
  paso 15        base = trunc(k * 12 * 1.25) (camino de paso fijo 0x2ed24 con FontGetCharWidth = 12:
                 ficha, rótulo del minimapa)
  paso 12,5      base = trunc(k * 10 * 1.25) (0xe6214 con el ancho forzado del ITX
                 DRAW_ON_CHARACTOR_FONT12_DISP_TOP_FORCE_CHAR_WIDTH = 10; es el candidato para la pestaña
                 del hablante, cscenedirection_1375 -> 0xc2f28; ver informe.md)
Pestaña del hablante: 72 px (v74/nombres_cortos). Rótulo: 10 casillas (150 px) en la placa de 239 px.
Solape: dos glifos distintos con tinta en la misma columna, o contacto (hueco de 0 px entre tintas).
Salida: previews/*.png (x3) y previews/solapes.json, verificacion_kanji.json.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[5]
sys.path.insert(0, str(HERE))
import apply as A  # noqa: E402

ESC, ALTO = 3, 16
ANTES = A.cargar(ROOT / 'work/ie1/capas/fuentes/glifos_eu/extra' / A.F12)
DESPUES = A.cargar(HERE / 'extra' / A.F12)
REG = {e['par']: e for e in json.loads(A.REGISTRO.read_text(encoding='utf-8'))['bigramas']}
INF = json.loads((HERE / 'informe.json').read_text(encoding='utf-8'))
MODELOS = {'proporcional': None, 'paso 15': 12, 'paso 12,5': 10}


def gis(fuente, celdas):
    out = []
    for c in celdas:
        if len(c) == 2:
            out.append((c, fuente.gi(int(REG[c]['unicode'][2:], 16))))
        else:
            out.append((c, fuente.gi(A.codepoint(c))))
    return out


def colocar(fuente, celdas, modelo):
    paso = MODELOS[modelo]
    pen = 0
    out = []
    for k, (c, gi) in enumerate(gis(fuente, celdas)):
        left, _w, adv = fuente.metrics[gi]
        base = pen if paso is None else int(k * paso * 1.25)
        x0 = base + A.desplazamiento(15, left, adv)
        px = {(x0 + x, y): v for y, row in enumerate(fuente.bitmap(gi)) for x, v in enumerate(row) if v}
        out.append(dict(c=c, base=base, x0=x0, px=px))
        pen += adv
    return out


def solapes(col):
    res = []
    for a, b in zip(col, col[1:]):
        if not a['px'] or not b['px']:
            continue
        fa = max(x for x, _ in a['px'])
        ib = min(x for x, _ in b['px'])
        comunes = set(a['px']) & set(b['px'])
        res.append(dict(par=f"{a['c']}|{b['c']}", hueco=ib - fa - 1, pixeles_comunes=len(comunes)))
    peor = min((r['hueco'] for r in res), default=None)
    return dict(huecos=res, hueco_min=peor, solape=any(r['hueco'] < 1 or r['pixeles_comunes'] for r in res))


def ancho(col):
    xs = [x for g in col for x, _ in g['px']]
    return max(xs) + 1 if xs else 0


def lienzo(filas, titulo, limite=None, ancho_px=260):
    W = (ancho_px + 10) * ESC + 330
    H = len(filas) * (ALTO + 12) * ESC + 40
    img = Image.new('RGB', (W, H), (24, 28, 40))
    dr = ImageDraw.Draw(img)
    dr.text((6, 6), titulo, fill=(255, 255, 160))
    y0 = 30
    for etiqueta, col, rejilla in filas:
        dr.text((6, y0 + ALTO * ESC // 2 - 6), etiqueta, fill=(220, 220, 220))
        ox = 320
        for g in col:
            x = ox + g['base'] * ESC
            dr.line([(x, y0), (x, y0 + ALTO * ESC)], fill=(70, 70, 95))
        if limite:
            x = ox + limite * ESC
            dr.line([(x, y0 - 3), (x, y0 + ALTO * ESC + 3)], fill=(220, 60, 60), width=2)
        for k, g in enumerate(col):
            tono = (255, 255, 255) if len(g['c']) == 1 else (140, 220, 255)
            for (x, y), v in g['px'].items():
                f = v / 15
                X, Y = ox + x * ESC, y0 + y * ESC
                dr.rectangle([X, Y, X + ESC - 1, Y + ESC - 1],
                             fill=tuple(int(c * f) for c in tono))
        y0 += (ALTO + 12) * ESC
    return img


def main():
    out = HERE / 'previews'
    out.mkdir(exist_ok=True)
    informe = {}
    casos = []
    # nombres
    aurelia = next(n for n in INF['nombres'] if n['registro'] == 1153 and n['campo'] == 16)
    silvia = next(n for n in INF['nombres'] if n['registro'] == 14)
    for nombre, celdas in (('Aurelia', aurelia['celdas']), ('Silvia', silvia['celdas'])):
        filas = []
        for modelo in MODELOS:
            ca = colocar(ANTES, list(nombre), modelo)
            cd = colocar(DESPUES, celdas, modelo)
            filas.append((f'antes  {modelo} ({ancho(ca)} px)', ca, None))
            filas.append((f'despues {modelo} ({ancho(cd)} px)', cd, None))
            informe[f'pestana {nombre} {modelo}'] = dict(antes_px=ancho(ca), despues_px=ancho(cd), cabe_72=ancho(cd) <= 72,
                                                         antes=solapes(ca), despues=solapes(cd))
        lienzo(filas, f'{nombre}: pestana del hablante (72 px, linea roja) y ficha (paso 15). '
                      f'Celeste = bigrama. {"|".join(celdas)}', limite=72, ancho_px=110) \
            .save(out / f'nombre_{nombre}_x3.png')
        casos.append(f'nombre_{nombre}_x3.png')
    # rótulos
    for viejo, d in INF['rotulos'].items():
        antes_txt = next(r['antes'] for r in INF['rotulos_aplicados'] if r['antes'].strip(' ') == viejo)
        ca = colocar(ANTES, list(antes_txt), 'paso 15')
        despues = [' '] * d['espacios'] + d['celdas']
        cd = colocar(DESPUES, despues, 'paso 15')
        cp = colocar(DESPUES, despues, 'proporcional')
        filas = [(f'antes «{antes_txt.strip()}» ({len(antes_txt)} casillas)', ca, None),
                 (f'despues «{d["nuevo"]}» ({len(despues)} casillas)', cd, None),
                 ('despues, si fuera proporcional', cp, None)]
        nom = d['nuevo'].replace(' ', '_')
        lienzo(filas, f'Rotulo 0x4037 (paso 15, limite 10 casillas = 150 px en rojo): {"|".join(d["celdas"])}',
               limite=150, ancho_px=240).save(out / f'rotulo_{nom}_x3.png')
        casos.append(f'rotulo_{nom}_x3.png')
        informe[f'rotulo {d["nuevo"]}'] = dict(casillas=len(despues), antes=solapes(ca), despues=solapes(cd),
                                               despues_px=ancho(cd), proporcional=solapes(cp))
    # hoja de glifos
    filas = []
    for p, e in REG.items():
        col = colocar(DESPUES, [p], 'paso 15')
        filas.append((f"«{p}» {e['kanji']} {e['sjis']} cwdh {e['cwdh']} D {e['D']}", col, None))
    lienzo(filas, 'Glifos del registro en su casilla de 15 px (linea roja = fin de la casilla)', limite=15,
           ancho_px=20).save(out / 'glifos_registro_x3.png')
    casos.append('glifos_registro_x3.png')
    solape_bigramas = {k: v['despues']['solape'] for k, v in informe.items()}
    (out / 'solapes.json').write_text(json.dumps(dict(modelos={k: str(v) for k, v in MODELOS.items()},
                                                      resumen_solape_despues=solape_bigramas, detalle=informe,
                                                      imagenes=casos), ensure_ascii=False, indent=1),
                                      encoding='utf-8')
    # verificación de kanji: apariciones en v85 == colocadas por la sonda
    esc = json.loads((HERE / 'escaneo_v85.json').read_text(encoding='utf-8'))
    base = json.loads((HERE / 'escaneo_base_v84.json').read_text(encoding='utf-8'))
    esperado = {e['sjis']: 0 for e in REG.values()}
    for n in INF['nombres']:
        for c in n['celdas']:
            if len(c) == 2:
                esperado[REG[c]['sjis']] += 1
    for r in INF['rotulos_aplicados']:
        for c in r['celdas']:
            if len(c) == 2:
                esperado[REG[c]['sjis']] += 1
    ver = {}
    for code, n in esperado.items():
        v = esc['codigos'][code]
        ver[code] = dict(kanji=bytes.fromhex(code).decode('cp932'), texto_v85=v.get('texto', 0), colocados=n,
                         binario_textual_v85=v.get('binario_textual', 0),
                         texto_v84=base['codigos'][code].get('texto', 0),
                         binario_textual_v84=base['codigos'][code].get('binario_textual', 0),
                         ok=v.get('texto', 0) == n and not v.get('binario_textual')
                         and not base['codigos'][code].get('texto') and not base['codigos'][code].get('binario_textual'))
    (HERE / 'verificacion_kanji.json').write_text(json.dumps(dict(
        criterio='escaneo_kanji.py (4 juegos + menu/import/message + CRO + code.bin): en v84 0 apariciones '
                 'alineadas en texto y 0 en contexto textual de binarios; en v85 exactamente las colocadas',
        codigos=ver, ok=all(x['ok'] for x in ver.values())), ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(solape_bigramas, ensure_ascii=False, indent=1))
    for k, v in informe.items():
        print(k, {kk: vv for kk, vv in v.items() if not isinstance(vv, dict)},
              'hueco_min despues', v['despues']['hueco_min'], 'antes', v['antes']['hueco_min'])
    print('kanji ok', all(x['ok'] for x in ver.values()))


if __name__ == '__main__':
    main()
