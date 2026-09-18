"""v89 · ritmo uniforme en descripciones, objetivos y nombres (FONT12, 15 px) sobre probe_ie1_v88.

Queja del usuario sobre v88: «S u gran c u erpo es un / muro en d e fen s a.»; letras sueltas centradas y
pares estrechos dejan huecos grandes y desiguales dentro de las palabras.

Qué hace (modelo en ritmo.py):
1. Decodifica con el registro de v88 las descripciones (unitbase.STR), los objetivos (0x402f arg 2/3) y los
   nombres (unitbase.dat +0/+16).
2. Descripciones y objetivos (solo FONT12): «trozos» de 1-4 caracteres y variantes de un glifo alineadas a
   izquierda/derecha, elegidos por programación dinámica (huecos de 1-2 px dentro de palabra, >= 4 px entre
   palabras).
3. Nombres (FONT12 + FONT8 + FONT12T): solo pares que caben en las tres fuentes (reglas de v88 para FONT8 y
   FONT12T), misma programación dinámica en FONT12 y el bucle de v88 contra solapes en FONT8 (10 px) y
   FONT12T (15 px).
4. Rótulos (solo FONT8 en pantalla): cuerpos de v88 sin cambios; sus pares conservan código y dibujos.
5. Códigos: un trozo que ya era par en v88 conserva su código (y sus dibujos FONT8/FONT12T); el resto sale de
   los códigos de v88 que quedan libres, de los 26 limpios del escaneo de v88 aún sin usar y de kanji sin
   aparición en texto cuya única aparición «textual» en binario está en ficheros gráficos y sin literal en
   code.bin/CRO (escaneo_literales.py). Glifo propio en FONT12 (y en FONT8/FONT12T para los de nombres).
   En FONT12 todos los códigos se dibujan con la maqueta nueva. Si hay más trozos que códigos, se descartan
   los trozos de descripción menos usados y se repite.
Garantías: hueco sólido >= 1 px entre casillas (FONT12T >= 0 como en v88), sin crecer (STR con la capacidad de
v87, nombres <= 15 B, eventos <= v87), eventos protegidos y rótulos intactos.
Salida: registro.json, extra/font/*.bcfnt, extra/inazuma1/data_iz/logic/unitbase.{dat,STR}, events/*.ssd,
informe.json. Uso: python -X utf8 work/ie1/capas/v89/bigramas_ritmo/apply.py
"""
from __future__ import annotations

import collections
import hashlib
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
V88DIR = HERE.parents[1] / 'v88/bigramas_total'
sys.path.insert(0, str(HERE))
sys.path.insert(1, str(V88DIR))
import ritmo as R  # noqa: E402
import comun88  # noqa: E402

A88 = comun88.modulo('v88_bigramas', V88DIR / 'apply.py')

K = A88.K
ROOT = K.ROOT
BASE = ROOT / 'work/shared/candidatas/probe_ie1_v88/archive.fa'
REG88 = V88DIR / 'registro.json'
INF88 = V88DIR / 'informe.json'
ESC88 = V88DIR / 'escaneo_base_v87.json'
LITERALES = HERE / 'literales.json'
F12, F8, F12T = A88.F12, A88.F8, A88.F12T
FUENTES = A88.FUENTES
UNIT, USTR = A88.UNIT, A88.USTR
S, V79 = A88.S, A88.V79
GRAFICOS = re.compile(r'/(pic3d|pic2d|a_field|model|effect3d|face2d|spr|map2d|map3d)/')
PASOS_NOMBRE = [(F8, 10), (F12T, 15)]     # FONT12 lo controla la programación dinámica
REPARTIR_NOMBRES = False   # probado: con las restricciones de FONT8/FONT12T no mejora (ver informe)


def clave_de(e):
    return e.get('clave', e['par'])


