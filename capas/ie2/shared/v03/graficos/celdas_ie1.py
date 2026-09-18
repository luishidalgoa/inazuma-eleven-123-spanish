"""Trasplante por celdas QNA desde IE1 (cualquier posición/textura/arc).

Índice: por cada textura IE1 que v89 cambió y cada caja QNA de esa textura cuya celda cambió,
clave = hash(píxeles JP normalizados de la celda) -> celda traducida. También clave de forma
(máscara alfa + máscara de color relativo) para celdas que solo cambian de paleta.
Para IE2: cada caja QNA; si su celda coincide, se copia la celda traducida (recoloreada si hace falta).
Solo se aplica si todas las celdas con trazo japonés de la textura quedan resueltas o si la textura
no tiene más cajas con cambios en IE1 (no se dejan texturas mezcladas: lo decide apply por zonas).
"""
import hashlib
import pickle
from collections import defaultdict

import numpy as np

import comun as C
from apply import recolorear_zona


def _norm(a):
    b = a.copy()
    b[b[..., 3] == 0] = 0
    return b


def _h(a):
    return hashlib.sha1(np.ascontiguousarray(_norm(a)).tobytes() + str(a.shape[:2]).encode()).hexdigest()


def _forma(a):
    n = _norm(a)
    cols = {}
    idx = np.zeros(a.shape[:2], np.int32)
    for i, px in enumerate(map(tuple, n.reshape(-1, 4))):
        idx.flat[i] = cols.setdefault(px, len(cols))
    return hashlib.sha1(idx.tobytes() + str(a.shape[:2]).encode()).hexdigest()


def _cajas(ruta, arc):
    try:
        return C.qna_cajas(ruta, arc)
    except Exception:  # noqa: BLE001
        return {}


def indice():
    cache = C.HERE / '_celdas_ie1.pkl'
    if cache.exists():
        return pickle.loads(cache.read_bytes())
    jp, tr = C.jp(), C.ie1tr()
    exacto, forma = {}, {}
    for p in jp.rutas('inazuma1/'):
        if not p.endswith('.arc') or p not in tr:
            continue
        a, b = C.U.unwrap(jp.get(p)), C.U.unwrap(tr.get(p))
        ta, tb = C.texturas(a), C.texturas(b)
        if len(ta) != len(tb):
            continue
        q = _cajas(p, jp)
        for (n, _, _, x), (_, _, _, y) in zip(ta, tb):
            if x == y or len(x) != len(y) or n not in q:
                continue
            A, B = np.asarray(C.decodificar(x)), np.asarray(C.decodificar(y))
            for x0, y0, x1, y1 in q[n]:
                x0, x1 = sorted((max(x0, 0), min(x1, A.shape[1])))
                y0, y1 = sorted((max(y0, 0), min(y1, A.shape[0])))
                if x1 - x0 < 4 or y1 - y0 < 4:
                    continue
                ca, cb = A[y0:y1, x0:x1], B[y0:y1, x0:x1]
                if np.array_equal(_norm(ca), _norm(cb)) or not (ca[..., 3] > 0).any():
                    continue
                exacto.setdefault(_h(ca), (ca.copy(), cb.copy(), f'{p}:{n}'))
                forma.setdefault(_forma(ca), (ca.copy(), cb.copy(), f'{p}:{n}'))
    res = (exacto, forma)
    cache.write_bytes(pickle.dumps(res))
    return res


def aplicar(ediciones):
    exacto, forma = indice()
    jp = C.jp()
    n_tex = 0
    for ruta in sorted(jp.rutas('inazuma2/')):
        if not ruta.endswith('.arc'):
            continue
        q = _cajas(ruta, jp)
        if not q:
            continue
        raw = C.U.unwrap(jp.get(ruta))
        for nombre, off, ln, blob in C.texturas(raw):
            if nombre not in q or C.T.metadata(blob)[3] not in C.EDITABLES:
                continue
            previa = ediciones.get((ruta, nombre))
            if previa and not previa['pendientes']:
                continue
            base = np.asarray(previa['imagen']) if previa else np.asarray(C.decodificar(blob))
            out = base.copy()
            hechas = 0
            for x0, y0, x1, y1 in sorted(set(q[nombre])):
                x0, x1 = sorted((max(x0, 0), min(x1, out.shape[1])))
                y0, y1 = sorted((max(y0, 0), min(y1, out.shape[0])))
                if x1 - x0 < 4 or y1 - y0 < 4:
                    continue
                c = base[y0:y1, x0:x1]
                k = _h(c)
                if k in exacto:
                    out[y0:y1, x0:x1] = exacto[k][1]
                    hechas += 1
                    continue
                f = forma.get(_forma(c))
                if f is not None:
                    r = recolorear_zona(f[0], f[1], c)
                    if r is not None:
                        out[y0:y1, x0:x1] = r
                        hechas += 1
            if not hechas:
                continue
            from PIL import Image
            pend = previa['pendientes'] if previa else []
            ediciones[(ruta, nombre)] = dict(imagen=Image.fromarray(out, 'RGBA'), modo='ie1_celdas',
                                             pendientes=pend, celdas=hechas)
            n_tex += 1
    return n_tex
