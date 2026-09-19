"""v88/v89 · Bigramas en todos los nombres, rótulos, objetivos y descripciones de IE1.

Autorización del usuario (2026-09-16): tras validar v87 («Aurelia» = A|ur|el|ia en la pestaña), aplicar
bigramas a todos los nombres y rótulos; ampliación: también a los objetivos (0x402f arg 2/3) y a las
descripciones de la ficha (unitbase.STR), con pares que pueden llevar espacio.

Fuentes y paso real de cada texto (ina_main1.cro; gestores data+188 FONT8 tipo 1, data+196 FONT12 tipo 0,
data+200 FONT12T tipo 2):
  nombres  unitbase +16 pestaña del hablante (FONT8, 10 px), listas (FONT12 proporcional), presentación y
           barras del partido (util_play/PlayerIntro: FONT8 y gestor sin atar -> también FONT12T);
           unitbase +0 ficha (0x128474, FONT12, 15 px).                  -> FONT12 + FONT8 + FONT12T
  rótulos  eve.pkb 0x4037 arg 3 (0x7a54c, FONT8, 10 px, 10 casillas)        -> FONT12 + FONT8
  objetivo eve.pkb 0x402f arg 2/3 (0x7a090, FONT12, 15 px, 128 casillas)    -> FONT12
  descr.   unitbase.STR (0x12929c, FONT12, 15 px; una textura de 14x2 = 28 casillas por línea)  -> FONT12
Un par se usa en un campo solo si cabe en todas las fuentes de ese campo; se dibuja en toda fuente en la
que cabe (FONT12T solo si lo usa un nombre).

Partición «natural+» (v83/bigramas/variante2.py) como programación dinámica: mínimo de casillas; a
igualdad, pares con más aire. Tras cada partición se simula el dibujo al paso real de cada fuente y, si
una casilla con par queda a menos de 1 px de su vecina, ese par se prohíbe en ese texto y se repite.

Registro: el de v87 (13 pares) se conserva tal cual; los pares nuevos se añaden al final con kanji de
nivel 2 de v83/bigramas/huecos.json que el escaneo estricto (escaneo_kanji88.py sobre v87, copia de la
de v85 que ya no pierde coincidencias solapadas) da como
limpios (sin aparición en texto ni en contexto textual en los cuatro juegos). Si faltan códigos, se
quedan los pares que más casillas ahorran.

Rótulos: nombre largo aprobado (v76/rotulos_largos/propuesta.md, mapeado por v79/informe.json) si cabe
con bigramas en 10 casillas; si no, la abreviatura de v79 comprimida. Centrado de v81:
k = min(round((165 - 15n)/30), 10 - n). Objetivos y descripciones: solo se comprime (el número de
casillas por línea nunca crece; los saltos y las líneas no cambian).
Exclusiones: eventos 92010100..92010509 y 81000040, índices reutilizados por otras instrucciones,
registros cuyo nombre (+0/+16) es ダミー y el protagonista (registro 0, nombre editable y guardado: riesgo
de teclado/partida). Nota: 775 registros llevan ダミー solo en el nombre largo (+32) pero tienen nombre
español en +0/+16 y son hablantes reales (169 de ellos aparecen en el arg 2 de 0x301a, p. ej. «Gato»,
«Profe 1», o el 1614 «Aurelia» de la sonda v85): esos SÍ se tratan.

Salida: registro.json, extra/font/{FONT12,FONT8,FONT12T}.bcfnt, extra/inazuma1/data_iz/logic/unitbase.{dat,STR},
events/*.ssd, informe.json.
Uso: python -X utf8 work/ie1/capas/historial/fuentes/v88_bigramas_total/apply.py [--base .../probe_ie1_v87/archive.fa]
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import shutil
import sys
import tempfile
from functools import lru_cache
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import comun88 as K  # noqa: E402

ROOT = K.ROOT
V85 = K.modulo('v85_bigramas', ROOT / 'work/ie1/capas/historial/fuentes/v85_bigramas_sonda/apply.py')
V87 = K.modulo('v87_bigramas', ROOT / 'work/ie1/capas/historial/fuentes/v87_bigramas_fuentes/apply.py')
V79 = V85.V79
V75G = V85.V75G
C, S, decompress, parse_index = V79.C, V79.S, V79.decompress, V79.parse_index
a_texto = V79.a_texto
from fuentes import cargar, codepoint  # noqa: E402
from font_patch import morton8  # noqa: E402  (solo lectura de la herramienta congelada)

BASE = ROOT / 'work/shared/candidatas/probe_ie1_v87/archive.fa'
REG_V87 = ROOT / 'work/ie1/capas/historial/fuentes/v87_bigramas_fuentes/registro.json'
INF_V79 = ROOT / 'work/ie1/capas/historial/rotulos_objetivos/v79_rotulos/informe.json'
INF_V85 = ROOT / 'work/ie1/capas/historial/fuentes/v85_bigramas_sonda/informe.json'
ESCANEO = HERE / 'escaneo_base_v87.json'
REGISTRO = HERE / 'registro.json'
F12, F8, F12T = 'font/FONT12.bcfnt', 'font/FONT8.bcfnt', 'font/FONT12T.bcfnt'
FUENTES = (F12, F8, F12T)
UNIT = 'inazuma1/data_iz/logic/unitbase.dat'
USTR = 'inazuma1/data_iz/logic/unitbase.STR'
PROTEGIDOS = range(92010100, 92010510)
DONT_TOUCH = {81000040}
EXCLUIR_UNIDADES = {0: 'protagonista (nombre editable/guardado)'}
ESPACIO = '　'.encode('cp932')
LIMITE_ROTULO = 10
PLACA = 165
PASO_ROTULO_V81 = 15

CAMPOS = {  # campo -> (fuentes exigidas, [(fuente, paso real)] para la simulación)
    'nombre': ((F12, F8, F12T), [(F8, 10), (F12, 15), (F12T, 15)]),
    'rotulo': ((F12, F8), [(F8, 10)]),
    'objetivo': ((F12,), [(F12, 15)]),
    'descripcion': ((F12,), [(F12, 15)]),
}
CELDA = {F12: 15, F8: 11, F12T: 16}   # FINF width (x = lápiz + trunc((celda - advance)/2) + left)
SOLIDO = {F12: 5, F8: 8, F12T: 1}     # alfa mínimo que cuenta como tinta al medir huecos
HUECO_MIN = {F12: 1, F8: 1, F12T: 0}  # FONT12T: los contornos pueden tocarse (como sus letras nativas)


# ---------------------------------------------------------------------------------------------------
# glifos de pares por fuente
# ---------------------------------------------------------------------------------------------------
class Pares:
    def __init__(self, fuentes):
        self.F = fuentes
        self.g12 = V85.Glifos(fuentes[F12])

    @lru_cache(None)
    def f12(self, p):
        """(px desde x=0, ancho, left, width, advance) o None si no cabe (tinta <= 14)."""
        try:
            px, ancho, D, R = self.g12.par(p[0], p[1])
        except KeyError:
            return None
        if not px or ancho > V85.TINTA_MAX or D < 0 or D + ancho > 15:
            return None
        adv = D + ancho + R
        left = D - int((15 - adv) / 2)
        if not (-128 <= left <= 127 and 0 < adv <= 255):
            return None
        return px, ancho, left, ancho, adv, D

    @lru_cache(None)
    def f8(self, p):
        """Composición de v87 (núcleo <= 10, 1 px entre núcleos) con trunc en la colocación."""
        F = self.F[F8]
        try:
            px, wc, s = V87.par(F, p[0], p[1])
        except (AssertionError, TypeError):
            return None
        if not (1 <= wc <= V87.MAX_NUCLEO and 1 <= s and s + wc <= V87.W and px):
            return None
        adv = wc + (4 if ' ' in p else 0)
        left = (s - 1) - int((V87.W - adv) / 2)
        if not -128 <= left <= 127:
            return None
        return px, wc, left, min(wc + 2, V87.W), adv, s - 1

    @lru_cache(None)
    def f12t(self, p):
        """Par con el estilo de FONT12T (relleno L=F, contorno negro de 1 px) a partir de las letras de
        FONT12, 2 px entre rellenos (1 px, contorno compartido, si no cabe); ancho total con contorno <= 14 (paso 15)."""
        g = self.g12
        partes = []
        for ch in p:
            if ch == ' ':
                partes.append(None)
                continue
            try:
                _, _, _, pl, _ = g.letra(ch)
            except KeyError:
                return None
            fill = {(x, y) for (x, y), v in pl.items() if v >= 6}
            if not fill:
                return None
            partes.append(fill)
        for sep in (2, 1):
            r = self._f12t(p, partes, sep)
            if r is not None:
                return r
        return None

    @staticmethod
    def _f12t(p, partes, sep):
        fill, x = set(), 1
        for pt in partes:
            if pt is None:
                continue
            x0 = min(a for a, _ in pt)
            x1 = max(a for a, _ in pt)
            fill |= {(a - x0 + x, b + 1) for a, b in pt}
            x += (x1 - x0 + 1) + sep
        borde = set()
        for (a, b) in fill:
            for da in (-1, 0, 1):
                for db in (-1, 0, 1):
                    q = (a + da, b + db)
                    if q not in fill:
                        borde.add(q)
        todo = fill | borde
        x0 = min(a for a, _ in todo)
        W = max(a for a, _ in todo) - x0 + 1
        if W > 14:
            return None
        if p[1] == ' ':
            D = 0
        elif p[0] == ' ':
            D = 14 - W
        else:
            D = (15 - W) // 2
        px = {}
        for (a, b) in borde:
            if 0 <= b <= 16:
                px[(a - x0, b)] = 0x0F
        for (a, b) in fill:
            if 0 <= b <= 16:
                px[(a - x0, b)] = 0xFF
        return px, W, D, W, 16, D

    def cabe(self, p, fuentes):
        return all({F12: self.f12, F8: self.f8, F12T: self.f12t}[f](p) is not None for f in fuentes)

    def glifo(self, f, p):
        return {F12: self.f12, F8: self.f8, F12T: self.f12t}[f](p)


class CeldasLA4:
    def __init__(self, fuente):
        self.fu, self.f, self.t = fuente, fuente.f, fuente.t
        assert self.t['fmt'] == 9

    def escribir(self, gi, x, y, v):
        sheet, cell = divmod(gi, self.f.PER)
        X = (cell % self.t['ncols']) * self.fu.sx + x
        Y = (cell // self.t['ncols']) * self.fu.sy + y
        tile = (Y // 8) * (self.t['sheet_w'] // 8) + (X // 8)
        off = self.f.doff + sheet * self.t['sheet_size'] + tile * 64 + morton8(X % 8, Y % 8)
        self.f.data[off] = v & 0xFF
        self.fu._cache.pop(gi, None)


# ---------------------------------------------------------------------------------------------------
# texto <-> tokens
# ---------------------------------------------------------------------------------------------------
class Codec:
    def __init__(self, registro):
        self.por_codigo = {bytes.fromhex(e['sjis']): e['par'] for e in registro}
        self.por_par = {e['par']: bytes.fromhex(e['sjis']) for e in registro}

    @staticmethod
    def letra(tok):
        """Carácter español de un token de 2 B si es latino con glifo y vuelve a codificarse igual."""
        try:
            c = a_texto(tok)
        except UnicodeDecodeError:
            return None
        if len(c) != 1 or '぀' <= c <= '鿿' or c in '\n\r%':
            return None
        try:
            if V79.codificar(c) != tok:
                return None
        except (UnicodeEncodeError, UnicodeDecodeError):
            return None
        return c

    def tokens(self, body):
        """[(bytes, texto o None)]: texto = letra o par (del registro); None = opaco."""
        out, i = [], 0
        while i < len(body):
            b = body[i]
            if (0x81 <= b <= 0x9F or 0xE0 <= b <= 0xFC) and i + 1 < len(body):
                tok = body[i:i + 2]
                i += 2
                if tok in self.por_codigo:
                    out.append((tok, self.por_codigo[tok]))
                else:
                    out.append((tok, self.letra(tok)))
            else:
                out.append((body[i:i + 1], None))
                i += 1
        return out

    def segmentos(self, body):
        """[('t', texto) | ('o', bytes)]."""
        out = []
        for tok, t in self.tokens(body):
            k = 't' if t is not None else 'o'
            if out and out[-1][0] == k:
                out[-1] = (k, out[-1][1] + (t if k == 't' else tok))
            else:
                out.append((k, t if k == 't' else tok))
        return out

    def texto(self, body):
        return ''.join(v if k == 't' else '¤' for k, v in self.segmentos(body))

    def codificar(self, celdas):
        return b''.join(self.por_par[c] if len(c) == 2 else V79.codificar(c) for c in celdas)


def particion(t, pares, fuentes, permitidos, prohibidos=frozenset()):
    @lru_cache(None)
    def f(i):
        if i >= len(t):
            return (0, 0, ())
        c, s, r = f(i + 1)
        mejor = (c + 1, s, (t[i],) + r)
        if i + 1 < len(t):
            p = t[i:i + 2]
            if p != '  ' and p not in prohibidos and (permitidos is None or p in permitidos) \
                    and pares.cabe(p, fuentes):
                ancho = pares.f12(p)[1]
                c, s, r = f(i + 2)
                cand = (c + 1, s - (V85.TINTA_MAX - ancho) ** 0.5, (p,) + r)
                if cand[:2] < mejor[:2]:
                    mejor = cand
        return mejor
    return list(f(0)[2])


# ---------------------------------------------------------------------------------------------------
# simulación del dibujo a paso fijo
# ---------------------------------------------------------------------------------------------------
class Dibujo:
    def __init__(self, fuentes, pares, codigos):
        self.F, self.P, self.cod = fuentes, pares, codigos   # codigos: par -> codepoint (o None si aún no)

    def celda(self, f, c):
        """(px relativos al lápiz) de una casilla con el glifo final."""
        if len(c) == 2:
            px, _, left, _, adv, D = self.P.glifo(f, c)
            x0 = int((CELDA[f] - adv) / 2) + left
            assert x0 == D, (f, c, x0, D)
            return {(x + x0, y): v for (x, y), v in px.items()}
        F = self.F[f]
        gi = F.gi(codepoint(c))
        if gi is None:
            return {}
        left, _, adv = F.metrics[gi]
        x0 = int((CELDA[f] - adv) / 2) + left
        return {(x + x0, y): v for y, row in enumerate(F.bitmap(gi)) for x, v in enumerate(row) if v}

    def colocar(self, f, celdas, paso):
        return [dict(c=c, px={(x + k * paso, y): v for (x, y), v in self.celda(f, c).items()})
                for k, c in enumerate(celdas)]

    @staticmethod
    def huecos(col, solido):
        res = []
        for i in range(len(col) - 1):
            a = [x for (x, _), v in col[i]['px'].items() if v >= solido]
            b = [x for (x, _), v in col[i + 1]['px'].items() if v >= solido]
            if a and b:
                res.append((i, min(b) - max(a) - 1))
        return res

    def fallos(self, celdas, campo):
        malos = set()
        for f, paso in CAMPOS[campo][1]:
            col = self.colocar(f, celdas, paso)
            for i, g in self.huecos(col, SOLIDO[f]):
                if g < HUECO_MIN[f]:
                    for c in (celdas[i], celdas[i + 1]):
                        if len(c) == 2:
                            malos.add(c)
        return malos


def partir(t, campo, pares, dib, permitidos):
    fuentes = CAMPOS[campo][0]
    prohibidos = set()
    while True:
        cel = particion(t, pares, fuentes, permitidos, frozenset(prohibidos))
        malos = dib.fallos(cel, campo)
        if not malos:
            return cel, sorted(prohibidos)
        prohibidos |= malos


def n_espacios(n):
    return min(max(0, round((PLACA - PASO_ROTULO_V81 * n) / 2 / PASO_ROTULO_V81)), LIMITE_ROTULO - n)


# ---------------------------------------------------------------------------------------------------
def recoger(get, codec):
    """Unidades de texto a comprimir: [(campo, clave, lista de segmentos)] y datos auxiliares."""
    unidades = []
    # nombres
    ub = get(UNIT)
    inf85 = json.loads(INF_V85.read_text(encoding='utf-8'))
    for i in range((len(ub) - 96) // 96):
        r = ub[96 + i * 96:192 + i * 96]
        dummy = 'ダミー'.encode('cp932') in r[:32]   # nombre ダミー (ver nota de ダミー en +32)
        for campo_off in (0, 16):
            body = r[campo_off:campo_off + 16].split(b'\0')[0]
            segs = codec.segmentos(body)
            if not body or len(segs) != 1 or segs[0][0] != 't':
                continue
            unidades.append(dict(tipo='nombre', registro=i, campo=campo_off, body=body, segs=segs,
                                 excluido=('ダミー' if dummy else EXCLUIR_UNIDADES.get(i))))
    # descripciones
    st = get(USTR)
    usados = collections.defaultdict(list)
    for i in range((len(ub) - 96) // 96):
        off = int.from_bytes(ub[96 + i * 96 + 94:96 + i * 96 + 96], 'little') * 32
        if off:
            usados[off].append(i)
    for off in sorted(usados):
        if off >= len(st):
            continue
        body = st[off:st.index(b'\0', off)]
        segs = codec.segmentos(body)
        if not any(k == 't' for k, _ in segs):
            continue
        todos_dummy = all('ダミー'.encode('cp932') in ub[96 + i * 96:96 + i * 96 + 32] for i in usados[off])
        unidades.append(dict(tipo='descripcion', offset=off, registros=usados[off], body=body, segs=segs,
                             excluido='ダミー' if todos_dummy else None))
    # eventos
    inf79 = json.loads(INF_V79.read_text(encoding='utf-8'))
    propuesta = {(f['evento'], f['indice']): f for f in inf79['rotulos'] + inf79['rotulos_iguales']}
    pkb = get(C.PKB)
    eventos = {}
    for eid, o, s in parse_index(get(C.PKH)):
        data = decompress(pkb[o:o + s])
        try:
            _, ops, recs = S.parse(data)
            refs = C.text_refs(data)
        except (ValueError, KeyError):
            continue
        for i, r in enumerate(recs):
            clave = {(0x4037, 3): 'rotulo', (0x402f, 2): 'objetivo', (0x402f, 3): 'objetivo'}.get(
                (ops.get(r.instruction), r.argument))
            if not clave or not r.body:
                continue
            segs = codec.segmentos(r.body)
            if not any(k == 't' and v.strip() for k, v in segs):
                continue
            excl = None
            if eid in PROTEGIDOS or eid in DONT_TOUCH:
                excl = 'evento protegido'
            else:
                otros = [x for x in refs.get(i, []) if (x[1], x[2]) != (ops.get(r.instruction), r.argument)]
                if otros:
                    excl = f'índice reutilizado por {otros}'
            u = dict(tipo=clave, evento=eid, indice=i, arg=r.argument, body=r.body, segs=segs, excluido=excl)
            if clave == 'rotulo' and not excl:
                p = propuesta.get((eid, i))
                if p is None:
                    raise SystemExit(f'rótulo sin propuesta v79: {eid} {i} {codec.texto(r.body)!r}')
                actual = codec.texto(r.body).strip(' ')
                if actual not in (p['nuevo'], p['propuesta']):
                    raise SystemExit(f'rótulo inesperado: {eid} {i} {actual!r} vs {p}')
                u.update(largo=p['propuesta'], abreviatura=p['nuevo'])
            unidades.append(u)
            eventos.setdefault(eid, data)
    return unidades, eventos, ub, st, inf85


def textos_de(u, codec):
    """Textos (sin espacios de centrado) que hay que partir para la unidad u."""
    if u['tipo'] == 'rotulo':
        return [u['largo'], u['abreviatura']]
    return [v for k, v in u['segs'] if k == 't']


def elegir_codigos(fuentes, n, ya):
    esc = json.loads(ESCANEO.read_text(encoding='utf-8'))
    inversos = {}
    for f in FUENTES:
        inv = collections.defaultdict(list)
        for cp, gi in fuentes[f].cmap.items():
            inv[gi].append(cp)
        inversos[f] = inv
    out = []
    for c in esc['limpios']:
        code = int(c, 16)
        if not 0x989F <= code <= 0xEAA4 or c in ya:
            continue
        b = code.to_bytes(2, 'big')
        ch = b.decode('cp932')
        if b.decode('shift_jis', 'replace') != ch or ch.encode('cp932') != b:
            continue
        ok = True
        for f in FUENTES:
            gi = fuentes[f].gi(ord(ch))
            if gi is None or inversos[f][gi] != [ord(ch)]:
                ok = False
        if ok:
            out.append(c)
    return out[:n], len(out)


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', type=Path, default=BASE)
    args = ap.parse_args()
    base = args.base.resolve()
    get = K.abrir(base)
    tmp = Path(tempfile.mkdtemp(prefix='ie123_v88_'))
    fuentes, antes_f = {}, {}
    for f in FUENTES:
        p = tmp / Path(f).name
        antes_f[f] = get(f)
        p.write_bytes(antes_f[f])
        fuentes[f] = cargar(p)
    reg87 = json.loads(REG_V87.read_text(encoding='utf-8'))
    assert hashlib.sha256(antes_f[F12]).hexdigest() == reg87['fuentes_dibujadas'][F12]
    assert hashlib.sha256(antes_f[F8]).hexdigest() == reg87['fuentes_dibujadas'][F8]
    viejos = [e['par'] for e in reg87['bigramas']]
    codec = Codec(reg87['bigramas'])
    pares = Pares(fuentes)
    dib = Dibujo(fuentes, pares, None)

    unidades, eventos, ub, st, inf85 = recoger(get, codec)
    activas = [u for u in unidades if not u['excluido']]

    # 1) particiones ------------------------------------------------------------------------------
    abreviar = set()     # rótulos (evento, índice) que vuelven a la abreviatura para no agrandar el evento

    def particiones(permitidos):
        res, uso, elegidos = {}, collections.Counter(), set()

        def de(tipo, t):
            if (tipo, t) not in res:
                res[(tipo, t)] = partir(t, tipo, pares, dib, permitidos)
            return res[(tipo, t)][0]
        for u in activas:
            if u['tipo'] == 'rotulo':
                t = u['largo']
                if len(de('rotulo', t)) > LIMITE_ROTULO or (u['evento'], u['indice']) in abreviar:
                    t = u['abreviatura']
                ts = [t]
            else:
                ts = textos_de(u, codec)
            for t in ts:
                elegidos.add((u['tipo'], t))
                uso.update(c for c in de(u['tipo'], t) if len(c) == 2)
        return res, uso, elegidos

    def cuerpo(u, res, cod):
        """(cuerpo nuevo, celdas, texto elegido, espacios) de una unidad activa."""
        if u['tipo'] == 'rotulo':
            largo = res[('rotulo', u['largo'])][0]
            if len(largo) <= LIMITE_ROTULO and (u['evento'], u['indice']) not in abreviar:
                elegido, cel = u['largo'], largo
            else:
                elegido, cel = u['abreviatura'], res[('rotulo', u['abreviatura'])][0]
            k = n_espacios(len(cel))
            assert k >= 0 and k + len(cel) <= LIMITE_ROTULO
            return ESPACIO * k + cod(cel), cel, elegido, k
        partes, celdas_tot = [], []
        for k_, v in u['segs']:
            if k_ == 'o':
                partes.append(v)
                celdas_tot.append(None)
            else:
                cel = res[(u['tipo'], v)][0]
                partes.append(cod(cel))
                celdas_tot += cel
        return b''.join(partes), celdas_tot, None, None

    def provisional(cel):
        return b''.join(b'\x98\x9f' if len(c) == 2 else V79.codificar(c) for c in cel)

    def sin_crecer(res):
        """Añade a `abreviar` los rótulos largos que harían crecer su evento. True si cambió algo."""
        por_ev = collections.defaultdict(list)
        for u in activas:
            if u['tipo'] in ('rotulo', 'objetivo'):
                por_ev[u['evento']].append(u)
        cambio = False
        for eid, us in por_ev.items():
            while True:
                cambios = {}
                for u in us:
                    b = cuerpo(u, res, provisional)[0]
                    if b != u['body']:
                        cambios[u['indice']] = b
                if not cambios or len(S.replace(eventos[eid], cambios)) <= len(eventos[eid]):
                    break
                largos = [u for u in us if u['tipo'] == 'rotulo' and (eid, u['indice']) not in abreviar
                          and len(res[('rotulo', u['largo'])][0]) <= LIMITE_ROTULO
                          and len(cuerpo(u, res, provisional)[0]) > len(u['body'])]
                assert largos, f'el evento {eid} crece sin rótulos largos que deshacer'
                peor = max(largos, key=lambda u: len(cuerpo(u, res, provisional)[0]) - len(u['body']))
                abreviar.add((eid, peor['indice']))
                cambio = True
        return cambio

    def resolver(permitidos):
        res, uso, elegidos = particiones(permitidos)
        while sin_crecer(res):
            res, uso, elegidos = particiones(permitidos)
        return res, uso, elegidos

    res, uso, elegidos = resolver(None)
    necesarios = [p for p, _ in uso.most_common()]
    nuevos_dem = [p for p in necesarios if p not in viejos]
    libres, n_libres = elegir_codigos(fuentes, 10 ** 6, {e['sjis'] for e in reg87['bigramas']})
    print('pares pedidos', len(necesarios), 'nuevos', len(nuevos_dem), 'códigos limpios', n_libres)
    recorte = None
    if len(nuevos_dem) > len(libres):
        recorte = len(libres)
        permitidos = frozenset(set(viejos) | set(nuevos_dem[:len(libres)]))
        res, uso, elegidos = resolver(permitidos)
    usados = [p for p, _ in uso.most_common()]
    nuevos = [p for p in usados if p not in viejos]
    assert len(nuevos) <= len(libres), (len(nuevos), len(libres))

    # 2) registro (solo añadir) ----------------------------------------------------------------------
    registro = [dict(e) for e in reg87['bigramas']]
    for p, c in zip(nuevos, libres):
        ch = bytes.fromhex(c).decode('cp932')
        registro.append(dict(par=p, sjis=c, unicode=f'U+{ord(ch):04X}', kanji=ch))
    codec = Codec(registro)
    campos_de = collections.defaultdict(set)
    for tipo, t in elegidos:
        for c in res[(tipo, t)][0]:
            if len(c) == 2:
                campos_de[c].add(tipo)

    # 3) dibujo ---------------------------------------------------------------------------------------
    escritor = {F12: V75G.Celdas(fuentes[F12]), F8: V75G.Celdas(fuentes[F8]), F12T: CeldasLA4(fuentes[F12T])}
    for e in registro:
        p = e['par']
        cp = int(e['unicode'][2:], 16)
        exigidas = set()
        for campo in campos_de.get(p, ()):
            exigidas |= set(CAMPOS[campo][0])
        dibujar = [f for f in FUENTES if pares.glifo(f, p) is not None and (f != F12T or F12T in exigidas)]
        assert exigidas <= set(dibujar), (p, exigidas, dibujar)
        e['fuentes'] = dict(e.get('fuentes', {}))
        for f in dibujar:
            if p in viejos and f in (F12, F8):
                g = pares.glifo(f, p)
                assert list(g[2:5]) == e['fuentes'][f]['cwdh'], (p, f, g[2:5], e['fuentes'][f])
                continue   # dibujo de v87, ya en la base
            F = fuentes[f]
            gi = F.gi(cp)
            px, ancho, left, width, adv, D = pares.glifo(f, p)
            for y in range(F.sy):
                for x in range(F.sx):
                    escritor[f].escribir(gi, x, y, 0)
            for (x, y), v in px.items():
                assert 0 <= x < F.sx - 1 and 0 <= y < F.sy - 1, (p, f, x, y)
                escritor[f].escribir(gi, 1 + x, 1 + y, v)
            viejo = list(F.metrics[gi])
            F.set_metrics(gi, left, width, adv)
            leido = {(x, y): v for y, row in enumerate(F.bitmap(gi)) for x, v in enumerate(row) if v}
            esperado = px if f != F12T else {k: max(v >> 4, v & 0xF) for k, v in px.items()}
            assert leido == esperado, (p, f)
            e['fuentes'][f] = dict(glifo=gi, cwdh_kanji=viejo, cwdh=[left, width, adv], tinta_px=ancho, columna=D,
                                   pixeles_sha1=hashlib.sha1(json.dumps(sorted(px.items())).encode()).hexdigest())
            if f == F12:
                e.update(glifo=gi, cwdh_kanji=viejo, cwdh=[left, width, adv], tinta_px=ancho, D=D,
                         R=adv - D - ancho, pixeles_sha1=e['fuentes'][f]['pixeles_sha1'])
        e['campos'] = sorted(campos_de.get(p, ()))
    salida = {}
    for f in FUENTES:
        datos = fuentes[f].data()
        assert len(datos) == len(antes_f[f])
        if datos != antes_f[f]:
            salida[f] = datos

    # 4) aplicar a los datos -----------------------------------------------------------------------------
    usos = collections.defaultdict(set)
    ub2, st2 = bytearray(ub), bytearray(st)
    cambios_nom, cambios_desc, cambios_ev, excluidos = [], [], [], []
    ev_cambios = collections.defaultdict(dict)

    def marca(cel, donde):
        for c in cel:
            if c and len(c) == 2:
                usos[c].add(donde)

    for u in unidades:
        if u['excluido']:
            excluidos.append({k: v for k, v in u.items() if k not in ('body', 'segs')} |
                             dict(texto=codec.texto(u['body'])))
            continue
        nuevo, cel, elegido, k = cuerpo(u, res, codec.codificar)
        assert len(nuevo) <= len(u['body']) or u['tipo'] == 'rotulo', u
        vista = '|'.join(c if c else '¤' for c in cel)
        if u['tipo'] == 'nombre':
            assert len(nuevo) <= 15 or len(u['body']) == 16
            off = 96 + u['registro'] * 96 + u['campo']
            ub2[off:off + 16] = nuevo + bytes(16 - len(nuevo))
            if nuevo != u['body']:
                cambios_nom.append(dict(registro=u['registro'], campo=u['campo'], texto=codec.texto(u['body']),
                                        celdas=vista, casillas_antes=len(codec.tokens(u['body'])),
                                        casillas=len(cel), bytes_antes=len(u['body']), bytes=len(nuevo)))
            marca(cel, f"IE1 unitbase.dat +{u['campo']}")
        elif u['tipo'] == 'descripcion':
            off = u['offset']
            st2[off:off + len(u['body'])] = nuevo + bytes(len(u['body']) - len(nuevo))
            if nuevo != u['body']:
                cambios_desc.append(dict(offset=off, registros=u['registros'], texto=codec.texto(u['body']),
                                         celdas=vista, bytes_antes=len(u['body']), bytes=len(nuevo)))
            marca(cel, 'IE1 unitbase.STR')
        elif u['tipo'] == 'objetivo':
            if nuevo != u['body']:
                ev_cambios[u['evento']][u['indice']] = nuevo
                cambios_ev.append(dict(tipo='objetivo', evento=u['evento'], indice=u['indice'], arg=u['arg'],
                                       texto=codec.texto(u['body']), celdas=vista,
                                       bytes_antes=len(u['body']), bytes=len(nuevo)))
            marca(cel, f"IE1 eve.pkb 0x402f arg {u['arg']}")
        else:
            assert len(nuevo) <= 2 * LIMITE_ROTULO
            if nuevo != u['body']:
                ev_cambios[u['evento']][u['indice']] = nuevo
                cambios_ev.append(dict(tipo='rotulo', evento=u['evento'], indice=u['indice'],
                                       antes=codec.texto(u['body']), despues=elegido, largo=u['largo'],
                                       largo_cabe=elegido == u['largo'],
                                       abreviado_por_tamano=(u['evento'], u['indice']) in abreviar,
                                       celdas=vista, espacios=k, casillas=k + len(cel),
                                       bytes_antes=len(u['body']), bytes=len(nuevo)))
            marca(cel, 'IE1 eve.pkb 0x4037 arg 3')
    out_dir = HERE / 'extra'
    if out_dir.exists():
        shutil.rmtree(out_dir)
    for f, datos in salida.items():
        (out_dir / f).parent.mkdir(parents=True, exist_ok=True)
        (out_dir / f).write_bytes(datos)
    for rel, antes, despues in ((UNIT, ub, ub2), (USTR, st, st2)):
        assert len(antes) == len(despues)
        if bytes(despues) != antes:
            (out_dir / rel).parent.mkdir(parents=True, exist_ok=True)
            (out_dir / rel).write_bytes(bytes(despues))
    ev_dir = HERE / 'events'
    if ev_dir.exists():
        shutil.rmtree(ev_dir)
    ev_dir.mkdir()
    tam = []
    for eid, cambios in sorted(ev_cambios.items()):
        data = eventos[eid]
        nuevo = S.replace(data, cambios)
        _, ops, recs = S.parse(data)
        _, ops2, recs2 = S.parse(nuevo)
        assert ops2 == ops and len(recs2) == len(recs)
        assert len(nuevo) <= len(data), (eid, len(nuevo), len(data))
        tam.append(dict(evento=eid, bytes_antes=len(data), bytes=len(nuevo), registros=sorted(cambios)))
        (ev_dir / f'{eid}.ssd').write_bytes(nuevo)

    for e in registro:
        e['uso'] = sorted(set(e.get('uso', [])) | usos[e['par']]) if e['par'] in viejos else sorted(usos[e['par']])
    reg_out = dict(
        descripcion=reg87['descripcion'] + ' v88: todos los nombres (+0/+16), rótulos, objetivos (0x402f) y '
                    'descripciones (unitbase.STR) de IE1; los pares nuevos van al final. «fuentes» indica en '
                    'qué fuentes está dibujado cada código; «campos», qué textos lo usan.',
        version='v88', fuente=F12, fuente_base_sha256=reg87['fuente_base_sha256'],
        regla_codigos=reg87['regla_codigos'] + '; v88: escaneo estricto sobre probe_ie1_v87 '
                      '(escaneo_kanji88.py -> escaneo_base_v87.json: sin «texto» ni «binario_textual»), con glifo propio en '
                      'FONT12, FONT8 y FONT12T',
        regla_metricas=reg87['regla_metricas'],
        regla_metricas_FONT8=reg87['regla_metricas_FONT8'] + ' (v88: trunc en la colocación)',
        regla_metricas_FONT12T='relleno L=F/A=F de las letras de FONT12 (alfa >= 6) bajado 1 fila, contorno '
                               'L=0/A=F de 1 px, 2 px entre rellenos (1 si no cabe), ancho total <= 14; '
                               'left = columna, advance = 16 (como las letras nativas)',
        espaciado=reg87['espaciado'],
        campos={k: dict(fuentes=list(v[0]), paso=[f'{f} {q} px' for f, q in v[1]]) for k, v in CAMPOS.items()},
        bigramas=registro,
        fuentes_dibujadas={f: hashlib.sha256(fuentes[f].data()).hexdigest() for f in FUENTES},
    )
    REGISTRO.write_text(json.dumps(reg_out, ensure_ascii=False, indent=1), encoding='utf-8')

    por_fuente = {f: sum(1 for e in registro if f in e['fuentes']) for f in FUENTES}
    rot = [u for u in activas if u['tipo'] == 'rotulo']
    caben = sorted({u['largo'] for u in rot if len(res[('rotulo', u['largo'])][0]) <= LIMITE_ROTULO
                    and (u['evento'], u['indice']) not in abreviar})
    por_tamano = sorted({u['largo'] for u in rot if (u['evento'], u['indice']) in abreviar})
    no_caben = sorted({(u['largo'], u['abreviatura'], len(res[('rotulo', u['largo'])][0])) for u in rot
                       if len(res[('rotulo', u['largo'])][0]) > LIMITE_ROTULO})
    informe = dict(
        base=str(base), registro=str(REGISTRO.relative_to(ROOT)),
        pares_total=len(registro), pares_nuevos=len(nuevos), pares_v87=len(viejos),
        pares_pedidos_sin_limite=len(necesarios), codigos_limpios_disponibles=n_libres, recorte=recorte,
        pares_por_fuente=por_fuente,
        pares_por_campo={k: sum(1 for e in registro if k in e['campos']) for k in CAMPOS},
        pares_sin_uso=[e['par'] for e in registro if not e['campos']],
        fuentes_cambiadas=sorted(salida),
        nombres_cambiados=len(cambios_nom), descripciones_cambiadas=len(cambios_desc),
        rotulos_cambiados=sum(1 for c in cambios_ev if c['tipo'] == 'rotulo'),
        objetivos_cambiados=sum(1 for c in cambios_ev if c['tipo'] == 'objetivo'),
        rotulos_largos_que_caben=caben, rotulos_largos_abreviados_por_tamano=por_tamano,
        rotulos_largos_que_no_caben=no_caben,
        eventos=tam, prohibidos_por_solape={f'{t}|{x}': q for (t, x), (_, q) in res.items() if q},
        nombres=cambios_nom, descripciones=cambios_desc, textos_evento=cambios_ev, excluidos=excluidos,
    )
    (HERE / 'informe.json').write_text(json.dumps(informe, ensure_ascii=False, indent=1), encoding='utf-8')
    print('pares', len(registro), 'nuevos', len(nuevos), 'por fuente', por_fuente, 'recorte', recorte)
    print('por campo', informe['pares_por_campo'], 'sin uso', informe['pares_sin_uso'])
    print('nombres', len(cambios_nom), 'descripciones', len(cambios_desc),
          'rótulos', informe['rotulos_cambiados'], 'objetivos', informe['objetivos_cambiados'],
          'eventos', len(tam), 'excluidos', len(excluidos))
    print('largos que caben', len(caben), caben)
    print('abreviados por tamaño', por_tamano)
    print('no caben', no_caben)
    for f in FUENTES:
        print(f, reg_out['fuentes_dibujadas'][f], 'cambiada' if f in salida else 'igual')
    shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    main()