class Codec(A88.Codec):
    def __init__(self, registro):
        self.por_codigo = {bytes.fromhex(e['sjis']): e['par'] for e in registro}
        self.clave_cod = {bytes.fromhex(e['sjis']): clave_de(e) for e in registro}
        self.por_par = {clave_de(e): bytes.fromhex(e['sjis']) for e in registro}

    def codificar(self, celdas):
        return b''.join(self.por_par[c] if len(c) >= 2 else V79.codificar(c) for c in celdas)

    def claves(self, body):
        """Claves de casilla de un cuerpo (None = opaco)."""
        return [self.clave_cod.get(tok, t) if t is not None else None for tok, t in self.tokens(body)]


class Maqueta(R.Maqueta):
    def __init__(self, F, cp):
        super().__init__(F, cp)
        self.fijos = {}

    def trozo(self, t):
        if t in self.fijos:
            return self.fijos[t]
        return super().trozo(t)


def medir(F, gi):
    """Maqueta equivalente del dibujo que tiene un código en FONT12."""
    left, width, adv = F.metrics[gi]
    x0 = int((R.CELDA - adv) / 2) + left
    px = {(x, y): v for y, row in enumerate(F.bitmap(gi)) for x, v in enumerate(row) if v}
    sol = [x for (x, _), v in px.items() if v >= R.SOLIDO]
    xs = [x for x, _ in px]
    return dict(px={(x - min(xs), y): v for (x, y), v in px.items()}, S0=x0 + min(sol), S1=x0 + max(sol),
                D=x0 + min(xs), ancho=max(xs) - min(xs) + 1, g=None, medido=True)


def unico(F, inv, c):
    b = bytes.fromhex(c)
    try:
        ch = b.decode('cp932')
    except UnicodeDecodeError:
        return False
    if ch.encode('cp932') != b or b.decode('shift_jis', 'replace') != ch:
        return False
    gi = F.gi(ord(ch))
    return gi is not None and inv[gi] == [ord(ch)]


def pool_extra(fuentes, v88):
    """Códigos fuera de v88: [(sjis, origen, válido en las tres fuentes)] en orden de preferencia."""
    esc = json.loads(ESC88.read_text(encoding='utf-8'))
    lit = json.loads(LITERALES.read_text(encoding='utf-8'))
    inv = {}
    for f in FUENTES:
        d = collections.defaultdict(list)
        for cp, gi in fuentes[f].cmap.items():
            d[gi].append(cp)
        inv[f] = d
    out = []
    limpios = [c for c in esc['limpios'] if c not in v88 and int(c, 16) >= 0x889F]
    graf = []
    for c, v in esc['codigos'].items():
        if c in v88 or int(c, 16) < 0x889F or v.get('texto'):
            continue
        if c not in lit or lit[c] or not unico(fuentes[F12], inv[F12], c):
            continue
        tres = all(unico(fuentes[f], inv[f], c) for f in FUENTES)
        if c in limpios:
            out.append((c, 'limpio_escaneo_v88', tres))
            continue
        rutas = [r for r, _ in esc['apariciones_textuales'].get(c, [])]
        if all(GRAFICOS.search(r) for r in rutas):
            graf.append((len(rutas), sum(v.values()), c, tres))
    for _, _, c, tres in sorted(graf):
        out.append((c, 'solo_graficos', tres))
    return out


