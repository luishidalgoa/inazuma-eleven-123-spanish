"""IE2 v03 · tablas A · lista de trabajo (worklist.json) emparejada por ID con el NDS ES.

Emparejado (nunca por orden de cadenas):
  command   registro i (28 B) 3DS <-> registro i NDS; punteros +20/+22. Verificación: resto del registro igual.
  item      registro i (3DS 36 B / NDS 48 B); cola 3DS +20 = NDS +32. Verificación: cola sin punteros/precio.
  rpgtitle  hueco i <-> hueco i; rpgtitle.dat +30 == i y rpgtitle.dat idéntico al NDS.
  jinmyaku  sucesos por `kind`, pistas por `id` (parser wide); aristas idénticas.
  fieldinf  clave (mapa +0, nombre) contra el NDS japonés logic/fieldinf.dat; su índice da el ES de logic01/sp.
  gamerule  registro i (288 B); cabecera +0..+32 idéntica al NDS.
  games     sin texto ES en el NDS (logic/games.STR sigue en japonés): se usa el ES oficial de gamerule
            con el mismo japonés (puente por texto japonés, mismo campo de objetivo).

Texto propuesto (sin parafrasear; norma del usuario 2026-09-17):
  oficial  el NDS tal cual (normalizado: sin comillas/apóstrofos, sin caracteres sin glifo).
  recorte  el NDS quitando palabras/frases enteras, o la palabra del tipo (objetos), o abreviatura fija.
  manual   manual.json (recorte a mano, siempre con motivo).
Uso: python -X utf8 preparar.py
"""
from __future__ import annotations

import json
import re
import struct
from itertools import combinations

import tablas as T

ABREV = {'Regate': 'R.', 'Tornado': 'Tor.'}          # abreviaturas fijas de IE1 (skill §10)
TIPO_OBJ = ('Botas de ', 'Botas ', 'Guantes de ', 'Guantes ', 'Pulsera de ', 'Pulsera ', 'Equipo ', 'Llave de ',
            'Llave ', 'Nota de ', 'Hojas de ', 'Medalla ', 'Colgante ', 'Ropa de ', 'Zapatos ')
CONECT = re.compile(r' (de|del|la|el|los|las) ')
CONECTORES = {'de', 'del', 'la', 'el', 'los', 'las', 'a', 'con', 'en', 'y'}
GENERICAS = {'Botas', 'Guantes', 'Pulsera', 'Equipo', 'Calzado', 'Manoplas', 'Colgante', 'Medalla', 'Llave',
             'Nota', 'Hojas', 'Ropa', 'Zapatos', 'Tornado', 'Regate', 'Remate', 'Tiro', 'Disparo', 'Chut',
             'Despeje', 'Muralla', 'Escudo', 'Barrido', 'Ataque', 'Corte', 'Cabezazo', 'Entrada', 'Bloqueo',
             'Técnica', 'Tarjeta', 'Flecha', 'Fuerza', 'Amuleto'}
CLAVE_EFECTO = re.compile(r'\b(PE|PT|Aumenta|Recupera|Devuelve|Restablece|Permite|Abre|Enseña|técnica|Sube|Mejora|Llave)\b')
MANUAL_RE = re.compile(r'^Cuaderno que enseña la técnica (ofensiva |defensiva |de disparo |de tiro |de portero |)(.+)$')


def tokens(s):
    return [w for w in re.split(r'[\s.,;:¡!¿?()…]+', s.lower()) if w]


def es_recorte(corto: str, oficial: str) -> bool:
    """El corto solo quita palabras (o usa una abreviatura fija) del oficial, en orden."""
    a, b = tokens(corto), tokens(oficial)
    abrev = {v.lower().rstrip('.'): k.lower() for k, v in ABREV.items()}
    j = 0
    for w in a:
        w2 = abrev.get(w, w)
        while j < len(b) and b[j] != w2:
            j += 1
        if j == len(b):
            return False
        j += 1
    return True


