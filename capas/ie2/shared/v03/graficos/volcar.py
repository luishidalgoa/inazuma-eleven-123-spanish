"""Vuelca a PNG todas las texturas CTPK de inazuma2 (japonés) y de IE1 (JP y traducido) para revisarlas.

Salida: <dir>/{ie2,ie1jp,ie1tr}/<ruta del arc>/<textura>.png y un índice JSON.
Comprueba el decodificador numpy contra ctpk_ui.decode en una muestra por formato.
Uso: python volcar.py <dir_salida>
"""
import json
import sys
from pathlib import Path

import comun as C


def main():
    out = Path(sys.argv[1])
    verificados = {}
    indice = []
    fuentes = [('ie2', C.jp(), 'inazuma2/'), ('ie1jp', C.jp(), 'inazuma1/'), ('ie1tr', C.ie1tr(), 'inazuma1/')]
    for etiqueta, arc, pref in fuentes:
        for p in sorted(arc.rutas(pref)):
            if not p.endswith(('.arc', '.lzs')):
                continue
            raw = C.U.unwrap(arc.get(p))
            for nombre, off, ln, blob in C.texturas(raw):
                try:
                    im = C.decodificar(blob)
                except ValueError as e:
                    print('sin decodificar', p, nombre, e)
                    continue
                fmt = C.T.metadata(blob)[3]
                if fmt not in verificados and etiqueta == 'ie2' and fmt in C.EDITABLES:
                    ref = C.T.decode(blob)
                    if ref.tobytes() != im.tobytes():
                        raise SystemExit(f'decodificador distinto en formato {fmt}: {p} {nombre}')
                    verificados[fmt] = f'{p}:{nombre}'
                destino = out / etiqueta / p / (Path(nombre).stem + '.png')
                destino.parent.mkdir(parents=True, exist_ok=True)
                im.save(destino)
                indice.append(dict(fuente=etiqueta, arc=p, textura=nombre, w=im.width, h=im.height,
                                   fmt=fmt, clave=C.clave_pixeles(blob)))
    (out / 'indice.json').write_text(json.dumps(indice, ensure_ascii=False), encoding='utf-8')
    print(len(indice), 'texturas; formatos verificados:', verificados)


if __name__ == '__main__':
    main()
