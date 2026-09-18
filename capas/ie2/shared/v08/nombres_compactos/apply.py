"""IE2 v08 · nombres compactos (unitbase +16 de IE1 e IE2) y rótulos largos (0x4037 arg 3) con casillas
compactas de FONT8. No construye ni instala.

Diagnóstico (diag.py / explorar.py sobre probe_ie2_v05): la pestaña del hablante dibuja cada casilla en
FONT8 a paso fijo de 10 px. Los pares de v87/v88 exigen que el núcleo de las dos letras (con 1 px entre
ellas) quepa en 10 columnas y, además, en FONT12T (<= 14 px): dos letras normales de FONT8 (5-7 px) ya
miden 11-13, así que casi solo entran pares con i/l/r/t/f/j. El resto de letras queda suelta y centrada
en su casilla (núcleo 5-7 px en 10): huecos de 4-6 px («A x e l»). «Silvia» sale bien porque Si|lv|ia
llevan letras estrechas (huecos 2-3).

Diseño (diseno08.py / modelo8.py): cada casilla es un trozo de 1-3 caracteres (rótulos: 1-4 con espacios)
dibujado con su núcleo en una columna elegida dentro de su celda (nombres [0, 10]; rótulos [0, 9]), de
modo que las casillas se pegan a sus vecinas: 1 px dentro de la casilla, 2-3 px entre casillas (como
Silvia), 4-5 px entre palabras. Una casilla = (texto, columna) = un código. Letras nativas y códigos del
registro ya dibujados en FONT8 se usan sin coste; el resto sale de (1) códigos del registro con ese mismo
texto que aún no tienen dibujo en FONT8 (solo se usaban en FONT12) y (2) códigos libres (escaneo).

Salida: registro.json (v07 + casillas v08 al final; entradas reutilizadas ampliadas), extra/font/*.bcfnt,
extra/inazuma{1,2}/data_iz/logic/unitbase.dat, ie1/events/*.ssd, ie2/events/*.ssd,
cambios_registros.json (cuerpos por registro para fusionar con otras capas de eventos), informe.json.
Uso: python -X utf8 work/ie2/shared/capas/v08/nombres_compactos/apply.py
"""
from __future__ import annotations

import collections
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import comun08 as K  # noqa: E402
import diseno08 as D  # noqa: E402
import modelo8 as M8  # noqa: E402

A88, A89, R = K.A88, K.A89, K.R
F12, F8, F12T = K.F12, K.F8, K.F12T
W = K.W
S, C, V79 = A88.S, A88.C, A88.V79
DUMMY = ('ダミー'.encode('cp932'), '未定'.encode('cp932'))
ESPACIO = '　'.encode('cp932')
PLACA = 165
LIMITE_ROT = 10
PROT_IE1 = set(range(92010100, 92010510)) | {81000040}
PROT_IE2 = {22010100, 22010200, 22010300, 22010500}
PK = {'ie1': ('inazuma1/data_iz/script/eve.pkh', 'inazuma1/data_iz/script/eve.pkb'),
      'ie2': ('inazuma2/data_iz/script/eve.pkh', 'inazuma2/data_iz/script/eve.pkb')}
INF88 = W / 'ie1/capas/v88/bigramas_total/informe.json'
TABLA_IE2 = W / 'ie2/tormenta_de_fuego/capas/v03/rotulos/tabla.json'
INF_IE2 = W / 'ie2/tormenta_de_fuego/capas/v03/rotulos/informe.json'
ESC_JP = HERE / 'escaneo_base_jp.json'
ESC_V05 = HERE / 'escaneo_v05.json'
LIT_V08 = HERE / 'escaneo_literales_v08.json'
V07 = W / 'ie2/shared/capas/v07/media'
ESC88 = W / 'ie1/capas/v88/bigramas_total/escaneo_base_v87.json'
LIT89 = W / 'ie1/capas/v89/bigramas_ritmo/literales.json'
LIT90 = W / 'ie1/capas/v90/cro_restantes/escaneo_literales_v90.json'
RONDAS = 3
# formas intermedias (petición del usuario) para rótulos bloqueados solo por el tamaño del evento
INTERMEDIAS = {'Zona de clubes': ['Zona clubes'], 'Tienda maquetas': ['T. maquetas'],
               'Entrada Royal': ['Entr. Royal'], 'Torre (cima)': ['Torre cima'],
               'Junto a las vías': ['Junto vías'],
               **{f'Laboratorio pl. {n}': [f'Lab. pl. {n}', f'Labor. P{n}'] for n in range(1, 5)}}
# copia de work/ie2/shared/capas/v07/media/comun_media.GRAFICOS_V90 (mismo depósito que v07)
GRAFICOS_V90 = re.compile(r'/(pic3d|pic2d|a_field|model|effect3d|face2d|spr|map2d|map3d)/|\.(arc|lzs|pac_)$'
                          r'|(^|/)code\.bin$|\.cr[os]$')


def sha(b):
    return hashlib.sha256(b).hexdigest()


# ---------------------------------------------------------------------------------------------------------
def eventos(get, juego):
    pkh, pkb = get(PK[juego][0]), get(PK[juego][1])
    for eid, o, s in A88.parse_index(pkh):
        c = pkb[o:o + s]
        if not c:
            continue
        yield eid, (A88.decompress(c) if c[:1] == b'\x10' else c)


