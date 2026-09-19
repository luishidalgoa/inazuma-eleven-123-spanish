"""Línea v20 · textos de IE2 (issue #77): menú de campo, caja de Pasión/Amistad, nombre completo de la ficha
y hueco vacío de accesorio. No construye ni instala.

Base: work/shared/candidatas/probe_ie2_v18 (archive.fa + romfs/cro/ina_main2.cro, con los parches de ancho
de diálogo de v14/v15, que se conservan: esta capa solo reescribe bytes de literales).
Registro de bigramas: work/ie2/shared/capas/nombres/nombres_compactos/registro.json (fuentes de la v18 = las
dibujadas por la v08, comprobado por sha256). Los códigos nuevos salen del depósito de la v08
(pool_codigos, recalculado contra el registro actual) y se añaden al final del registro (nunca se reasigna uno existente).

1. Menú de campo (ina_main2.cro 0xfbf6c, lista de 6 leída con strlen+1 por 0x107e80; 0xbd35c = copia de
   «セーブ» que 0xbd2a8 compara con la entrada de guardar). Dibujo: 0xbd1e8 -> 0x121a78 con el gestor
   [0x29b28c] = FONT12 (no FONT8; ver informe), paso fijo 15 px, x = lápiz + trunc((15 - adv)/2) + left.
   Casillas compactas nuevas de FONT12 con la tinta colocada a mano (columna D libre) para que la palabra
   empiece en la columna 0-1 y las casillas queden a 1-2 px. Cada entrada conserva su longitud en bytes
   (relleno con espacios de ancho completo AL FINAL: alineado a la izquierda).
2. Caja de Pasión/Amistad (0x6ab6c / 0x6ab80, 0x6a7d0/0x6a8a4 -> 0xf4320 con el gestor [0x29b284] = FONT8,
   paso 10): casillas compactas de FONT8 (modelo de la v08). Bytes <= japonés y casillas <= caracteres.
3. unitbase.dat +32 (nombre completo en kana, 32 B): nombre completo oficial de la NDS (+0 NDS), emparejado
   por registro con la función de la v03, con casillas del registro ya dibujadas en FONT8/FONT12/FONT12T
   (sin glifos nuevos); <= 15 casillas + NUL.
4. item.dat registro 0 («なし», hueco vacío de accesorio): «Vacío». La NDS española conserva «なし» en ese
   registro (no hay palabra oficial NDS); «Vacío» es la del port europeo oficial de IE1 3DS
   (es/inazuma1/data_iz/logic/item.dat registro 0).

Salida: romfs/cro/ina_main2.cro, extra/font/FONT{12,8,12T}.bcfnt (solo si cambian),
extra/inazuma2/data_iz/logic/{unitbase,item}.dat, registro.json, informe.json, previews/*_x4.png.
Uso: python -X utf8 work/ie2/shared/capas/historial/nombres/v20_textos/apply.py   (después validate.py)
"""
from __future__ import annotations

import collections
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[6]
V08 = ROOT / 'work/ie2/shared/capas/nombres/nombres_compactos'
V03 = ROOT / 'work/ie2/shared/capas/historial/nombres/v03_textos'
sys.path.insert(0, str(V08))
sys.path.insert(0, str(V03))
import comun08 as K  # noqa: E402
import diseno08 as D  # noqa: E402
import modelo8 as M8  # noqa: E402

A88, A89, R = K.A88, K.A89, K.R
F12, F8, F12T = K.F12, K.F8, K.F12T
V79 = A88.V79

CAND = ROOT / 'work/shared/candidatas/probe_ie2_v18'
ARCHIVE = CAND / 'archive.fa'
CRO_BASE = CAND / 'romfs/cro/ina_main2.cro'
CRO_JP = ROOT / 'work/shared/base_3ds/romfs/cro/ina_main2.cro'
REGISTRO = V08 / 'registro.json'
EU = ROOT / 'work/ie1/fuentes/3ds_eu/romfs/archive.fa'
UNIT = 'inazuma2/data_iz/logic/unitbase.dat'
ITEM = 'inazuma2/data_iz/logic/item.dat'
REC, NREG = 96, 2399
ESPACIO = '　'.encode('cp932')
PREF12 = ''           # clave de las casillas FONT12 compactas de esta capa: PREF12 D PREF12 texto

