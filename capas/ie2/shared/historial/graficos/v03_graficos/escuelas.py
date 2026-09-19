"""Nombres de escuela en a_data_replace (issue #73). Nombre oficial: team.pkb de la NDS española por el
identificador de textura (u16 en +32 del registro; ver nombres.equipos).

Estilo de cada familia imitando la 3DS europea de IE1 (misma metadata que la japonesa):
  vs_school_name 128x32  relleno 246, contorno 1 px (color japonés), Bahnschrift Bold a 1 bit
  game_school    128x32  relleno 222, contorno 0
  pk_school_name 64x16   relleno 255, contorno 57 (FONT12 negrita o Bahnschrift 12)
  score_school   128x16  relleno 246, contorno 32, centrado
  formation_school 256x32 «<nombre> - Formación», relleno 255, contorno 2 px 57 + sombra 16
  3ddemo_school  128x64  cabecera «Valor total» copiada de la europea; nombre rosa sobre la barra
Si el nombre no cabe con la fuente más estrecha se abrevia (como la europea: «Royal A.»).
"""
import re

import numpy as np

import comun as C
import fuente as F
import nombres as N
import pintado as P

BAHN = P.BAHN
EXTRA_ES = {525: 'Génesis B', 15: 'Naniwa', 20: 'Raimon'}


def nombre_equipo(tid):
    if tid in EXTRA_ES:
        return EXTRA_ES[tid]
    return N.equipo(tid)


def abreviaturas(texto):
    """Variantes cada vez más cortas del nombre (sin tocar números ni letras sueltas)."""
    vistos = set()

    def emitir(pal):
        t = ' '.join(pal)
        if t not in vistos:
            vistos.add(t)
            return t
        return None

    pal = texto.split()
    t = emitir(pal)
    if t:
        yield t
    cortas = [p for p in pal if p.lower() not in ('de', 'del', 'la', 'las', 'los', 'el', 'y')]
    if cortas and cortas != pal:
        pal = cortas
        t = emitir(pal)
        if t:
            yield t
    # recortar las palabras largas a 6, 5 y 4 letras + '.' (de la más larga a la más corta)
    for n in (6, 5, 4):
        while True:
            cand = [i for i, p in enumerate(pal) if len(p.rstrip('.')) > n + 1 and not p[0].isdigit()]
            if not cand:
                break
            i = max(cand, key=lambda k: len(pal[k].rstrip('.')))
            pal = pal[:i] + [pal[i].rstrip('.')[:n] + '.'] + pal[i + 1:]
            t = emitir(pal)
            if t:
                yield t
    # iniciales de las primeras palabras
    for i in range(len(pal) - 1):
        if len(pal[i]) > 2:
            pal = pal[:i] + [pal[i][0] + '.'] + pal[i + 1:]
            t = emitir(pal)
            if t:
                yield t


def ttf(texto, var, tam):
    return F.ttf_linea(texto, BAHN, tam, var)


def recorte_v(m, ref):
    """Recorta filas con la caja de la cadena de referencia (misma línea base para todos)."""
    r = np.where(ref.any(1))[0]
    return m[r[0]:r[-1] + 1]


def encajar(texto, fuentes, ancho, alto, legibles=None):
    """Primera combinación que cabe. Con `legibles`, se prueban todas las abreviaturas con esas fuentes
    antes de recurrir a las más estrechas."""
    grupos = [fuentes[:legibles], fuentes[legibles:]] if legibles else [fuentes]
    for grupo in grupos:
        for t in abreviaturas(texto):
            for f in grupo:
                m = f(t)
                if m.shape[1] <= ancho and m.shape[0] <= alto:
                    return m, t
    raise ValueError(f'«{texto}» no cabe en {ancho}x{alto}')


def f_ttf(var, tam, ref='ÁÉgjpqy'):
    def g(t):
        return recorte_v(ttf(t, var, tam), ttf(ref + t, var, tam))
    return g


def f_f12b(t):
    m = F.negrita(P.f12().texto(t, espacio=3, tracking=2))
    return m[1:13]


def f_f8b(t):
    import pintado_menus as PM
    return F.negrita(PM.f8().texto(t, espacio=3, tracking=2))[:10]


def f_f8(t):
    import pintado_menus as PM
    return PM.f8().texto(t, espacio=3, tracking=1)[:10]