def frases(t):
    out = []
    for f in re.split(r'(?<=[.!?…])\s+', T.plano(t)):
        if out and re.search(r'(^|\s)\w\.$', out[-1]):      # «S. Stevens», «n.º»: no es fin de frase
            out[-1] += ' ' + f
        elif f:
            out.append(f)
    return out


def recorte_desc(oficial, cabe):
    """Primer recorte por palabras que cabe: frases enteras, luego plantilla de manual."""
    fs = frases(oficial)
    mejor = None
    for n in range(len(fs) - 1, 0, -1):
        for comb in combinations(range(len(fs)), n):
            t = ' '.join(fs[i] for i in comb)
            if cabe(t):
                primera = 0 in comb and len(fs[0].split()) >= 3      # la frase que describe la acción
                puntos = (bool(CLAVE_EFECTO.search(t)), primera, len(t))
                if mejor is None or puntos > mejor[0]:
                    mejor = (puntos, t)
        if mejor:
            return mejor[1], 'se quitan frases enteras'
    m = MANUAL_RE.match(T.plano(oficial))
    if m:
        for t in (f'Enseña la técnica {m.group(1)}{m.group(2)}', f'Enseña la técnica {m.group(2)}',
                  f'Enseña {m.group(2)}'):
            if cabe(t):
                return t, 'manual: se quita «Cuaderno que» (y el tipo de técnica)'
    return None, None


def recorte_nombre(oficial, limite, tipo=True):
    cands = []
    if len(oficial) <= limite:
        return oficial, None
    s = CONECT.sub(' ', f' {oficial} ').strip()
    cands.append((s, 'sin conectores'))
    if tipo:
        for p in TIPO_OBJ:
            if oficial.startswith(p):
                r = oficial[len(p):]
                cands.append((r[0].upper() + r[1:], 'sin la palabra del tipo (el icono lo indica)'))
    w = oficial.split(' ', 1)
    if len(w) == 2 and w[0] in ABREV:
        cands.append((ABREV[w[0]] + w[1], f'abreviatura fija {ABREV[w[0]]}'))
        cands.append((ABREV[w[0]] + CONECT.sub(' ', f' {w[1]} ').strip(), f'abreviatura fija {ABREV[w[0]]} sin conectores'))
    for t, m in cands:
        if len(t) <= limite:
            return t, m
    if not tipo:
        # técnicas (15): abreviatura al estilo aprobado en IE1 («Remate serpien.»): se corta la última palabra
        base = s if len(s) < len(oficial) else oficial
        pre, _, ult = base.rpartition(' ')
        if pre and len(ult) > 4:
            corte = limite - len(pre) - 2
            if corte >= 4 and corte < len(ult):
                return f'{pre} {ult[:corte]}.', 'abreviatura de la última palabra (estilo IE1)'
        return None, None
    return subconjunto(oficial, limite, tipo)


def subconjunto(oficial, limite, tipo):
    """Palabras del oficial en orden (se quitan palabras; «R.»/«Tor.» para la genérica). Prioriza conservar
    las palabras distintivas y el mayor número de letras."""
    ws = oficial.split()
    if len(ws) > 7:
        return None, None
    mejor = None
    for mask in range(1, 1 << len(ws)):
        for abre in (False, True):
            sel = []
            for k, w in enumerate(ws):
                if mask >> k & 1:
                    sel.append(ABREV[w] if abre and k == 0 and w in ABREV else w)
            if not sel or sel[0].lower() in CONECTORES or sel[-1].lower() in CONECTORES:
                continue
            t = ''
            for w in sel:
                t += w if (not t or t.endswith('.')) else ' ' + w
            if len(t) > limite:
                continue
            distintivas = sum(1 for k, w in enumerate(ws) if mask >> k & 1 and w not in GENERICAS
                              and w.lower() not in CONECTORES)
            if not distintivas:
                continue
            quitadas = [w for k, w in enumerate(ws) if not mask >> k & 1 and w.lower() not in CONECTORES]
            pierde = sum(1 for w in quitadas if w not in GENERICAS)
            puntos = (-pierde, distintivas, len(t))
            if mejor is None or puntos > mejor[0]:
                mejor = (puntos, t[0].upper() + t[1:], quitadas)
    if mejor is None:
        return None, None
    return mejor[1], 'se quitan palabras: ' + ' '.join(mejor[2])


