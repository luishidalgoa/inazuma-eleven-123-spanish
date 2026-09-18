"""hoja.py salida.png arc_rel tex_sub... [--s N]: JP de texturas concretas (0 = todas sin cambiar en v03)."""
import sys
sys.path.insert(0, r'C:/Users/luish/Projects/inazuma-eleven-123-spanish/work/ie2/shared/capas/v06/graficos')
import numpy as np
import base as B
C = B.C
a = sys.argv[1:]
s = 1
if '--s' in a:
    i = a.index('--s'); s = int(a[i + 1]); del a[i:i + 2]
out, arcs = a[0], a[1].split(',')
subs = a[2:]
ims = []
for arc in arcs:
    ruta = 'inazuma2/data_iz/' + arc
    v = {n: b for n, _, _, b in C.texturas(C.U.unwrap(B.base_arc(ruta)))}
    for n, _, _, b in C.texturas(C.U.unwrap(C.jp().get(ruta))):
        if subs and not any(x in n for x in subs):
            continue
        if not subs and v[n] != b:
            continue
        im = C.decodificar(b)
        if max(im.size) < 9 or not (np.array(im)[..., 3] > 0).any():
            continue
        ims.append(C.par(im, im, s=s, titulo=arc.split('/')[-1] + ' ' + n) if False else
                   C.hoja([C.ampliar(im, s)], ancho=max(200, im.width * s + 20)))
        ims[-1] = C.par(im, C.ampliar(im, 1), s=s, titulo=n) if False else ims[-1]
        from PIL import ImageDraw
        d = ImageDraw.Draw(ims[-1]); d.text((2, 0), n, fill=(255, 255, 0, 255))
C.hoja(ims, ancho=2000).save(out)