def contorno(m, n=1):
    for _ in range(n):
        m = P.dil(m)
    return m


def colocar(shape, m, x, y):
    return P.colocar(m, shape, x, y)


def color_mas(arr, excluir=()):
    from collections import Counter
    op = arr[arr[..., 3] > 0]
    c = Counter(map(tuple, op))
    return [k for k, _ in c.most_common() if k not in excluir]


# ------------------------------------------------------------------ familias

def dos_colores(arr, texto, fuentes, caja, relleno, borde, alinear='l', legibles=None):
    h, w = arr.shape[:2]
    x0, y0, x1, y1 = caja
    m, usado = encajar(texto, fuentes, x1 - x0 - 2, y1 - y0 - 2, legibles)
    if alinear == 'c':
        x = x0 + (x1 - x0 - m.shape[1]) // 2
    else:
        x = x0 + 1
    y = y0 + (y1 - y0 - m.shape[0]) // 2
    mask = colocar((h, w), m, x, y)
    out = P.vaciar(arr)
    return P.componer(out, [(contorno(mask), borde), (mask, relleno)]), usado


GRANDE = [f_ttf(b'Bold SemiCondensed', 19), f_ttf(b'Bold Condensed', 19), f_ttf(b'Bold Condensed', 17),
          f_ttf(b'Bold Condensed', 15), f_ttf(b'Bold Condensed', 14)]
def f_f12(t):
    return P.f12().texto(t, espacio=3, tracking=1)[1:13]


PEQUE = [f_f12b, f_f12, f_ttf(b'Bold SemiCondensed', 12), f_ttf(b'Bold Condensed', 12)]


def vs_school(arr, tid):
    borde = color_mas(arr)[0]
    return dos_colores(arr, nombre_equipo(tid), GRANDE, (0, 3, 128, 29), (246, 246, 246, 255), borde)


def game_school(arr, tid):
    return dos_colores(arr, nombre_equipo(tid), GRANDE, (6, 0, 128, 24), (222, 222, 222, 255), (0, 0, 0, 255))


CORTOS_PK = {2: 'Royal A.', 14: 'Vet. Inaz.', 31: 'Géminis', 34: 'Épsilon P.', 35: 'S. Secreto', 37: 'Claustro',
             38: 'R.A. Rdx.', 41: 'Emp. Osc.', 43: 'Robots G.', 44: 'Árboles', 45: 'Jóv. Inaz.', 47: 'Prominen.',
             48: 'Diamantes', 505: 'Ases I. 1', 518: 'Ases I. 2', 504: 'Sel. nac. A', 517: 'Sel. nac. B',
             510: 'F. prev. A', 523: 'F. prev. B', 511: 'F. nac. A', 524: 'F. nac. B', 522: 'Intercam.',
             526: 'Inazuma A', 527: 'Ultra Raim.', 543: 'U. Raim. B', 528: 'Tarjeteros', 530: 'Occult P.',
             531: 'Súper 3C', 532: 'IKFC Plus', 500: 'Neo Royal', 513: 'R. Dark AS', 539: 'Enmasc. A',
             540: 'Enmasc. B', 541: 'Sospech. A', 542: 'Sospech. B', 516: 'Chaval. A', 546: 'Chaval. B',
             550: 'N. Alpino', 551: 'N. Claustro', 552: 'N. Fauxsh.', 555: 'N. Géminis', 556: 'N. Épsilon',
             557: 'N. Génesis', 562: 'N. Shuriken', 564: 'N. Kirkw.', 509: 'A. Kirkw.', 9: 'Kirkwood',
             503: 'Adultos', 512: 'Dioses y al.', 520: 'R. Claus. B', 507: 'R. Claus. A', 536: 'Chupab. 4',
             533: 'Chupab. 1', 534: 'Chupab. 2', 535: 'Chupab. 3', 537: 'Chupab. 5', 538: 'Chupab. 6',
             544: 'S. juv. B', 519: 'S. juv. A', 553: 'N. Mary T.', 561: 'N. Royal A.', 554: 'N. R.A. Rdx.'}


def pk_school(arr, tid):
    return dos_colores(arr, CORTOS_PK.get(tid) or nombre_equipo(tid), PEQUE, (0, 0, 64, 15), (255, 255, 255, 255), (57, 57, 57, 255), legibles=2)


