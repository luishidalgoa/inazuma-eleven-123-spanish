"""v90 (IE1) / v04 (IE2) · literales CRO restantes: tipografía de bigramas y utilidades comunes.

Fuente que pinta los literales del CRO (comprobado en ina_main1.cro e ina_main2.cro, ver informe.json):
todos los caminos de texto (IE2 0x121a78 / virtual +8 del gestor, IE1 0x2ed24 y 0xe6214) acaban en
cGameTextSystem::DrawTextHintOnVram(FONT_TYPE) de code.bin, que pinta con la BCFNT del tipo del gestor
(font/FONT12.bcfnt, FONT8.bcfnt, FONT12T.bcfnt). El avance sale de FontGetCharWidth (constante por tipo:
paso fijo 15 px en FONT12, 10 px en FONT8) o de NWFontGetCharWidth (BCFNT). La NFTR solo se carga en el
objeto NNS del gestor: no se usa para pintar ni para medir (los portadores de acento griegos de las
traducciones del CRO de v33/v89 se ven como vocales acentuadas en juego, cosa imposible si pintase la NFTR).
Por eso los bigramas se dibujan en las BCFNT compartidas y las NFTR no se tocan.

Registro: el de v89 (work/ie1/capas/fuentes/bigramas_ritmo/registro.json) + pares añadidos al final con códigos
nuevos (kanji sin aparición en texto ni literal en code.bin/CRO: escaneo de v88 + escaneo_literales de v89 +
escaneo_literales_v90.json). A un par existente se le añade el dibujo de FONT8/FONT12T si un campo lo exige y su
código tiene glifo propio en esa fuente.

Campos:
  f12     solo FONT12 (paso 15 o proporcional): casillas de 1-4 caracteres y variantes (ritmo.py de v89).
  f8      FONT12 + FONT8: pares de 2 letras; sin solape en FONT8 a paso 10.
  nombre  FONT12 + FONT8 + FONT12T: pares de 2 letras; sin solape en FONT8 (10) ni FONT12T (15).
"""
from __future__ import annotations

import collections
import hashlib
import json
import re
import sys
import tempfile
from functools import lru_cache
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[5]
W = ROOT / 'work'
for p in (HERE, W / 'ie1/capas/historial/fuentes/v88_bigramas_total', W / 'ie2/shared/capas/historial/nombres/v03_textos/cro', ROOT / 'tools/src',
          ROOT / 'tools'):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import comun88  # noqa: E402

A89 = comun88.modulo('v89_bigramas_ritmo', W / 'ie1/capas/fuentes/bigramas_ritmo/apply.py')
A88 = A89.A88
R = A89.R
V79 = A88.V79
V87 = A88.V87
F12, F8, F12T = A88.F12, A88.F8, A88.F12T
FUENTES = (F12, F8, F12T)
from crorefs2 import Refs  # noqa: E402  (IE2 v03, genérico)

BASE_IE1 = W / 'shared/candidatas/probe_ie1_v89/archive.fa'
REG89 = W / 'ie1/capas/fuentes/bigramas_ritmo/registro.json'
ESC88 = W / 'ie1/capas/historial/fuentes/v88_bigramas_total/escaneo_base_v87.json'
LIT89 = W / 'ie1/capas/fuentes/bigramas_ritmo/literales.json'
LIT90 = HERE / 'escaneo_literales_v90.json'
REG90 = HERE / 'registro.json'
EXTRA_FUENTES = HERE / 'extra'
# v90: además de las carpetas gráficas de v89, texturas empaquetadas (.arc ARCV/SSZL, .lzs, .pac_) y los
# ejecutables (code.bin y CRO), cuyas apariciones ya descarta el escaneo de literales en cadena.
GRAFICOS_V90 = re.compile(r'/(pic3d|pic2d|a_field|model|effect3d|face2d|spr|map2d|map3d)/|\.(arc|lzs|pac_)$'
                          r'|(^|/)code\.bin$|\.cr[os]$')

