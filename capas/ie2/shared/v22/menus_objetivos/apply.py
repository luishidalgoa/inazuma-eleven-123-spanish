"""IE2 v22 · menú de campo, submenú de Tácticas, caja Pasión/Amistad y objetivos (issue #77). No construye ni instala.

Base: work/shared/candidatas/probe_ie2_v21 (archive.fa: fuentes de v20/textos y eventos de v18;
romfs/cro/ina_main2.cro = el de v20/textos con los tres parches de ancho de v15, que se comprueban y conservan).
Solo cambia DATOS: literales del CRO, glifos de códigos libres de FONT12/FONT8 y cuerpos de objetivos en eve/mch.

A-C. Literales del CRO (modelo en casillas22.py; colocación x = lápiz + trunc((CAJA - adv)/2) + left):
  - Menú de campo, lista de 6 leída con strlen+1 desde 0xfbf6c (único ADR, 0xfbe50). Se REPARTE el bloque
    0xfbf6c..0xfbfa3 entre las entradas (0xfbfa4 es un literal que carga 0xfbe58: no se toca). Cada entrada
    <= 10 B (lo que ocupa la más larga en japonés, por si el menú copia a búferes de ese tamaño).
    0xbd2a8 compara la entrada con la copia de «セーブ» de 0xbd35c (8 B hasta 0xbd363; 0xbd364 es «？？？？»,
    que se muestra en las entradas bloqueadas). La copia se escribe con los mismos bytes que «Guardar», así
    que la entrada de guardar debe caber en 7 B. «Guardar» necesita 4 casillas (8 B): la G mide 9 px y ni
    «Gu» ni «uar» caben en 15 px, así que no hay reparto en 3 casillas; se usa «Guar.» (3 casillas).
  - Submenú de Tácticas (しあい/バトル/つうしん), lista strlen+1 desde 0xfc2bc (único ADR): bloque
    0xfc2bc..0xfc2d3 (0xfc2d4 lo referencia otro ADR). Cada entrada <= 8 B.
  - Caja Pasión/Amistad (FONT8, paso 10): 0x6ab6c (ADR 0x6a7d0) puede crecer hasta 0x6ab77 (0x6ab78 es un
    puntero con relocalización que carga 0x6a7b8); 0x6ab80 (ADR 0x6a8a4) hasta 0x6ab8b.
  Antes de escribir se comprueba que ningún byte del hueco es destino de ADR, de LDR/VLDR con pc ni de una
  relocalización, salvo el inicio de cada literal.
  Casillas: letras nativas, códigos del registro ya dibujados, o códigos NUEVOS de los libres (los 11 que dejó
  la v20 y los 3 que la v20 dibujó solo para estos menús, que se recuperan). Huecos de tinta 1-2 px (FONT12,
  sin tocarse ni con el antialias) o 1-3 px de núcleo (FONT8, 2 preferido), primera tinta en la columna 0-1.

D. Objetivos (0x2017/0x2018/0x201c/0x2023 arg 3; caja de 0x8a0a8: el texto está en objeto+0x262 y el motor
  pone un NUL en objeto+0x28a antes de dibujar => se ven 40 BYTES, no casillas). Con el registro actual cada
  casilla ocupa 2 B, así que el límite es 20 casillas. Se reparten de nuevo con el modelo de ritmo de v89
  (ritmo.py, trozos del registro medidos en la FONT12 actual) con como mucho 20 casillas; si el texto no cabe,
  se usa el primer resumen de resumenes.py que cabe (excepción autorizada solo para objetivos).

Salida: romfs/cro/ina_main2.cro, extra/font/FONT12.bcfnt y FONT8.bcfnt, ie2/eve/*.ssd, ie2/mch/*.ssd,
registro.json, informe.json, previews/*_x4.png.
Uso: python -X utf8 work/ie2/shared/capas/v22/menus_objetivos/apply.py   (después validate.py)
"""
from __future__ import annotations

import collections
import hashlib
import itertools
import json
import shutil
import struct
import sys
import tempfile
from functools import lru_cache
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[5]
V08 = ROOT / 'work/ie2/shared/capas/v08/nombres_compactos'
V20 = ROOT / 'work/ie2/shared/capas/v20/textos'
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(V08))
sys.path.insert(0, str(ROOT / 'work/ie2/tormenta_de_fuego/capas/v02/dialogo'))
import casillas22 as C  # noqa: E402
import comun08 as K  # noqa: E402
import comun_ie2 as MI  # noqa: E402
from resumenes import RESUMEN  # noqa: E402
PREFERIDOS = set()  # objetivos a mostrar primero en la muestra (texto del juego: no se versiona)

A88, A89, R = K.A88, K.A89, K.R
F12, F8, F12T = K.F12, K.F8, K.F12T