def score_school(arr, tid):
    return dos_colores(arr, nombre_equipo(tid), PEQUE, (0, 0, arr.shape[1], 16), (246, 246, 246, 255),
                       (32, 32, 32, 255), alinear='c', legibles=2)


FORMACION = [f_ttf(b'Bold SemiCondensed', 24), f_ttf(b'Bold Condensed', 24), f_ttf(b'Bold Condensed', 22),
             f_ttf(b'Bold Condensed', 20)]


def formation_school(arr, tid):
    h, w = arr.shape[:2]
    base = nombre_equipo(tid)
    for t in abreviaturas(base):
        texto = f'{t} - Formación'
        for f in FORMACION:
            m = f(texto)
            if m.shape[1] + 6 <= w - 4 and m.shape[0] + 3 <= h:
                break
        else:
            continue
        break
    else:
        raise ValueError(f'formación «{base}» no cabe')
    y = max(2, (h - m.shape[0] - 3) // 2 + 1)
    mask = colocar((h, w), m, 6, min(y, h - m.shape[0] - 2))
    o2 = contorno(mask, 2)
    sombra = P.desplazar(o2, 1, 1) & ~o2
    return P.componer(P.vaciar(arr), [(sombra, (16, 16, 16, 255)), (o2, (57, 57, 57, 255)),
                                     (mask, (255, 255, 255, 255))]), texto


def _cabecera_eu():
    ruta = 'inazuma1/data_iz/a_data_replace/3ddemo_school/data/ie01_3ddemo_school_ts002r.arc'
    jp = np.array(C.decodificar(C.texturas(C.U.unwrap(C.jp().get(ruta)))[0][3]))
    eu = np.array(C.decodificar(C.texturas(C.U.unwrap(C.ie1tr().get(ruta)))[0][3]))
    return jp[:10], eu[:10]


def demo_school(arr, tid):
    """ts###r: cabecera europea + nombre rosa (FONT8 negrita) sobre la barra (filas 54-61, x 2..97)."""
    out = arr.copy()
    jpc, euc = _cabecera_eu()
    if not np.array_equal(P_norm(out[:10]), P_norm(jpc)):
        raise ValueError('cabecera distinta de la japonesa de IE1')
    out[:10] = euc
    # barra: columna de muestra x=3 (sin texto) para filas 54..61; encima de la barra, transparente
    trans = out[out[..., 3] == 0][0]
    zona_y0, bar0, bar1 = 44, 54, 62
    cols = np.where((arr[bar0 + 2, :, 3] > 0))[0]
    bx0, bx1 = cols[0] + 1, cols[-1] + 1
    for y in range(zona_y0, bar0):
        fila = out[y, bx0:bx1]
        fila[:] = trans
    for y in range(bar0, bar1):
        out[y, bx0:bx1] = arr[y, bx1 - 2]
    rosa, oscuro = (246, 156, 156, 255), (32, 49, 65, 255)
    if tid not in EXTRA_ES and tid not in N.equipos():
        return out, ''
    m, usado = encajar(nombre_equipo(tid), [f_f8b, f_f8], bx1 - 16 - 2, 12, legibles=2)
    y = 49
    mask = colocar(out.shape[:2], m, 16, y)
    return P.componer(out, [(contorno(mask), oscuro), (mask, rosa)]), usado


def P_norm(a):
    b = a.copy()
    b[b[..., 3] == 0] = 0
    return b


FAMILIAS = {
    'vs_school_name': (r'_vs_school_name_(\d{3})\.tga$', vs_school),
    'game_school': (r'_game_school_s(\d{3})\.tga$', game_school),
    'pk_school_name': (r'_pk_school_name_t(\d{3})\.tga$', pk_school),
    'score_school': (r'_score_school_td(\d{3})\.tga$', score_school),
    'formation_school': (r'_formation_school_(\d{3})\.tga$', formation_school),
    '3ddemo_school': (r'_3ddemo_school_ts(\d{3})r\.tga$', demo_school),
}


def pintor(familia):
    patron, fn = FAMILIAS[familia]

    def f(arr, nombre):
        m = re.search(patron, nombre)
        if not m:
            raise ValueError(f'textura no reconocida {nombre}')
        return fn(arr, int(m.group(1)))[0]
    return patron, f
