"""Sugiere, para cada celda QNA de las texturas IE2 de un .arc, la celda IE1 (JP) más parecida del mismo
tamaño que IE1 v89 tradujo. Imprime (celda IE2, fuente IE1, error) y guarda una hoja
IE2 | IE1 JP | IE1 traducida para revisarla a ojo.

Uso: python sugerir.py <salida.png> <arc IE2 relativo a data_iz> [umbral=40]
Las parejas aceptadas se escriben a mano en planes_*.py con celda_ie1(...).
"""
import sys
from functools import lru_cache

import numpy as np
from PIL import Image

import comun as C


@lru_cache(None)
def celdas_ie1():
    jp, tr = C.jp(), C.ie1tr()
    out = []
    for p in jp.rutas('inazuma1/'):
        if not p.endswith('.arc') or p not in tr:
            continue
        a, b = C.U.unwrap(jp.get(p)), C.U.unwrap(tr.get(p))
        ta, tb = C.texturas(a), C.texturas(b)
        if len(ta) != len(tb):
            continue
        try:
            q = C.qna_cajas(p, jp)
        except Exception:  # noqa: BLE001
            continue
        for (n, _, _, x), (_, _, _, y) in zip(ta, tb):
            if x == y or len(x) != len(y) or n not in q:
                continue
            A = np.asarray(C.decodificar(x))
            B = np.asarray(C.decodificar(y))
            for x0, y0, x1, y1 in set(q[n]):
                x0, x1 = sorted((max(x0, 0), min(x1, A.shape[1])))
                y0, y1 = sorted((max(y0, 0), min(y1, A.shape[0])))
                if x1 - x0 < 6 or y1 - y0 < 6:
                    continue
                if np.array_equal(A[y0:y1, x0:x1], B[y0:y1, x0:x1]):
                    continue
                out.append((p, n, (x0, y0, x1, y1), A[y0:y1, x0:x1], B[y0:y1, x0:x1]))
    return out


def comparar(a, b):
    fa = a.astype(float)
    fb = b.astype(float)
    fa[..., :3] *= fa[..., 3:4] / 255
    fb[..., :3] *= fb[..., 3:4] / 255
    return float(np.abs(fa - fb).mean())


def sugerencias(ruta, umbral=40):
    raw = C.U.unwrap(C.jp().get(ruta))
    q = C.qna_cajas(ruta)
    res = []
    lib = celdas_ie1()
    for nombre, _, _, blob in C.texturas(raw):
        if nombre not in q:
            continue
        A = np.asarray(C.decodificar(blob))
        for x0, y0, x1, y1 in sorted(set(q[nombre])):
            x0, x1 = sorted((max(x0, 0), min(x1, A.shape[1])))
            y0, y1 = sorted((max(y0, 0), min(y1, A.shape[0])))
            if x1 - x0 < 6 or y1 - y0 < 6:
                continue
            c = A[y0:y1, x0:x1]
            if not (c[..., 3] > 0).any():
                continue
            mejor = None
            for p, n, caja, ja, tb in lib:
                if ja.shape != c.shape:
                    continue
                e = comparar(c, ja)
                if mejor is None or e < mejor[0]:
                    mejor = (e, p, n, caja, ja, tb)
            if mejor and mejor[0] <= umbral:
                res.append((nombre, (x0, y0, x1, y1), mejor))
    return res


def main():
    salida, arc = sys.argv[1], sys.argv[2]
    umbral = float(sys.argv[3]) if len(sys.argv) > 3 else 40
    ruta = 'inazuma2/data_iz/' + arc
    ims = []
    for nombre, caja, (e, p, n, c1, ja, tb) in sugerencias(ruta, umbral):
        print(f'{nombre} {caja} <- {p.split("/")[-1]}:{n} {c1} err={e:.1f}')
        raw = C.U.unwrap(C.jp().get(ruta))
        blob = [b for nn, _, _, b in C.texturas(raw) if nn == nombre][0]
        A = np.asarray(C.decodificar(blob))
        x0, y0, x1, y1 = caja
        s = 2 if max(ja.shape) < 200 else 1
        fila = [C.ampliar(Image.fromarray(np.ascontiguousarray(z)), s) for z in (A[y0:y1, x0:x1], ja, tb)]
        ims.append(C.hoja(fila, ancho=sum(f.width + 8 for f in fila)))
    if ims:
        C.hoja(ims, ancho=2400).save(salida)


if __name__ == '__main__':
    main()


@lru_cache(None)
def celdas_intactas_ie1():
    """Hashes (normalizados) de celdas QNA de IE1 que v89 NO cambió: se asumen sin texto."""
    import hashlib
    jp, tr = C.jp(), C.ie1tr()
    out = set()
    for p in jp.rutas('inazuma1/'):
        if not p.endswith('.arc') or p not in tr:
            continue
        a, b = C.U.unwrap(jp.get(p)), C.U.unwrap(tr.get(p))
        ta, tb = C.texturas(a), C.texturas(b)
        if len(ta) != len(tb):
            continue
        try:
            q = C.qna_cajas(p, jp)
        except Exception:  # noqa: BLE001
            continue
        for (n, _, _, x), (_, _, _, y) in zip(ta, tb):
            if n not in q:
                continue
            A = np.asarray(C.decodificar(x))
            B = A if x == y else np.asarray(C.decodificar(y))
            for x0, y0, x1, y1 in set(q[n]):
                x0, x1 = sorted((max(x0, 0), min(x1, A.shape[1])))
                y0, y1 = sorted((max(y0, 0), min(y1, A.shape[0])))
                ca = A[y0:y1, x0:x1]
                if ca.size and np.array_equal(ca, B[y0:y1, x0:x1]):
                    out.add(hash_celda(ca))
    return out


def hash_celda(c):
    import hashlib
    n = c.copy()
    n[n[..., 3] == 0] = 0
    return hashlib.sha1(n.tobytes() + str(n.shape).encode()).hexdigest()


def cobertura(ruta, nombre, arr, cajas_cubiertas):
    """Celdas QNA con contenido que no están cubiertas ni son 'sin texto' según IE1."""
    q = C.qna_cajas(ruta).get(nombre, ())
    intactas = celdas_intactas_ie1()
    faltan = []
    cub = np.zeros(arr.shape[:2], bool)
    for a, b, cc, d in cajas_cubiertas:
        cub[max(b, 0):d, max(a, 0):cc] = True
    for x0, y0, x1, y1 in set(q):
        x0, x1 = sorted((max(x0, 0), min(x1, arr.shape[1])))
        y0, y1 = sorted((max(y0, 0), min(y1, arr.shape[0])))
        if x1 - x0 < 6 or y1 - y0 < 6:
            continue
        c = arr[y0:y1, x0:x1]
        if not (c[..., 3] > 0).any():
            continue
        op = c[..., 3] > 0
        if (cub[y0:y1, x0:x1] & op).sum() >= 0.85 * op.sum():
            continue
        if hash_celda(c) in intactas:
            continue
        faltan.append([x0, y0, x1, y1])
    return faltan