CAND = ROOT / 'work/shared/candidatas/probe_ie2_v21'
ARCHIVE = CAND / 'archive.fa'
CRO_BASE = CAND / 'romfs/cro/ina_main2.cro'
CRO_JP = ROOT / 'work/shared/base_3ds/romfs/cro/ina_main2.cro'
REGISTRO = V20 / 'registro.json'
DEPOSITO = V20 / 'deposito_restante.json'
ANCHO = {0x66a24: 0xE3A01E1A, 0x4cabc: 0xE3A02E1A, 0x4d6a0: 0xE3A02D07}   # v15, se conservan
RECUPERAR = ['8BA2', '8F58', '98C6']     # códigos que la v20 dibujó solo para estos menús
OPS_OBJ = (0x2017, 0x2018, 0x201C, 0x2023)
LIMITE_OBJ = 40                          # bytes visibles (NUL forzado en objeto+0x28a, 0x8a104)
ESPACIO = '　'.encode('cp932')

# bloque: (inicio, último byte utilizable, máx. por entrada, fuente, [(japonés, [alternativas])])
MENU = (0xfbf6c, 0xfbfa3, 10, F12, [
    ('なかま', ['Equipo']), ('もちもの', ['Inventario']), ('せんじゅつ', ['Tácticas']),
    ('じょうほう', ['Datos']), ('システム', ['Sistema']), ('セーブ', ['Guardar', 'Guar.'])])
SUB = (0xfc2bc, 0xfc2d3, 8, F12, [
    ('しあい', ['Partido', 'Part.']), ('バトル', ['Duelo']), ('つうしん', ['Conexión', 'Conex.'])])
PASION = (0x6ab6c, 0x6ab77, 10, F8, [('ねっけつ', ['Pasión'])])
AMISTAD = (0x6ab80, 0x6ab8b, 10, F8, [('ゆうじょう', ['Amistad'])])
BLOQUES = {'menu_campo': MENU, 'submenu_tacticas': SUB, 'caja_pasion': PASION, 'caja_amistad': AMISTAD}
ESPEJO, ESPEJO_FIN = 0xbd35c, 0xbd363     # copia de «セーブ» (strcmp en 0xbd2a8); 0xbd364 = «？？？？»
ASCII_FINAL = set()     # probado en el modelo: ni con una «r» ASCII de 1 B cabe «Guardar» en 7 B (ver informe)


def sha(b):
    return hashlib.sha256(b).hexdigest()


# ------------------------------------------------------------------------------------------------ CRO
class Cro:
    """Destinos de ADR, LDR/VLDR con pc y relocalizaciones de un CRO."""

    def __init__(self, d):
        u = lambda o: struct.unpack_from('<I', d, o)[0]  # noqa: E731
        segs = [struct.unpack_from('<III', d, u(0xC8) + 12 * i) for i in range(u(0xCC))]
        cs, ce = segs[0][0], segs[0][0] + segs[0][1]
        self.reloc = set()
        for i in range(u(0x12C)):
            so = struct.unpack_from('<I', d, u(0x128) + 12 * i)[0]
            self.reloc.add(segs[so & 0xf][0] + (so >> 4))
        self.adr, self.ldr = collections.defaultdict(list), collections.defaultdict(list)

        def rot(w):
            r = ((w >> 8) & 0xf) * 2
            i = w & 0xff
            return ((i >> r) | (i << (32 - r))) & 0xffffffff
        for o in range(cs, ce, 4):
            w = u(o)
            if w >> 28 == 0xF:
                continue
            if (w & 0x0FEF0000) == 0x028F0000:
                self.adr[o + 8 + rot(w)].append(o)
            elif (w & 0x0FEF0000) == 0x024F0000:
                self.adr[o + 8 - rot(w)].append(o)
            elif (w & 0x0F7F0000) == 0x051F0000:                      # ldr/ldrb rX, [pc, #imm]
                imm = w & 0xfff
                self.ldr[o + 8 + (imm if w & (1 << 23) else -imm)].append(o)
            elif (w & 0x0E5F0090) == 0x004F0090 and (w & 0x60):       # ldrh/ldrsb/ldrsh/ldrd [pc, #imm]
                imm = ((w >> 4) & 0xf0) | (w & 0xf)
                self.ldr[o + 8 + (imm if w & (1 << 23) else -imm)].append(o)
            elif (w & 0x0F3F0E00) == 0x0D1F0A00:                      # vldr [pc, #imm]
                imm = (w & 0xff) * 4
                self.ldr[o + 8 + (imm if w & (1 << 23) else -imm)].append(o)

    def ocupados(self, lo, hi):
        """Bytes de [lo, hi] que son destino de algo (ADR/LDR de 1-8 B, relocalización de 4 B)."""
        out = {}
        for t, v in self.adr.items():
            if lo <= t <= hi:
                out[t] = ('adr', [hex(x) for x in v])
        for t, v in self.ldr.items():
            for k in range(4):
                if lo <= t + k <= hi:
                    out[t + k] = ('ldr', [hex(x) for x in v])
        for t in self.reloc:
            for k in range(4):
                if lo <= t + k <= hi:
                    out[t + k] = ('reloc', hex(t))
        return out


