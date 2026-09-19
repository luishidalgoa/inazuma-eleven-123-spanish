"""Validación offline de v22/ayuda: estructura ARCV/CTPK intacta, cambios solo donde toca. Escribe validate.json."""
import json
import sys

import numpy as np

import ayuda22 as K

C = K.C


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    jp = C.jp()
    fallos, ok = [], 0
    for f in sorted(p for p in K.EXTRA.rglob('*') if p.is_file()):
        ruta = f.relative_to(K.EXTRA).as_posix()
        orig, nuevo = jp.get(ruta), f.read_bytes()
        if ruta == K.MASTUTORIAL:
            if nuevo != orig:
                fallos.append((ruta, 'MASTutorial no es el japonés'))
            ok += 1
            continue
        ro, rn = C.U.unwrap(orig), C.U.unwrap(nuevo)
        if C.U.entries(ro) != C.U.entries(rn):
            fallos.append((ruta, 'entradas ARCV distintas'))
            continue
        to = {n: b for n, _, _, b in C.texturas(ro)}
        tn = {n: b for n, _, _, b in C.texturas(rn)}
        for n, b in tn.items():
            if C.T.metadata(b) != C.T.metadata(to[n]):
                fallos.append((ruta, n, 'metadata CTPK'))
        if '/data/' in ruta:
            (n, b), = tn.items()
            a, d = np.array(C.decodificar(to[n])), np.array(C.decodificar(b))
            ancho = 400 if 'syup_bg' in ruta else K.W3
            if not (a[K.H3:] == d[K.H3:]).all() or not (a[:, ancho:] == d[:, ancho:]).all():
                fallos.append((ruta, 'cambios fuera de la captura'))
            if (a[..., 3] != d[..., 3]).any():
                fallos.append((ruta, 'alfa cambiado'))
            if (a == d).all():
                fallos.append((ruta, 'sin cambios'))
        else:
            cambiadas = {n for n in tn if tn[n] != to[n]}
            permitidas = {'ie02_menu_system_window_b02.tga', 'ie02_menu_system_panel_b04.tga'}
            base = K.B6.EXTRA / ruta
            if base.exists():
                tb = {n: b for n, _, _, b in C.texturas(C.U.unwrap(base.read_bytes()))}
                extra = {n for n in tn if tn[n] != tb[n]} - permitidas
                if extra:
                    fallos.append((ruta, 'texturas v06 alteradas', sorted(extra)))
            if not permitidas <= cambiadas:
                fallos.append((ruta, 'pestañas sin cambiar'))
        ok += 1
    res = dict(ficheros=ok, fallos=fallos)
    (K.HERE / 'validate.json').write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding='utf-8')
    print(ok, 'ficheros;', len(fallos), 'fallos')
    for x in fallos:
        print(' ', x)
    sys.exit(1 if fallos else 0)


if __name__ == '__main__':
    main()