# offset, japonés, alternativas en orden (la primera que cabe), fuente
LISTA = [
    (0xfbf6c, 'なかま', ['Equipo']),
    (0xfbf73, 'もちもの', ['Inventario', 'Invent.']),
    (0xfbf7c, 'せんじゅつ', ['Tácticas']),
    (0xfbf87, 'じょうほう', ['Datos']),
    (0xfbf92, 'システム', ['Sistema', 'Sist.']),
    (0xfbf9b, 'セーブ', ['Guardar', 'Guar.']),
]
ESPEJO_GUARDAR = 0xbd35c
CAJA = [
    (0x6ab6c, 'ねっけつ', ['Pasión', 'Pas.']),
    (0x6ab80, 'ゆうじょう', ['Amistad']),
]
INF = M8.INF


def sha(b):
    return hashlib.sha256(b).hexdigest()


# ------------------------------------------------------------------------------------------------ CRO refs
class Refs:
    """Referencias ADR y de pool con relocación a un offset del CRO (como crorefs.py de IE1 v33)."""

    def __init__(self, data):
        import struct
        u32 = lambda o: struct.unpack_from('<I', data, o)[0]  # noqa: E731
        segs = [struct.unpack_from('<III', data, u32(0xC8) + 12 * i) for i in range(u32(0xCC))]
        cs, ce = segs[0][0], segs[0][0] + segs[0][1]
        self.byval = collections.defaultdict(list)
        for i in range(u32(0x12C)):
            so, typ, sidx, _, _, add = struct.unpack_from('<IBBBBI', data, u32(0x128) + 12 * i)
            self.byval[segs[sidx][0] + add].append(segs[so & 0xf][0] + (so >> 4))
        self.adr = collections.defaultdict(list)

        def rot(w):
            r = ((w >> 8) & 0xf) * 2
            i = w & 0xff
            return ((i >> r) | (i << (32 - r))) & 0xffffffff
        for off in range(cs, ce, 4):
            w = u32(off)
            if (w & 0x0FEF0000) == 0x028F0000:
                self.adr[off + 8 + rot(w)].append(off)
            elif (w & 0x0FEF0000) == 0x024F0000:
                self.adr[off + 8 - rot(w)].append(off)

    def a(self, o):
        return len(self.adr.get(o, [])) + len(self.byval.get(o, []))