# ------------------------------------------------------------------------------------------------ fuentes
def cargar_fuentes(get, reg):
    tmp = Path(tempfile.mkdtemp(prefix='ie2_v22_'))
    F, antes = {}, {}
    for f in K.FUENTES:
        d = get(f)
        assert sha(d) == reg['fuentes_dibujadas'][f], f'{f}: la fuente de la v21 no es la del registro v20'
        antes[f] = d
        (tmp / Path(f).name).write_bytes(d)
        F[f] = A88.cargar(tmp / Path(f).name)
    return F, antes, tmp


def modelos(F):
    c12 = {1: 0.0, 2: 0.0, 3: 0.8, 4: 3.0, 5: 6.0}
    c8 = {1: 0.6, 2: 0.0, 3: 0.3, 4: 2.5, 5: 5.0}
    m12 = C.Modelo(F[F12], 'FONT12', 15, 15, 1, 15, set(c12), c12.__getitem__, A88.codepoint, {1, 2, 3})
    m8 = C.Modelo(F[F8], 'FONT8', 10, 11, 8, 11, set(c8), c8.__getitem__, A88.codepoint, {1, 2, 3})
    return {F12: m12, F8: m8}


def escribir_glifo(F, f, gi, px, D, modelo):
    """Dibuja px (tinta relativa: x = 0 en la primera columna con tinta >= umbral) con esa tinta en la columna
    D del lápiz. Devuelve (cwdh antes, cwdh nuevo)."""
    Fu = F[f]
    escritor = A88.V75G.Celdas(Fu)                     # coordenadas de la celda de la hoja (con margen de 1 px)
    xs = [x for x, _ in px]
    x_min = min(xs)                                    # columna 0 del mapa de bits (bitmap() no incluye el margen)
    for y in range(Fu.sy):
        for x in range(Fu.sx):
            escritor.escribir(gi, x, y, 0)
    for (x, y), v in px.items():
        bx = x - x_min
        assert 0 <= bx <= Fu.sx - 2 and 0 <= y <= Fu.sy - 2, (f, gi, x, y)
        escritor.escribir(gi, 1 + bx, 1 + y, v)
    viejo = list(Fu.metrics[gi])
    ancho = max(xs) - x_min + 1
    adv = min(modelo.caja, max(1, D + ancho))
    left = D + x_min - int((modelo.caja - adv) / 2)
    assert -128 <= left <= 127
    Fu.set_metrics(gi, left, ancho, adv)
    p = modelo.perfil(modelo.columnas(gi))
    assert p is not None and p[0] == D, (f, gi, D, p)
    return viejo, [left, ancho, adv]


# ------------------------------------------------------------------------------------------------ menús
def opciones_registro(reg, F, f, excluir):
    por_texto = collections.defaultdict(list)
    for e in reg:
        if f not in e['fuentes'] or e['sjis'] in excluir:
            continue
        gi = F[f].gi(int(e['unicode'][2:], 16))
        if gi is not None:
            por_texto[e['par']].append((A89.clave_de(e), gi, e['sjis']))
    return lambda t: por_texto.get(t, [])


def resolver_bloques(Mo, reg, F, excluir, n_codigos):
    """Resuelve los cuatro bloques con el menor lambda (coste de un código nuevo) que quepa en el depósito."""
    ops = {f: opciones_registro(reg, F, f, excluir) for f in (F12, F8)}
    asc = lambda ch: F[F12].gi(ord(ch)) if ord(ch) < 0x80 else None  # noqa: E731
    for lam in (0.4, 0.8, 1.2, 1.6, 2.0, 2.5, 3.0, 4.0, 6.0, 12.0):
        elegido, no_caben = {}, {}
        for nombre, (ini, fin, max_e, f, entradas) in BLOQUES.items():
            M = Mo[f]
            total = fin - ini + 1
            cand = []
            for jp, alternativas in entradas:
                opc = []
                for alt in alternativas:
                    sols = C.resolver(M, alt, ops[f], lam, max_bytes=max_e,
                                      ascii_final=asc if (nombre, alt) in ASCII_FINAL else None)
                    if nombre == 'menu_campo' and jp == 'セーブ':
                        sols = {b: s for b, s in sols.items() if b <= ESPEJO_FIN - ESPEJO}
                    pareto, mejor_c = [], C.INF
                    for b in sorted(sols):
                        if sols[b].coste < mejor_c:
                            mejor_c = sols[b].coste
                            pareto.append((alternativas.index(alt), sols[b].coste, b, alt, sols[b]))
                    opc += pareto
                    if not sols:
                        no_caben.setdefault(nombre, []).append(alt)
                cand.append(opc)
            mejor = None
            for combo in itertools.product(*cand):
                if sum(c[2] + 1 for c in combo) > total:
                    continue
                clave = (sum(c[0] for c in combo), sum(c[1] for c in combo))
                if mejor is None or clave < mejor[0]:
                    mejor = (clave, combo)
            assert mejor, nombre
            elegido[nombre] = [(jp, c[3], c[4]) for (jp, _), c in zip(entradas, mejor[1])]
        nuevas = {(f, c['t'], c['g'], c['D'])
                  for nombre, (_, _, _, f, _) in BLOQUES.items()
                  for _, _, s in elegido[nombre] for c in s.casillas if c['tipo'] == 'nueva'}
        if len(nuevas) <= n_codigos:
            return lam, elegido, sorted(nuevas), no_caben
    raise SystemExit(f'no caben en el depósito: {len(nuevas)} casillas nuevas > {n_codigos}')