def main():
    ie1 = T.ie1_cortos()
    manual = json.loads((T.HERE / 'manual.json').read_text(encoding='utf-8'))
    filas, verif = [], {}
    usados_manual = set()

    def fila(key, fichero, tipo, jp, of, cabe, limite_txt, auto_desc=True, ie1_key=None, nombre_lim=None,
             tipo_obj=False, **extra):
        r = dict(key=key, fichero=fichero, tipo=tipo, jp=jp, oficial=of, limite=limite_txt, **extra)
        m_of = manual['por_oficial'].get(f'{fichero}|{tipo}', {}).get(of or '')
        m_jp = manual['por_jp'].get(f'{fichero}|{tipo}', {}).get(jp)
        m_k = manual['por_clave'].get(key)
        m = m_k or m_of or m_jp
        if m:
            r.update(texto=T.limpiar(m[0]), fuente='manual', motivo=m[1])
            usados_manual.add((f'{fichero}|{tipo}', of) if m is m_of else key)
        elif of is None:
            r.update(texto=None, fuente='sin_nds', motivo=extra.get('sin_motivo', 'el NDS ES no tiene texto español para este ID'))
        elif cabe(of):
            r.update(texto=of, fuente='oficial', motivo=None)
        else:
            t = m = None
            if nombre_lim and ie1_key and ie1_key in ie1 and cabe(ie1[ie1_key]):
                t, m = ie1[ie1_key], 'nombre corto aprobado en IE1 para el mismo oficial'
            elif nombre_lim:
                t, m = recorte_nombre(of, nombre_lim, tipo_obj)
            elif auto_desc:
                t, m = recorte_desc(of, cabe)
            if t is None and ie1_key and ie1_key in ie1 and cabe(ie1[ie1_key]):
                cand = ie1[ie1_key]
                if es_recorte(cand, of):
                    t, m = cand, 'recorte aprobado en IE1 para el mismo texto oficial'
            if t is not None and cabe(t):
                r.update(texto=t, fuente='recorte', motivo=m)
            else:
                r.update(texto=None, fuente='pendiente', motivo='no cabe: falta recorte a mano')
        if r['fuente'] == 'manual' and not cabe(r['texto']):
            r['fuente'], r['motivo'] = 'pendiente', f'el recorte manual no cabe: {r["texto"]!r}'
        filas.append(r)

    # ---------------------------------------------------------------- command
    jd, js, ed, es = T.base('command.dat'), T.base('command.STR'), T.nds('command.dat'), T.nds('command.STR')
    assert len(jd) == len(ed) and len(jd) % 28 == 0
    iguales = sum(jd[i * 28:i * 28 + 20] + jd[i * 28 + 24:(i + 1) * 28] == ed[i * 28:i * 28 + 20] + ed[i * 28 + 24:(i + 1) * 28]
                  for i in range(len(jd) // 28))
    verif['command'] = f'{iguales}/{len(jd) // 28} registros de 28 B idénticos fuera de los punteros +20/+22'
    vistos = {}
    for i in range(len(jd) // 28):
        for tipo, pos in (('nombre', 20), ('desc', 22)):
            p = struct.unpack_from('<H', jd, i * 28 + pos)[0]
            raw = T.at(js, p * 32) if p else b''
            if not raw:
                continue
            off = p * 32
            ep = struct.unpack_from('<H', ed, i * 28 + pos)[0]
            of = T.oficial(T.at(es, ep * 32)) if ep else None
            if off in vistos:
                if vistos[off] != of:
                    filas[-1].setdefault('avisos', []).append(f'hueco {off} compartido con otro oficial: {of}')
                continue
            vistos[off] = of
            cap = T.hueco(len(raw))
            assert not any(js[off + len(raw):off + cap]), (i, tipo)
            if tipo == 'nombre':
                lim = (cap - 1) // 2
                cabe = lambda t, lim=lim: len(t) <= lim and not T.malos(t) and '\n' not in t
                fila(f'command:nombre:{off}', 'command.STR', 'nombre', T.jp(raw), of and T.plano(of), cabe,
                     f'{lim} caracteres (hueco {cap} B)', ie1_key=('command', 'nombre', T.plano(of or '')),
                     nombre_lim=lim, id=i, offset=off, capacidad=cap)
            else:
                cabe = lambda t: T.cabe_multi(t, 0)
                fila(f'command:desc:{off}', 'command.STR', 'desc', T.jp(raw), of and T.plano(of), cabe,
                     f'{T.MAX_LINEAS}x{T.MAX_LINEA}, {cap} B', ie1_key=('command', 'desc', T.plano(of or '')),
                     id=i, offset=off, capacidad=cap)

    # ---------------------------------------------------------------- item
    jd, js, ed, es = T.base('item.dat'), T.base('item.STR'), T.nds('item.dat'), T.nds('item.STR')
    assert len(jd) == 1024 * 36 and len(ed) == 1024 * 48
    cola = lambda d, o: d[o:o + 6] + d[o + 8:o + 14]
    iguales = sum(cola(jd, i * 36 + 20) == cola(ed, i * 48 + 32) for i in range(1024))
    con_nombre = sum(1 for i in range(1024) if jd[i * 36] and ed[i * 48])
    verif['item'] = (f'cola 3DS +20..+34 (sin +26/+27 ni puntero) == NDS +32..+46 en {iguales}/1024 registros; '
                     f'{con_nombre} registros con nombre en ambos')
    vistos = {}
    for i in range(1024):
        rec, erec = jd[i * 36:(i + 1) * 36], ed[i * 48:(i + 1) * 48]
        nombre = rec[:20].split(b'\0')[0]
        if nombre:
            of = T.oficial(erec[:32]) if erec[0] else None
            cabe = lambda t: len(t) <= T.MAX_OBJETO and not T.malos(t) and '\n' not in t
            fila(f'item:nombre:{i}', 'item.dat', 'nombre', T.jp(nombre), of, cabe, '9 caracteres (18 B + NUL)',
                 ie1_key=('item', 'nombre', T.plano(of or '')), nombre_lim=T.MAX_OBJETO, tipo_obj=True,
                 id=i, offset=i * 36, capacidad=19)
        p = struct.unpack_from('<H', rec, 34)[0]
        raw = T.at(js, p * 32) if p else b''
        if not raw:
            continue
        off = p * 32
        ep = struct.unpack_from('<H', erec, 46)[0]
        of = T.oficial(T.at(es, ep * 32)) if ep else None
        if off in vistos:
            if vistos[off] != of:
                filas[-1].setdefault('avisos', []).append(f'hueco {off} compartido con otro oficial: {of}')
            continue
        vistos[off] = of
        cap = T.hueco(len(raw))
        assert not any(js[off + len(raw):off + cap]), i
        cabe = lambda t: T.cabe_multi(t, 0)
        fila(f'item:desc:{off}', 'item.STR', 'desc', T.jp(raw), of and T.plano(of), cabe,
             f'{T.MAX_LINEAS}x{T.MAX_LINEA}, {cap} B', ie1_key=('item', 'desc', T.plano(of or '')),
             id=i, offset=off, capacidad=cap)

    # ---------------------------------------------------------------- rpgtitle
    rs, rd = T.base('rpgtitle.STR'), T.base('rpgtitle.dat')
    ers = T.nds('rpgtitle.STR')
    assert rd == T.nds('rpgtitle.dat')
    verif['rpgtitle'] = 'rpgtitle.dat idéntico al NDS y +30 == índice en todos los huecos con texto'
    for i in range(len(rs) // 32):
        raw = rs[i * 32:(i + 1) * 32].split(b'\0')[0]
        if not raw:
            continue
        assert struct.unpack_from('<H', rd, i * 32 + 30)[0] == i
        of = T.oficial(ers[i * 32:(i + 1) * 32])
        cabe = lambda t: len(t) <= T.MAX_TITULO and not T.malos(t)
        fila(f'rpgtitle:{i}', 'rpgtitle.STR', 'titulo', T.jp(raw), of, cabe, '9 caracteres (búfer de 18 B)',
             nombre_lim=T.MAX_TITULO, id=i, offset=i * 32, capacidad=32)

    # ---------------------------------------------------------------- JinmyakuData
    dj, dn = T.jparse(T.base('JinmyakuData.dat')), T.jparse(T.nds('JinmyakuData.dat'))
    assert dj['edges'] == dn['edges'] and len(dj['records']) == len(dn['records'])
    ej = {r['kind']: r for r in dj['records'] if 'text' in r}
    en = {r['kind']: r for r in dn['records'] if 'text' in r}
    assert len(ej) == sum('text' in r for r in dj['records']) and set(ej) == set(en)
    hj, hn = {h['id']: h for h in dj['hints']}, {h['id']: h for h in dn['hints']}
    assert set(hj) == set(hn)
    verif['jinmyaku'] = (f'{len(ej)} sucesos por kind y {len(hj)} pistas por id, mismos conjuntos y aristas idénticas; '
                         f'registros con meta distinta: {sum(a != b for a, b in zip([{k: v for k, v in r.items() if k != "text"} for r in dj["records"]], [{k: v for k, v in r.items() if k != "text"} for r in dn["records"]]))}')
    cif = T.cifras_pista(dj)
    for k, r in ej.items():
        of = T.oficial(en[k]['text'].rstrip(b'\0'))
        cabe = lambda t: T.cabe_multi(t, 0) and '%' not in t
        fila(f'jinmyaku:event:{k}', 'JinmyakuData.dat', 'suceso', T.jp(r['text'].rstrip(b'\0')), of and T.plano(of),
             cabe, f'{T.MAX_LINEAS}x{T.MAX_LINEA}', id=k)
    for k, h in hj.items():
        jt = T.jp(h['text'])
        of = T.oficial(hn[k]['text'])
        n = cif.get(k, 5)
        want = T.pct(jt)
        cabe = lambda t, n=n, want=want: T.cabe_multi(t, n) and T.pct(t) == want and len(T.cuerpo_multi(t, n)[0]) <= 255
        fila(f'jinmyaku:hint:{k}', 'JinmyakuData.dat', 'pista', jt, of and T.plano(of), cabe,
             f'{T.MAX_LINEAS}x{T.MAX_LINEA}, %s = {n} cifras, %s/%d como el japonés {want}', auto_desc=True, id=k,
             cifras=n)

    # ---------------------------------------------------------------- fieldinf
    jf, n0, n1 = T.base('fieldinf.dat'), T.nds('fieldinf.dat', 'logic'), T.nds('fieldinf.dat', 'logic01/sp')
    indice = {}
    for i in range(len(n0) // 384):
        o = i * 384
        clave = (n0[o:o + 8], n0[o + 144:o + 164])
        indice.setdefault(clave, []).append(i)
    usados = 0
    for i in range(len(jf) // 384):
        o = i * 384
        raw = jf[o + 144:o + 164]
        if not raw.strip(b'\0'):
            continue
        idx = indice.get((jf[o:o + 8], raw), [])
        of = None
        motivo = 'el NDS japonés no tiene este campo (mapa + nombre)'
        if idx:
            of = T.oficial(n1[idx[0] * 384 + 144:idx[0] * 384 + 176])
            motivo = f'el NDS ES deja en japonés el registro {idx[0]} (no se muestra en DS)'
            usados += of is not None
        cabe = lambda t: len(t) <= T.MAX_CAMPO and not T.malos(t)
        fila(f'fieldinf:{i}', 'fieldinf.dat', 'campo', raw.split(b'\0')[0].decode('cp932'), of, cabe,
             '10 caracteres (20 B sin NUL)', ie1_key=('fieldinf', 'nombre', T.plano(of or '')), nombre_lim=T.MAX_CAMPO,
             id=i, offset=o + 144, capacidad=20, nds_indice=idx[0] if idx else None, sin_motivo=motivo)
    verif['fieldinf'] = (f'clave (mapa +0, nombre +144) del 3DS buscada en el NDS japonés; {usados} con texto ES en '
                         'logic01/sp (mismo índice que el NDS japonés, comprobado: mismo mapa +0)')
    for i in range(len(n0) // 384):
        assert n0[i * 384:i * 384 + 8] == n1[i * 384:i * 384 + 8]

    # ---------------------------------------------------------------- gamerule + games
    jg, eg = T.base('gamerule.dat'), T.nds('gamerule.dat')
    puente = {}
    iguales = 0
    for i in range(len(jg) // 288):
        o = i * 288
        raw = jg[o + 32:o + 288].split(b'\0')[0]
        if not raw:
            continue
        iguales += jg[o:o + 32] == eg[o:o + 32]
        assert not any(jg[o + 32 + len(raw):o + 288])
        of = T.oficial(eg[o + 32:o + 288].split(b'\0')[0])
        if jg[o:o + 32] != eg[o:o + 32]:
            of = None
        puente.setdefault(raw, of)
        cabe = lambda t: len(t) <= T.MAX_OBJETIVO and T.cabe_multi(t, 0) and len(T.envolver(t)) == 1
        fila(f'gamerule:{i}', 'gamerule.dat', 'objetivo', T.jp(raw), of, cabe,
             f'{T.MAX_OBJETIVO} caracteres, 1 línea', nombre_lim=None, auto_desc=False, id=i, offset=o + 32,
             capacidad=256)
    verif['gamerule'] = f'{iguales} registros con texto y cabecera +0..+32 idéntica al NDS'
    gs = T.base('games.STR')
    assert gs == T.nds('games.STR', 'logic')
    n_games = 0
    for off in range(32, len(gs), 32):
        if not gs[off] or gs[off - 1]:
            continue
        raw = T.at(gs, off)
        cap = T.hueco(len(raw))
        assert not any(gs[off + len(raw):off + cap])
        n_games += 1
        of = puente.get(raw)
        if of is None:
            # mismo objetivo sin el espacio inicial o con otra variante: se busca por texto japonés sin espacios
            for k, v in puente.items():
                if k.replace('　'.encode('cp932'), b'') == raw.replace('　'.encode('cp932'), b''):
                    of = v
        lim = min(T.MAX_OBJETIVO, (cap - 1) // 2)
        cabe = lambda t, lim=lim: len(t) <= lim and not T.malos(t) and '\n' not in t
        fila(f'games:{off}', 'games.STR', 'objetivo', T.jp(raw), of, cabe, f'{lim} caracteres, 1 línea ({cap} B)',
             auto_desc=False, offset=off, capacidad=cap,
             sin_motivo='el NDS ES no traduce games.STR y gamerule no tiene este japonés (texto de depuración)')
    verif['games'] = (f'{n_games} cadenas; games.STR idéntico al NDS japonés/ES (sin traducir en DS); ES tomado de '
                      'gamerule.dat por el mismo texto japonés')

    sin_uso = [f'{g}: {o}' for g, d in manual['por_oficial'].items() for o in d
               if (g, o) not in usados_manual and not g.endswith('|desc')]
    sin_uso += [f'{g}: {o}' for o in manual['por_oficial'].get('item.STR|desc', {})
                for g in ('desc',) if ('item.STR|desc', o) not in usados_manual
                and ('command.STR|desc', o) not in usados_manual]
    if sin_uso:
        print('AVISO manual sin uso:', *sin_uso, sep='\n  ')
    salida = dict(verificacion=verif, filas=filas)
    (T.HERE / 'worklist.json').write_text(json.dumps(salida, ensure_ascii=False, indent=1), encoding='utf-8')
    import collections
    c = collections.Counter((r['fichero'], r['tipo'], r['fuente']) for r in filas)
    for k in sorted(c):
        print(*k, c[k])


if __name__ == '__main__':
    main()