# ------------------------------------------------------------------------------------------------ depósito
def falsos_literales(usados):
    """Códigos que la v08 descartó solo porque su escaneo de literales los vio en ina_main2.cro, pero cuyas
    apariciones (en la CRO japonesa y en la de la v18) caen TODAS dentro del segmento de código (.text,
    instrucciones BL: 0x..eb): no son texto. Resto de criterios de la v08: sin aparición en texto
    (escaneo_v05.json) y apariciones «textuales» solo en ficheros gráficos."""
    import re
    import struct
    v5 = json.loads((V08 / 'escaneo_v05.json').read_text(encoding='utf-8'))
    lit = json.loads((V08 / 'escaneo_literales_v08.json').read_text(encoding='utf-8'))
    G = re.compile(r'/(pic3d|pic2d|a_field|model|effect3d|face2d|spr|map2d|map3d)/|\.(arc|lzs|pac_)$')
    cros = [CRO_JP.read_bytes(), CRO_BASE.read_bytes()]
    fin_text = []
    for d in cros:
        so = struct.unpack_from('<I', d, 0xC8)[0]
        a, n = struct.unpack_from('<II', d, so)[:2]
        fin_text.append((a, a + n))
    out = []
    for c, v in sorted(v5['codigos'].items()):
        if c in usados or v.get('texto') or not lit.get(c):
            continue
        if set(lit[c]) - {'base_3ds/cro/ina_main2.cro', 'v05/cro/ina_main2.cro'}:
            continue
        if not all(G.search(r) for r, _ in v5['apariciones_textuales'].get(c, [])):
            continue
        b = bytes.fromhex(c)
        ok = True
        for d, (a, e) in zip(cros, fin_text):
            i = d.find(b)
            while i >= 0 and ok:
                # dentro de .text y todas las palabras de 32 bits que toca son instrucciones ARM «siempre»
                palabras = {a + ((j - a) // 4) * 4 for j in (i, i + 1)}
                ok = a <= i and i + 2 <= e and all(d[w + 3] >> 4 == 0xE for w in palabras)
                i = d.find(b, i + 1)
        if ok:
            out.append(c)
    return out


# ------------------------------------------------------------------------------------------------ fuentes
def cargar(get, reg):
    tmp = Path(tempfile.mkdtemp(prefix='ie2_v20_'))
    F, antes = {}, {}
    for f in K.FUENTES:
        d = get(f)
        assert sha(d) == reg['fuentes_dibujadas'][f], f'{f}: la fuente de la v18 no es la del registro v08'
        antes[f] = d
        (tmp / Path(f).name).write_bytes(d)
        F[f] = A88.cargar(tmp / Path(f).name)
    return F, antes, tmp


class Compacta12:
    """Casillas FONT12 a paso fijo de 15 con la tinta en una columna libre (menú de campo)."""
    PASO = 15

    def __init__(self, Dz, F, reg):
        self.Dz, self.F, self.mq = Dz, F[F12], Dz.mq
        self.fijos = collections.defaultdict(list)       # texto -> [(S0, S1, clave)]
        for e in reg['bigramas']:
            if F12 not in e['fuentes']:
                continue
            gi = self.F.gi(int(e['unicode'][2:], 16))
            m = A89.medir(self.F, gi)
            self.fijos[e['par']].append((m['S0'], m['S1'], A89.clave_de(e)))

    def maqueta(self, t):
        """(px desde la columna 0 de la tinta, ancho total, s0 relativo, s1 relativo) o None."""
        if len(t) == 1:
            L = self.mq.letra(t)
            if L is None:
                return None
            p, s0, s1, f0, f1, _ = L
            return {(x - f0, y): v for (x, y), v in p.items()}, f1 - f0 + 1, s0 - f0, s1 - f0
        m = R.Maqueta.trozo(self.mq, t)
        if m is None or m.get('g') is None:
            return None
        return m['px'], m['ancho'], m['S0'] - m['D'], m['S1'] - m['D']

    def opciones(self, t):
        out = []
        if len(t) == 1:
            nat = self.mq.nativa(t)
            if nat is not None:
                out.append((nat[0], nat[1], 0.0, t))
        for s0, s1, c in self.fijos.get(t, ()):
            out.append((s0, s1, 0.0, c))
        mq = self.maqueta(t)
        if mq is not None:
            _, ancho, r0, r1 = mq
            for Dd in range(0, self.PASO - ancho + 1):
                out.append((Dd + r0, Dd + r1, 0.8, f'{PREF12}{Dd:+d}{PREF12}{t}'))
        return out

    @staticmethod
    def hueco(g):
        if g < 1:
            return INF
        return {1: 0.4, 2: 0.0, 3: 1.0, 4: 3.0, 5: 5.0}.get(g, 5.0 + 2.0 * (g - 5))

    def partir(self, texto, n_max):
        from functools import lru_cache
        n = len(texto)

        @lru_cache(None)
        def f(i, prev, k):
            if i >= n:
                return 0.0, ()
            if k >= n_max:
                return INF, ()
            mejor = (INF, ())
            for L in range(1, 4):
                if i + L > n:
                    break
                for s0, s1, c, clave in self.opciones(texto[i:i + L]):
                    if prev is None:     # a la izquierda: tinta desde la columna 0-1; cada px de más cuesta
                        cst = INF if s0 > 6 else 0.3 * max(0, s0 - 1)
                    else:
                        cst = self.hueco(s0 + self.PASO - prev - 1)
                    if cst == INF:
                        continue
                    r = f(i + L, s1, k + 1)
                    if cst + c + r[0] < mejor[0]:
                        mejor = (cst + c + r[0], ((clave, s0, s1),) + r[1])
            return mejor
        return f(0, None, 0)

    def minimo(self, texto):
        """Ancho sólido mínimo de la palabra con 1 px entre letras (para el informe)."""
        ws = [self.mq.letra(ch)[2] - self.mq.letra(ch)[1] + 1 for ch in texto if ch != ' ']
        return sum(ws) + len(ws) - 1


def texto12(c):
    if c.startswith(PREF12):
        return c.split(PREF12, 2)[2]
    return c


def de_clave12(c):
    _, o, t = c.split(PREF12, 2)
    return t, int(o)


# ------------------------------------------------------------------------------------------------ vista
def render(F, body, paso, caja, escala=4, fondo=(28, 32, 48)):
    from PIL import Image
    toks, i = [], 0
    while i < len(body):
        b = body[i]
        if b == 0:
            break
        if 0x81 <= b <= 0x9F or 0xE0 <= b <= 0xFC:
            toks.append(body[i:i + 2].decode('cp932'))
            i += 2
        else:
            toks.append(chr(b))
            i += 1
    W = paso * max(1, len(toks)) + 8
    H = F.sy + 2
    im = Image.new('RGB', (W, H), fondo)
    px = im.load()
    for k, ch in enumerate(toks):
        gi = F.gi(ord(ch))
        if gi is None:
            continue
        left, _, adv = F.metrics[gi]
        x0 = 4 + k * paso + int((caja - adv) / 2) + left
        for y, row in enumerate(F.bitmap(gi)):
            for x, v in enumerate(row):
                if v and 0 <= x0 + x < W:
                    a = v / 15
                    px[x0 + x, y + 1] = tuple(int(fondo[j] * (1 - a) + 255 * a) for j in range(3))
    for k in range(len(toks) + 1):                 # marcas de la rejilla del paso
        px[4 + k * paso - 1 if k else 3, H - 1] = (200, 60, 60)
    return im.resize((W * escala, H * escala), Image.NEAREST)


def hoja(filas, ruta):
    from PIL import Image, ImageDraw
    alto = sum(im.height + 30 for _, im in filas) + 10
    ancho = max(im.width for _, im in filas) + 20
    out = Image.new('RGB', (max(ancho, 600), alto), (16, 16, 24))
    d = ImageDraw.Draw(out)
    y = 5
    for rotulo, im in filas:
        d.text((10, y), rotulo, fill=(230, 230, 230))
        out.paste(im, (10, y + 16))
        y += im.height + 30
    out.save(ruta)


# ------------------------------------------------------------------------------------------------ main
def main():
    sys.stdout.reconfigure(encoding='utf-8')
    reg = json.loads(REGISTRO.read_text(encoding='utf-8'))
    get = K.comun88.abrir(ARCHIVE)
    F, antes_f, tmp = cargar(get, reg)
    Dz = D.Diseno(reg, F)
    C12 = Compacta12(Dz, F, reg)
    cro = bytearray(CRO_BASE.read_bytes())
    cro_jp = CRO_JP.read_bytes()
    refs = Refs(cro_jp)
    informe = dict(issue=77, base=str(CAND.relative_to(ROOT)), cro_base_sha256=sha(bytes(cro)),
                   archive_base_sha256=None, runtime_verified=False, cro={}, no_caben={})

    # ---- 1. menú de campo (FONT12) -------------------------------------------------------------------
    elegidos = {}
    for off, jp, alternativas in LISTA:
        jb = jp.encode('cp932')
        assert cro_jp[off:off + len(jb) + 1] == jb + b'\0', hex(off)
        dentro = [hex(o) for o in range(off + 1, off + len(jb) + 1) if refs.a(o)]
        assert not dentro, (hex(off), dentro)
        n_max = len(jp)
        for t in alternativas:
            coste, sel = C12.partir(t, n_max)
            if coste < INF:
                elegidos[off] = (t, sel)
                break
            informe['no_caben'][t] = dict(offset=hex(off), japones=jp, casillas_max=n_max, fuente='FONT12 paso 15',
                                          ancho_minimo_px=C12.minimo(t), disponible_px=15 * n_max,
                                          motivo='ninguna partición en casillas de <= 15 px de tinta (1-2 px entre letras) cabe en las casillas del japonés')
        assert off in elegidos, t

    # ---- 2. caja Pasión/Amistad (FONT8) ---------------------------------------------------------------
    def margen_izq(o, prev, k):
        # alineado a la izquierda: la primera tinta empieza en la columna 0-1 del lápiz (cada px de más cuesta)
        return 0.0 if o is None else (INF if o > 4 else 0.6 * max(0, o - 1))

    def hueco8(g, palabra):
        # compacto: 2 px entre casillas como dentro de un par; 3 px ya se penaliza (el usuario los ve sueltos)
        if g < M8.G_MIN:
            return INF
        return {2: 0.0, 3: 1.5, 4: 3.5, 5: 6.0}.get(g, 6.0 + 3.0 * (g - 5))

    Dz.coste_def = 0.8
    elegidos8 = {}
    for off, jp, alternativas in CAJA:
        jb = jp.encode('cp932')
        assert cro_jp[off:off + len(jb) + 1] == jb + b'\0', hex(off)
        dentro = [hex(o) for o in range(off + 1, off + len(jb) + 1) if refs.a(o)]
        assert not dentro, (hex(off), dentro)
        for t in alternativas:
            coste, sel = M8.particion(t, Dz.opciones('rotulo', t), 3, margen_izq, len(jp), coste=hueco8)
            if coste < INF:
                elegidos8[off] = (t, list(sel))
                break
            ws = [Dz.L8.nativa(ch)[1] for ch in t]
            informe['no_caben'][t] = dict(offset=hex(off), japones=jp, casillas_max=len(jp), fuente='FONT8 paso 10',
                                          ancho_minimo_px=sum(ws) + len(ws) - 1, disponible_px=10 * len(jp),
                                          motivo='cada casilla de FONT8 admite como mucho 11 columnas de núcleo '
                                                 '(«as», «Pa», «ón» miden 12-13): hacen falta 5 casillas')
        assert off in elegidos8, t

    # ---- 3/4. nombres completos (+32) y registro 0 de item.dat ------------------------------------------
    N3 = K.comun88.modulo('v03_nombres_v20', V03 / 'nombres/apply.py')
    K3 = N3.K
    ujp = K.comun88.abrir(K3.JP)(UNIT)
    ub = bytearray(get(UNIT))
    Nn = (K3.NDS / 'logic/sp/unitbase.dat').read_bytes()
    J = [ujp[REC + i * REC:REC * 2 + i * REC] for i in range(NREG)]
    Dn = [Nn[REC + i * REC:REC * 2 + i * REC] for i in range(NREG)]
    empar, _ = N3.emparejar(J, Dn)

    def solo_existentes(campo, texto):
        base = Dz.opciones(campo, texto)
        return lambda t: [x for x in base(t) if x[4] == 0.0]

    nombres, saltados = [], collections.Counter()
    for i in range(NREG):
        r = J[i]
        if bytes(ub[REC + i * REC + 32:REC + i * REC + 64]) != r[32:64]:
            saltados['+32 ya cambiado en la base'] += 1
            continue
        if 'ダミー' in r[:48].decode('cp932', 'replace') or not r[32:64].strip(b'\0'):
            saltados['ficticio o vacío'] += 1
            continue
        if i not in empar:
            saltados['sin pareja NDS'] += 1
            continue
        full = K3.dec_nds(Dn[empar[i]][:32])
        if not full or '未定' in full:
            saltados['NDS sin nombre completo'] += 1
            continue
        full = full.strip()
        coste, sel = M8.particion(full, solo_existentes('nombre', full), 3, Dz.margen_nombre, 15)
        if coste == INF:
            saltados['no cabe en 15 casillas'] += 1
            continue
        nombres.append((i, full, list(sel)))

    item = bytearray(get(ITEM))
    assert item[:20] == 'なし'.encode('cp932') + bytes(16), item[:20]
    eu = K.comun88.abrir(EU)('es/inazuma1/data_iz/logic/item.dat')
    import eu08
    vacio = eu08.dec(eu[:20].split(b'\0')[0])
    assert vacio == 'Vacío', vacio
    c_it, sel_it = M8.particion(vacio, solo_existentes('nombre', vacio), 3, Dz.margen_nombre, 9)
    assert c_it < INF

    # ---- códigos nuevos ------------------------------------------------------------------------------
    assert not any(e.get('clave', '').startswith(PREF12) for e in reg['bigramas'])
    nuevas12 = sorted({c for t, sel in elegidos.values() for c, _, _ in sel if c.startswith(PREF12)})
    nuevas8 = sorted({c for t, sel in elegidos8.values() for c, o, w in sel
                      if c != ' ' and len(c) > 1 and c not in Dz.por_clave})
    usados = {e['sjis'] for e in reg['bigramas']}
    inv = K.inversos(F)
    # depósito: mismo criterio que la v08 (pool_codigos: escaneos v88/v89/v90/v08, sin aparición en texto ni
    # literal en code.bin/CRO), recalculado contra el registro actual (el deposito_restante.json de la v08
    # quedó consumido por sus descripciones)
    A08 = K.comun88.modulo('v08_apply_v20', V08 / 'apply.py')
    pool = [c for c, _ in A08.pool_codigos(reg, F)
            if c not in usados and all(A89.unico(F[f], inv[f], c) for f in K.FUENTES)]
    origen_pool = {c: 'v08_pool' for c in pool}
    for c in falsos_literales(usados):
        if c not in origen_pool and all(A89.unico(F[f], inv[f], c) for f in K.FUENTES):
            pool.append(c)
            origen_pool[c] = 'v20_literal_falso_cro'
    faltan = nuevas12 + nuevas8
    assert len(faltan) <= len(pool), (len(faltan), len(pool))
    asign = dict(zip(faltan, pool))
    print([repr(c) for c in faltan]); print("casillas nuevas FONT12", len(nuevas12), 'FONT8', len(nuevas8), 'depósito', len(pool))

    escritor = {F12: A88.V75G.Celdas(F[F12]), F8: A88.V75G.Celdas(F[F8]), F12T: A88.CeldasLA4(F[F12T])}

    def pintar(f, gi, px):
        Fu = F[f]
        for y in range(Fu.sy):
            for x in range(Fu.sx):
                escritor[f].escribir(gi, x, y, 0)
        for (x, y), v in px.items():
            assert 0 <= x < Fu.sx - 1 and 0 <= y < Fu.sy - 1, (f, gi, x, y)
            escritor[f].escribir(gi, 1 + x, 1 + y, v)

    def sha1(px):
        return hashlib.sha1(json.dumps(sorted(px.items())).encode()).hexdigest()

    registro = [dict(e) for e in reg['bigramas']]
    añadidas = []
    for c in faltan:
        s = asign[c]
        ch = bytes.fromhex(s).decode('cp932')
        cp = ord(ch)
        e = dict(sjis=s, unicode=f'U+{cp:04X}', kanji=ch, origen=origen_pool[s], clave=c, fuentes={},
                 campos=['cro_ie2_v20'])
        if c in nuevas12:
            t, Dd = de_clave12(c)
            px, ancho, _, _ = C12.maqueta(t)
            Fu = F[F12]
            gi = Fu.gi(cp)
            viejo = list(Fu.metrics[gi])
            adv = Dd + ancho + 1
            left = Dd - int((15 - adv) / 2)
            pintar(F12, gi, px)
            Fu.set_metrics(gi, left, ancho, adv)
            leido = {(x, y): v for y, row in enumerate(Fu.bitmap(gi)) for x, v in enumerate(row) if v}
            assert leido == px, c
            assert int((15 - adv) / 2) + left == Dd
            e.update(par=t, variante=f'v20 casilla compacta FONT12 del menú (tinta desde la columna {Dd})')
            e['fuentes'][F12] = dict(glifo=gi, cwdh_antes=viejo, cwdh=[left, ancho, adv], columna=Dd,
                                     pixeles_sha1=sha1(px), maqueta='v20 compacta paso 15 (columna libre)')
            e.update(glifo=gi, cwdh=[left, ancho, adv], pixeles_sha1=sha1(px))
        else:
            t, o = D.de_clave(c)
            Fu = F[F8]
            gi = Fu.gi(cp)
            px, c0, left, width, adv = Dz.L8.dibujo(t, o, D.BMAX['rotulo'])
            viejo = list(Fu.metrics[gi])
            pintar(F8, gi, px)
            Fu.set_metrics(gi, left, width, adv)
            leido = {(x, y): v for y, row in enumerate(Fu.bitmap(gi)) for x, v in enumerate(row) if v}
            assert leido == px, c
            e.update(par=t, variante=f'v20 casilla compacta FONT8 (núcleo en la columna {o})')
            e['fuentes'][F8] = dict(glifo=gi, cwdh_antes=viejo, cwdh=[left, width, adv], nucleo_px=Dz.L8.trozo(t)['w'],
                                    columna=o, pixeles_sha1=sha1(px), maqueta='v08 nombres compactos (paso 10)')
            # FONT12 por coherencia del registro (como la v08)
            Fu = F[F12]
            gi = Fu.gi(cp)
            m = Dz.f12(t)
            viejo = list(Fu.metrics[gi])
            if m == 'nativa':
                gn = Fu.gi(A88.codepoint(t))
                px = {(x, y): v for y, row in enumerate(Fu.bitmap(gn)) for x, v in enumerate(row) if v}
                left, width, adv = Fu.metrics[gn]
                info = dict(maqueta='v08 copia de la letra nativa')
            else:
                width, Dd = m['ancho'], m['D']
                adv = Dd + width + 1
                left = Dd - int((15 - adv) / 2)
                px = m['px']
                info = dict(maqueta='v89', columna=Dd, solido=[m['S0'], m['S1']], hueco_interno=m['g'])
            pintar(F12, gi, px)
            Fu.set_metrics(gi, left, width, adv)
            e['fuentes'][F12] = dict(glifo=gi, cwdh_antes=viejo, cwdh=[left, width, adv], pixeles_sha1=sha1(px), **info)
            e.update(glifo=gi, cwdh=[left, width, adv], pixeles_sha1=sha1(px))
        registro.append(e)
        añadidas.append(e)

    por_clave = {A89.clave_de(e): e for e in registro}

    def vista_casilla(c):
        if c.startswith(PREF12):
            t, d = de_clave12(c)
            return f'{t}@{d} (nueva)'
        if c in por_clave:
            return por_clave[c]['par']
        return c

    def cod(c):
        if c == ' ':
            return ESPACIO
        if c in asign:
            return bytes.fromhex(asign[c])
        if c in por_clave:
            return bytes.fromhex(por_clave[c]['sjis'])
        assert len(c) == 1, c
        return V79.codificar(c)

    # ---- CRO ---------------------------------------------------------------------------------------------
    cro_v18 = bytes(cro)
    vistas = []
    for off, jp, _ in LISTA + CAJA:
        jb = jp.encode('cp932')
        t, sel = elegidos.get(off) or elegidos8.get(off)
        body = b''.join(cod(c) for c, _, _ in sel)
        assert len(body) <= len(jb) and len(sel) <= len(jp)
        nuevo = body + ESPACIO * ((len(jb) - len(body)) // 2)
        assert len(nuevo) == len(jb)            # listas strlen+1: misma longitud que el japonés
        antes = cro_v18[off:off + len(jb)]
        cro[off:off + len(jb)] = nuevo
        assert cro[off + len(jb)] == 0
        es_lista = off in elegidos
        informe['cro'][hex(off)] = dict(japones=jp, texto=t, casillas=[vista_casilla(c) for c, _, _ in sel],
                                        fuente='FONT12' if es_lista else 'FONT8', bytes=len(jb),
                                        antes_hex=antes.hex(), despues_hex=nuevo.hex(),
                                        referencias_dentro=0)
        vistas.append((off, jp, t, es_lista, antes, nuevo))
    # espejo de «セーブ» que 0xbd2a8 compara con la entrada de guardar: mismos bytes
    g_off = LISTA[-1][0]
    g_len = len(LISTA[-1][1].encode('cp932'))
    assert cro_jp[ESPEJO_GUARDAR:ESPEJO_GUARDAR + g_len + 1] == cro_jp[g_off:g_off + g_len + 1]
    cro[ESPEJO_GUARDAR:ESPEJO_GUARDAR + g_len] = cro[g_off:g_off + g_len]
    informe['cro'][hex(ESPEJO_GUARDAR)] = dict(igual_a=hex(g_off), motivo='strcmp en 0xbd2a8 (entrada de guardar)')
    cambiados = [i for i in range(len(cro)) if cro[i] != cro_v18[i]]
    permitidos = set()
    for off, jp, _ in LISTA + CAJA:
        permitidos |= set(range(off, off + len(jp.encode('cp932'))))
    permitidos |= set(range(ESPEJO_GUARDAR, ESPEJO_GUARDAR + g_len))
    assert set(cambiados) <= permitidos
    out_cro = HERE / 'romfs/cro/ina_main2.cro'
    out_cro.parent.mkdir(parents=True, exist_ok=True)
    out_cro.write_bytes(bytes(cro))

    # ---- unitbase +32 ------------------------------------------------------------------------------------
    ub0 = bytes(ub)
    muestras = []
    for i, full, sel in nombres:
        body = b''.join(cod(c) for c, _, _ in sel)
        assert len(body) <= 31
        ub[REC + i * REC + 32:REC + i * REC + 64] = body + bytes(32 - len(body))
        if len(muestras) < 40 or i in (0, 1, 2, 3):
            muestras.append(dict(registro=i, japones=J[i][32:64].split(b'\0')[0].decode('cp932', 'replace'),
                                 nds=full, casillas=[Dz.texto_de(c) for c, _, _ in sel], bytes=len(body)))
    for i in range(NREG):     # solo cambia +32..+63
        a, b = ub0[REC + i * REC:REC * 2 + i * REC], bytes(ub[REC + i * REC:REC * 2 + i * REC])
        assert a[:32] == b[:32] and a[64:] == b[64:], i
    assert ub0[:REC] == bytes(ub[:REC])
    body_it = b''.join(cod(c) for c, _, _ in sel_it)
    assert len(body_it) <= 18
    item[:20] = body_it + bytes(20 - len(body_it))

    extra = HERE / 'extra'
    if extra.exists():
        shutil.rmtree(extra)
    for ruta, datos in ((UNIT, bytes(ub)), (ITEM, bytes(item))):
        p = extra / ruta
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(datos)
    salida_f = {}
    for f in K.FUENTES:
        d = F[f].data()
        assert len(d) == len(antes_f[f])
        if d != antes_f[f]:
            p = extra / f
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(d)
            salida_f[f] = sha(d)

    # ---- registro e informe ----------------------------------------------------------------------------
    reg_out = dict(reg)
    reg_out['version'] = 'ie2_v20_textos'
    reg_out['bigramas'] = registro
    reg_out['fuentes_dibujadas'] = {f: sha(F[f].data()) for f in K.FUENTES}
    reg_out['pares_ie2_v20'] = [e['clave'] for e in añadidas]
    reg_out['descripcion'] = reg['descripcion'] + (
        ' IE2 v20 (work/ie2/shared/capas/historial/nombres/v20_textos): casillas compactas del menú de campo (FONT12, clave U+E00A '
        'columna U+E005 texto, tinta desde la columna indicada, paso 15) y de la caja Pasión/Amistad (FONT8, '
        'clave v08); códigos del depósito de la v08, añadidos al final.')
    (HERE / 'registro.json').write_text(json.dumps(reg_out, ensure_ascii=False, indent=1), encoding='utf-8')
    json.dump([c for c in pool[len(faltan):]], open(HERE / 'deposito_restante.json', 'w'))

    informe.update(
        archive_base_sha256=None,
        fuentes_base={f: sha(antes_f[f]) for f in K.FUENTES}, fuentes_salida=salida_f,
        casillas_nuevas=[dict(clave=e['clave'], sjis=e['sjis'], par=e['par'], fuentes=sorted(e['fuentes']))
                         for e in añadidas],
        dibujo={'menu_campo': '0xbd1e8 -> 0x121a78, gestor [0x29b28c] = FONT12 (paso 15)',
                'caja_pasion': '0x6a7d0/0x6a8a4 -> 0xf4320 -> 0x121a78, gestor [0x29b284] = FONT8 (paso 10)',
                'nota': 'los gestores de fuente 0x29b284/88/8c/90 = FONT8/RUBI8/FONT12/FONT12T '
                        '(work/ie1/capas/historial/menus_cro/v90_cro_restantes/explorar.py); el menú de campo NO usa FONT8'},
        unitbase=dict(ruta=UNIT, campo='+32 (32 B)', cambiados=len(nombres), saltados=dict(saltados),
                      casillas_max=max(len(s) for _, _, s in nombres),
                      bytes_max=max(len(b''.join(cod(c) for c, _, _ in s)) for _, _, s in nombres),
                      muestras=muestras),
        item=dict(ruta=ITEM, registro=0, antes='なし', texto=vacio, casillas=[Dz.texto_de(c) for c, _, _ in sel_it],
                  fuente_texto='port europeo oficial IE1 3DS es/inazuma1/data_iz/logic/item.dat registro 0 '
                               '(la NDS española de IE2 conserva «なし» en ese registro)'),
        salida=dict(cro=sha(bytes(cro)), unitbase=sha(bytes(ub)), item=sha(bytes(item))))

    # ---- vistas previas x4 -------------------------------------------------------------------------------
    prev = HERE / 'previews'
    if prev.exists():
        shutil.rmtree(prev)
    prev.mkdir()
    base_F = {}
    for f in K.FUENTES:
        (tmp / ('base_' + Path(f).name)).write_bytes(antes_f[f])
        base_F[f] = A88.cargar(tmp / ('base_' + Path(f).name))
    filas_menu, filas_caja = [], []
    for off, jp, t, es_lista, antes, nuevo in vistas:
        f, paso, caja = (F12, 15, 15) if es_lista else (F8, 10, 11)
        destino = filas_menu if es_lista else filas_caja
        destino.append((f'{hex(off)} {jp} - japonés', render(base_F[f], jp.encode('cp932'), paso, caja)))
        destino.append((f'{hex(off)} v18', render(base_F[f], antes, paso, caja)))
        destino.append((f'{hex(off)} v20 «{t}»', render(F[f], nuevo, paso, caja)))
    hoja(filas_menu, prev / 'menu_campo_FONT12_x4.png')
    hoja(filas_caja, prev / 'caja_pasion_amistad_FONT8_x4.png')
    filas = []
    for i, full, sel in nombres[:12]:
        body = b''.join(cod(c) for c, _, _ in sel)
        filas.append((f'{i} {full} FONT12', render(F[F12], body, 15, 15)))
        filas.append((f'{i} {full} FONT8', render(F[F8], body, 10, 11)))
    filas.append(('item 0 «Vacío» FONT12', render(F[F12], body_it, 15, 15)))
    hoja(filas, prev / 'nombres_completos_e_item_x4.png')
    informe['previews'] = sorted(p.name for p in prev.glob('*.png'))
    (HERE / 'informe.json').write_text(json.dumps(informe, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps({k: informe[k] for k in ('cro', 'no_caben', 'casillas_nuevas', 'item')}, ensure_ascii=False,
                     indent=1))
    print('unitbase', informe['unitbase']['cambiados'], informe['unitbase']['saltados'],
          informe['unitbase']['casillas_max'], informe['unitbase']['bytes_max'])


if __name__ == '__main__':
    main()
