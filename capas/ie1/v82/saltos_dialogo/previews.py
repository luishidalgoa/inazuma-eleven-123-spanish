"""Previews con el modelo REAL del motor (comun82.motor: 22 caracteres por línea, 3 por página, corte por
carácter). Por registro: v20 (antes del piloto), v81 (piloto v77, lo que se vio en Azahar) y v82.
Dibujo horizontal con motor.py + FONT12 de la base (caja de v77/previews.py, escala x2).
Uso: python previews.py -> previews/<evento>_<indice>.png
"""
import json, sys
from pathlib import Path
from PIL import Image, ImageDraw
import comun82 as M
K = M.K
sys.path.insert(0, str(M.V77))
import importlib.util
spec = importlib.util.spec_from_file_location('prev77', M.V77 / 'previews.py'); P = importlib.util.module_from_spec(spec); spec.loader.exec_module(P)
from dialogue_typography import encode_fullwidth
HERE = Path(__file__).resolve().parent
C = K.ROOT / 'work/shared/candidatas'
CASOS = [(81000090, 406), (92040100, 15)]

def paginas(cuerpo):
    return [K.SALTO.join(pg) for pg in M.paginas_motor(cuerpo)]

def main():
    ap = {(e['evento'], r['indice']): r for e in json.loads((HERE / 'aplicado.json').read_text(encoding='utf-8'))['eventos'] for r in e['registros']}
    v81, v82 = K.Archivo(C / 'probe_ie1_v81/archive.fa'), K.Archivo(C / 'probe_ie1_v82/archive.fa')
    f = v82.fuente()
    (HERE / 'previews').mkdir(exist_ok=True)
    for eid, idx in CASOS:
        cols = [('v20 (antes del piloto)', encode_fullwidth(ap[(eid, idx)]['v20'])),
                ('v81 (piloto v77, visto en Azahar)', K.S.parse(v81.evento(eid))[2][idx].body),
                ('v82 (22 caracteres)', K.S.parse(v82.evento(eid))[2][idx].body)]
        cajas = [(t, [P.caja(f, pg, t)[0] for pg in paginas(b)], paginas(b)) for t, b in cols]
        ch = P.CAJA_H * P.ESC + 26
        W = len(cajas) * (P.CAJA_W * P.ESC + 20) + 20
        H = 40 + ch * max(len(c[1]) for c in cajas)
        im = Image.new('RGB', (W, H), (10, 12, 20)); d = ImageDraw.Draw(im)
        d.text((10, 8), f'{eid} #{idx} - modelo del motor (ina_main1.cro 0x424f4): 22 car./línea, 3 líneas/página, corte por carácter', fill=(255, 220, 120))
        for k, (t, imgs, txt) in enumerate(cajas):
            x = 10 + k * (P.CAJA_W * P.ESC + 20)
            d.text((x, 24), t, fill=(170, 190, 230))
            for j, (c, s) in enumerate(zip(imgs, txt)):
                y = 40 + j * ch
                d.text((x, y), f'caja {j + 1}: ' + ' | '.join(s.split(K.SALTO)), fill=(150, 150, 150))
                im.paste(c, (x, y + 14))
        im.save(HERE / 'previews' / f'{eid}_{idx}.png')
        print(eid, idx)
        for t, _, txt in cajas:
            print('  ', t, [s.split(K.SALTO) for s in txt])

main()