INF_NOM_IE2 = W / 'ie2/shared/capas/v03/textos/nombres/informe.json'


def oficiales_apostrofo():
    """{(juego, registro): nombre corto oficial con apóstrofo}: IE1 del port europeo 3DS (+32, ’ -> '),
    IE2 de la NDS (v03 nombres: modo «oficial sin apóstrofo»)."""
    import eu08
    out = {}
    eu = eu08.Eu()
    for i in range(2399):
        c = eu.registro(i)['corto'].replace('’', K.APOSTROFO)
        if K.APOSTROFO in c:
            out[('ie1', i)] = c
    for n in json.loads(INF_NOM_IE2.read_text(encoding='utf-8'))['nombres']:
        if K.APOSTROFO in n.get('nds_corto', ''):
            out[('ie2', n['registro'])] = n['nds_corto']
    return out


def recoger_nombres(get, codec):
    apo = oficiales_apostrofo()
    out = []
    for juego in ('ie1', 'ie2'):
        ub = get(K.UNIT[juego])
        for i in range((len(ub) - 96) // 96):
            r = ub[96 + i * 96:192 + i * 96]
            if any(d in r[:32] for d in DUMMY):
                continue
            body = r[16:32].split(b'\0')[0]
            if not body:
                continue
            cl = codec.claves(body)
            if None in cl:
                continue
            t = codec.texto(body)
            u = dict(juego=juego, registro=i, body=body, texto=t)
            of = apo.get((juego, i))
            if of and of.replace(K.APOSTROFO, '').startswith(t) and K.APOSTROFO not in t:
                # apóstrofo oficial restaurado: el nombre completo o, si no cabe, el prefijo más largo
                u['candidatos'] = [of[:n] for n in range(len(of), len(t), -1)] + [t]
                u['apostrofo'] = of
                u['body0'] = r[0:16].split(bytes(1))[0]
            out.append(u)
    return out


CACHE = Path(r'C:/Users/luish/AppData/Local/Temp/claude/C--Users-luish-Projects-inazuma-eleven-123-spanish/'
             r'b57e1d16-53c1-4e5e-b5c8-805598a92e70/scratchpad/v08_rotulos.pkl')


def recoger_rotulos(get, codec):
    """Con caché (fuera del repositorio) de los eventos con rótulo; se invalida si cambia la candidata."""
    import pickle
    clave_cache = (K.CAND.stat().st_size, K.CAND.stat().st_mtime, K.BASE_JP.stat().st_mtime)
    if CACHE.exists():
        c = pickle.loads(CACHE.read_bytes())
        if c['clave'] == clave_cache:
            return _rotulos(c['eventos'], c['jp'], codec)
    ev, jp = {}, {}
    for juego in ('ie1', 'ie2'):
        for eid, data in eventos(get, juego):
            if bytes((0x37, 0x40)) in data:
                ev[(juego, eid)] = data
    jp_get = K.comun88.abrir(K.BASE_JP)
    ids2 = {e for j, e in ev if j == 'ie2'}
    pkh, pkb = jp_get(PK['ie2'][0]), jp_get(PK['ie2'][1])
    for eid, o, s in A88.parse_index(pkh):
        if eid in ids2 and s:
            c = pkb[o:o + s]
            jp[eid] = A88.decompress(c) if c[:1] == bytes((0x10,)) else c
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_bytes(pickle.dumps(dict(clave=clave_cache, eventos=ev, jp=jp)))
    return _rotulos(ev, jp, codec)


def _rotulos(ev, jp_ev, codec):
    """Rótulos (0x4037 arg 3) no protegidos y con índice no reutilizado, con sus textos candidatos."""
    inf88 = json.loads(INF88.read_text(encoding='utf-8'))
    largo_ie1 = {(t['evento'], t['indice']): t['largo'] for t in inf88['textos_evento'] if t['tipo'] == 'rotulo'}
    tabla = json.loads(TABLA_IE2.read_text(encoding='utf-8'))['rotulos']
    abrev = json.loads(INF_IE2.read_text(encoding='utf-8'))['rotulos_abreviados']
    # distinción al estilo IE1: un nombre largo compartido por lugares con abreviaturas distintas
    por_largo = collections.defaultdict(set)
    for jp, cands in tabla.items():
        if cands:
            por_largo[cands[0]].add(jp)
    out, eventos_datos = [], {}
    for (juego, eid), data in sorted(ev.items()):
        prot = PROT_IE1 if juego == 'ie1' else PROT_IE2
        if True:
            try:
                _, ops, recs = S.parse(data)
                refs = C.text_refs(data)
            except (ValueError, KeyError):
                continue
            for i, r in enumerate(recs):
                if (ops.get(r.instruction), r.argument) != (0x4037, 3) or not r.body:
                    continue
                if codec.claves(r.body).count(None):
                    continue
                actual = codec.texto(r.body).strip(' ')
                if not actual:
                    continue
                excl = None
                if eid in prot:
                    excl = 'evento protegido'
                elif any((x[1], x[2]) != (0x4037, 3) for x in refs.get(i, [])):
                    excl = 'índice reutilizado'
                if juego == 'ie1':
                    largo = largo_ie1.get((eid, i))
                    if largo is None:
                        excl = excl or 'sin nombre largo v88'
                        cands = [actual]
                    else:
                        cands = [largo] + ([actual] if actual != largo else [])
                else:
                    try:
                        _, ops_j, recs_j = S.parse(jp_ev[eid])
                        jp = recs_j[i].body.decode('cp932')
                    except (KeyError, IndexError, ValueError, UnicodeDecodeError):
                        jp = None
                    base = tabla.get(jp) if jp else None
                    if not base:
                        excl = excl or 'sin entrada en tabla.json'
                        cands = [actual]
                    else:
                        cands = list(base)
                        if len(por_largo[base[0]]) > 1 and len(base) > 1:
                            suf = base[1].split(' ')[-1]
                            cands = [f'{base[0]} {suf}'] + cands[1:]
                        if actual not in cands:
                            cands.append(actual)
                if cands and cands[0] in INTERMEDIAS:
                    cands = [cands[0]] + [x for x in INTERMEDIAS[cands[0]] if x not in cands] + cands[1:]
                out.append(dict(juego=juego, evento=eid, indice=i, body=r.body, actual=actual,
                                candidatos=cands, largo_original=cands[0], excluido=excl))
                eventos_datos[(juego, eid)] = data
    return out, eventos_datos


# ---------------------------------------------------------------------------------------------------------
def pool_codigos(reg, Fs):
    """Códigos libres en orden: restos del depósito v07 (escaneo v88 + literales v89/v90) y los del escaneo
    v08 sobre probe_ie2_v05 (escaneo08.py: sin aparición en texto; apariciones «textuales» solo en ficheros
    gráficos, como el criterio de v89/v07; sin literal en code.bin/CRO: escaneo_literales08.py)."""
    usados = {e['sjis'] for e in reg['bigramas']}
    inv = K.inversos(Fs)

    def unico3(c):
        return all(A89.unico(Fs[f], inv[f], c) for f in K.FUENTES)
    esc = json.loads(ESC88.read_text(encoding='utf-8'))
    lit = json.loads(LIT89.read_text(encoding='utf-8'))
    lit.update(json.loads(LIT90.read_text(encoding='utf-8')))
    out = []
    graf = []
    for c, v in esc['codigos'].items():
        if c in usados or int(c, 16) < 0x889F or v.get('texto'):
            continue
        if c not in lit or lit[c] or not unico3(c):
            continue
        if c in esc['limpios']:
            out.append((c, 'v07_resto_limpio_v88'))
            continue
        rutas = [r for r, _ in esc['apariciones_textuales'].get(c, [])]
        if all(GRAFICOS_V90.search(r) for r in rutas):
            graf.append((len(rutas), sum(v.values()), c))
    out += [(c, 'v07_resto_solo_graficos') for _, _, c in sorted(graf)]
    if ESC_V05.exists() and LIT_V08.exists():
        v5 = json.loads(ESC_V05.read_text(encoding='utf-8'))
        litv = json.loads(LIT_V08.read_text(encoding='utf-8'))
        ext_e, ext_l = HERE / 'escaneo_v05_extra.json', HERE / 'escaneo_literales_extra.json'
        if ext_e.exists() and ext_l.exists():         # 101 códigos no kanji (griego, cirílico, NEC, IBM)
            e2 = json.loads(ext_e.read_text(encoding='utf-8'))
            v5 = dict(v5, codigos={**v5['codigos'], **e2['codigos']},
                      apariciones_textuales={**v5['apariciones_textuales'], **e2['apariciones_textuales']})
            litv = {**litv, **json.loads(ext_l.read_text(encoding='utf-8'))}
        limpios, graf = [], []
        for c, v in v5['codigos'].items():
            if c in usados or v.get('texto') or c not in litv or litv[c] or not unico3(c):
                continue
            rutas = [r for r, _ in v5['apariciones_textuales'].get(c, [])]
            if not rutas:
                limpios.append(c)
            elif all(GRAFICOS_V90.search(r) for r in rutas):
                graf.append((len(rutas), sum(v.values()), c))
        out += [(c, 'v08_limpio') for c in sorted(limpios)]
        out += [(c, 'v08_solo_graficos') for _, _, c in sorted(graf)]
    vistos = set()
    return [(c, o) for c, o in out if not (c in vistos or vistos.add(c))]


# ---------------------------------------------------------------------------------------------------------
def main():
    sys.stdout.reconfigure(encoding='utf-8')
    reg, Fs, antes_f, tmp = K.cargar_fuentes()
    codec = A89.Codec(reg['bigramas'])
    get = K.comun88.abrir(K.CAND)
    Dz = D.Diseno(reg, Fs)

    nombres = recoger_nombres(get, codec)
    for u in nombres:
        if 'candidatos' in u:
            u['texto_antes'] = u['texto']
            for t in u['candidatos']:
                if Dz.partir('nombre', t, 7)[0] < M8.INF:
                    u['texto'] = t
                    break
    rotulos, ev_datos = recoger_rotulos(get, codec)
    textos_nom = collections.Counter(u['texto'] for u in nombres)
    rot_act = [u for u in rotulos if not u['excluido']]
    print('nombres', len(nombres), 'distintos', len(textos_nom), 'rótulos', len(rotulos), 'activos', len(rot_act))

    # ---- rondas de partición --------------------------------------------------------------------------
    def rotulo_de(u, part):
        """(texto elegido, sel, k) del primer candidato que cabe en 10 casillas con su centrado."""
        for t in u['candidatos']:
            cst, sel = part('rotulo', t, LIMITE_ROT)
            if cst == M8.INF:
                continue
            k = min(centrado(sel), u.get('k_max', LIMITE_ROT))
            if k + len(sel) <= LIMITE_ROT:
                return t, sel, k
        return None

    def centrado(sel):
        """Espacios nativos delante para centrar la tinta en la placa de 165 px (origen del texto = borde
        izquierdo de la placa; paso 10)."""
        xs = []
        for j, (c, o, w) in enumerate(sel):
            if c != ' ':
                xs += [10 * j + o, 10 * j + o + w - 1]
        mid = (min(xs) + max(xs) + 1) / 2
        k = int((PLACA / 2 - mid) / 10 + 0.5)
        return max(0, min(k, LIMITE_ROT - len(sel)))

    cache = {}

    def part(campo, t, nmax):
        k = (campo, t)
        if k not in cache:
            while True:
                cst, sel = Dz.partir(campo, t, nmax)
                if cst == M8.INF:
                    break
                malos = Dz.fallos(sel, campo)
                if not malos:
                    break
                Dz.prohibidos[(campo, t)] |= malos
            cache[k] = (cst, sel)
        return cache[k]

    elegido_rot = {}
    for ronda in range(RONDAS):
        cache.clear()
        uso = collections.Counter()
        for t, n in textos_nom.items():
            cst, sel = part('nombre', t, 7)
            assert cst < M8.INF, t
            uso.update({c: n for c, _, _ in sel if c.startswith(D.PREF)})
        for u in rot_act:
            r = rotulo_de(u, part)
            elegido_rot[id(u)] = r
            if r:
                uso.update(c for c, _, _ in r[1] if c.startswith(D.PREF))
        print('ronda', ronda, 'casillas nuevas', len(uso), flush=True)
        Dz.coste = {c: (0.1 if v >= 4 else 0.4 if v >= 2 else 0.8) for c, v in uso.items()}
        Dz.coste_def = 1.2

    # ---- tamaño de eventos: los rótulos no pueden agrandar su evento ---------------------------------
    def cuerpo_rot(u, r, cod):
        t, sel, k = r
        return ESPACIO * k + b''.join(cod(c) for c, _, _ in sel)

    def provisional(c):
        return ESPACIO if c == ' ' else (V79.codificar(c) if len(c) == 1 else b'\x98\x9f')

    def ajustar_tamano():
        for (juego, eid), data in ev_datos.items():
            us = [u for u in rot_act if u['juego'] == juego and u['evento'] == eid]
            while True:
                cambios = {}
                for u in us:
                    r = elegido_rot[id(u)]
                    if r is None:
                        continue
                    b = cuerpo_rot(u, r, provisional)
                    if b != u['body']:
                        cambios[u['indice']] = b
                if not cambios or len(S.replace(data, cambios)) <= len(data):
                    break
                # 1) espacios de centrado por encima de los de v05; 2) abreviar; 3) menos espacios que en v05
                def k_v05(u):
                    n, b = 0, u['body']
                    while b[2 * n:2 * n + 2] == ESPACIO:
                        n += 1
                    return n
                etapa1 = [u for u in us if elegido_rot[id(u)] and elegido_rot[id(u)][2] > k_v05(u)]
                crecen = [u for u in us if elegido_rot[id(u)] and len(u['candidatos']) > 1
                          and len(cuerpo_rot(u, elegido_rot[id(u)], provisional)) > len(u['body'])
                          and u['candidatos'].index(elegido_rot[id(u)][0]) + 1 < len(u['candidatos'])]
                etapa3 = [u for u in us if elegido_rot[id(u)] and elegido_rot[id(u)][2] > 0]
                inter = {x for v in INTERMEDIAS.values() for x in v}
                # una forma intermedia (petición del usuario) se conserva quitando centrado antes que abreviarla
                crecen = [u for u in crecen if not (elegido_rot[id(u)][0] in inter and elegido_rot[id(u)][2] > 0)]
                if etapa1 or (not crecen and etapa3):
                    peor = max(etapa1 or etapa3, key=lambda u: elegido_rot[id(u)][2])
                    peor['k_max'] = elegido_rot[id(peor)][2] - 1
                    peor['centrado_reducido_por_tamano'] = True
                else:
                    assert crecen, (juego, eid)
                    peor = max(crecen, key=lambda u: len(cuerpo_rot(u, elegido_rot[id(u)], provisional)) - len(u['body']))
                    t0 = elegido_rot[id(peor)][0]
                    peor['candidatos'] = peor['candidatos'][peor['candidatos'].index(t0) + 1:]
                    peor['abreviado_por_tamano'] = True
                elegido_rot[id(peor)] = rotulo_de(peor, part)

    # mismo lugar, mismo nombre en todos sus eventos: si una aparición tuvo que abreviarse por tamaño, se
    # abrevian todas y se repite el ajuste (abreviar nunca agranda)
    while True:
        ajustar_tamano()
        por_lugar = collections.defaultdict(list)
        for u in rot_act:
            if elegido_rot[id(u)]:
                por_lugar[(u['juego'], u['largo_original'])].append(u)
        cambio = False
        for us_l in por_lugar.values():
            textos = {elegido_rot[id(u)][0] for u in us_l}
            if len(textos) <= 1:
                continue
            # el texto más abreviado del grupo (el más avanzado en su lista de candidatos)
            peor = max(us_l, key=lambda u: u['largo_original'] != elegido_rot[id(u)][0] and
                       len(u['largo_original']) - len(elegido_rot[id(u)][0]))
            t_min = elegido_rot[id(peor)][0]
            for u in us_l:
                if elegido_rot[id(u)][0] != t_min and t_min in u['candidatos']:
                    u['candidatos'] = u['candidatos'][u['candidatos'].index(t_min):]
                    u['abreviado_por_coherencia'] = True
                    elegido_rot[id(u)] = rotulo_de(u, part)
                    cambio = True
        if not cambio:
            break

    # ---- códigos ----------------------------------------------------------------------------------------
    usadas = collections.Counter()
    campos_de = collections.defaultdict(set)
    part_nom = {t: part('nombre', t, 7)[1] for t in textos_nom}
    for u in nombres:
        for c, _, _ in part_nom[u['texto']]:
            if c != ' ' and (c.startswith(D.PREF) or c in Dz.por_clave):
                campos_de[c].add(f"nombre_{u['juego']}")
                usadas[c] += 1
    for u in rot_act:
        r = elegido_rot[id(u)]
        if r:
            for c, _, _ in r[1]:
                if c != ' ' and (c.startswith(D.PREF) or c in Dz.por_clave):
                    campos_de[c].add(f"rotulo_{u['juego']}")
                    usadas[c] += 1
    # apóstrofo suelto (petición del usuario): código propio aunque ningún nombre lo use solo
    suelto = D.clave_nueva(K.APOSTROFO, 4)
    campos_de[suelto].add('nombre_apostrofo_suelto')
    usadas[suelto] += 0
    nuevas = sorted((c for c in usadas if c.startswith(D.PREF)), key=lambda c: (-usadas[c], c))
    # (1) reutilizables: mismo texto, sin FONT8, FONT12 de maqueta v89/v88 (no subtítulos ni literales CRO)
    reutil = collections.defaultdict(list)
    for e in reg['bigramas']:
        cl = A89.clave_de(e)
        if F8 in e['fuentes'] or R.variante(cl) or cl != e['par']:
            continue
        maq = e['fuentes'].get(F12, {}).get('maqueta', 'v88')
        if maq not in ('v89', 'v88', 'v88 (sin cambios)'):
            continue
        if not any(x in ('descripcion', 'objetivo') for x in e.get('campos', [])) or \
                any(x not in ('descripcion', 'objetivo') for x in e.get('campos', [])):
            continue
        reutil[e['par']].append(e)
    pool = pool_codigos(reg, Fs)
    asign = {}
    for c in nuevas:
        t, o = D.de_clave(c)
        if reutil.get(t):
            asign[c] = ('reutilizado', reutil[t].pop(0))
    faltan = [c for c in nuevas if c not in asign]
    print('casillas nuevas', len(nuevas), 'reutilizadas', len(asign), 'con código libre', len(faltan),
          'depósito', len(pool), collections.Counter(o for _, o in pool))
    if len(faltan) > len(pool):
        raise SystemExit(f'faltan códigos: {len(faltan)} > {len(pool)}')
    for c, (s, origen) in zip(faltan, pool):
        asign[c] = ('nuevo', s, origen)
    (HERE / 'deposito_restante.json').write_text(json.dumps([s for s, _ in pool[len(faltan):]]), encoding='utf-8')

    # ---- dibujo ------------------------------------------------------------------------------------------
    escritor = {F12: A88.V75G.Celdas(Fs[F12]), F8: A88.V75G.Celdas(Fs[F8]), F12T: A88.CeldasLA4(Fs[F12T])}

    def pintar(f, gi, px):
        Fu = Fs[f]
        for y in range(Fu.sy):
            for x in range(Fu.sx):
                escritor[f].escribir(gi, x, y, 0)
        for (x, y), v in px.items():
            assert 0 <= x < Fu.sx - 1 and 0 <= y < Fu.sy - 1, (f, gi, x, y)
            escritor[f].escribir(gi, 1 + x, 1 + y, v)

    def sha1(px):
        return hashlib.sha1(json.dumps(sorted(px.items())).encode()).hexdigest()

    registro = [dict(e) for e in reg['bigramas']]
    por_sjis = {e['sjis']: e for e in registro}
    añadidas, reutilizadas = [], []
    for c in nuevas:
        t, o = D.de_clave(c)
        a = asign[c]
        if a[0] == 'reutilizado':
            e = por_sjis[a[1]['sjis']]
            e['fuentes'] = dict(e['fuentes'])
            reutilizadas.append(dict(sjis=e['sjis'], par=t, columna_font8=o, clave_v08=c))
        else:
            s = a[1]
            ch = bytes.fromhex(s).decode('cp932')
            e = dict(par=t, sjis=s, unicode=f'U+{ord(ch):04X}', kanji=ch, origen=a[2], clave=c,
                     variante=f'v08 casilla compacta FONT8 (núcleo en la columna {o})', fuentes={})
            registro.append(e)
            por_sjis[s] = e
            añadidas.append(c)
        cp = int(e['unicode'][2:], 16)
        nombre = any(x.startswith('nombre') for x in campos_de[c])
        # FONT8
        Fu = Fs[F8]
        gi = Fu.gi(cp)
        px, c0, left, width, adv = Dz.L8.dibujo(t, o, D.BMAX['nombre'])
        viejo = list(Fu.metrics[gi])
        pintar(F8, gi, px)
        Fu.set_metrics(gi, left, width, adv)
        leido = {(x, y): v for y, row in enumerate(Fu.bitmap(gi)) for x, v in enumerate(row) if v}
        assert leido == px, c
        assert int((11 - adv) / 2) + left == c0
        e['fuentes'][F8] = dict(glifo=gi, cwdh_antes=viejo, cwdh=[left, width, adv], nucleo_px=Dz.L8.trozo(t)['w'],
                                columna=o, pixeles_sha1=sha1(px), maqueta='v08 nombres compactos (paso 10)')
        # FONT12 (solo códigos nuevos: los reutilizados ya lo tienen)
        if a[0] == 'nuevo':
            F = Fs[F12]
            gi = F.gi(cp)
            m = Dz.f12(t)
            viejo = list(F.metrics[gi])
            if m == 'nativa':
                gn = F.gi(A88.codepoint(t))
                px = {(x, y): v for y, row in enumerate(F.bitmap(gn)) for x, v in enumerate(row) if v}
                left, width, adv = F.metrics[gn]
                pintar(F12, gi, px)
                F.set_metrics(gi, left, width, adv)
                info = dict(maqueta='v08 copia de la letra nativa')
            else:
                ancho, Dd = m['ancho'], m['D']
                Rr = 5 if t.endswith(' ') else 1
                adv = Dd + ancho + Rr
                left = Dd - int((15 - adv) / 2)
                px = m['px']
                pintar(F12, gi, px)
                F.set_metrics(gi, left, ancho, adv)
                width = ancho
                info = dict(maqueta='v89', columna=Dd, solido=[m['S0'], m['S1']], hueco_interno=m['g'])
            leido = {(x, y): v for y, row in enumerate(F.bitmap(gi)) for x, v in enumerate(row) if v}
            assert leido == px, c
            e['fuentes'][F12] = dict(glifo=gi, cwdh_antes=viejo, cwdh=[left, width, adv], pixeles_sha1=sha1(px), **info)
            e.update(glifo=gi, cwdh=[left, width, adv], pixeles_sha1=sha1(px))
        # FONT12T (nombres)
        if nombre and F12T not in e['fuentes']:
            Ft = Fs[F12T]
            gi = Ft.gi(cp)
            px, Wt, Dt = Dz.f12t(t)
            viejo = list(Ft.metrics[gi])
            pintar(F12T, gi, px)
            Ft.set_metrics(gi, Dt, Wt, 16)
            leido = {(x, y): v for y, row in enumerate(Ft.bitmap(gi)) for x, v in enumerate(row) if v}
            assert leido == {k: max(v >> 4, v & 0xF) for k, v in px.items()}, c
            e['fuentes'][F12T] = dict(glifo=gi, cwdh_kanji=viejo, cwdh=[Dt, Wt, 16], tinta_px=Wt, columna=Dt,
                                      pixeles_sha1=sha1(px), maqueta='v08 (<= 16 px, contorno compartible)')
        e['campos'] = sorted(set(e.get('campos', [])) | campos_de[c])
    for c in usadas:
        if not c.startswith(D.PREF):
            e = por_sjis[Dz.por_clave[c]['sjis']]
            e['campos'] = sorted(set(e.get('campos', [])) | campos_de[c])

    salida = {}
    for f in K.FUENTES:
        datos = Fs[f].data()
        assert len(datos) == len(antes_f[f])
        if datos != antes_f[f]:
            salida[f] = datos

    # ---- cuerpos ----------------------------------------------------------------------------------------
    clave_sjis = {}
    for c in nuevas:
        a = asign[c]
        clave_sjis[c] = bytes.fromhex(a[1]['sjis'] if a[0] == 'reutilizado' else a[1])
    for c in usadas:
        if not c.startswith(D.PREF):
            clave_sjis[c] = bytes.fromhex(Dz.por_clave[c]['sjis'])

    def cod(c):
        if c == ' ':
            return ESPACIO
        if c in clave_sjis:
            return clave_sjis[c]
        assert len(c) == 1, c
        return V79.codificar(c)

    codec2 = A89.Codec(registro)
    ubs = {j: bytearray(get(K.UNIT[j])) for j in ('ie1', 'ie2')}
    cambios_nom = []
    for u in nombres:
        sel = part_nom[u['texto']]
        nuevo = b''.join(cod(c) for c, _, _ in sel)
        assert codec2.texto(nuevo) == u['texto'], (u, nuevo)
        if 'texto_antes' in u:
            codec2_ok = u['texto'].replace(K.APOSTROFO, '').startswith(u['texto_antes'][:len(u['texto']) - 1])
            assert codec2_ok, u
        assert len(sel) <= 7 and len(nuevo) <= 15, u
        off = 96 + u['registro'] * 96 + 16
        ubs[u['juego']][off:off + 16] = nuevo + bytes(16 - len(nuevo))
        if 'apostrofo' in u and u['texto'] != u['texto_antes']:
            # la ficha (+0) llevaba el mismo nombre sin apóstrofo: se pone el mismo cuerpo
            assert codec.texto(u['body0']) == u['texto_antes'], u
            ubs[u['juego']][off - 16:off] = nuevo + bytes(16 - len(nuevo))
        h_antes = Dz.huecos8([(c, *medir_sel(Dz, c)) for c in codec.claves(u['body'])])
        h = Dz.huecos8(sel)
        if nuevo != u['body']:
            cambios_nom.append(dict(juego=u['juego'], registro=u['registro'], texto=u['texto'],
                                    texto_antes=u.get('texto_antes', u['texto']),
                                    apostrofo_oficial=u.get('apostrofo'),
                                    casillas_antes='|'.join(codec.claves(u['body'])),
                                    casillas='|'.join(vista(Dz, c, o) for c, o, _ in sel),
                                    huecos_antes=[g for g, _ in h_antes], huecos=[g for g, _ in h],
                                    bytes_antes=len(u['body']), bytes=len(nuevo)))
    out_dir = HERE / 'extra'
    if out_dir.exists():
        shutil.rmtree(out_dir)
    for f, datos in salida.items():
        (out_dir / f).parent.mkdir(parents=True, exist_ok=True)
        (out_dir / f).write_bytes(datos)
    for j, b in ubs.items():
        if bytes(b) != get(K.UNIT[j]):
            p = out_dir / K.UNIT[j]
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(bytes(b))

    ev_cambios = collections.defaultdict(dict)
    filas_rot, no_caben = [], []
    for u in rotulos:
        if u['excluido']:
            continue
        r = elegido_rot[id(u)]
        largo = u['candidatos'][0]
        if r is None:
            no_caben.append(dict(juego=u['juego'], evento=u['evento'], indice=u['indice'], actual=u['actual'],
                                 candidatos=u['candidatos'], motivo='ningún candidato cabe'))
            continue
        t, sel, k = r
        nuevo = cuerpo_rot(u, r, cod)
        assert len(nuevo) <= 20 and k + len(sel) <= LIMITE_ROT
        assert codec2.texto(nuevo).strip(' ') == t, (u, t)
        if nuevo != u['body']:
            ev_cambios[(u['juego'], u['evento'])][u['indice']] = nuevo
        filas_rot.append(dict(juego=u['juego'], evento=u['evento'], indice=u['indice'], antes=u['actual'],
                              despues=t, largo_pedido=u.get('largo_original', largo), espacios=k,
                              casillas='|'.join(vista(Dz, c, o) for c, o, _ in sel), total_casillas=k + len(sel),
                              huecos=[g for g, _ in Dz.huecos8(sel)], bytes_antes=len(u['body']), bytes=len(nuevo),
                              abreviado_por_tamano=u.get('abreviado_por_tamano', False),
                              centrado_reducido_por_tamano=u.get('centrado_reducido_por_tamano', False),
                              abreviado_por_coherencia=u.get('abreviado_por_coherencia', False)))
    for j in ('ie1', 'ie2'):
        d = HERE / j / 'events'
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)
    tam, por_registro = [], []
    for (j, eid), cmb in sorted(ev_cambios.items()):
        data = ev_datos[(j, eid)]
        prot = PROT_IE1 if j == 'ie1' else PROT_IE2
        assert eid not in prot
        nuevo = S.replace(data, cmb)
        _, ops, recs = S.parse(data)
        _, ops2, recs2 = S.parse(nuevo)
        assert ops2 == ops and len(recs2) == len(recs)
        for i, (r1, r2) in enumerate(zip(recs, recs2)):
            if i not in cmb:
                assert (r1.instruction, r1.argument, r1.body) == (r2.instruction, r2.argument, r2.body)
        assert len(nuevo) <= len(data), (j, eid, len(nuevo), len(data))
        (HERE / j / 'events' / f'{eid}.ssd').write_bytes(nuevo)
        tam.append(dict(juego=j, evento=eid, bytes_antes=len(data), bytes=len(nuevo), registros=sorted(cmb)))
        for i, b in sorted(cmb.items()):
            por_registro.append(dict(juego=j, paquete=PK[j][1], evento=eid, indice=i, arg=3, opcode='0x4037',
                                     cuerpo_antes=recs[i].body.hex(), cuerpo=b.hex()))
    (HERE / 'cambios_registros.json').write_text(json.dumps(dict(
        nota='Cuerpos por registro (base probe_ie2_v05) para fusionar con otras capas que reescriben los '
             'mismos eventos completos (p. ej. work/ie1/capas/v91). Contiene texto del juego: no publicar.',
        registros=por_registro), ensure_ascii=False, indent=1), encoding='utf-8')

    # ---- registro e informe ----------------------------------------------------------------------------
    reg_out = dict(reg)
    reg_out['version'] = 'ie2_v08_nombres_compactos'
    reg_out['descripcion'] = (reg['descripcion'] + ' IE2 v08 (work/ie2/shared/capas/v08/nombres_compactos): '
                              'casillas compactas de FONT8 para los nombres +16 de IE1/IE2 y los rótulos. Clave '
                              'U+E004 columna U+E004 texto; la columna es la del núcleo (alfa >= 8) respecto al '
                              'lápiz en FONT8. Algunas entradas anteriores sin dibujo FONT8 (solo descripciones/'
                              'objetivos) reciben dibujo FONT8/FONT12T y campo nombre/rótulo (ver pares_ie2_v08_reutilizados).')
    reg_out['regla_metricas_FONT8_v08'] = ('x = lápiz + trunc((11 - advance)/2) + left; advance = núcleo (+4 con espacio); '
                                           'núcleo en [0, 10] (nombres) o [0, 9] (rótulos); halo fuera de [0, 10] recortado; '
                                           '1 px entre letras, 4 px por espacio')
    reg_out['regla_metricas_FONT12T_v08'] = ('relleno de FONT12 (alfa >= 6) bajado 1 fila + contorno 1 px; 2 px entre '
                                             'rellenos (1 si no cabe); ancho <= 16; left = D (centrado en 15, 0 si 16); advance 16')
    reg_out['bigramas'] = registro
    reg_out['fuentes_dibujadas'] = {f: sha(Fs[f].data()) for f in K.FUENTES}
    reg_out['pares_ie2_v08'] = añadidas
    reg_out['pares_ie2_v08_reutilizados'] = reutilizadas
    (HERE / 'registro.json').write_text(json.dumps(reg_out, ensure_ascii=False, indent=1), encoding='utf-8')

    hist = {}
    for nom, lista in (('antes', 'huecos_antes'), ('despues', 'huecos')):
        hc = collections.Counter(g for x in cambios_nom for g in x[lista])
        hist[nom] = dict(sorted(hc.items()))
    informe = dict(
        capa=str(HERE.relative_to(K.ROOT)), base=str(K.CAND.relative_to(K.ROOT)),
        nota='Contiene texto del juego: no publicar. Validación offline; pendiente de prueba en Azahar.',
        fuentes_base={f: sha(antes_f[f]) for f in K.FUENTES}, fuentes_salida=reg_out['fuentes_dibujadas'],
        fuentes_cambiadas=sorted(salida),
        codigos=dict(casillas_nuevas=len(nuevas), reutilizados=len(reutilizadas), nuevos=len(añadidas),
                     nuevos_por_origen=dict(collections.Counter(asign[c][2] for c in añadidas)),
                     deposito_total=len(pool), deposito_sobrante=len(pool) - len(añadidas),
                     deposito_por_origen=dict(collections.Counter(o for _, o in pool)),
                     por_campo={k: sum(1 for c in nuevas if k in campos_de[c]) for k in
                                ('nombre_ie1', 'nombre_ie2', 'rotulo_ie1', 'rotulo_ie2')}),
        nombres=dict(registros=len(nombres), distintos=len(textos_nom),
                     cambiados={j: sum(1 for x in cambios_nom if x['juego'] == j) for j in ('ie1', 'ie2')},
                     huecos_nombres_cambiados=hist,
                     con_hueco_mayor_de_3=sorted({x['texto'] for x in cambios_nom
                                                  if any(g > 3 for g, p in zip(x['huecos'], [0] * 99))
                                                  and ' ' not in x['texto']}),
                     prohibidos={f'{k[0]}|{k[1]}': sorted(v) for k, v in Dz.prohibidos.items() if v}),
        rotulos=dict(registros=len(rotulos), excluidos=[{k: v for k, v in u.items() if k != 'body'}
                                                        for u in rotulos if u['excluido']],
                     cambiados={j: sum(1 for x in filas_rot if x['juego'] == j and x['bytes'] != x['bytes_antes'] or
                                       x['juego'] == j and x['antes'] != x['despues']) for j in ('ie1', 'ie2')},
                     largos_que_no_caben=sorted({(x['juego'], x['largo_pedido'], x['despues']) for x in filas_rot
                                                 if x['despues'] != x['largo_pedido']}),
                     sin_candidato=no_caben),
        eventos=tam, cambios_nombres=cambios_nom, cambios_rotulos=filas_rot,
    )
    (HERE / 'informe.json').write_text(json.dumps(informe, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(informe['codigos'], ensure_ascii=False))
    print('nombres cambiados', informe['nombres']['cambiados'], 'huecos', hist)
    print('rótulos', informe['rotulos']['cambiados'], 'no caben', informe['rotulos']['largos_que_no_caben'])
    print('eventos', len(tam), 'fuentes', sorted(salida))
    shutil.rmtree(tmp, ignore_errors=True)


def medir_sel(Dz, c):
    if c == ' ':
        return None, 0
    if len(c) == 1:
        return Dz.L8.nativa(c)
    return Dz.medir8(Dz.por_clave[c])


def vista(Dz, c, o):
    if c == ' ':
        return '␣'
    t = Dz.texto_de(c)
    if c.startswith(D.PREF):
        return f'{t}@{o}'
    return t if len(c) == 1 else f'{t}#'


if __name__ == '__main__':
    main()
