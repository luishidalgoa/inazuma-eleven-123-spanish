"""Rótulos de menús, botones y partido pintados sobre la textura japonesa (issue #73).

PLAN = {ruta_arc: {textura: [op, ...]}}; las ops están en planes_menus.py.

Una op es un dict:
  caja      (x0, y0, x1, y1)  rectángulo del rótulo japonés (exclusivo). Nada fuera cambia.
  texto     texto español ('' = solo borrar). '\\n' separa líneas.
  fuente    'f12' | 'f12b' (negrita 1 px) | 'f8' | 'f8b' | ('bahn', variación, tamaño)
  color     RGBA del relleno o 'auto' (color dominante del trazo japonés)
  borde     RGBA | 'auto' | None     contorno de 1 px (8 vecinos)
  sombra    (dx, dy, RGBA) | None
  alinear   'c' | 'l' | 'r'          (en 'l' el texto empieza en el primer píxel del japonés)
  borrar    'fila' (cada fila toma su color de fondo) | 'columna' | 'transparente' | 'nada'
  fondo_x   columna de muestra para 'fila' (por defecto la moda de la fila dentro de la caja)
  dy        desplazamiento vertical extra
  tracking  espaciado entre letras (por defecto 1; 2 con f12b)
Borrado: solo se tocan los píxeles del trazo japonés (los que difieren del fondo de su fila/columna),
nunca se pinta una caja. El texto se compone encima con alfa de 1 bit.
"""
from collections import Counter

import numpy as np


def norm(a):
    """Copia para comparar: todo píxel con alfa 0 pasa a (0,0,0,0)."""
    b = a.copy()
    b[b[..., 3] == 0] = 0
    return b

import fuente as F
import pintado as P

_F8 = None


def f8():
    global _F8
    if _F8 is None:
        _F8 = F.Fuente('FONT8')
    return _F8


def grupo(ruta):
    return ruta.split('/')[2]


def _moda(px):
    c = Counter(map(tuple, px))
    return np.array(c.most_common(1)[0][0], np.uint8)


def _real(fila, nfila, k):
    """Valor real (con su RGB de transparente) de un píxel de la fila igual a la clave k."""
    iguales = np.all(nfila == k, -1)
    return fila[iguales][0] if iguales.any() else k


def borrar(arr, caja, modo, fondo_x=None, colores_borrar=(), fondo_color=None):
    x0, y0, x1, y1 = caja
    zona = arr[y0:y1, x0:x1]
    trazo = np.zeros(zona.shape[:2], bool)
    if modo == 'transparente':
        trans = arr[arr[..., 3] == 0]
        color = trans[0] if len(trans) else np.zeros(4, np.uint8)
        trazo[:] = zona[..., 3] > 0
        zona[trazo] = color
    elif modo == 'fila':
        n = norm(zona)
        for i in range(zona.shape[0]):
            k = norm(arr[y0 + i:y0 + i + 1, fondo_x])[0] if fondo_x is not None else _moda(n[i])
            t = np.any(n[i] != k, -1)
            trazo[i] = t
            zona[i][t] = _real(zona[i], n[i], k)
    elif modo == 'colores':
        n = norm(zona)
        if isinstance(fondo_color, str):
            fondo_color = tuple(int(v) for v in _moda(zona[~np.any([np.all(n == np.array(c, np.uint8), -1)
                                                                        for c in colores_borrar], 0)]))
        for c in colores_borrar:
            t = np.all(n == np.array(c, np.uint8), -1)
            trazo |= t
            zona[t] = np.array(fondo_color, np.uint8)
    elif modo == 'columna':
        n = norm(zona)
        for j in range(zona.shape[1]):
            k = _moda(n[:, j])
            t = np.any(n[:, j] != k, -1)
            trazo[:, j] = t
            zona[:, j][t] = _real(zona[:, j], n[:, j], k)
    return trazo


