"""IE2 Fuego v02 · previews de 8 registros con el modelo real del motor (comun82: 22 × 3, corte por carácter).

Caja de v77/previews.py (FONT12.bcfnt de la base, escala x2). %s/%d se dibujan con su hueco reservado (Ｘ).
Uso: python -X utf8 previews.py -> previews/<paquete>_<evento>_<indice>.png
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

import comun_ie2 as M

sys.path.insert(0, str(M.K82.V77))
import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location('prev77', M.K82.V77 / 'previews.py')
P = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(P)


def elegir(aplicado):
    """8 casos variados: desplazado, igual, %s, varias cajas, guion, mch, el más largo, la sonda v01."""
    ev = aplicado['eventos']
    todos = [(k, r) for k, e in ev.items() for r in e['registros']]
    casos = []

    def primero(cond):
        for k, r in todos:
            if (k, r['indice']) not in {(c[0], c[1]['indice']) for c in casos} and cond(k, r):
                casos.append((k, r))
                return

    primero(lambda k, r: k.startswith('eve:2601') and r['clase'] == 'desplazado' and r['cajas'] >= 2)
    primero(lambda k, r: r['clase'] == 'igual' and k.startswith('eve:23') and r['cajas'] == 1)
    primero(lambda k, r: '%s' in r['texto'] and not k.startswith('eve:21'))
    primero(lambda k, r: r['cajas'] >= 4)
    primero(lambda k, r: '−' in r['texto'])
    primero(lambda k, r: k.startswith('mch:') and r['cajas'] >= 2)
    mayor = max(todos, key=lambda t: t[1]['bytes'])
    casos.append(mayor)
    return casos


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    aplicado = json.loads((M.HERE / 'aplicado.json').read_text(encoding='utf-8'))
    pares = json.loads((M.HERE / 'pares.json').read_text(encoding='utf-8'))
    jp = M.Archivo(M.JP)
    tmp = Path(tempfile.mkdtemp()) / 'FONT12.bcfnt'
    base = next(M.CAND / f'probe_ie1_{v}/archive.fa' for v in ('v89', 'v88')
                if (M.CAND / f'probe_ie1_{v}/archive.fa').exists())
    tmp.write_bytes(M.Archivo(base).get(P.F12))   # FONT12 con los portadores de acentos (v74/v75)
    fuente = M.K.cargar(tmp)
    out = M.HERE / 'previews'
    out.mkdir(exist_ok=True)
    for x in out.glob('*.png'):
        x.unlink()
    casos = elegir(aplicado)
    v01 = M.S.parse((M.V01_EVENTOS / '22010100.ssd').read_bytes())[2]
    idx = aplicado['protegido_v01']['registro']
    casos.append(('eve:22010100', dict(indice=idx, texto=None, clase='protegido (sonda v01)', cuerpo=v01[idx].body)))
    for k, r in casos:
        pk, eid = k.split(':')
        if r.get('cuerpo') is not None:
            cuerpo = r['cuerpo']
            jpt = M.S.parse(jp.evento(pk, int(eid)))[2][r['indice']].body.decode('cp932')
            fuente_es = '(sonda v01)'
        else:
            cuerpo = M.transportar(r['texto'])
            fila = next(f for f in pares[k] if f['indice'] == r['indice'])
            jpt, fuente_es = fila['jp'], fila['es']
        pags = M.paginas(cuerpo)
        cajas = [P.caja(fuente, M.SALTO.join(M.normalizar(x) for x in pg), '')[0] for pg in pags]
        ch = P.CAJA_H * P.ESC + 26
        W = P.CAJA_W * P.ESC + 40
        H = 70 + ch * len(cajas)
        im = Image.new('RGB', (W, H), (10, 12, 20))
        d = ImageDraw.Draw(im)
        d.text((10, 6), f'{k} #{r["indice"]}  clase {r["clase"]}  {len(cuerpo)} B  modelo del motor 22 car. x 3 líneas',
               fill=(255, 220, 120))
        d.text((10, 22), 'NDS: ' + fuente_es[:110], fill=(170, 190, 230))
        for j, (c, pg) in enumerate(zip(cajas, pags)):
            y = 60 + j * ch
            d.text((10, y), f'caja {j + 1}: ' + ' | '.join(pg), fill=(150, 150, 150))
            im.paste(c, (10, y + 14))
        nombre = f'{pk}_{eid}_{r["indice"]}.png'
        im.save(out / nombre)
        print(nombre, [len(x) for pg in pags for x in pg], pags)


if __name__ == '__main__':
    main()