# ------------------------------------------------------------------------------------------------ objetivos
class Ritmo:
    """Partición v89 (ritmo.py) de un objetivo con como mucho N casillas, con los trozos del registro."""

    def __init__(self, F, reg):
        self.mq = A89.Maqueta(F[F12], A88.codepoint)
        self.adm = set()
        for e in reg:
            if F12 in e['fuentes']:
                c = A89.clave_de(e)
                self.mq.fijos[c] = A89.medir(F[F12], F[F12].gi(int(e['unicode'][2:], 16)))
                self.adm.add(c)

    def partir(self, tx, nmax):
        n, mq, adm = len(tx), self.mq, self.adm

        def es_pal(i):
            return tx[i - 1] == ' ' or tx[i] == ' '

        @lru_cache(None)
        def f(i, s1, k):
            if i >= n:
                return 0.0, ()
            if k >= nmax:
                return R.INF, ()
            mejor = (R.INF, ())
            ops = []
            for L in range(1, 5):
                if i + L > n:
                    break
                ops.append((L, tx[i:i + L]))
                if L == 1 and tx[i] != ' ':
                    ops += [(1, R.IZQ + tx[i]), (1, R.DER + tx[i])]
            for L, c in ops:
                if L == 1 and not R.variante(c):
                    ext = mq.nativa(c) if c != ' ' else None
                    if c != ' ' and ext is None:
                        continue
                else:
                    if c not in adm or mq.trozo(c) is None:
                        continue
                    ext = mq.extremos(c)
                if ext is None:
                    nuevo, cst = (None if s1 is None else s1 - R.CELDA), 0.0
                else:
                    cst = 0.0 if s1 is None else R.coste_hueco(R.CELDA + ext[0] - s1 - 1, es_pal(i))
                    nuevo = ext[1]
                if cst == R.INF:
                    continue
                r = f(i + L, nuevo, k + 1)
                tot = cst + r[0] + (0.05 if R.variante(c) else 0.0)
                if tot < mejor[0]:
                    mejor = (tot, (c,) + r[1])
            return mejor
        return f(0, None, 0)

    def huecos(self, cel):
        return R.huecos(list(cel), self.mq)


def calidad(huecos):
    """(huecos dentro de palabra fuera de 1-2 px, huecos entre palabras fuera de 4-8 px, peor hueco interno)."""
    dentro = [g for g, p in huecos if not p]
    entre = [g for g, p in huecos if p]
    return (sum(1 for g in dentro if g not in (1, 2)), sum(1 for g in entre if not 4 <= g <= 8),
            max(dentro) if dentro else 0)