def mascara(texto, fuente, tracking):
    lineas = texto.split('\n')
    ms = []
    for ln in lineas:
        if isinstance(fuente, tuple):
            m = F.ttf_linea(ln, P.BAHN, fuente[2], fuente[1])
        else:
            f = P.f12() if fuente.startswith('f12') else f8()
            m = f.texto(ln, espacio=3 if fuente.startswith('f12') else 2,
                        tracking=tracking if tracking is not None else (2 if fuente.endswith('b') else 1))
            if fuente.endswith('b'):
                m = F.negrita(m)
            # celda: filas 0-1 tildes, 2..2+alto glifo
            alto = f.ch + 2
            m = m[:alto]
        ms.append(m)
    ancho = max(m.shape[1] for m in ms)
    filas = [np.pad(m, ((0, 0), (0, ancho - m.shape[1]))) for m in ms]
    return filas


CADENAS = {
    'auto12': [('f12', 1), ('f12', 0), (('bahn', b'SemiBold', 12), None), (('bahn', b'SemiBold SemiCondensed', 12), None),
               (('bahn', b'SemiBold Condensed', 12), None), (('bahn', b'SemiBold Condensed', 11), None)],
    'auto12b': [('f12b', 2), ('f12b', 1), (('bahn', b'Bold', 12), None), (('bahn', b'Bold SemiCondensed', 12), None),
                (('bahn', b'Bold Condensed', 12), None), (('bahn', b'Bold Condensed', 11), None)],
    'fina16': [(('bahn', b'Light', 16), None), (('bahn', b'Light SemiCondensed', 16), None),
               (('bahn', b'Light Condensed', 16), None), (('bahn', b'Light Condensed', 15), None)],
    'semifina16': [(('bahn', b'SemiLight', 16), None), (('bahn', b'SemiLight SemiCondensed', 16), None),
                   (('bahn', b'SemiLight Condensed', 16), None)],
    'nombre': [(('bahn', b'Light', 16), None), (('bahn', b'Light SemiCondensed', 16), None),
               (('bahn', b'Light Condensed', 16), None), ('f12', 1), ('f12', 0),
               (('bahn', b'SemiBold Condensed', 12), None), (('bahn', b'SemiBold Condensed', 11), None)],
    'titulo': [(('bahn', b'Bold', 24), None), (('bahn', b'Bold SemiCondensed', 24), None),
               (('bahn', b'Bold', 22), None), (('bahn', b'Bold Condensed', 22), None)],
    'auto8': [('f8', 1), ('f8', 0)],
    'msg': [(('bahn', b'SemiBold Condensed', 13), None), (('bahn', b'SemiBold Condensed', 12), None)],
    'auto8b': [('f8b', 1), ('f8', 1), ('f8', 0)],
    'grande': [(('bahn', b'Bold', 15), None), (('bahn', b'Bold SemiCondensed', 15), None),
               (('bahn', b'Bold Condensed', 15), None), (('bahn', b'Bold Condensed', 14), None),
               (('bahn', b'Bold Condensed', 13), None)],
}


def candidatos(op):
    f = op.get('fuente', 'auto12')
    if isinstance(f, str) and f in CADENAS:
        return CADENAS[f]
    return [(f, op.get('tracking'))]


