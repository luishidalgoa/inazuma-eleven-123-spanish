"""Texturas pintadas (sin pieza IE1 ni NDS) — issue #73.

Reglas (obligatorias, del usuario):
  * el texto se pinta en una capa transparente y se compone sobre los píxeles originales; nunca una caja
    de fondo. Solo se borra el trazo japonés (y en rótulos de solo-texto, la textura entera es el rótulo).
  * nítido a tamaño nativo: fuente del juego (FONT12.NFTR) en negrita de 1 px para los rótulos pequeños,
    Bahnschrift Bold SemiCondensed renderizada a 1 bit para los grandes (imita la 3DS europea de IE1).
    Sin supermuestreo ni reescalado.
  * cada textura pintada deja un zoom ×4 original|nuevo en previews/x4_<grupo>_NN.png.
Textos: nombres oficiales de la NDS española (nombres.py).
"""
import re

import numpy as np
from PIL import Image

import comun as C
import fuente as F
import nombres as N

BAHN = 'C:/Windows/Fonts/bahnschrift.ttf'
_F12 = None


def f12():
    global _F12
    if _F12 is None:
        _F12 = F.Fuente('FONT12')
    return _F12


def zoom(antes, despues, titulo):
    return C.par(antes, despues, s=4, titulo=titulo)


def componer(base, capas):
    """capas: [(máscara bool del tamaño de base, color RGBA)] en orden de pintado."""
    out = base.copy()
    for m, color in capas:
        out[m] = color
    return out


def colocar(m, shape, x, y):
    out = np.zeros(shape, bool)
    h, w = m.shape
    if x < 0 or y < 0 or x + w > shape[1] or y + h > shape[0]:
        raise ValueError(f'no cabe: {w}x{h} en ({x},{y}) de {shape[1]}x{shape[0]}')
    out[y:y + h, x:x + w] = m
    return out


def desplazar(m, dx, dy):
    out = np.zeros_like(m)
    h, w = m.shape
    out[max(dy, 0):h + min(dy, 0), max(dx, 0):w + min(dx, 0)] = m[max(-dy, 0):h - max(dy, 0), max(-dx, 0):w - max(dx, 0)]
    return out


def dil(m):
    return F.dilatar(m)[1:-1, 1:-1]


def vaciar(arr):
    """Deja la textura transparente conservando el valor RGB del transparente original."""
    trans = arr[arr[..., 3] == 0]
    color = trans[0] if len(trans) else np.array([0, 0, 0, 0], np.uint8)
    out = arr.copy()
    out[:] = color
    return out


# ------------------------------------------------------------ técnicas pequeñas (bc/bg, 128x16)

def sufijo_nivel(arr):
    """Superíndice de nivel del japonés (B/L arriba a la derecha): (recorte RGBA, x0) o None.
    Columnas finales cuya tinta queda en las filas 0-8 y que tienen color distinto del contorno blanco/gris
    del rótulo (el superíndice tiene su propio color)."""
    a = arr[..., 3] > 0
    cols = np.where(a.any(0))[0]
    if not len(cols):
        return None
    x = cols[-1]
    while x >= 0 and a[:, x].any() and not a[9:, x].any():
        x -= 1
    ini = x + 1
    if cols[-1] - ini < 4:
        return None
    return arr[:9, ini:cols[-1] + 1].copy(), ini


def mascaras_pequenas(texto):
    f = f12()
    b = F.negrita(f.texto(texto, espacio=3, tracking=2))
    yield b[min(np.where(b.any(1))[0][0], 2):13]
    m = f.texto(texto, espacio=3, tracking=1)
    yield m[min(np.where(m.any(1))[0][0], 2):13]
    for var, tam in ((b'SemiBold', 12), (b'SemiBold SemiCondensed', 12), (b'SemiBold Condensed', 13), (b'SemiBold Condensed', 12)):
        yield F.recortar(F.ttf_linea(texto, BAHN, tam, var))