def colapsar(cel):
    out = []
    for c in cel:
        if not (c is None and out and out[-1] is None):
            out.append(c)
    return out


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    get = K.abrir(BASE)
    tmp = Path(tempfile.mkdtemp(prefix='ie123_v89_'))
    fuentes, antes_f = {}, {}
    for f in FUENTES:
        antes_f[f] = get(f)
        (tmp / Path(f).name).write_bytes(antes_f[f])
        fuentes[f] = A88.cargar(tmp / Path(f).name)
    reg88 = json.loads(REG88.read_text(encoding='utf-8'))
    for f in FUENTES:
        assert hashlib.sha256(antes_f[f]).hexdigest() == reg88['fuentes_dibujadas'][f], f
    inf88 = json.loads(INF88.read_text(encoding='utf-8'))
    codec88 = Codec(reg88['bigramas'])
    unidades, eventos, ub, st, _ = A88.recoger(get, codec88)
    por_par88 = {e['par']: e for e in reg88['bigramas']}
    v88_sjis = {e['sjis'] for e in reg88['bigramas']}

    F = fuentes[F12]
    mq = Maqueta(F, A88.codepoint)
    pares = A88.Pares(fuentes)
    dib = A88.Dibujo(fuentes, pares, None)

    # rótulos: sin cambios ------------------------------------------------------------------------------------
    rotulos = [u for u in unidades if u['tipo'] == 'rotulo' and not u['excluido']]
    claves_rot = {c for u in rotulos for c in codec88.claves(u['body']) if c and len(c) >= 2}
    for p in claves_rot:
        if R.Maqueta.trozo(mq, p) is None:     # la maqueta nueva no lo admite: se queda el dibujo de v88
            mq.fijos[p] = medir(F, F.gi(int(por_par88[p]['unicode'][2:], 16)))

    # nombres ------------------------------------------------------------------------------------------------
    nombres = [u for u in unidades if u['tipo'] == 'nombre' and not u['excluido']]
    textos_nom = sorted({u['segs'][0][1] for u in nombres})

    def admite_nombre(prohib):
        def ok(c):
            return (len(c) == 2 and not R.variante(c) and c not in prohib
                    and pares.f8(c) is not None and pares.f12t(c) is not None)
        return ok

    def fallos_nombre(cel):
        malos = set()
        for f, paso in PASOS_NOMBRE:
            col = dib.colocar(f, cel, paso)
            for i, g in dib.huecos(col, A88.SOLIDO[f]):
                if g < A88.HUECO_MIN[f]:
                    malos |= {c for c in (cel[i], cel[i + 1]) if len(c) == 2}
        return malos

    part_nom, prohib_nom = {}, {}
    if REPARTIR_NOMBRES:
        for t in textos_nom:
            prohib = set()
            while True:
                coste, cel = R.particion(t, mq, admite_nombre(prohib), largo_max=2)
                assert coste < R.INF, t
                cel = list(cel)
                malos = fallos_nombre(cel)
                if not malos:
                    break
                prohib |= malos
            part_nom[t] = (coste, cel)
            if prohib:
                prohib_nom[t] = sorted(prohib)
    else:
        # Los pares de nombre deben caber en FONT8 (paso 10: tinta <= 10) y en FONT12T; con esas fuentes
        # la partición de v88 ya es casi la única posible, así que se conserva (cuerpos idénticos).
        for u in nombres:
            cel = [c for c in codec88.claves(u['body'])]
            assert None not in cel
            part_nom.setdefault(u['segs'][0][1], (0.0, cel))
            assert part_nom[u['segs'][0][1]][1] == cel
    claves_nom = {c for _, cel in part_nom.values() for c in cel if len(c) >= 2}
    for p in claves_nom:
        if R.Maqueta.trozo(mq, p) is None:
            mq.fijos[p] = medir(F, F.gi(int(por_par88[p]['unicode'][2:], 16)))

    # descripciones y objetivos ------------------------------------------------------------------------------
    activas = [u for u in unidades if u['tipo'] in ('descripcion', 'objetivo') and not u['excluido']]
    textos = collections.Counter(v for u in activas for k, v in u['segs'] if k == 't')
    extra = pool_extra(fuentes, v88_sjis)
    total_codigos = len(v88_sjis) + len(extra)
    fijas = claves_rot | claves_nom
    nuevas_nom = [c for c in claves_nom if c not in por_par88]
    tres_libres = sum(1 for _, _, t3 in extra if t3) + sum(1 for e in reg88['bigramas'] if e['par'] not in fijas)
    assert len(nuevas_nom) <= tres_libres
    print('rótulos', len(claves_rot), 'nombres', len(claves_nom), 'nuevos de nombre', len(nuevas_nom),
          'códigos totales', total_codigos, collections.Counter(o for _, o, _ in extra))

    descartados = set()

    def admitido(c):
        return c in fijas or c not in descartados

    ronda = 0
    while True:
        res, uso = {}, collections.Counter()
        for t, n in textos.items():
            coste, cel = R.particion(t, mq, admitido)
            assert coste < R.INF, t
            res[t] = (coste, list(cel))
            for c in cel:
                if len(c) >= 2 and c not in fijas:
                    uso[c] += n
        exceso = len(fijas) + len(uso) - total_codigos
        print('ronda', ronda, 'trozos de texto', len(uso), 'exceso', exceso,
              'coste', round(sum(c for c, _ in res.values()), 1), flush=True)
        if exceso <= 0:
            break
        quitar = sorted(uso.items(), key=lambda kv: (kv[1], kv[0]))[:max(5, exceso // 3)]
        descartados |= {c for c, _ in quitar}
        ronda += 1

    # asignación de códigos --------------------------------------------------------------------------------
    claves = sorted(fijas) + [c for c, _ in uso.most_common()]
    asign, origen = {}, {}
    for c in claves:
        if c in por_par88:
            asign[c] = por_par88[c]['sjis']
            origen[c] = por_par88[c].get('origen', 'v88')
    libres88 = [e['sjis'] for e in reg88['bigramas'] if e['sjis'] not in set(asign.values())]
    libres3 = [c for c, _, t3 in extra if t3]
    libres1 = [c for c, _, t3 in extra if not t3]
    org_extra = {c: o for c, o, _ in extra}
    for c in claves:                               # nombres primero: necesitan glifo propio en las tres fuentes
        if c in asign or c not in claves_nom:
            continue
        if libres88:
            asign[c], origen[c] = libres88.pop(0), 'v88_reasignado'
        else:
            s = libres3.pop(0)
            asign[c], origen[c] = s, org_extra[s]
    for c in claves:
        if c in asign:
            continue
        if libres88:
            asign[c], origen[c] = libres88.pop(0), 'v88_reasignado'
        elif libres1:
            s = libres1.pop(0)
            asign[c], origen[c] = s, org_extra[s]
        else:
            s = libres3.pop(0)
            asign[c], origen[c] = s, org_extra[s]
    assert len(set(asign.values())) == len(asign)

    campos = collections.defaultdict(set)
    for c in claves_rot:
        campos[c].add('rotulo')
    for c in claves_nom:
        campos[c].add('nombre')

    registro = []
    for c in claves:
        s = asign[c]
        ch = bytes.fromhex(s).decode('cp932')
        e = dict(par=R.texto(c), sjis=s, unicode=f'U+{ord(ch):04X}', kanji=ch, origen=origen[c])
        if R.variante(c):
            e.update(clave=c, variante='izquierda' if c[0] == R.IZQ else 'derecha')
        viejo = por_par88.get(c)
        e['fuentes'] = {}
        if viejo is not None and viejo['sjis'] == s:
            e['fuentes'] = {f: dict(v) for f, v in viejo.get('fuentes', {}).items() if f != F12}
        registro.append(e)
    codec = Codec(registro)

    # dibujo --------------------------------------------------------------------------------------------------
    escritor = {F12: A88.V75G.Celdas(fuentes[F12]), F8: A88.V75G.Celdas(fuentes[F8]),
                F12T: A88.CeldasLA4(fuentes[F12T])}

    def pintar(f, gi, px):
        Fu = fuentes[f]
        for y in range(Fu.sy):
            for x in range(Fu.sx):
                escritor[f].escribir(gi, x, y, 0)
        for (x, y), v in px.items():
            assert 0 <= x < Fu.sx - 1 and 0 <= y < Fu.sy - 1, (f, gi, x, y)
            escritor[f].escribir(gi, 1 + x, 1 + y, v)

    for e in registro:
        c = clave_de(e)
        cp = int(e['unicode'][2:], 16)
        # FONT12: maqueta nueva (o el dibujo de v88 si no la admite)
        gi = F.gi(cp)
        m = mq.trozo(c)
        if m.get('medido'):
            e['fuentes'][F12] = dict(glifo=gi, cwdh=list(F.metrics[gi]), maqueta='v88 (sin cambios)')
        else:
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
            assert int((R.CELDA - adv) / 2) + left == D
            sha = hashlib.sha1(json.dumps(sorted(m['px'].items())).encode()).hexdigest()
            e['fuentes'][F12] = dict(glifo=gi, cwdh_antes=viejo, cwdh=[left, ancho, adv], tinta_px=ancho,
                                     columna=D, solido=[m['S0'], m['S1']], hueco_interno=m['g'],
                                     pixeles_sha1=sha, maqueta='v89')
            e.update(glifo=gi, cwdh=[left, ancho, adv], tinta_px=ancho, D=D, R=Rr, pixeles_sha1=sha)
        # FONT8 / FONT12T: solo los pares de nombres/rótulos que aún no tienen su dibujo
        exigidas = set()
        if 'nombre' in campos[c]:
            exigidas = {F8, F12T}
        elif 'rotulo' in campos[c]:
            exigidas = {F8}
        for f in sorted(exigidas):
            if f in e['fuentes']:
                continue
            Fu = fuentes[f]
            gf = Fu.gi(cp)
            px, ancho, left, width, adv, D = pares.glifo(f, c)
            viejo = list(Fu.metrics[gf])
            pintar(f, gf, px)
            Fu.set_metrics(gf, left, width, adv)
            leido = {(x, y): v for y, row in enumerate(Fu.bitmap(gf)) for x, v in enumerate(row) if v}
            esperado = px if f != F12T else {k: max(v >> 4, v & 0xF) for k, v in px.items()}
            assert leido == esperado, (c, f)
            e['fuentes'][f] = dict(glifo=gf, cwdh_kanji=viejo, cwdh=[left, width, adv], tinta_px=ancho, columna=D,
                                   pixeles_sha1=hashlib.sha1(json.dumps(sorted(px.items())).encode()).hexdigest())
    salida = {}
    for f in FUENTES:
        datos = fuentes[f].data()
        assert len(datos) == len(antes_f[f])
        if datos != antes_f[f]:
            salida[f] = datos

    # aplicar ------------------------------------------------------------------------------------------------
    cap_desc = {d['offset']: d['bytes_antes'] for d in inf88['descripciones']}
    tam_v87 = {d['evento']: d['bytes_antes'] for d in inf88['eventos']}
    nom_v87 = {(d['registro'], d['campo']): d['bytes_antes'] for d in inf88['nombres']}
    st2, ub2 = bytearray(st), bytearray(ub)
    ev_cambios = collections.defaultdict(dict)
    cambios = dict(descripcion=[], objetivo=[], nombre=[])
    celdas_de = {}

    def cuerpo(u, part):
        partes, celdas = [], []
        for k, v in u['segs']:
            if k == 'o':
                partes.append(v)
                celdas.append(None)
            else:
                cel = part[v][1]
                assert ''.join(R.texto(c) for c in cel) == v
                partes.append(codec.codificar(cel))
                celdas += cel
                for c in cel:
                    if len(c) >= 2:
                        campos[c].add(u['tipo'])
        return b''.join(partes), celdas

    for u in activas + nombres:
        nuevo, celdas = cuerpo(u, part_nom if u['tipo'] == 'nombre' else res)
        assert codec.texto(nuevo) == codec88.texto(u['body']), u
        assert colapsar(codec.claves(nuevo)) == colapsar(celdas)
        celdas_de[id(u)] = celdas
        vista = '|'.join(R.texto(c) if c else '¤' for c in celdas)
        antes = '|'.join(c if c else '¤' for c in codec88.claves(u['body']))
        if nuevo == u['body']:
            continue
        if u['tipo'] == 'descripcion':
            off = u['offset']
            cap = cap_desc.get(off, len(u['body']))
            assert st[off + len(u['body']):off + cap] == bytes(cap - len(u['body'])), off
            assert len(nuevo) <= cap
            st2[off:off + cap] = nuevo + bytes(cap - len(nuevo))
            cambios['descripcion'].append(dict(offset=off, texto=codec.texto(nuevo), celdas_v88=antes,
                                               celdas=vista, bytes_v87=cap, bytes_v88=len(u['body']),
                                               bytes=len(nuevo)))
        elif u['tipo'] == 'objetivo':
            ev_cambios[u['evento']][u['indice']] = nuevo
            cambios['objetivo'].append(dict(evento=u['evento'], indice=u['indice'], texto=codec.texto(nuevo),
                                            celdas_v88=antes, celdas=vista, bytes_v88=len(u['body']),
                                            bytes=len(nuevo)))
        else:
            v87 = nom_v87.get((u['registro'], u['campo']), len(u['body']))
            assert len(nuevo) <= 15 or v87 == 16, u
            assert len(nuevo) <= max(v87, len(u['body']))
            off = 96 + u['registro'] * 96 + u['campo']
            ub2[off:off + 16] = nuevo + bytes(16 - len(nuevo))
            cambios['nombre'].append(dict(registro=u['registro'], campo=u['campo'], texto=codec.texto(nuevo),
                                          celdas_v88=antes, celdas=vista, bytes_v88=len(u['body']),
                                          bytes=len(nuevo)))
    for u in rotulos:                               # intactos: los mismos bytes decodifican igual
        assert codec.texto(u['body']) == codec88.texto(u['body'])
        assert codec.claves(u['body']) == codec88.claves(u['body'])
    for e in registro:
        e['campos'] = sorted(campos[clave_de(e)])
    assert all(e['campos'] for e in registro)

    out_dir = HERE / 'extra'
    if out_dir.exists():
        shutil.rmtree(out_dir)
    for f, datos in salida.items():
        (out_dir / f).parent.mkdir(parents=True, exist_ok=True)
        (out_dir / f).write_bytes(datos)
    for rel, a, b in ((UNIT, ub, ub2), (USTR, st, st2)):
        assert len(a) == len(b)
        if bytes(b) != a:
            (out_dir / rel).parent.mkdir(parents=True, exist_ok=True)
            (out_dir / rel).write_bytes(bytes(b))
    ev_dir = HERE / 'events'
    if ev_dir.exists():
        shutil.rmtree(ev_dir)
    ev_dir.mkdir()
    tam = []
    for eid, cmb in sorted(ev_cambios.items()):
        assert eid not in A88.PROTEGIDOS and eid not in A88.DONT_TOUCH
        data = eventos[eid]
        nuevo = S.replace(data, cmb)
        _, ops, recs = S.parse(data)
        _, ops2, recs2 = S.parse(nuevo)
        assert ops2 == ops and len(recs2) == len(recs)
        for i, (r1, r2) in enumerate(zip(recs, recs2)):
            if i not in cmb:
                assert (r1.instruction, r1.argument, r1.body) == (r2.instruction, r2.argument, r2.body)
        v87 = tam_v87.get(eid, len(data))
        assert len(nuevo) <= v87, (eid, len(nuevo), v87)
        tam.append(dict(evento=eid, bytes_v87=v87, bytes_v88=len(data), bytes=len(nuevo), registros=sorted(cmb)))
        (ev_dir / f'{eid}.ssd').write_bytes(nuevo)

    # estadísticas (con los dibujos reales de antes y de después) -------------------------------------------
    F12_v89 = tmp / 'FONT12_v89.bcfnt'
    F12_v89.write_bytes(fuentes[F12].data())

    def maqueta_de(ruta, reg):
        Fx = A88.cargar(ruta)
        mx = Maqueta(Fx, A88.codepoint)
        for e in reg:
            mx.fijos[clave_de(e)] = medir(Fx, Fx.gi(int(e['unicode'][2:], 16)))
        return mx
    mq88 = maqueta_de(tmp / 'FONT12.bcfnt', reg88['bigramas'])
    mq89 = maqueta_de(F12_v89, registro)

    def stats(us, cod, mx, nuevo):
        h = collections.Counter()
        for u in us:
            cel = celdas_de[id(u)] if nuevo else cod.claves(u['body'])
            for g, pal in R.huecos(cel, mx):
                h[f"{'palabra' if pal else 'interno'} {g:02d}"] += 1
        return dict(sorted(h.items()))
    est = {}
    for nom, us in (('desc_obj', activas), ('nombres_ficha', nombres)):
        est[nom] = dict(v88=stats(us, codec88, mq88, False), v89=stats(us, codec, mq89, True))

    registro_json = dict(
        descripcion=reg88['descripcion'] + ' v89: descripciones, objetivos y nombres repartidos con ritmo '
                    'uniforme (ritmo.py). «par» es el texto de la casilla (1-4 caracteres, puede llevar '
                    'espacios); las variantes de un glifo llevan «clave» (U+E000 izquierda, U+E001 derecha) y '
                    '«variante». Un par de v88 que sigue en uso conserva su código.',
        version='v89', fuente=F12, fuente_base_sha256=reg88['fuente_base_sha256'],
        regla_codigos=reg88['regla_codigos'] + '; v89: códigos de v88 liberados se reasignan; nuevos: limpios '
                      'del escaneo de v88 y kanji sin aparición en texto cuya aparición textual en binario solo '
                      'está en ficheros gráficos, sin literal en code.bin/CRO (escaneo_literales.py); glifo '
                      'propio en FONT12 (y en FONT8/FONT12T si lo usa un nombre)',
        regla_metricas='v89 FONT12: x = lápiz + trunc((15 - advance)/2) + left = D; advance = D + ancho + R '
                       '(R = 1, o 5 si la casilla acaba en espacio)',
        regla_maqueta=dict(hueco_interno='2 px sólidos (1 si con 2 la tinta sólida pasa de 13)',
                           espacio_interior=R.ESP, tinta_max=R.CELDA,
                           colocacion='solo letras: centrado; espacio delante: tinta sólida hasta la columna 13; '
                                      'espacio detrás: desde la columna 1; variantes: columna 0 (izquierda) o '
                                      'hasta la 14 (derecha)',
                           tinta_solida_max_con_espacio=R.CELDA - R.PAL_MIN,
                           huecos_objetivo='1-2 px dentro de palabra, >= 4 px entre palabras'),
        regla_metricas_FONT8=reg88['regla_metricas_FONT8'],
        regla_metricas_FONT12T=reg88['regla_metricas_FONT12T'],
        espaciado=reg88['espaciado'], campos=reg88['campos'],
        bigramas=registro,
        fuentes_dibujadas={f: hashlib.sha256(fuentes[f].data()).hexdigest() for f in FUENTES},
    )
    (HERE / 'registro.json').write_text(json.dumps(registro_json, ensure_ascii=False, indent=1), encoding='utf-8')
    por_origen = collections.Counter(e['origen'] for e in registro)
    informe = dict(
        base=str(BASE), codigos=len(registro), codigos_por_origen=dict(por_origen),
        codigos_disponibles=total_codigos, rondas_descarte=ronda, trozos_descartados=len(descartados),
        codigos_fuera_de_v88=sorted(e['sjis'] for e in registro if e['sjis'] not in v88_sjis),
        codigos_v88_sin_uso=sorted(v88_sjis - {e['sjis'] for e in registro}),
        claves_rotulo=len(claves_rot), claves_nombre=len(claves_nom), nombres_pares_nuevos=len(nuevas_nom),
        claves_por_tipo=dict(collections.Counter(
            'variante' if R.variante(clave_de(e)) else f'{len(e["par"])} car.' for e in registro)),
        fijos_con_dibujo_v88=sorted(mq.fijos), prohibidos_nombres=prohib_nom,
        fuentes_cambiadas=sorted(salida), huecos=est,
        descripciones_cambiadas=len(cambios['descripcion']), objetivos_cambiados=len(cambios['objetivo']),
        nombres_cambiados=len(cambios['nombre']), eventos=tam,
        eventos_mayores_que_v88=[t for t in tam if t['bytes'] > t['bytes_v88']],
        **cambios,
    )
    (HERE / 'informe.json').write_text(json.dumps(informe, ensure_ascii=False, indent=1), encoding='utf-8')
    print('códigos', len(registro), dict(por_origen), informe['claves_por_tipo'])
    print('cambios: descripciones', len(cambios['descripcion']), 'objetivos', len(cambios['objetivo']),
          'nombres', len(cambios['nombre']), 'eventos', len(tam), 'mayores que v88',
          len(informe['eventos_mayores_que_v88']), 'fuentes', sorted(salida))
    for k, v in est.items():
        print(k, 'v88', v['v88'])
        print(k, 'v89', v['v89'])
    for f in FUENTES:
        print(f, registro_json['fuentes_dibujadas'][f], 'cambiada' if f in salida else 'igual')
    shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    main()
