import sys, json
sys.path.insert(0, r'C:/Users/luish/Projects/inazuma-eleven-123-spanish/work/ie2/shared/capas/v06/graficos')
import numpy as np
import base as B
C = B.C
pend = json.load(open(B.V03 / 'pendientes.json', encoding='utf-8'))
pk = {(p.get('arc'), p.get('textura')): p['tipo'] for p in pend}
dirs = sys.argv[1:] or ['a_field', 'a_title', 'a_event']
for d in dirs:
    for ruta in sorted(C.jp().rutas('inazuma2/data_iz/' + d + '/')):
        if not ruta.endswith('.arc'):
            continue
        raw = C.U.unwrap(C.jp().get(ruta))
        v = {n: b for n, _, _, b in C.texturas(C.U.unwrap(B.base_arc(ruta)))}
        filas = []
        for n, _, _, b in C.texturas(raw):
            try:
                a = C.decodificar(b)
            except Exception:
                filas.append(f'{n}:ERR'); continue
            if max(a.size) < 9 or not (np.array(a)[..., 3] > 0).any():
                continue
            st = ('v03' if v[n] != b else 'jp') + '/' + pk.get((ruta, n), '')
            filas.append(f'{n.replace("ie02_", "")}[{a.width}x{a.height}]{st}')
        print(ruta.split('data_iz/')[1], len(filas))
        for f in filas:
            print('   ', f)