def tecnica_pequena(arr, texto):
    h, w = arr.shape[:2]
    op = arr[arr[..., 3] > 0]
    colores = {}
    for px in map(tuple, op):
        colores[px] = colores.get(px, 0) + 1
    blanco, gris = (255, 255, 255, 255), (164, 164, 164, 255)
    relleno = max((c for c in colores if c not in (blanco, gris)), key=colores.get)
    x0 = int(np.where(arr[..., 3].any(0))[0][0])
    suf = sufijo_nivel(arr)
    extra = suf[0].shape[1] + 1 if suf else 0
    for m in mascaras_pequenas(texto):
        ancho = m.shape[1] + 3 + extra
        if ancho <= w and m.shape[0] + 3 <= h:
            break
    else:
        raise ValueError(f'no cabe «{texto}» en {w} px')
    x = x0 if x0 + ancho <= w else w - ancho
    top = (h - m.shape[0] - 3) // 2 + 1
    mask = colocar(m, (h, w), x + 1, top)
    borde = dil(mask)
    sombra = desplazar(borde, 1, 1) & ~borde
    out = componer(vaciar(arr), [(sombra, gris), (borde, blanco), (mask, relleno)])
    if suf:
        rec, _ = suf
        sx = x + m.shape[1] + 2
        if sx + rec.shape[1] > w:
            raise ValueError('el superíndice no cabe')
        zona = out[:rec.shape[0], sx:sx + rec.shape[1]]
        opaco = rec[..., 3] > 0
        zona[opaco] = rec[opaco]
    return out


# ------------------------------------------------------------ técnicas grandes (3ddemo tc, 256x32)

def tecnica_grande(arr, texto):
    h, w = arr.shape[:2]
    for var, tam in ((b'Bold SemiCondensed', 24), (b'Bold Condensed', 24), (b'Bold Condensed', 22),
                     (b'Bold Condensed', 20)):
        m = F.ttf_linea(texto, BAHN, tam, var)
        if m.shape[1] + 6 <= min(w, 244):
            break
    else:
        raise ValueError(f'no cabe «{texto}»')
    dy = 3 if m.shape[0] + 3 <= h - 1 else max(0, h - 1 - m.shape[0])
    mask = colocar(m[:h - dy - 1], (h, w), 4, dy)
    borde = dil(mask)
    blanco, negro = (255, 255, 255, 255), (0, 0, 0, 255)
    return componer(vaciar(arr), [(borde, negro), (mask, blanco)])


PINTORES = [
    # (regex de ruta, regex de textura, grupo, función(arr, nombre)->arr)
    (r'/command_technique/', r'_tec_b[cg](\d{3})\.tga$', 'command_technique',
     lambda arr, n: tecnica_pequena(arr, N.tecnica(N.id_textura(n)))),
    (r'/3ddemo_technique/', r'_tec_tc(\d{3})\.tga$', '3ddemo_technique',
     lambda arr, n: tecnica_grande(arr, N.tecnica(N.id_textura(n)))),
]

import escuelas as _E  # noqa: E402
for _fam in _E.FAMILIAS:
    _pat, _fn = _E.pintor(_fam)
    PINTORES.append((rf'/{_fam}/', _pat, _fam, _fn))


def aplicar(ediciones, solo=None):
    import pintado_menus as PM
    jp = C.jp()
    pendientes = []
    for ruta in sorted(jp.rutas('inazuma2/')):
        if not ruta.endswith('.arc'):
            continue
        reglas = [p for p in PINTORES if re.search(p[0], ruta)]
        menus = PM.PLAN.get(ruta, {})
        if not reglas and not menus:
            continue
        raw = C.U.unwrap(jp.get(ruta))
        for nombre, off, ln, blob in C.texturas(raw):
            fn = grupo = None
            for _, rt, g, f in reglas:
                if re.search(rt, nombre):
                    fn, grupo = f, g
            if nombre in menus:
                fn, grupo = (lambda arr, n, ops=menus[nombre]: PM.pintar(arr, ops)), PM.grupo(ruta)
            if fn is None:
                continue
            previa = ediciones.get((ruta, nombre))
            if previa and not previa['pendientes'] and nombre not in menus:
                continue
            if C.T.metadata(blob)[3] not in C.EDITABLES:
                pendientes.append((ruta, nombre, 'formato no editable'))
                continue
            antes = C.decodificar(blob)
            try:
                arr = fn(np.array(antes), nombre)
            except (ValueError, KeyError) as e:
                pendientes.append((ruta, nombre, str(e)))
                continue
            if nombre in menus and all(o.get('tipo') in ('celda_ie1', 'nada') for o in menus[nombre]):
                import sugerir as SG
                faltan = SG.cobertura(ruta, nombre, np.array(antes), [tuple(o['caja']) for o in menus[nombre]])
                if faltan:
                    pendientes.append((ruta, nombre, f'solo celdas IE1; sin cubrir {faltan[:6]}'))
                    continue
            im = Image.fromarray(arr, 'RGBA')
            final = C.cuantizar(blob, im)
            ediciones[(ruta, nombre)] = dict(imagen=im, modo='pintada', pendientes=[], grupo=grupo,
                                             zoom=[zoom(antes, final, f'{ruta.split("/")[-1]} {nombre}')])
    return pendientes
