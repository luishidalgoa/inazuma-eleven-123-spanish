"""IE2 v07 · media: rótulos del dibujo japoneses sustituidos por los del vídeo NDS español (issue #74).

Mismo método que el logotipo de op00: el fotograma NDS (YCgCo, 320x240) se registra en tiempo (fotograma NDS más
parecido cerca de t*20/24 + desfase) y en espacio (ECC afín), se ajusta de color (recta por canal) y se compone
sobre el 3DS solo donde difiere. Tres modos:
- plancha: plano fijo (marcador): planchas JP y ES medianas; se pinta la ES donde difiere de la JP y el tablero se
  ve (|3DS - plancha JP| pequeño), así los personajes que pasan por delante quedan intactos.
- movil: plano con movimiento (piezas del marcador volando): registro por fotograma y composición donde difiere.
- pizarra: el interior de la pizarra (verde pizarra en el 3DS) se sustituye entero, con color por fotograma
  (fundidos) y solo si el registro es fiable (ECC >= 0,85).
Entrada/salida: RGB de pantalla 320x240 (videos.yuv_a_rgb / videos.nds_a_rgb).
"""
from __future__ import annotations

import cv2
import numpy as np
from scipy.ndimage import binary_dilation, gaussian_filter

ECC_MIN = 0.85
CRIT = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 200, 1e-6)
def g(x): return cv2.cvtColor(np.ascontiguousarray(x).astype(np.uint8), cv2.COLOR_RGB2GRAY).astype(np.float32)
def ecc(ref, mov, modo=cv2.MOTION_AFFINE, masc=None, w=None):
    w = np.eye(2, 3, dtype=np.float32) if w is None else w.astype(np.float32)
    try:
        c, w = cv2.findTransformECC(ref, mov, w, modo, CRIT, masc, 5)
    except cv2.error:
        c = -1
    return c, w
def warp(img, w): return cv2.warpAffine(np.ascontiguousarray(img).astype(np.float32), w, (320, 240), flags=cv2.INTER_CUBIC | cv2.WARP_INVERSE_MAP, borderMode=cv2.BORDER_REPLICATE)
def ajuste_color(pares):
    a = np.concatenate([p[0].reshape(-1, 3) for p in pares]).astype(np.float64)
    b = np.concatenate([p[1].reshape(-1, 3) for p in pares]).astype(np.float64)
    return [np.polyfit(a[::13, c], b[::13, c], 1) for c in range(3)]
def color(x, G): return np.clip(np.stack([np.polyval(G[c], x[..., c]) for c in range(3)], -1), 0, 255).astype(np.float32)
NIT = np.array([[0, -.2, 0], [-.2, 1.8, -.2], [0, -.2, 0]], np.float32)
def caja(x0, y0, x1, y1):
    m = np.zeros((240, 320), bool); m[y0:y1, x0:x1] = True; return m
def mezcla(fondo, nuevo, dif, zona, dil=3, sig=1.2):
    m = binary_dilation(dif & zona, iterations=dil).astype(np.float32)
    m = (gaussian_filter(m, sig) * zona)[..., None]
    return np.clip(nuevo * m + fondo * (1 - m), 0, 255).round().astype(np.uint8), m
def dif_mapa(a, b, s=1.0):
    return np.abs(gaussian_filter(a, (s, s, 0)) - gaussian_filter(b, (s, s, 0))).max(-1)

