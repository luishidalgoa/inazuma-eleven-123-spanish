"""Genera sugerencias.json con las parejas celda IE2 <- celda IE1 (err <= umbral) de todos los .arc de inazuma2
(salvo a_data_replace) y una hoja por arc en <dir>. Revisar a ojo antes de aceptarlas en planes."""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

import comun as C
import sugerir as S


def main():
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    umbral = float(sys.argv[2]) if len(sys.argv) > 2 else 25
    todo = {}
    for ruta in sorted(C.jp().rutas('inazuma2/data_iz/')):
        if not ruta.endswith('.arc') or 'a_data_replace' in ruta:
            continue
        try:
            sug = S.sugerencias(ruta, umbral)
        except Exception as e:  # noqa: BLE001
            print('error', ruta, e)
            continue
        if not sug:
            continue
        raw = C.U.unwrap(C.jp().get(ruta))
        tex = {n: np.asarray(C.decodificar(b)) for n, _, _, b in C.texturas(raw)}
        ims = []
        for nombre, caja, (e, p, n, c1, ja, tb) in sug:
            todo.setdefault(ruta, []).append(dict(textura=nombre, caja=caja, ie1=p, tex1=n, caja1=list(c1), err=e))
            x0, y0, x1, y1 = caja
            s = 2 if max(ja.shape) < 200 else 1
            fila = [C.ampliar(Image.fromarray(np.ascontiguousarray(z)), s)
                    for z in (tex[nombre][y0:y1, x0:x1], tb)]
            ims.append(C.hoja(fila, ancho=sum(f.width + 8 for f in fila)))
        C.hoja(ims, ancho=2400).save(out / (ruta.split('/')[-2] + '__' + ruta.split('/')[-1] + '.png'))
        print(ruta, len(sug))
    (C.HERE / 'sugerencias.json').write_text(json.dumps(todo, ensure_ascii=False, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()
