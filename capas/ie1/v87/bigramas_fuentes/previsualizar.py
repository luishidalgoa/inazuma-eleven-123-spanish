"""v87 · Vista previa con los mapas de bits de FONT8 (antes = v86, después = extra/) y control de solapes.

Modelo (apply.py): paso fijo de 10 px (pestaña en pantalla superior y rótulo del minimapa);
x = lápiz + trunc((11 - advance)/2) + left. Se añade el paso de 9 px (el de la pantalla inferior para
e6214: trunc(7 * 1.25) + 1) solo como margen de seguridad.
Solape: núcleos (alfa >= 8) de casillas distintas en la misma columna o separados por 0 px.
Salida: previews/*.png (x4) y previews/solapes.json.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import apply as A  # noqa: E402

ESC = 4
REG = {e['par']: e for e in json.loads(A.REGISTRO.read_text(encoding='utf-8'))['bigramas']}
INF85 = json.loads((A.ROOT / 'work/ie1/capas/v85/bigramas_sonda/informe.json').read_text(encoding='utf-8'))


def fuentes():
    tmp = Path(tempfile.mkdtemp(prefix='ie123_v87p_'))
    (tmp / 'antes.bcfnt').write_bytes(A.abrir(A.BASE)(A.F8))
    return A.cargar(tmp / 'antes.bcfnt'), A.cargar(HERE / 'extra' / A.F8)


def colocar(F, celdas, paso):
    out = []
    for k, c in enumerate(celdas):
        cp = int(REG[c]['unicode'][2:], 16) if len(c) == 2 else A.codepoint(c)
        gi = F.gi(cp)
        left, _w, adv = F.metrics[gi]
        x0 = k * paso + (A.W - adv) // 2 + left
        px = {(x0 + x, y): v for y, row in enumerate(F.bitmap(gi)) for x, v in enumerate(row) if v}
        out.append(dict(c=c, px=px))
    return out


def solapes(col):
    res, gaps = [], []
    for i in range(len(col) - 1):
        a = [x for (x, _), v in col[i]['px'].items() if v >= A.SOLIDO]
        b = [x for (x, _), v in col[i + 1]['px'].items() if v >= A.SOLIDO]
        if not a or not b:
            continue
        g = min(b) - max(a) - 1
        gaps.append(g)
        if g < 1:
            res.append(dict(entre=[col[i]['c'], col[i + 1]['c']], hueco=g))
    return res, (min(gaps) if gaps else None)


def pintar(filas, ruta):
    ancho = max(120, max(max((x for c in col for x, _ in c['px']), default=0) for _, col in filas) + 8)
    img = Image.new('RGB', ((ancho + 90) * ESC, (len(filas) * 16 + 4) * ESC), (40, 44, 60))
    d = ImageDraw.Draw(img)
    for r, (titulo, col) in enumerate(filas):
        oy = 2 + r * 16
        d.text((2 * ESC, (oy + 2) * ESC), titulo, fill=(200, 200, 120))
        for k, c in enumerate(col):
            tono = (255, 255, 255) if k % 2 == 0 else (150, 220, 255)
            for (x, y), v in c['px'].items():
                a = v / 15
                rgb = tuple(int(40 + (t - 40) * a) for t in tono)
                X, Y = (90 + 2 + x) * ESC, (oy + y) * ESC
                d.rectangle([X, Y, X + ESC - 1, Y + ESC - 1], fill=rgb)
    img.save(ruta)


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    antes, despues = fuentes()
    casos = {}
    for n in INF85['nombres']:
        casos.setdefault(f"pestaña {n['texto']}", n['celdas'])
    for viejo, r in INF85['rotulos'].items():
        casos[f"rótulo {r['nuevo']}"] = [' '] * r['espacios'] + r['celdas']
    informe = {}
    (HERE / 'previews').mkdir(exist_ok=True)
    for nombre, celdas in casos.items():
        filas = []
        texto = ''.join(celdas).strip()
        for paso in (10, 9):
            nativo = colocar(despues, list(texto), paso) if len(texto) <= 10 else None
            col_a = colocar(antes, celdas, paso)
            col_d = colocar(despues, celdas, paso)
            s, g = solapes(col_d)
            informe[f'{nombre} · paso {paso}'] = dict(celdas=celdas, solapes=s, hueco_minimo=g,
                                                      nativo_hueco_minimo=solapes(nativo)[1] if nativo else None)
            filas += [(f'v86 paso {paso}', col_a), (f'v87 paso {paso}', col_d)]
            if nativo:
                filas.append((f'letras paso {paso}', nativo))
        nom = nombre.replace(' ', '_').replace('ñ', 'n').replace('ó', 'o')
        pintar(filas, HERE / 'previews' / f'{nom}_x{ESC}.png')
    glifos = [(p, [p]) for p in REG]
    pintar([(f'«{p}»', colocar(despues, c, 10)) for p, c in glifos], HERE / 'previews' / f'glifos_x{ESC}.png')
    (HERE / 'previews' / 'solapes.json').write_text(json.dumps(informe, ensure_ascii=False, indent=1),
                                                     encoding='utf-8')
    for k, v in informe.items():
        print(k, '|'.join(v['celdas']), 'solapes', v['solapes'], 'hueco mín', v['hueco_minimo'],
              'letras sueltas', v['nativo_hueco_minimo'])


if __name__ == '__main__':
    main()