def boton_a_fila(arr, op):
    """Botón con icono (naranja) a la izquierda y texto claro con sombra 1 px arriba-izquierda.
    Devuelve una op 'fila' con la caja de texto, el color de muestra y la sombra detectados."""
    x0, y0, x1, y1 = op['caja']
    z = arr[y0:y1, x0:x1].astype(int)
    if op.get('relleno'):
        if op['relleno'] == 'auto':
            opacos = z[z[..., 3] > 0]
            rel = np.array(Counter(map(tuple, opacos)).most_common(1)[0][0])
        else:
            rel = np.array(op['relleno'])
        m = np.all(z == rel, -1)
        rr, cc = np.where(m.any(1))[0], np.where(m.any(0))[0]
        a0, a1, b0, b1 = rr[0], rr[-1] + 1, cc[0], cc[-1] + 1
        zona = z[a0:a1, b0:b1]
        cuenta = Counter(map(tuple, zona[~np.all(zona == rel, -1)])).most_common()
        otros = [c for c, _ in cuenta]
        d = {k: v for k, v in op.items() if k not in ('tipo', 'relleno')}
        if 'color' not in d and cuenta:
            dos = [c for c, _ in cuenta[:2]]
            dos.sort(key=lambda c: -sum(c[:3]))
            d['color'] = tuple(int(v) for v in dos[0])
            if len(dos) > 1 and 'borde' not in d and op.get('contorno', True):
                d['borde'] = tuple(int(v) for v in dos[1])
        if d.get('borde') is None:
            d.pop('borde', None)
        d.update(caja=(x0 + b0, y0 + a0, x0 + b1, y0 + a1), borrar='colores', colores_borrar=otros,
                 fondo_color=tuple(int(v) for v in rel))
        d.setdefault('fuente', 'grande')
        return d
    fondo = np.array(Counter(map(tuple, z.reshape(-1, 4))).most_common(1)[0][0])
    cuenta = np.all(z == fondo, -1).sum(0)
    fx = int(np.where(cuenta > 0)[0][-1])
    if op.get('icono', True):
        naranja = (z[..., 0] > 150) & (z[..., 2] < 90) & (z[..., 0] - z[..., 1] > 50) & (z[..., 3] > 0)
        naranja &= ~np.all(z == fondo, -1)
        cols = np.where(naranja[:, :(x1 - x0) // 2].any(0))[0]
        ix = (cols[-1] + 2) if len(cols) else 2
    else:
        ix = int(np.where(np.all(z == fondo, -1).any(0))[0][0])
    filas = np.where(np.all(z[:, ix:fx + 1] == fondo, -1).any(1))[0]
    ty0, ty1 = filas[0], filas[-1] + 1
    zona = z[ty0:ty1, ix:fx + 1]
    dif = np.any(zona != fondo, -1)
    cs = Counter(map(tuple, zona[dif])).most_common(2)
    if len(cs) < 2:
        raise ValueError(f'botón sin texto en {op["caja"]}')
    # el texto es el más claro de los dos colores; la sombra, el otro
    (c1, _), (c2, _) = cs
    claro, sombra = (c1, c2) if sum(c1[:3]) >= sum(c2[:3]) else (c2, c1)
    d = dict(op)
    d.pop('tipo')
    extra = [c for c, _ in Counter(map(tuple, zona[dif])).most_common(4)[2:]] if op.get('todos') else []
    d.update(caja=(x0 + ix, y0 + ty0, x0 + fx + 1, y0 + ty1), borrar='colores',
             colores_borrar=[claro, sombra] + extra, fondo_color=tuple(int(v) for v in fondo))
    d.setdefault('color', tuple(int(v) for v in claro))
    if op.get('contorno'):
        d.setdefault('borde', tuple(int(v) for v in sombra))
    else:
        d.setdefault('sombra', (-1, -1, tuple(int(v) for v in sombra)))
    d.setdefault('fuente', 'auto12')
    return d


def texto_aa(arr, op):
    """Rótulo suavizado para texturas cuyo original está suavizado (RGBA8/4444 con antialias).

    op: caja, texto, fuente=('bahn', var, tam) o lista de ellas, degradado=[(y_rel, RGBA), ...] o color,
    capas=[(ancho_trazo, RGBA), ...] (de fuera a dentro), borrar, alinear, dy.
    """
    from PIL import Image, ImageDraw, ImageFont
    arr = arr.copy()
    x0, y0, x1, y1 = op['caja']
    W, H = x1 - x0, y1 - y0
    modo = op.get('borrar', 'transparente')
    borrar(arr, op['caja'], modo, op.get('fondo_x'))
    capas = op.get('capas', [])
    margen = max([w for w, _ in capas] + [0])
    fuentes = op['fuente'] if isinstance(op['fuente'], list) else [op['fuente']]
    if not op['texto']:
        return arr
    for fu in fuentes:
        f = ImageFont.truetype(P.BAHN, fu[2])
        f.set_variation_by_name(fu[1])
        l, t, r, b = f.getbbox(op['texto'], stroke_width=margen)
        if r - l <= W and b - t <= H:
            break
    else:
        raise ValueError(f'«{op["texto"]}» no cabe (aa) en {op["caja"]}')
    tw, th = r - l, b - t
    al = op.get('alinear', 'c')
    ox = (W - tw) // 2 if al == 'c' else (0 if al == 'l' else W - tw)
    oy = (H - th) // 2 + op.get('dy', 0)
    base = Image.fromarray(arr[y0:y1, x0:x1].copy(), 'RGBA')
    for ancho, color in capas:
        m = Image.new('L', (W, H), 0)
        ImageDraw.Draw(m).text((ox - l, oy - t), op['texto'], font=f, fill=255, stroke_width=ancho, stroke_fill=255)
        capa = Image.new('RGBA', (W, H), tuple(color[:3]) + (0,))
        a = (np.array(m).astype(float) * color[3] / 255).astype(np.uint8)
        capa.putalpha(Image.fromarray(a))
        base.alpha_composite(capa)
    m = Image.new('L', (W, H), 0)
    ImageDraw.Draw(m).text((ox - l, oy - t), op['texto'], font=f, fill=255)
    grad = op.get('degradado', [(0.0, (255, 255, 255, 255))])
    if not isinstance(grad, list):
        grad = [(0.0, grad)]
    relleno = np.zeros((H, W, 4), np.uint8)
    for yy in range(H):
        rel = (yy - oy) / max(th - 1, 1)
        c = grad[0][1]
        for (p0, c0), (p1, c1) in zip(grad, grad[1:]):
            if p0 <= rel <= p1:
                k = (rel - p0) / max(p1 - p0, 1e-6)
                c = tuple(int(round(c0[i] + (c1[i] - c0[i]) * k)) for i in range(4))
                break
            if rel > p1:
                c = c1
        relleno[yy] = c
    rimg = Image.fromarray(relleno, 'RGBA')
    ra = (np.array(m).astype(float) * relleno[..., 3] / 255).astype(np.uint8)
    rimg.putalpha(Image.fromarray(ra))
    base.alpha_composite(rimg)
    arr[y0:y1, x0:x1] = np.array(base)
    return arr


def insignia(arr, op):
    """Letras de pixel art dentro de una insignia: borra todo lo que no sea el fondo de la caja."""
    import insignias as I
    arr = arr.copy()
    x0, y0, x1, y1 = op['caja']
    zona = arr[y0:y1, x0:x1]
    n = norm(zona)
    fondo = zona[0, 0].copy()
    trazo = np.any(n != norm(zona[:1, :1])[0, 0], -1)
    c = Counter(map(tuple, n[trazo])).most_common(2)
    if not c:
        raise ValueError(f'insignia vacía {op["caja"]}')
    lleno = np.array(op.get('color', c[0][0]), np.uint8)
    suave = np.array(op.get('suave', c[1][0] if len(c) > 1 else c[0][0]), np.uint8)
    zona[trazo] = fondo
    for hueco in (None, 1, 0):
        g = I.palabra(op['texto'], op.get('juego', 'grande11'), hueco)
        extra = 1 if op.get('sombra') else 0
        if g.shape[1] + extra <= x1 - x0 and g.shape[0] + extra <= y1 - y0:
            break
    else:
        raise ValueError(f'insignia «{op["texto"]}» no cabe en {op["caja"]}')
    ox = (x1 - x0 - g.shape[1] + 1) // 2 + op.get('dx', 0)
    oy = (y1 - y0 - g.shape[0]) // 2 + op.get('dy', 0)
    if op.get('sombra'):
        dx, dy, cs = op['sombra']
        sh = zona[oy + dy:oy + dy + g.shape[0], ox + dx:ox + dx + g.shape[1]]
        sh[g[:sh.shape[0], :sh.shape[1]] == '#'] = np.array(cs, np.uint8)
    sub = zona[oy:oy + g.shape[0], ox:ox + g.shape[1]]
    sub[g == '#'] = lleno
    sub[g == '+'] = suave
    return arr


def pintar(arr, ops):
    arr = arr.copy()
    for op in ops:
        if op.get('tipo') == 'boton':
            op = boton_a_fila(arr, op)
        if op.get('aa'):
            arr = texto_aa(arr, op)
            continue
        if op.get('tipo') == 'nada':
            continue
        if op.get('tipo') == 'celda_ie1':
            import piezas_ie1 as PI
            a, b = PI.texturas(op['ie1'])
            x0, y0, x1, y1 = op['caja1']
            celda = b[op['tex1']][y0:y1, x0:x1]
            X0, Y0, X1, Y1 = op['caja']
            if celda.shape[:2] != (Y1 - Y0, X1 - X0):
                raise ValueError('celda IE1 de otro tamaño')
            arr = arr.copy()
            arr[Y0:Y1, X0:X1] = celda
            continue
        if op.get('tipo') == 'pieza':
            import piezas_ie1 as PI
            if op.get('limpiar'):
                arr = PI.borrar_kanji_boton(arr.copy(), op['caja'], op.get('margen', 7))
            elif op.get('vaciar', True):
                x0, y0, x1, y1 = op['caja']
                arr = arr.copy()
                z = arr[y0:y1, x0:x1]
                trans = arr[arr[..., 3] == 0]
                z[:] = trans[0] if len(trans) else 0
            pz = op['pieza']()
            arr = PI.pegar(arr.copy(), pz[:op['caja'][3] - op['caja'][1], :op['caja'][2] - op['caja'][0]],
                           op['caja'], op.get('dx', 0), op.get('dy', 0))
            continue
        if op.get('tipo') == 'funcion':
            arr = op['f'](arr.copy())
            continue
        if op.get('tipo') == 'insignia':
            arr = insignia(arr, op)
            continue
        ultimo = None
        for fuente, trk in candidatos(op):
            o = dict(op, fuente=fuente, tracking=trk)
            try:
                arr = _pintar_una(arr, o)
                break
            except NoCabe as e:
                ultimo = e
        else:
            raise ValueError(str(ultimo))
    return arr


class NoCabe(ValueError):
    pass


def _pintar_una(arr, op):
    arr = arr.copy()
    for op in [op]:
        c = op['caja']
        caja = (max(c[0], 0), max(c[1], 0), min(c[2], arr.shape[1]), min(c[3], arr.shape[0]))
        x0, y0, x1, y1 = caja
        antes = arr[y0:y1, x0:x1].copy()
        modo = op.get('borrar', 'auto')
        if modo == 'auto':
            zona = arr[y0:y1, x0:x1]
            modo = 'transparente' if (zona[..., 3] == 0).mean() > 0.3 else 'fila'
        trazo = borrar(arr, caja, modo, op.get('fondo_x'), op.get('colores_borrar', ()), op.get('fondo_color'))
        texto = op.get('texto', '')
        if not texto:
            continue
        # colores del japonés
        na = norm(antes)
        tpx = na[trazo]
        if not len(tpx) and ('auto' in (op.get('color', 'auto'), op.get('borde'))):
            raise ValueError(f'sin trazo japonés en {caja}')
        exterior = trazo & np.pad(~trazo, 1, constant_values=True)[:-2, 1:-1] |             trazo & np.pad(~trazo, 1, constant_values=True)[2:, 1:-1] |             trazo & np.pad(~trazo, 1, constant_values=True)[1:-1, :-2] |             trazo & np.pad(~trazo, 1, constant_values=True)[1:-1, 2:]
        borde = op.get('borde')
        color = op.get('color', 'auto')
        if borde == 'auto':
            borde = tuple(int(v) for v in _moda(na[exterior]))
            interior = trazo & ~exterior
            color = color if color != 'auto' else tuple(int(v) for v in _moda(na[interior] if interior.any() else tpx))
        elif color == 'auto':
            color = tuple(int(v) for v in _moda(tpx))
        sombra = op.get('sombra')
        fuente = op.get('fuente', 'f12')
        filas = mascara(texto, fuente, op.get('tracking'))
        extra = (2 if borde else 0) + (abs(sombra[0]) if sombra else 0)
        extra_v = (2 if borde else 0) + (abs(sombra[1]) if sombra else 0)
        # recorte vertical común: quita filas vacías de arriba/abajo del bloque
        paso = op.get('paso')
        bloques = []
        for m in filas:
            bloques.append(m)
        todo = np.concatenate(bloques, 0)
        usadas = np.where(todo.any(1))[0]
        if not len(usadas):
            raise ValueError('texto vacío')
        if len(filas) == 1 and isinstance(fuente, tuple):
            ref = F.ttf_linea('ÁÉÍÓÚÑbdfhklgjpqy', P.BAHN, fuente[2], fuente[1])
            ru = np.where(ref.any(1))[0]
            # sin tildes en el texto: la caja empieza en la altura de las ascendentes
            asc = np.where(F.ttf_linea('bdfhklI', P.BAHN, fuente[2], fuente[1]).any(1))[0][0]
            r0 = min(asc, usadas[0])
            bloque = filas[0][r0:ru[-1] + 1]
        elif len(filas) == 1:
            m = filas[0]
            r0 = min(usadas[0], 2)
            bloque = m[r0:max(usadas[-1] + 1, 13)]
        else:
            alto_l = paso or (filas[0].shape[0] - 2)
            partes = []
            for k, m in enumerate(filas):
                partes.append(m[2:2 + alto_l] if not isinstance(fuente, tuple) else m)
            bloque = np.concatenate(partes, 0)
            u = np.where(bloque.any(1))[0]
            bloque = bloque[:u[-1] + 1]
        bh, bw = bloque.shape
        W, H = x1 - x0, y1 - y0
        if bw + extra > W or bh + extra_v > H:
            raise NoCabe(f'«{texto}» ({bw}x{bh}) no cabe en {W}x{H} {caja}')
        al = op.get('alinear', 'c')
        off = 1 if borde else 0
        if 'x' in op:
            x = op['x'] + off
        elif al == 'l':
            cols = np.where(trazo.any(0))[0]
            x = (cols[0] if len(cols) else 0) + off
            x = min(x, W - bw - extra + off)
        elif al == 'r':
            x = W - bw - extra + off
        else:
            x = (W - bw - extra) // 2 + off
        y = (H - bh - extra_v) // 2 + off + op.get('dy', 0)
        y = max(off, min(y, H - bh - extra_v + off))
        mask = np.zeros((arr.shape[0], arr.shape[1]), bool)
        mask[y0 + y:y0 + y + bh, x0 + x:x0 + x + bw] = bloque
        capas = []
        if sombra:
            base = P.dil(mask) if borde else mask
            s = P.desplazar(base, sombra[0], sombra[1])
            capas.append((s, tuple(sombra[2])))
        if borde:
            capas.append((P.dil(mask), tuple(borde)))
        capas.append((mask, tuple(color)))
        dentro = np.zeros_like(mask)
        dentro[y0:y1, x0:x1] = True
        for m, c in capas:
            arr[m & dentro] = c
    return arr


# ------------------------------------------------------------------ plan
from planes_menus import PLAN  # noqa: E402,F401
