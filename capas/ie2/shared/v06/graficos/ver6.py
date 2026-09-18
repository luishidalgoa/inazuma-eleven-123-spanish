"""Original | v06 (×escala) de texturas concretas ya escritas en extra/.
Uso: python ver6.py <salida.png> <arc rel. a data_iz> <subcadena de textura>... [--s N] [--caja x0 y0 x1 y1]"""
import sys

import base as B
C = B.C


def main():
    args = sys.argv[1:]
    s, caja = 4, None
    if '--s' in args:
        i = args.index('--s')
        s = int(args[i + 1])
        del args[i:i + 2]
    if '--caja' in args:
        i = args.index('--caja')
        caja = tuple(int(v) for v in args[i + 1:i + 5])
        del args[i:i + 5]
    out, arc, subs = args[0], 'inazuma2/data_iz/' + args[1], args[2:]
    jp = {n: b for n, _, _, b in C.texturas(C.U.unwrap(C.jp().get(arc)))}
    f = B.EXTRA / arc
    nu = {n: b for n, _, _, b in C.texturas(C.U.unwrap(f.read_bytes()))} if f.exists() else jp
    ims = []
    for n in jp:
        if any(x in n for x in subs):
            a, b = C.decodificar(jp[n]), C.decodificar(nu[n])
            if caja:
                a, b = a.crop(caja), b.crop(caja)
            ims.append(C.par(a, b, s=s, titulo=n))
    C.hoja(ims, ancho=max(i.width for i in ims)).save(out)


if __name__ == '__main__':
    main()
