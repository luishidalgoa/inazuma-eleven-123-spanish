"""IE2 Fuego v13 · inicio: previews de todas las frases traducidas (caja de v02/previews.py: modelo del
motor 22 × 3 y FONT12.bcfnt con portadores). Una imagen por evento: previews/<evento>.png.
Uso: python -X utf8 previews.py
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

import apply as A

M = A.M
P02 = A._modulo('v02_previews', A.V02 / 'previews.py')
P = P02.P


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    informe = json.loads((A.HERE / 'informe.json').read_text(encoding='utf-8'))
    tmp = Path(tempfile.mkdtemp()) / 'FONT12.bcfnt'
    base = next(M.CAND / f'probe_ie1_{v}/archive.fa' for v in ('v89', 'v88')
                if (M.CAND / f'probe_ie1_{v}/archive.fa').exists()) \
        if any((M.CAND / f'probe_ie1_{v}/archive.fa').exists() for v in ('v89', 'v88')) else A.BASE
    tmp.write_bytes(M.Archivo(base).get(P.F12))
    fuente = M.K.cargar(tmp)
    out = A.HERE / 'previews'
    out.mkdir(exist_ok=True)
    for x in out.glob('*.png'):
        x.unlink()
    ch = P.CAJA_H * P.ESC + 18
    W = (P.CAJA_W * P.ESC + 20) * 3 + 20
    for eid, info in informe['eventos'].items():
        filas = [f for f in info['registros'] if f['estado'] == 'traducido']
        bloques = []
        for f in filas:
            cuerpo = M.transportar(f['texto'])
            pags = M.paginas(cuerpo)
            cajas = [P.caja(fuente, M.SALTO.join(M.normalizar(x) for x in pg), '')[0] for pg in pags]
            bloques.append((f, cajas))
        filas_img = sum((len(c) + 2) // 3 for _, c in bloques)
        H = 20 + len(bloques) * 34 + filas_img * ch
        im = Image.new('RGB', (W, H), (10, 12, 20))
        d = ImageDraw.Draw(im)
        y = 6
        for f, cajas in bloques:
            etiqueta = f"#{f['indice']} id {f['id']}->{f['id_nds']} ord {f['ordinal']} {f['bytes']} B {f['voz'] or ''}"
            if 'condensado' in f:
                etiqueta += '  CONDENSADO: ' + f['motivo']
            d.text((10, y), etiqueta, fill=(255, 220, 120))
            d.text((10, y + 14), 'JP: ' + f['jp'].replace('\\n', ' ')[:90], fill=(170, 190, 230))
            y += 32
            for j, c in enumerate(cajas):
                x = 10 + (j % 3) * (P.CAJA_W * P.ESC + 20)
                if j and j % 3 == 0:
                    y += ch
                im.paste(c, (x, y))
            y += ch + 2
        im.save(out / f'{eid}.png')
        print(eid, len(bloques), im.size)


if __name__ == '__main__':
    main()