CAMPOS = {
    'f12': ((F12,), []),
    'f12s': ((F12,), []),                 # FONT12 sin variantes (literales de fuente dudosa con dibujo extra)
    'dlg': ((F12,), [('prop', F12)]),     # ventana de diálogo/mensaje: además paso proporcional (avance CWDH)
    'f8': ((F12, F8), [(F8, 10)]),
    'f8p': ((F12, F8), [(F8, 10)]),       # pintado con FONT8 (paso 10): coste de huecos medido en FONT8
    'nombre': ((F12, F8, F12T), [(F8, 10), (F12T, 15)]),
}
PASO = {F12: 15, F8: 10, F12T: 15}
MODELO = {'f12': 'fijo12', 'f12s': 'fijo12', 'dlg': 'prop12', 'f8': 'fijo12', 'f8p': 'fijo8', 'nombre': 'fijo12'}
REALES = {'f12': (F12,), 'f12s': (F12,), 'dlg': (F12,), 'f8': (F12, F8), 'f8p': (F8,), 'nombre': (F12, F8, F12T)}
PROP = '\ue002'         # prefijo de clave: par para el camino proporcional (tinta desde la columna 1)


def es_prop(c):
    return c[:1] == PROP


def texto(c):
    return c[1:] if c[:1] in (R.IZQ, R.DER, PROP) else c
CELDA = A88.CELDA
PEN_NUEVO = 0.4          # coste de un par que necesita código o dibujo nuevo
ORD = 'º'                # sin glifo en las BCFNT: se dibuja a mano
GI_ORD = 1 << 20         # índice ficticio de lectura (no se escribe en la fuente)


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _ord_bitmap(F, grande: bool):
    """Mapa de bits de «º» con la altura de las minúsculas de la fuente: anillo arriba y raya debajo."""
    bm = F.bitmap(F.gi(A88.codepoint('o')))
    filas = [y for y, row in enumerate(bm) if any(v >= 5 for v in row)]
    top = [y for y, row in enumerate(F.bitmap(F.gi(A88.codepoint('T')))) if any(v >= 5 for v in row)][0]
    H, Wd = len(bm), len(bm[0])
    out = [[0] * Wd for _ in range(H)]
    if grande:
        anillo = ['.##.', '#..#', '#..#', '.##.']
        raya_y = top + 5
    else:
        anillo = ['###', '#.#', '###']
        raya_y = top + 4
    for dy, fila in enumerate(anillo):
        for dx, ch in enumerate(fila):
            if ch == '#':
                out[top + dy][1 + dx] = 15
    for dx in range(len(anillo[0])):
        out[raya_y][1 + dx] = 15
    assert raya_y <= max(filas)
    return out