def plancha(J, N, k0, k1, off, zona, umbral=30, vis=22):
    """Plano estático: plancha ES (mediana NDS registrada) donde difiere de la plancha JP y el tablero se ve."""
    zm = zona.astype(np.uint8)
    ks = list(range(k0, k1))
    ref = g(J[(k0 + k1) // 2])
    tj = {k: ecc(ref, g(J[k]), cv2.MOTION_TRANSLATION, zm)[1] for k in ks}
    PJ = np.median(np.stack([warp(J[k], tj[k]) for k in ks]), 0)
    ms = sorted({int(round(k * 20 / 24)) + off for k in ks})
    refn = g(N[ms[len(ms) // 2]])
    PN = np.median(np.stack([warp(N[m], ecc(refn, g(N[m]), cv2.MOTION_TRANSLATION, zm)[1]) for m in ms]), 0)
    c, A = ecc(g(PJ), g(PN), cv2.MOTION_AFFINE, zm)
    PN = warp(PN, A)
    G = ajuste_color([(PN[zona], PJ[zona])])
    PE = cv2.filter2D(color(PN, G), -1, NIT)
    dif = dif_mapa(PE, PJ) > umbral
    out, info = {}, dict(ecc_nds=round(float(c), 3), afin=A.round(4).tolist())
    for k in ks:
        Jk = J[k].astype(np.float32)
        # plancha JP/ES llevadas a la posición del fotograma k
        inv = cv2.invertAffineTransform(tj[k])
        PJk, PEk = warp(PJ, inv), warp(PE, inv)
        difk = warp(dif.astype(np.float32), inv) > .5
        vis_k = gaussian_filter(np.abs(Jk - PJk).max(-1), 1.5) < vis
        # la tinta JP también cuenta como visible si coincide con la plancha
        visible = binary_dilation(vis_k & zona, iterations=1) & vis_k | (vis_k & difk)
        o, _ = mezcla(Jk, PEk, difk & visible, zona, dil=2, sig=1.0)
        out[k] = o
    return out, dict(info, fotogramas=[k0, k1 - 1], nds=[ms[0], ms[-1]])

def zona_cartel(J, caja_):
    """Zona = cartel claro y poco saturado dentro de la caja (se mueve con la cámara)."""
    from scipy.ndimage import binary_closing, binary_fill_holes
    def f(k):
        hsv = cv2.cvtColor(np.ascontiguousarray(J[k]), cv2.COLOR_RGB2HSV)
        m = (hsv[..., 2] > 150) & (hsv[..., 1] < 60) & caja_
        m = binary_fill_holes(binary_closing(m, np.ones((5, 5), bool)))
        return binary_dilation(m, iterations=1) & caja_
    return f


def movil(J, N, k0, k1, off, zona_fn, rad=2, umbral=34, dil=4, caja_=None):
    if zona_fn == 'cartel':
        zona_fn = zona_cartel(J, caja(*caja_))
    """Plano con movimiento: mejor fotograma NDS cercano, registro afín por fotograma, composición donde difiere."""
    out, regs = {}, []
    G = None
    cand = {}
    for k in range(k0, k1):
        c0 = int(round(k * 20 / 24)) + off
        rj = g(J[k][:208]); best = None
        for m in range(max(0, c0 - rad), min(len(N), c0 + rad + 1)):
            c, w = ecc(np.pad(rj, ((0, 32), (0, 0))), g(N[m]), cv2.MOTION_AFFINE, caja(0, 0, 320, 205).astype(np.uint8))
            if best is None or c > best[0]:
                best = (c, m, w)
        cand[k] = best
    G = ajuste_color([(warp(N[cand[k][1]], cand[k][2])[8:200:2, 8:312:2], J[k][8:200:2, 8:312:2].astype(np.float32))
                      for k in range(k0, k1, 3) if cand[k][0] > .6])
    for k in range(k0, k1):
        c, m, w = cand[k]
        E = cv2.filter2D(color(warp(N[m], w), G), -1, NIT)
        Jk = J[k].astype(np.float32)
        zona = zona_fn(k)
        dif = dif_mapa(E, Jk, 1.2) > umbral
        out[k], _ = mezcla(Jk, E, dif, zona, dil=dil, sig=1.5)
        regs.append((k, m, round(float(c), 3)))
    return out, dict(fotogramas=[k0, k1 - 1], ecc_min=min(r[2] for r in regs),
                     ganancia=[[round(float(x), 4) for x in gg] for gg in G])

def pizarra(J, N, k0, k1, off, rad=3, hue=(80, 112), smin=50, vmax=150, cierre=15, eros=3):
    """Pizarra en movimiento: interior (color verde pizarra en el 3DS) sustituido entero por el NDS registrado,
    con ajuste de color por fotograma (fundidos)."""
    from scipy.ndimage import binary_closing, binary_fill_holes, binary_erosion, label
    out, regs, mascs = {}, [], {}
    for k in range(k0, k1):
        c0 = int(round(k * 20 / 24)) + off
        rj = np.pad(g(J[k][:208]), ((0, 32), (0, 0))); best = None
        for m in range(max(0, c0 - rad), min(len(N), c0 + rad + 1)):
            c, w = ecc(rj, g(N[m]), cv2.MOTION_AFFINE, caja(0, 0, 320, 205).astype(np.uint8))
            if best is None or c > best[0]:
                best = (c, m, w)
        c, m, w = best
        Jk = J[k].astype(np.float32)
        Wn = warp(N[m], w)
        G = ajuste_color([(Wn[8:200:2, 8:312:2], Jk[8:200:2, 8:312:2])])
        E = cv2.filter2D(color(Wn, G), -1, NIT)
        hsv = cv2.cvtColor(np.ascontiguousarray(J[k]), cv2.COLOR_RGB2HSV)
        # en los fundidos a negro, umbral de valor relativo
        base = (hsv[..., 0] >= hue[0]) & (hsv[..., 0] <= hue[1]) & (hsv[..., 1] >= smin) & (hsv[..., 2] <= vmax)
        base[208:] = False
        z = binary_closing(base, np.ones((cierre, cierre), bool))
        z = binary_fill_holes(z)
        lab, nl = label(z)
        if nl:
            tam = np.bincount(lab.ravel()); tam[0] = 0
            z = lab == tam.argmax()
            if tam.max() < 1500:
                z[:] = False
        z = binary_erosion(z, iterations=eros)
        if c < ECC_MIN:
            z[:] = False
        mm = gaussian_filter(z.astype(np.float32), 1.5)[..., None]
        out[k] = np.clip(E * mm + Jk * (1 - mm), 0, 255).round().astype(np.uint8)
        mascs[k] = int(z.sum()); regs.append((k, m, round(float(c), 3)))
    return out, dict(fotogramas=[k0, k1 - 1], ecc_min=min(r[2] for r in regs), px_min=min(mascs.values()),
                     nds=[regs[0][1], regs[-1][1]])


# nombre -> tramos (fotogramas 3DS [k0, k1), desfase NDS). Fotogramas NDS ~ k*20/24 + desfase.
TRAMOS = {
    'a2m06': [
        ('plancha', dict(k0=572, k1=659, off=0, zona=caja(95, 12, 272, 158))),      # marcador fijo
        ('movil', dict(k0=659, k1=676, off=3, zona_fn=lambda k: caja(0, 0, 320, 160), rad=4, umbral=24)),  # piezas
        ('pizarra', dict(k0=959, k1=1018, off=6)),                                   # pizarra final
    ],
    'a2m20b': [
        # cartel pequeño al fondo del paneo (帝国学園 -> Royal Academy)
        ('movil', dict(k0=30, k1=84, off=0, zona_fn='cartel', caja_=(160, 150, 235, 205), umbral=12, dil=2)),
        # primer plano del cartel
        ('movil', dict(k0=84, k1=132, off=0, zona_fn=lambda k: caja(0, 0, 320, 205), umbral=30)),
    ],
}


def componer(n, J, N):
    """Devuelve (J con los tramos compuestos, informe)."""
    out = np.array(J, copy=True)
    info = []
    for modo, kw in TRAMOS[n]:
        fr, i = globals()[modo](J, N, **kw)
        for k, f in fr.items():
            out[k] = f
        info.append(dict(modo=modo, **i))
    return out, info