def referencias(data):
    """índice de texto -> {(opcode, posición del argumento)} (lectura de SceneScriptData)."""
    count = struct.unpack_from('<H', data, 12)[0]
    pos, out = 32, collections.defaultdict(set)
    for _ in range(count):
        ident, length, opcode, argc, _ = struct.unpack_from('<HHHBB', data, pos)
        types = 4 * ((argc + 7) // 8)
        for a in range(argc):
            if ((data[pos + 8 + a // 2] >> (4 * (a % 2))) & 15) == 3:
                out[struct.unpack_from('<I', data, pos + 8 + types + 4 * a)[0]].add((opcode, a + 1))
        pos += length
    return out


def objetivos(A, codec, ritmo):
    """Recorre eve/mch: {(pk, eid): {índice: cuerpo nuevo}}, filas del informe."""
    cache, cambios, filas = {}, collections.defaultdict(dict), []
    for pk in ('eve', 'mch'):
        for eid in A.ids(pk):
            data = A.evento(pk, eid)
            try:
                _, ins, recs = MI.S.parse(data)
            except ValueError:
                continue
            refs = None
            for i, r in enumerate(recs):
                op = ins.get(r.instruction)
                if op not in OPS_OBJ or r.argument != 3:
                    continue
                antes = codec.texto(r.body)
                if '¤' in antes or not antes.strip():
                    continue
                if refs is None:
                    refs = referencias(data)
                if refs.get(i, set()) != {(op, 3)}:
                    filas.append(dict(paquete=pk, evento=eid, indice=i, texto=antes, estado='referencias raras'))
                    continue
                if antes not in cache:
                    cache[antes] = elegir_objetivo(antes, codec, ritmo)
                res = cache[antes]
                previo = [c for c in codec.claves(r.body)]
                fila = dict(paquete=pk, evento=eid, indice=i, opcode=hex(op), antes=antes, bytes_antes=len(r.body),
                            calidad_v21=calidad(ritmo.huecos(previo)) if None not in previo else None,
                            **{k: v for k, v in res.items() if k != 'cuerpo'})
                filas.append(fila)
                if res['cuerpo'] != r.body:
                    cambios[(pk, eid)][i] = res['cuerpo']
    return cambios, filas


def elegir_objetivo(texto, codec, ritmo):
    """El texto íntegro si cabe en 20 casillas; si no, el primer resumen que cabe (en orden de preferencia)."""
    base = ritmo.huecos(ritmo.partir(texto, 99)[1])
    for k, t in enumerate([texto] + RESUMEN.get(texto, [])):
        coste, cel = ritmo.partir(t, LIMITE_OBJ // 2)
        if coste == R.INF:
            continue
        q = calidad(ritmo.huecos(cel))
        cuerpo = codec.codificar(list(cel))
        assert len(cuerpo) <= LIMITE_OBJ and codec.texto(cuerpo) == t, (t, cuerpo)
        return dict(texto=t, resumido=k > 0, casillas=list(cel), bytes=len(cuerpo), coste=round(coste, 2),
                    huecos_fuera=q, cuerpo=cuerpo, calidad_sin_limite=calidad(base))
    raise SystemExit(f'objetivo sin versión que quepa en {LIMITE_OBJ} B con ritmo v89: {texto!r}')


# ------------------------------------------------------------------------------------------------ vistas
def render(F, body, paso, caja, escala=4, fondo=(28, 32, 48), marcas=True):
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
    if marcas:
        for k in range(len(toks) + 1):
            px[4 + k * paso - 1 if k else 3, H - 1] = (200, 60, 60)
    return im.resize((W * escala, H * escala), Image.NEAREST)


def hoja(filas, ruta):
    from PIL import Image, ImageDraw, ImageFont
    try:
        fuente = ImageFont.truetype('arial.ttf', 12)
    except OSError:
        fuente = None
    alto = sum(im.height + 30 for _, im in filas) + 10
    ancho = max(im.width for _, im in filas) + 20
    out = Image.new('RGB', (max(ancho, 600), alto), (16, 16, 24))
    d = ImageDraw.Draw(out)
    y = 5
    for rotulo, im in filas:
        d.text((10, y), rotulo, fill=(230, 230, 230), font=fuente)
        out.paste(im, (10, y + 16))
        y += im.height + 30
    out.save(ruta)


# ------------------------------------------------------------------------------------------------ main
def main():
    sys.stdout.reconfigure(encoding='utf-8')
    reg_doc = json.loads(REGISTRO.read_text(encoding='utf-8'))
    reg = reg_doc['bigramas']
    get = K.comun88.abrir(ARCHIVE)
    F, antes_f, tmp = cargar_fuentes(get, reg_doc)
    Mo = modelos(F)
    cro = bytearray(CRO_BASE.read_bytes())
    cro_v21 = bytes(cro)
    cro_jp = CRO_JP.read_bytes()
    for a, w in ANCHO.items():
        assert int.from_bytes(cro[a:a + 4], 'little') == w, hex(a)
    X = Cro(cro_jp)
    informe = dict(issue=77, base=str(CAND.relative_to(ROOT)), cro_base_sha256=sha(cro_v21),
                   runtime_verified=False, bloques={}, no_caben={})

    # ---- depósito de códigos -------------------------------------------------------------------------------
    deposito = json.loads(DEPOSITO.read_text())
    por_sjis = {e['sjis']: e for e in reg}
    for s in RECUPERAR:
        e = por_sjis[s]
        assert e['campos'] == ['cro_ie2_v20'], s
        b = bytes.fromhex(s)
        # solo aparece (alineado a carácter) en los literales de la v20 que esta capa reescribe
        vistos = [i for i in range(len(cro_v21) - 1) if cro_v21[i:i + 2] == b]
        zonas = [(MENU[0], MENU[1]), (ESPEJO, ESPEJO_FIN), (PASION[0], PASION[1]), (AMISTAD[0], AMISTAD[1])]
        fuera = [hex(i) for i in vistos if not any(lo <= i <= hi for lo, hi in zonas) and cro_jp[i:i + 2] != b]
        assert not fuera, (s, fuera)
    pool = deposito + RECUPERAR
    excluir = set(RECUPERAR)

    # ---- huecos libres de cada bloque ------------------------------------------------------------------
    for nombre, (ini, fin, _, _, entradas) in BLOQUES.items():
        occ = X.ocupados(ini, fin)
        assert set(occ) == {ini}, (nombre, occ)
        # el original ocupa [ini, fin_original]; el resto hasta fin son ceros sin uso
        largo_jp = sum(len(jp.encode('cp932')) + 1 for jp, _ in entradas)
        assert cro_jp[ini:ini + largo_jp] == b''.join(jp.encode('cp932') + b'\0' for jp, _ in entradas), nombre
        assert set(cro_jp[ini + largo_jp:fin + 1]) <= {0}, nombre
    occ = X.ocupados(ESPEJO, ESPEJO_FIN)
    assert set(occ) == {ESPEJO}, occ
    assert cro_jp[ESPEJO:ESPEJO_FIN + 1] == 'セーブ'.encode('cp932') + b'\0\0'
    assert X.adr.get(ESPEJO_FIN + 1) and cro_jp[ESPEJO_FIN + 1:ESPEJO_FIN + 10] == '？？？？'.encode('cp932') + b'\0'

    lam, elegido, nuevas, no_caben = resolver_bloques(Mo, reg, F, excluir, len(pool))
    print('lambda', lam, 'casillas nuevas', len(nuevas), 'de', len(pool))
    asign = dict(zip(nuevas, pool))

    # ---- dibujar las casillas nuevas ---------------------------------------------------------------------
    registro = [dict(e) for e in reg if e['sjis'] not in excluir]
    añadidas = []
    for (f, t, g, D), s in asign.items():
        ch = bytes.fromhex(s).decode('cp932')
        gi = F[f].gi(ord(ch))
        px, w = Mo[f].nueva(t, g)
        viejo, cwdh = escribir_glifo(F, f, gi, px, D, Mo[f])
        e = dict(sjis=s, unicode=f'U+{ord(ch):04X}', kanji=ch, par=t,
                 clave=f'{Mo[f].nombre}{D:+d}g{g}{t}',
                 origen='v22_recuperado_v20' if s in RECUPERAR else 'v20_deposito',
                 campos=['cro_ie2_v22'], variante=f'v22 casilla {Mo[f].nombre} (tinta desde la columna {D}, '
                                                   f'hueco interno {g})',
                 fuentes={f: dict(glifo=gi, cwdh_antes=viejo, cwdh=cwdh, columna=D, hueco_interno=g,
                                  pixeles_sha1=hashlib.sha1(json.dumps(sorted(px.items())).encode()).hexdigest())},
                 glifo=gi, cwdh=cwdh)
        registro.append(e)
        añadidas.append(e)

    def cod(c):
        if c['tipo'] == 'nueva':
            return bytes.fromhex(asign[(f_act, c['t'], c['g'], c['D'])])
        if c['tipo'] == 'registro':
            return bytes.fromhex(c['sjis'])
        if c['tipo'] == 'ascii':
            return c['t'].encode('ascii')
        return A88.V79.codificar(c['t'])

    # ---- escribir los bloques ----------------------------------------------------------------------------
    cuerpos = {}
    for nombre, (ini, fin, max_e, f, entradas) in BLOQUES.items():
        f_act = f
        M = Mo[f]
        buf = b''
        filas = []
        for jp, texto, s in elegido[nombre]:
            body = b''.join(cod(c) for c in s.casillas)
            assert len(body) <= max_e and b'\0' not in body
            cuerpos[(nombre, jp)] = body
            buf += body + b'\0'
            hs = C.huecos_de(M, s.casillas)
            filas.append(dict(japones=jp, texto=texto, bytes=len(body), bytes_japones=len(jp.encode('cp932')),
                              casillas=[dict(t=c['t'], tipo=c['tipo'], columna=c['s0'],
                                             **({'sjis': asign[(f, c['t'], c['g'], c['D'])]} if c['tipo'] == 'nueva'
                                                else {'sjis': c['sjis']} if c['tipo'] == 'registro' else {}))
                                        for c in s.casillas],
                              huecos=hs, primera_columna=s.casillas[0]['s0'], antes_hex=None,
                              despues_hex=body.hex()))
        assert len(buf) <= fin - ini + 1, nombre
        cro[ini:fin + 1] = buf + bytes(fin - ini + 1 - len(buf))
        informe['bloques'][nombre] = dict(inicio=hex(ini), fin=hex(fin), bytes_usados=len(buf),
                                          bytes_disponibles=fin - ini + 1, fuente=M.nombre, entradas=filas,
                                          antes_hex=cro_v21[ini:fin + 1].hex())
    g = cuerpos[('menu_campo', 'セーブ')]
    assert len(g) <= ESPEJO_FIN - ESPEJO
    cro[ESPEJO:ESPEJO_FIN + 1] = g + bytes(ESPEJO_FIN + 1 - ESPEJO - len(g))
    informe['espejo_guardar'] = dict(offset=hex(ESPEJO), bytes=g.hex(), igual_a='entrada de guardar (セーブ) del menú de campo',
                                     motivo='0xbd2a8: strcmp(entrada, 0xbd35c); si no coincide y la entrada está '
                                            'bloqueada (estado 3) se muestra «？？？？» de 0xbd364')
    informe['no_caben'] = {k: v for k, v in no_caben.items()}
    permitidos = set()
    for ini, fin, *_ in BLOQUES.values():
        permitidos |= set(range(ini, fin + 1))
    permitidos |= set(range(ESPEJO, ESPEJO_FIN + 1))
    cambiados = {i for i in range(len(cro)) if cro[i] != cro_v21[i]}
    assert cambiados <= permitidos
    for a, w in ANCHO.items():
        assert int.from_bytes(cro[a:a + 4], 'little') == w
    out_cro = HERE / 'romfs/cro/ina_main2.cro'
    out_cro.parent.mkdir(parents=True, exist_ok=True)
    out_cro.write_bytes(bytes(cro))

    # ---- objetivos -------------------------------------------------------------------------------------------
    codec = A89.Codec(registro)
    ritmo = Ritmo(F, registro)
    A = MI.Archivo(ARCHIVE)
    cambios, filas_obj = objetivos(A, codec, ritmo)
    salida = {'eve': HERE / 'ie2/eve', 'mch': HERE / 'ie2/mch'}
    for d in salida.values():
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)
    ev_info = []
    for (pk, eid), cmb in sorted(cambios.items()):
        data = A.evento(pk, eid)
        nuevo = MI.S.replace(data, cmb)
        _, ins, recs = MI.S.parse(data)
        _, ins2, recs2 = MI.S.parse(nuevo)
        assert ins2 == ins and len(recs2) == len(recs)
        for j, (a, b) in enumerate(zip(recs, recs2)):
            assert (a.instruction, a.argument) == (b.instruction, b.argument)
            assert (b.body == cmb[j]) if j in cmb else (a.raw == b.raw), (pk, eid, j)
        (salida[pk] / f'{eid}.ssd').write_bytes(nuevo)
        ev_info.append(dict(paquete=pk, evento=eid, registros=sorted(cmb), bytes_antes=len(data), bytes=len(nuevo)))
    unicos = {}
    for fr in filas_obj:
        if 'texto' in fr:
            unicos.setdefault(fr['antes'], fr)
    resumidos = [dict(antes=k, despues=v['texto'], bytes=v['bytes']) for k, v in unicos.items() if v['resumido']]
    q21 = [v['calidad_v21'] for v in unicos.values() if v.get('calidad_v21')]
    q22 = [v['huecos_fuera'] for v in unicos.values()]
    resumen_calidad = dict(
        textos=len(unicos),
        v21_huecos_dentro_de_palabra_fuera_de_1_2=sum(q[0] for q in q21),
        v22_huecos_dentro_de_palabra_fuera_de_1_2=sum(q[0] for q in q22),
        v21_huecos_entre_palabras_fuera_de_4_8=sum(q[1] for q in q21),
        v22_huecos_entre_palabras_fuera_de_4_8=sum(q[1] for q in q22),
        v21_peor_hueco_dentro=max(q[2] for q in q21), v22_peor_hueco_dentro=max(q[2] for q in q22),
        nota='v21 medido con sus casillas sobre la FONT12 actual (la v08 redibujó códigos que usaban)')
    informe['objetivos'] = dict(
        limite=dict(bytes=LIMITE_OBJ, casillas=LIMITE_OBJ // 2,
                    origen='ina_main2.cro 0x8a0a8: texto en objeto+0x262, 0x8a104 strb #0 en objeto+0x28a '
                           '(0x28a - 0x262 = 40 B); el corte es por bytes, cada casilla del registro ocupa 2 B'),
        registros=len([f for f in filas_obj if 'texto' in f]), textos_unicos=len(unicos),
        cambiados=sum(len(v) for v in cambios.values()), eventos=ev_info,
        resumidos=resumidos, calidad=resumen_calidad,
        sin_tocar=[f for f in filas_obj if 'texto' not in f],
        detalle=list(unicos.values()))

    # ---- fuentes y registro ------------------------------------------------------------------------------
    extra = HERE / 'extra'
    if extra.exists():
        shutil.rmtree(extra)
    salida_f = {}
    for f in K.FUENTES:
        d = F[f].data()
        assert len(d) == len(antes_f[f])
        if d != antes_f[f]:
            p = extra / f
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(d)
            salida_f[f] = sha(d)
    reg_out = dict(reg_doc)
    reg_out['version'] = 'ie2_v22_menus_objetivos'
    reg_out['bigramas'] = registro
    reg_out['fuentes_dibujadas'] = {f: sha(F[f].data()) for f in K.FUENTES}
    reg_out['pares_ie2_v22'] = [e['clave'] for e in añadidas]
    reg_out['recuperados_ie2_v22'] = RECUPERAR
    reg_out['descripcion'] = reg_doc['descripcion'] + (
        ' IE2 v22 (work/ie2/shared/capas/v22/menus_objetivos): casillas de los menús de campo/Tácticas (FONT12, '
        'paso 15) y de la caja Pasión/Amistad (FONT8, paso 10) con la tinta en la columna indicada; se recuperan '
        'los 3 códigos de los menús de la v20.')
    (HERE / 'registro.json').write_text(json.dumps(reg_out, ensure_ascii=False, indent=1), encoding='utf-8')
    json.dump(pool[len(nuevas):], open(HERE / 'deposito_restante.json', 'w'))
    informe.update(lam=lam, casillas_nuevas=[dict(sjis=e['sjis'], par=e['par'], clave=e['clave'],
                                                  fuentes=sorted(e['fuentes'])) for e in añadidas],
                   fuentes_base={f: sha(antes_f[f]) for f in K.FUENTES}, fuentes_salida=salida_f,
                   salida=dict(cro=sha(bytes(cro))))

    # ---- vistas previas ×4 ---------------------------------------------------------------------------------
    prev = HERE / 'previews'
    if prev.exists():
        shutil.rmtree(prev)
    prev.mkdir()
    base_F = {}
    for f in K.FUENTES:
        (tmp / ('base_' + Path(f).name)).write_bytes(antes_f[f])
        base_F[f] = A88.cargar(tmp / ('base_' + Path(f).name))

    def filas_bloque(nombre):
        ini, fin, _, f, entradas = BLOQUES[nombre]
        paso, caja = (15, 15) if f == F12 else (10, 11)
        out, o_a, o_d = [], ini, ini
        for jp, texto, s in elegido[nombre]:
            a = cro_v21[o_a:cro_v21.index(b'\0', o_a)]
            d = bytes(cro[o_d:cro.index(b'\0', o_d)])
            out.append((f'{jp} v21: {A89.Codec(reg).texto(a)!r}', render(base_F[f], a, paso, caja)))
            out.append((f'{jp} v22: {texto!r}  huecos {C.huecos_de(Mo[f], s.casillas)}', render(F[f], d, paso, caja)))
            o_a += len(a) + 1
            o_d += len(d) + 1
        return out
    hoja(filas_bloque('menu_campo'), prev / 'menu_campo_FONT12_x4.png')
    hoja(filas_bloque('submenu_tacticas'), prev / 'submenu_tacticas_FONT12_x4.png')
    hoja(filas_bloque('caja_pasion') + filas_bloque('caja_amistad'), prev / 'caja_pasion_amistad_FONT8_x4.png')
    muestra = []
    ya = set()
    orden = sorted(unicos.values(), key=lambda v: (not v['resumido'], -len(v['antes'])))
    for v in orden:
        if v['antes'] in ya or len(muestra) >= 5:
            continue
        if v['antes'] in PREFERIDOS or len(muestra) < 4:
            ya.add(v['antes'])
            muestra.append(v)
    filas = []
    codec21 = A89.Codec(reg)
    for v in muestra:
        b21 = cuerpo_v21(v, A)
        filas.append((f'v21 ({len(b21)} B, el juego muestra 40): {v["antes"]!r}', render(base_F[F12], b21[:LIMITE_OBJ], 15, 15)))
        b22 = codec.codificar(v['casillas'])
        filas.append((f'v22 ({len(b22)} B): {v["texto"]!r}', render(F[F12], b22, 15, 15)))
    hoja(filas, prev / 'objetivos_FONT12_x4.png')
    informe['previews'] = sorted(p.name for p in prev.glob('*.png'))
    (HERE / 'informe.json').write_text(json.dumps(informe, ensure_ascii=False, indent=1, default=str),
                                       encoding='utf-8')
    print(json.dumps({k: [(e['texto'], e['bytes'], [c['t'] for c in e['casillas']], e['huecos'])
                          for e in v['entradas']] for k, v in informe['bloques'].items()}, ensure_ascii=False, indent=1))
    print('no caben:', informe['no_caben'])
    print('objetivos:', informe['objetivos']['registros'], 'registros,', informe['objetivos']['cambiados'],
          'cambiados,', len(resumidos), 'textos resumidos')
    print(json.dumps(resumen_calidad, ensure_ascii=False))


def cuerpo_v21(v, A):
    """Cuerpo original (v21) del primer registro con ese texto."""
    _, _, recs = MI.S.parse(A.evento(v['paquete'], v['evento']))
    return recs[v['indice']].body


if __name__ == '__main__':
    main()