class Tipografia:
    """Registro v89 ampliado + fuentes BCFNT de probe_ie1_v89 (idénticas en probe_ie2_v02)."""

    def __init__(self):
        self.reg89 = json.loads(REG89.read_text(encoding='utf-8'))
        get = comun88.abrir(BASE_IE1)
        self.tmp = Path(tempfile.mkdtemp(prefix='ie123_v90_'))
        self.antes, self.F = {}, {}
        for f in FUENTES:
            datos = get(f)
            assert sha(datos) == self.reg89['fuentes_dibujadas'][f], f'{f} no es la de v89'
            self.antes[f] = datos
            (self.tmp / Path(f).name).write_bytes(datos)
            self.F[f] = A88.cargar(self.tmp / Path(f).name)
        # «º» de lectura (no hay glifo): índice ficticio en FONT12 y FONT8
        for f, grande in ((F12, True), (F8, False)):
            Fu = self.F[f]
            bm = _ord_bitmap(Fu, grande)
            Fu.cmap[ord(ORD)] = GI_ORD
            Fu._cache[GI_ORD] = bm
            xs = [x for row in bm for x, v in enumerate(row) if v]
            adv = Fu.metrics[Fu.gi(A88.codepoint('o'))][2]
            Fu.metrics[GI_ORD] = (0, max(xs) + 1, adv)
        self.reg = [dict(e) for e in self.reg89['bigramas']]
        self.por_clave = {A89.clave_de(e): e for e in self.reg}
        self.mq = A89.Maqueta(self.F[F12], A88.codepoint)
        for e in self.reg:
            self.mq.fijos[A89.clave_de(e)] = A89.medir(self.F[F12], self.F[F12].gi(int(e['unicode'][2:], 16)))
        self.pares = A88.Pares(self.F)
        self.dib = A88.Dibujo(self.F, self.pares, None)
        self.inv = {}
        for f in FUENTES:
            d = collections.defaultdict(list)
            for cp, gi in self.F[f].cmap.items():
                if gi != GI_ORD:
                    d[gi].append(cp)
            self.inv[f] = d
        self.pool = self._pool()
        self.nuevos = {}          # clave -> set(fuentes)
        self.exigidas = collections.defaultdict(set)   # clave existente -> fuentes añadidas
        self.campos = collections.defaultdict(set)
        self.codec = None

    # ------------------------------------------------------------------ códigos libres
    def unico(self, f, sjis):
        return A89.unico(self.F[f], self.inv[f], sjis)

    def _pool(self):
        esc = json.loads(ESC88.read_text(encoding='utf-8'))
        lit = json.loads(LIT89.read_text(encoding='utf-8'))
        lit.update(json.loads(LIT90.read_text(encoding='utf-8')))
        usados = {e['sjis'] for e in self.reg}
        out = []
        graf = []
        for c, v in esc['codigos'].items():
            if c in usados or int(c, 16) < 0x889F or v.get('texto'):
                continue
            if c not in lit or lit[c] or not self.unico(F12, c):
                continue
            tres = all(self.unico(f, c) for f in FUENTES)
            if c in esc['limpios']:
                out.append((c, 'limpio_escaneo_v88', tres))
                continue
            rutas = [r for r, _ in esc['apariciones_textuales'].get(c, [])]
            if all(GRAFICOS_V90.search(r) for r in rutas):
                graf.append((len(rutas), sum(v.values()), c, tres))
        out += [(c, 'solo_graficos_v90', t) for _, _, c, t in sorted(graf)]
        return out

    # ------------------------------------------------------------------ disponibilidad de casillas
    @lru_cache(None)
    def trozo_prop(self, c):
        """Par proporcional (clave PROP+texto): mismo dibujo que el trozo, tinta desde la columna 1."""
        core = c[1:]
        if len(core) < 2 or ' ' in core:
            return None
        m = self.mq.trozo(core)
        if m is None:
            return None
        return dict(px=m['px'], ancho=m['ancho'], D=1)

    @lru_cache(None)
    def dibujable(self, c, f):
        if es_prop(c):
            return f == F12 and self.trozo_prop(c) is not None
        if f == F12:
            return self.mq.trozo(c) is not None
        if len(c) != 2 or R.variante(c):
            return False
        return self.pares.glifo(f, c) is not None

    def disponible(self, c, fuentes):
        """(válida, nueva) para una casilla de >= 2 caracteres o variante."""
        e = self.por_clave.get(c)
        if e is not None:
            nueva = False
            for f in fuentes:
                if f == F12 or f in e['fuentes']:
                    continue
                if not (self.unico(f, e['sjis']) and self.dibujable(c, f)):
                    return False, False
                nueva = True
            return True, nueva
        if not all(self.dibujable(c, f) for f in fuentes):
            return False, False
        return True, True

    # ------------------------------------------------------------------ modelos de colocación
    @lru_cache(None)
    def ext(self, modelo, c):
        """(x0, x1, avance): columnas sólidas relativas al lápiz (None si no hay tinta) y avance del lápiz."""
        if modelo == 'fijo12':
            e = self.mq.nativa(c) if len(c) == 1 else self.mq.extremos(c)
            return (e[0], e[1], 15) if e else (None, None, 15)
        if modelo == 'fijo8':
            F = self.F[F8]
            if len(c) == 2:
                px, _, _, _, _, D = self.pares.f8(c)
                xs = [x + D for (x, _), v in px.items() if v >= A88.SOLIDO[F8]]
            else:
                gi = F.gi(A88.codepoint(c))
                left, _, adv = F.metrics[gi]
                x0 = int((CELDA[F8] - adv) / 2) + left
                xs = [x + x0 for row in F.bitmap(gi) for x, v in enumerate(row) if v >= A88.SOLIDO[F8]]
            return (min(xs), max(xs), 10) if xs else (None, None, 10)
        xs, adv = self._prop_celda(c)
        return (min(xs), max(xs), adv) if xs else (None, None, adv)

    def _prop_celda(self, c):
        """(columnas sólidas relativas al lápiz, avance) de una casilla en el camino proporcional de FONT12."""
        F = self.F[F12]
        e = self.por_clave.get(c)
        if es_prop(c) and e is None:
            m = self.trozo_prop(c)
            adv = m['D'] + m['ancho'] + 1
            return [x + m['D'] for (x, _), v in m['px'].items() if v >= A88.SOLIDO[F12]], adv
        if (len(c) >= 2 or R.variante(c)) and e is None:
            m = self.mq.trozo(c)
            adv = m['D'] + m['ancho'] + (5 if R.texto(c).endswith(' ') else 1)
            return [x + m['D'] for (x, _), v in m['px'].items() if v >= A88.SOLIDO[F12]], adv
        cp = int(e['unicode'][2:], 16) if e is not None else A88.codepoint(c)
        gi = F.gi(cp)
        left, _, adv = F.metrics[gi]
        x0 = int((CELDA[F12] - adv) / 2) + left
        return [x + x0 for row in F.bitmap(gi) for x, v in enumerate(row) if v >= A88.SOLIDO[F12]], adv

    # ------------------------------------------------------------------ partición
    def particion(self, t, campo, nmax, prohib=frozenset()):
        fuentes, _ = CAMPOS[campo]
        modelo = MODELO[campo]
        n = len(t)
        INF = R.INF
        largo = 4 if campo in ('f12', 'f12s') else 3 if campo == 'dlg' else 2

        def es_palabra(i):
            return i > 0 and (t[i - 1] == ' ' or t[i] == ' ')

        def opciones(i):
            out = []
            for k in range(1, largo + 1):
                if i + k > n:
                    break
                s_ = t[i:i + k]
                if k == 1:
                    if s_ == ORD or (s_ != ' ' and self.mq.nativa(s_) is None):
                        continue
                    if modelo == 'fijo8' and s_ != ' ' and self.F[F8].gi(A88.codepoint(s_)) is None:
                        continue
                    out.append((1, s_, 0.0))
                    if campo == 'f12' and s_ != ' ':
                        for v in (R.IZQ + s_, R.DER + s_):
                            ok, nueva = self.disponible(v, fuentes)
                            if ok and v not in prohib:
                                out.append((1, v, 0.05 + (PEN_NUEVO if nueva else 0.0)))
                    continue
                c = PROP + s_ if campo == 'dlg' else s_
                if c in prohib or '  ' in s_:
                    continue
                ok, nueva = self.disponible(c, fuentes)
                if ok:
                    out.append((k, c, PEN_NUEVO if nueva else 0.0))
            return out

        @lru_cache(None)
        def f(i, usadas, cola):
            if i >= n:
                return 0.0, ()
            if usadas >= nmax:
                return INF, ()
            mejor = (INF, ())
            for k, c, pen in opciones(i):
                x0, x1, adv = self.ext(modelo, c)
                if x0 is None:
                    nuevo = None if cola is None else cola + adv
                    cst = 0.0
                else:
                    cst = 0.0 if cola is None else R.coste_hueco(cola + x0, es_palabra(i))
                    nuevo = adv - x1 - 1
                if cst == INF:
                    continue
                resto, cel = f(i + k, usadas + 1, nuevo)
                total = cst + resto + pen + 0.01
                if total < mejor[0]:
                    mejor = (total, (c,) + cel)
            return mejor

        return f(0, 0, None)

    def _solapes(self, cel, pasos):
        malos = set()
        for f, paso in pasos:
            if f == 'prop':
                pen, prev = 0, None
                for i, c in enumerate(cel):
                    xs, adv = self._prop_celda(c)
                    if xs:
                        if prev is not None and pen + min(xs) - prev[1] - 1 < A88.HUECO_MIN[F12]:
                            malos |= {x for x in (cel[prev[0]], c) if len(x) >= 2 or R.variante(x)}
                        prev = (i, pen + max(xs))
                    pen += adv
                continue
            col = self.dib.colocar(f, cel, paso)
            for i, g in self.dib.huecos(col, A88.SOLIDO[f]):
                if g < A88.HUECO_MIN[f]:
                    malos |= {c for c in (cel[i], cel[i + 1]) if len(c) >= 2}
        return malos

    def celdas(self, t, campo, nmax):
        """Casillas de un texto plano con como mucho nmax casillas (ValueError si no cabe)."""
        _, pasos = CAMPOS[campo]
        prohib = set()
        while True:
            coste, cel = self.particion(t, campo, nmax, frozenset(prohib))
            if coste == R.INF:
                raise ValueError(f'{t!r} no cabe en {nmax} casillas ({campo})')
            cel = list(cel)
            malos = self._solapes(cel, pasos)
            if not malos:
                return cel
            prohib |= malos

    def usar(self, cel, campo, uso):
        """Registra las casillas usadas (fuentes exigidas) antes de asignar códigos."""
        fuentes, _ = CAMPOS[campo]
        for c in cel:
            if len(c) < 2 and not R.variante(c):
                continue
            self.campos[c].add(uso)
            e = self.por_clave.get(c)
            if e is None:
                self.nuevos.setdefault(c, set()).update(fuentes)
            else:
                for f in fuentes:
                    if f != F12 and f not in e['fuentes']:
                        self.exigidas[c].add(f)

    def extra(self, cel, fuentes):
        """Dibuja además los pares en otras fuentes cuando caben (cobertura por si ese gestor los pinta).
        Devuelve [(casilla, fuente)] que NO se han podido cubrir."""
        faltan = []
        for c in cel:
            if len(c) < 2 or R.variante(c) or es_prop(c):
                continue
            for f in fuentes:
                e = self.por_clave.get(c)
                if e is not None and f in e['fuentes']:
                    continue
                if not self.dibujable(c, f) or (e is not None and not self.unico(f, e['sjis'])):
                    faltan.append((c, f))
                    continue
                if e is None:
                    self.nuevos.setdefault(c, set()).add(f)
                else:
                    self.exigidas[c].add(f)
        return faltan

    # ------------------------------------------------------------------ códigos y dibujo
    def asignar_y_dibujar(self):
        escritor = {F12: A88.V75G.Celdas(self.F[F12]), F8: A88.V75G.Celdas(self.F[F8]),
                    F12T: A88.CeldasLA4(self.F[F12T])}

        def pintar(f, gi, px):
            Fu = self.F[f]
            for y in range(Fu.sy):
                for x in range(Fu.sx):
                    escritor[f].escribir(gi, x, y, 0)
            for (x, y), v in px.items():
                assert 0 <= x < Fu.sx - 1 and 0 <= y < Fu.sy - 1, (f, gi, x, y)
                escritor[f].escribir(gi, 1 + x, 1 + y, v)

        libres = list(self.pool)
        añadidos = []
        for c in sorted(self.nuevos, key=lambda c: (-len(self.nuevos[c]), c)):
            necesita = self.nuevos[c] - {F12}
            k = next(i for i, (s, _, _) in enumerate(libres) if all(self.unico(f, s) for f in necesita))
            s, origen, _ = libres.pop(k)
            ch = bytes.fromhex(s).decode('cp932')
            e = dict(par=R.texto(c), sjis=s, unicode=f'U+{ord(ch):04X}', kanji=ch, origen=origen, fuentes={})
            if R.variante(c):
                e.update(clave=c, variante='izquierda' if c[0] == R.IZQ else 'derecha')
            if es_prop(c):
                e.update(par=c[1:], clave=c, variante='proporcional')
            self.reg.append(e)
            self.por_clave[c] = e
            añadidos.append(c)
            self.exigidas[c] |= necesita
            # FONT12 (maqueta v89)
            F = self.F[F12]
            cp = ord(ch)
            gi = F.gi(cp)
            m = self.trozo_prop(c) if es_prop(c) else self.mq.trozo(c)
            ancho, D = m['ancho'], m['D']
            Rr = 5 if e['par'].endswith(' ') else 1
            adv = D + ancho + Rr
            left = D - int((R.CELDA - adv) / 2)
            assert -128 <= left <= 127 and 0 < adv <= 255
            viejo = list(F.metrics[gi])
            pintar(F12, gi, m['px'])
            F.set_metrics(gi, left, ancho, adv)
            leido = {(x, y): v for y, row in enumerate(F.bitmap(gi)) for x, v in enumerate(row) if v}
            assert leido == m['px'], c
            px_sha = hashlib.sha1(json.dumps(sorted(m['px'].items())).encode()).hexdigest()
            e['fuentes'][F12] = dict(glifo=gi, cwdh_antes=viejo, cwdh=[left, ancho, adv], tinta_px=ancho,
                                     columna=D, solido=[m.get('S0'), m.get('S1')], hueco_interno=m.get('g'),
                                     pixeles_sha1=px_sha,
                                     maqueta='v90 proporcional (tinta en la columna 1)' if es_prop(c)
                                     else 'v89 (v90)')
            e.update(glifo=gi, cwdh=[left, ancho, adv], tinta_px=ancho, D=D, R=Rr, pixeles_sha1=px_sha)
            if not es_prop(c):
                self.mq.fijos[c] = A89.medir(F, gi)
                assert (self.mq.fijos[c]['S0'], self.mq.fijos[c]['S1']) == (m['S0'], m['S1']), c
        for c, fs in sorted(self.exigidas.items()):
            e = self.por_clave[c]
            cp = int(e['unicode'][2:], 16)
            for f in sorted(fs):
                if f in e['fuentes']:
                    continue
                assert self.unico(f, e['sjis']), (c, f)
                Fu = self.F[f]
                gf = Fu.gi(cp)
                px, ancho, left, width, adv, D = self.pares.glifo(f, c)
                viejo = list(Fu.metrics[gf])
                pintar(f, gf, px)
                Fu.set_metrics(gf, left, width, adv)
                leido = {(x, y): v for y, row in enumerate(Fu.bitmap(gf)) for x, v in enumerate(row) if v}
                esperado = px if f != F12T else {k: max(v >> 4, v & 0xF) for k, v in px.items()}
                assert leido == esperado, (c, f)
                e['fuentes'][f] = dict(glifo=gf, cwdh_kanji=viejo, cwdh=[left, width, adv], tinta_px=ancho,
                                       columna=D, v90=True,
                                       pixeles_sha1=hashlib.sha1(json.dumps(sorted(px.items())).encode()).hexdigest())
        for c, usos in self.campos.items():
            e = self.por_clave[c]
            e['campos'] = sorted(set(e.get('campos', [])) | {'cro'})
            e.setdefault('usos_cro_v90', [])
            e['usos_cro_v90'] = sorted(set(e['usos_cro_v90']) | usos)
        self.codec = A89.Codec(self.reg)
        return añadidos

    def codificar(self, cel) -> bytes:
        return self.codec.codificar(list(cel))

    def escribir_fuentes(self, destino: Path):
        salida = {}
        for f in FUENTES:
            datos = self.F[f].data()
            assert len(datos) == len(self.antes[f])
            if datos != self.antes[f]:
                p = destino / f
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(datos)
                salida[f] = sha(datos)
        return salida

    def registro_json(self, añadidos, fuentes_sha):
        r = dict(self.reg89)
        r['version'] = 'v90'
        r['descripcion'] = (self.reg89['descripcion'] + ' v90 (work/ie1/capas/historial/menus_cro/v90_cro_restantes): literales del '
                            'CRO de IE1 e IE2 que quedaban en japonés; pares nuevos al final (campo «cro», '
                            '«usos_cro_v90» = juego:offset), y dibujo de FONT8/FONT12T añadido a pares '
                            'existentes cuando un literal pintado con ese gestor los usa (marca v90).')
        r['regla_codigos'] = (self.reg89['regla_codigos'] + '; v90: mismos criterios que v89 con el escaneo de '
                              'literales ampliado a los 576 códigos sin escanear (escaneo_literales_v90.json)')
        r['bigramas'] = self.reg
        r['fuentes_dibujadas'] = {f: fuentes_sha.get(f, self.reg89['fuentes_dibujadas'][f]) for f in FUENTES}
        r['pares_v90'] = añadidos
        return r

    # ------------------------------------------------------------------ vistas previas
    def celda_px(self, f, c):
        """Píxeles de una casilla relativos al lápiz, con los dibujos finales de la fuente."""
        Fu = self.F[f]
        if len(c) >= 2 or R.variante(c):
            cp = int(self.por_clave[c]['unicode'][2:], 16)
        else:
            cp = A88.codepoint(c)
        gi = Fu.gi(cp)
        if gi is None:
            return {}, 0
        left, _, adv = Fu.metrics[gi]
        x0 = int((CELDA[f] - adv) / 2) + left
        return {(x + x0, y): v for y, row in enumerate(Fu.bitmap(gi)) for x, v in enumerate(row) if v}, adv

    def la(self, f, gi):
        """{(x, y): (L, A)} de un glifo LA4 (FONT12T) sin el margen de 1 px."""
        Fu = self.F[f]
        t, fo = Fu.t, Fu.f
        sheet, cell = divmod(gi, fo.PER)
        ox = (cell % t['ncols']) * Fu.sx
        oy = (cell // t['ncols']) * Fu.sy
        out = {}
        for y in range(Fu.sy - 1):
            for x in range(Fu.sx - 1):
                X, Y = ox + 1 + x, oy + 1 + y
                tile = (Y // 8) * (t['sheet_w'] // 8) + (X // 8)
                b = fo.data[fo.doff + sheet * t['sheet_size'] + tile * 64 + A88.morton8(X % 8, Y % 8)]
                if b & 0xF:
                    out[(x, y)] = (b >> 4, b & 0xF)
        return out

    def colocar(self, f, lineas, proporcional=False):
        """[(x, y, alfa | (L, A))] de varias líneas de casillas (None = hueco de un carácter de formato)."""
        out = []
        for ln, cel in enumerate(lineas):
            pen = 0
            for c in cel:
                if c is None:
                    pen += PASO[f] if not proporcional else 12
                    continue
                px, adv = self.celda_px(f, c)
                if f == F12T and px:
                    Fu = self.F[f]
                    cp = int(self.por_clave[c]['unicode'][2:], 16) if (len(c) >= 2 or R.variante(c))                         else A88.codepoint(c)
                    gi = Fu.gi(cp)
                    left, _, adv2 = Fu.metrics[gi]
                    x0 = int((CELDA[f] - adv2) / 2) + left
                    px = {(x + x0, y): la for (x, y), la in self.la(f, gi).items()}
                out += [(x + pen, y + ln * (self.F[f].sy + 2), v) for (x, y), v in px.items()]
                pen += adv if proporcional else PASO[f]
        return out

    def huecos_min(self, f, cel, proporcional=False):
        """Hueco sólido mínimo entre casillas vecinas con tinta (None si no hay pares)."""
        cols = []
        pen = 0
        for c in cel:
            px, adv = self.celda_px(f, c)
            xs = [x + pen for (x, _), v in px.items() if v >= A88.SOLIDO[f]]
            cols.append(xs)
            pen += adv if proporcional else PASO[f]
        gaps = [min(b) - max(a) - 1 for a, b in zip(cols, cols[1:]) if a and b]
        return min(gaps) if gaps else None


def png(puntos, destino: Path, escala=4):
    """Vista previa ampliada: alfa de 4 bits en blanco sobre azul; (L, A) de FONT12T mezclado con el fondo."""
    from PIL import Image
    if not puntos:
        puntos = [(0, 0, 0)]
    w = max(x for x, _, _ in puntos) + 3
    h = max(y for _, y, _ in puntos) + 3
    fondo = (24, 32, 72)
    img = Image.new('RGB', (w * escala, h * escala), fondo)
    px = img.load()
    for x, y, v in puntos:
        if x < 0 or y < 0:
            continue
        if isinstance(v, tuple):
            L, A = v
            a = A / 15
            col = tuple(int(round(fondo[i] * (1 - a) + L * 17 * a)) for i in range(3))
        else:
            if v <= 0:
                continue
            a = min(255, v * 17)
            col = (a, a, a)
        for dx in range(escala):
            for dy in range(escala):
                px[(x + 1) * escala + dx, (y + 1) * escala + dy] = col
    destino.parent.mkdir(parents=True, exist_ok=True)
    img.save(destino)


# ---------------------------------------------------------------------- CRO
FMT = re.compile(r'(%[0-9]*[sd]|\n)')


def cuerpo(d: bytes, o: int) -> bytes:
    return d[o:d.index(b'\0', o)]


def construir(T: Tipografia, e, uso):
    """Piezas del literal traducido ([('c', casillas) | ('f', formato)]) y casillas por línea."""
    jp = e['japones'].encode('cp932')
    campo = e['campo']
    if 'celdas' in e:                      # partición fijada a mano (IE1 千羽山)
        cel = list(e['celdas'])
        for c in cel:
            if len(c) >= 2:
                ok, _ = T.disponible(c, CAMPOS[campo][0])
                assert ok, (e['offset'], c)
        T.usar(cel, campo, uso)
        return [('c', cel)], [cel]
    texto = e['espanol']
    if not FMT.search(texto):
        n = len(jp) // 2
        cel = T.celdas(texto, campo, n)
        if e.get('exacto'):
            cel = cel + [' '] * (n - len(cel))
        T.usar(cel, campo, uso)
        return [('c', cel)], [cel]
    trozos = [t for t in FMT.split(texto) if t]
    resto = len(jp) - sum(len(t) for t in trozos if FMT.fullmatch(t))
    piezas, lineas = [], [[]]
    for t in trozos:
        if FMT.fullmatch(t):
            piezas.append(('f', t))
            if t == chr(10):
                lineas.append([])
            else:
                lineas[-1].append(None)
            continue
        cel = T.celdas(t, campo, resto // 2)
        resto -= 2 * len(cel)
        piezas.append(('c', cel))
        lineas[-1] += cel
        T.usar(cel, campo, uso)
    return piezas, lineas


def bytes_de(T: Tipografia, piezas) -> bytes:
    return b''.join(T.codificar(v) if k == 'c' else v.encode('ascii') for k, v in piezas)
