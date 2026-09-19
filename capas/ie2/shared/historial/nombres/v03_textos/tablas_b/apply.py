"""IE2 v03 · tablas B: resto de datos textuales de inazuma2/data_iz con el texto oficial NDS.

Base: work/shared/candidatas/probe_ie2_v02/archive.fa (comun_v03.base). Fuente: NDS ES (comun_v03.NDS).
Emparejado (se comprueba en cada fichero, ver ALINEADO en informe.json):
  team.pkb        ID de team.pkh (tipo 3, registros fijos de 320 B) + resto del registro idéntico.
  schinfo.dat     índice de registro (32 B / 48 B NDS) + bytes de datos idénticos.
  BinderData_*    ID de equipo del registro -> nombre corto de team.pkb.
  teamtitle, clubinfo, livetalk, ClearCondition, gamerule: índice de registro + bytes de datos idénticos.
  movie_view.dat  índice de registro + id y nombre de vídeo idénticos.
  ShopName.dat    número de línea.
  blogpost.dat    cabecera de 2 B idéntica; la NDS tiene 2 pares de registros de más tras el 3 (j = i + 4).
  blogres.dat     índice de registro + cabecera de 3 B idéntica.
Texto: NDS literal si cabe; si no, recorte a mano (manual.json). Ancho completo (comun_v03.transportar),
sin comillas/apóstrofos (normalizar), sin bigramas, huecos fijos rellenos con NUL.
Uso: python -X utf8 apply.py
"""
from __future__ import annotations

import json
import re
import struct
import sys
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import comun_v03 as K  # noqa: E402
import survey  # noqa: E402
from dialogue_typography import ACCENTS  # noqa: E402

RAIZ = 'inazuma2/data_iz/'
EXTRA = HERE / 'extra'
MAN = json.loads((HERE / 'manual.json').read_text(encoding='utf-8'))
INV_ACC = {v: k for k, v in ACCENTS.items()}
ART = ('Los ', 'Las ', 'El ', 'La ')
JAP = re.compile(r'[぀-ヿ一-鿿]')

# Límites (caracteres visibles) y su origen
LIM = {
    'team': (9, 'skill §10: cuadro de pachanga pegado al borde (9); cuadro de equipo 11'),
    'schinfo': (9, 'hueco de 19 B (9 de ancho completo + NUL)'),
    'binder': (9, 'mismo nombre corto que team.pkb (hueco de 20 B)'),
    'teamtitle': (9, 'japonés más largo 9 (título de equipo, como rpgtitle)'),
    'clubinfo': (9, 'hueco de 19 B'),
    'livetalk': (7, 'hueco de 16 B (7 + NUL); precedente IE1 v89'),
    'clear': (22, 'una línea de FONT12 (22 caracteres); hueco 79 B'),
    'gamerule': (22, 'una línea de FONT12 (22 caracteres); precedente IE1 v89'),
    'shop': (30, 'línea de texto sin hueco fijo (búfer de 0x100 en ina_main2 0x83e94); ancho sin medir'),
    'movie': (19, 'hueco de 39 B (19 + NUL); el japonés lo llena'),
    'blog_titulo': (16, 'japonés más largo 16'),
    'blog_linea': (16, 'línea japonesa más larga 16; máx. 5 líneas; hueco 224 B'),
    'res_linea': (17, 'línea japonesa más larga 17; máx. 2 líneas; hueco 261 B'),
}
PCT_ANCHO = 7   # %s = nombre de unitbase (7 casillas)

cambios: list[dict] = []
sin_traducir: list[dict] = []
alineado: dict[str, str] = {}


# ----------------------------------------------------------------------------- utilidades
def get(p):
    return K.base()(RAIZ + p)


def nds(p):
    for q in (K.NDS / p, K.NDS / p.replace('/', '/sp/', 1)):
        if q.exists():
            return q.read_bytes()
    raise FileNotFoundError(p)


def sj(b: bytes) -> str:
    return b.split(b'\0')[0].decode('cp932')


def dn(b: bytes):
    return K.dec_nds(b)


def norm(t: str) -> str:
    return K.normalizar(t).strip()


def enc(t: str) -> bytes:
    body = K.transportar(t)
    falta = K.M.sin_glifo(body.replace(bytes([10]), b''))   # 0x0A = salto de línea del japonés
    assert not falta, (t, falta)
    return body


def desde(body: bytes) -> str:
    """Cuerpo de ancho completo -> texto (inverso de transportar)."""
    s = body.decode('cp932')
    out = []
    for part in re.split(r'(%[0-9]*[A-Za-z])', s):
        if re.fullmatch(r'%[0-9]*[A-Za-z]', part):
            out.append(part)
            continue
        for ch in part:
            if ch == '－':
                out.append('−')
            elif ch in INV_ACC:
                out.append(INV_ACC[ch])
            elif ch == '　':
                out.append(' ')
            elif '！' <= ch <= '～':
                out.append(chr(ord(ch) - 0xfee0))
            else:
                out.append(ch)
    return ''.join(out)


def ancho(linea: str) -> int:
    return len(re.sub(r'%[0-9]*s', 'x' * PCT_ANCHO, linea))


def visible_jp(s: str) -> str:
    return re.sub(r'\[([^/\]]*)/[^\]]*\]', r'\1', s)


def elegir(fichero, clave, jp, texto_nds, manual, lim_nombre, sin_nds_motivo=None):
    """Devuelve el texto español y registra el cambio."""
    lim, origen = LIM[lim_nombre]
    lit = norm(texto_nds) if texto_nds is not None else None
    if manual is not None:
        es = manual
        estado = 'sin_nds' if lit is None else ('literal' if norm(es) == lit else 'recortado')
    elif lit is None:
        raise SystemExit(f'{fichero} {clave}: sin texto NDS ni manual')
    else:
        es = lit
        estado = 'literal'
    es = norm(es)
    for linea in es.split('\n'):
        if ancho(linea) > lim:
            raise SystemExit(f'{fichero} {clave}: {linea!r} pasa de {lim}')
    reg = {'fichero': fichero, 'clave': clave, 'japones': jp, 'nds': texto_nds, 'espanol': es, 'estado': estado}
    if estado == 'recortado':
        reg['motivo'] = f'límite {lim}: {origen}'
    if estado == 'sin_nds':
        reg['motivo'] = sin_nds_motivo
    cambios.append(reg)
    return es


def poner(buf: bytearray, off: int, size: int, texto: str, maxbytes: int | None = None):
    body = enc(texto)
    lim = (size - 1) if maxbytes is None else maxbytes
    assert len(body) <= lim, (texto, len(body), lim)
    assert desde(body) == texto, (desde(body), texto)
    buf[off:off + size] = body + bytes(size - len(body))


def escribir(rel: str, data: bytes):
    out = EXTRA / RAIZ / rel
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)


def auto_nombre(n: str):
    n = norm(n)
    if len(n) <= LIM['team'][0]:
        return n
    for a in ART:
        if n.startswith(a) and len(n) - len(a) <= LIM['team'][0]:
            return n[len(a):]
    return None


# ----------------------------------------------------------------------------- team.pkb
def equipos():
    a, b = get('logic/team.pkb'), nds('logic/team.pkb')
    ha, hb = get('logic/team.pkh'), nds('logic/team.pkh')
    na, nb = struct.unpack_from('<H', ha, 0x16)[0], struct.unpack_from('<H', hb, 0x16)[0]
    ra = struct.unpack_from('<I', ha, 0x1c)[0]
    assert ra == 320 and len(a) == na * ra and len(b) == nb * ra
    ia = struct.unpack_from(f'<{na}I', ha, 0x30)
    ib = struct.unpack_from(f'<{nb}I', hb, 0x30)
    pb = {i: k for k, i in enumerate(ib)}
    buf = bytearray(a)
    por_id, por_nds = {}, {}
    iguales, minimo = 0, 1.0
    for k, tid in enumerate(ia):
        o = k * ra
        jp = sj(a[o:o + 32])
        if tid in pb:
            ob = pb[tid] * ra
            x, y = a[o + 32:o + ra], b[ob + 32:ob + ra]
            parecido = sum(p == q for p, q in zip(x, y)) / len(x)
            assert parecido >= 0.9, f'registro {tid} desalineado ({parecido:.2f})'
            iguales += x == y
            minimo = min(minimo, parecido)
            texto_nds = dn(b[ob:ob + 32])
        else:
            texto_nds = None
        if texto_nds is not None and JAP.search(texto_nds):
            sin_traducir.append({'fichero': 'logic/team.pkb', 'clave': tid, 'japones': jp,
                                 'motivo': 'la NDS lo deja en japonés (equipo interno)'})
            continue
        man = MAN['equipos'].get(str(tid))
        motivo = None
        if texto_nds is None:
            man, motivo = MAN['equipos_sin_nds'][str(tid)]
        elif man is None:
            man = auto_nombre(texto_nds)
            if man is None:
                raise SystemExit(f'equipo {tid} {texto_nds!r} sin recorte')
        es = elegir('logic/team.pkb', tid, jp, texto_nds, man, 'team', motivo)
        poner(buf, o, 32, es, maxbytes=2 * LIM['team'][0])
        por_id[tid] = es
        if texto_nds is not None:
            por_nds.setdefault(norm(texto_nds), es)
    alineado['logic/team.pkb'] = (f'ID de team.pkh: {len(set(ia) & set(ib))} de {na} IDs en la NDS; {iguales} con los 288 B '
                                  f'de datos idénticos y el resto con parecido >= {minimo:.2f}; sin NDS: {sorted(set(ia) - set(ib))}')
    assert len(buf) == len(a)
    escribir('logic/team.pkb', bytes(buf))
    return por_id, por_nds


# ----------------------------------------------------------------------------- otros
def schinfo(por_nds):
    a, b = get('logic/schinfo.dat'), nds('logic/schinfo.dat')
    buf = bytearray(a)
    alias = {'Royal Academy Redux': 'Royal Academy Rdx.'}
    n = 0
    for r in range(len(a) // 32):
        o, ob = r * 32, r * 48
        jp = sj(a[o:o + 19])
        if not jp or jp == 'システム予約':
            continue
        assert a[o + 19:o + 28] == b[ob + 39:ob + 48], f'schinfo {r} desalineado'
        t = dn(b[ob:ob + 32])
        man = por_nds.get(norm(alias.get(t, t)))
        es = elegir('logic/schinfo.dat', r, jp, t, man, 'schinfo')
        poner(buf, o, 19, es)
        n += 1
    alineado['logic/schinfo.dat'] = f'índice de registro; {n} nombres con bytes de datos 3DS[19:28] = NDS[39:48]'
    escribir('logic/schinfo.dat', bytes(buf))


def binder(por_id):
    for f in ('BinderData_B', 'BinderData_F'):
        rel = f'logic/{f}.dat'
        a = get(rel)
        buf = bytearray(a)
        n = 0
        for r in range(len(a) // 28):
            o = r * 28
            cat, tid = a[o], struct.unpack_from('<H', a, o + 2)[0]
            jp = sj(a[o + 4:o + 24])
            if cat < 2 or tid == 0 or not jp:
                if jp and JAP.search(jp):
                    sin_traducir.append({'fichero': rel, 'clave': r, 'japones': jp, 'motivo':
                                         'pestaña de índice por silabario (あ…わ): el orden de la carpeta es '
                                         'japonés; la NDS usa ABC/DEF con otra agrupación'})
                continue
            es = por_id[tid]
            cambios.append({'fichero': rel, 'clave': r, 'japones': jp, 'nds': f'team ID {tid}', 'espanol': es,
                            'estado': 'nombre_team', 'motivo': 'nombre corto de team.pkb por ID de equipo'})
            poner(buf, o + 4, 20, es)
            n += 1
        alineado[rel] = f'ID de equipo del registro (u16 en +2) -> team.pkb; {n} nombres'
        escribir(rel, bytes(buf))


def tabla(rel, clave_lim, rs, rsn, campo, campon, datos, man_key, saltar=('システム予約',)):
    """Tabla de registros fijos con un solo campo de texto."""
    a, b = get(rel), nds(rel)
    buf = bytearray(a)
    man = MAN.get(man_key, {})
    n = 0
    for r in range(len(a) // rs):
        o, ob = r * rs, r * rsn
        jp = visible_jp(sj(a[o + campo[0]:o + campo[0] + campo[1]]))
        if not jp or not JAP.search(jp) or jp in saltar:
            continue
        for (x, y), (xn, yn) in datos:
            assert a[o + x:o + y] == b[ob + xn:ob + yn], f'{rel} {r} desalineado'
        t = dn(b[ob + campon[0]:ob + campon[0] + campon[1]])
        if t is None or JAP.search(t):
            sin_traducir.append({'fichero': rel, 'clave': r, 'japones': jp,
                                 'motivo': 'la NDS lo deja en japonés (etiqueta interna)'})
            continue
        es = elegir(rel, r, jp, t, man.get(str(r)), clave_lim)
        poner(buf, o + campo[0], campo[1], es)
        n += 1
    alineado[rel] = f'índice de registro ({rs} B; NDS {rsn} B) con bytes de datos idénticos; {n} textos'
    escribir(rel, bytes(buf))


def shopname():
    rel = 'logic/ShopName.dat'
    a, b = get(rel).split(b'\r\n'), nds(rel).split(b'\r\n')
    assert len(a) == len(b)
    out = []
    n = 0
    for i, (x, y) in enumerate(zip(a, b)):
        jp = x.decode('cp932')
        if not JAP.search(jp) or jp == 'ダミー':
            out.append(x)
            continue
        es = elegir(rel, i, visible_jp(jp), dn(y), None, 'shop')
        body = enc(es)
        assert desde(body) == es
        out.append(body)
        n += 1
    alineado[rel] = f'número de línea (65 líneas en ambas); {n} nombres; «ダミー» (línea 0) igual que la NDS'
    escribir(rel, b'\r\n'.join(out))


def gamerule():
    rel = 'logic/gamerule.dat'
    a, b = get(rel), nds(rel)
    buf = bytearray(a)
    n = 0
    for r in range(len(a) // 0x120):
        o = r * 0x120
        jp = sj(a[o + 0x20:o + 0x120])
        if not JAP.search(jp):
            continue
        assert a[o:o + 0x20] == b[o:o + 0x20], f'gamerule {r} desalineado'
        t = dn(b[o + 0x20:o + 0x120])
        es = elegir(rel, r, jp, t, MAN['gamerule'].get(str(r)), 'gamerule')
        poner(buf, o + 0x20, 0x100, es)
        n += 1
    alineado[rel] = (f'índice de registro (0x120 B: 0x20 de datos + 0x100 de texto) con los datos idénticos; '
                     f'{n} textos (se quita el espacio inicial del japonés, como IE1 v89)')
    escribir(rel, bytes(buf))


def movie_view():
    rel = 'logic/movie_view.dat'
    a, b = get(rel), nds(rel)
    buf = bytearray(a)
    n = 0
    for r in range(len(a) // 96):
        o, ob = r * 96, r * 114
        assert a[o:o + 18] == b[ob:ob + 18], f'movie_view {r} desalineado'
        jp = sj(a[o + 57:o + 96])
        t = dn(b[ob + 66:ob + 114])
        es = elegir(rel, r, jp, t, MAN['movie_view'].get(str(r)), 'movie')
        poner(buf, o + 57, 39, es)
        n += 1
    sin_traducir.append({'fichero': rel, 'clave': 'todos', 'japones': 'ＮＯ．０１…',
                         'motivo': 'rótulo de número ya en latín; «N.º» no tiene glifo (º)'})
    alineado[rel] = f'índice de registro (96 B; NDS 114 B) con id y nombre de vídeo idénticos; {n} títulos'
    escribir(rel, bytes(buf))


def blogpost():
    rel = 'script/blogpost.dat'
    a, b = get(rel), nds(rel)
    buf = bytearray(a)
    n = 0
    for i in range(len(a) // 292):
        o = i * 292
        j = i if i < 4 else i + 4
        ob = j * 292
        assert a[o:o + 2] == b[ob:ob + 2], f'blogpost {i}/{j} desalineado'
        tj, cj = visible_jp(sj(a[o + 2:o + 68])), visible_jp(sj(a[o + 68:o + 292]))
        if not tj:
            continue
        tn, cn = dn(b[ob + 2:ob + 68]), dn(b[ob + 68:ob + 292])
        mt, mc = MAN['blogpost'][str(i)]
        es_t = elegir(rel, f'{i}.titulo', tj, tn, mt, 'blog_titulo')
        es_c = elegir(rel, f'{i}.cuerpo', cj, cn, mc, 'blog_linea')
        assert es_c.count('\n') <= 4
        assert K.M.pct(es_c) == K.M.pct(cj), (i, es_c)
        poner(buf, o + 2, 66, es_t)
        poner(buf, o + 68, 224, es_c)
        n += 1
    alineado[rel] = (f'registros de 292 B; 3DS i -> NDS i (i<4) o i+4 (la NDS repite los dos avisos de fichaje); '
                     f'cabecera de 2 B idéntica en los {n} pares; %s coincide con el japonés')
    escribir(rel, bytes(buf))


def blogres():
    rel = 'script/blogres.dat'
    a, b = get(rel), nds(rel)
    buf = bytearray(a)
    n = 0
    for i in range(len(a) // 264):
        o = i * 264
        jp = visible_jp(sj(a[o + 3:o + 264]))
        if not jp:
            continue
        assert a[o:o + 3] == b[o:o + 3], f'blogres {i} desalineado'
        es = elegir(rel, i, jp, dn(b[o + 3:o + 264]), MAN['blogres'].get(str(i)), 'res_linea')
        assert es.count('\n') <= 1
        poner(buf, o + 3, 261, es)
        n += 1
    alineado[rel] = f'índice de registro (264 B) con cabecera de 3 B idéntica; {n} comentarios'
    escribir(rel, bytes(buf))


# ----------------------------------------------------------------------------- informe
NO_TRADUCIDOS = {
    'logic/PracticeGame*.dat': 'nombres de equipo internos; la NDS los deja en japonés (no se muestran)',
    'logic/gmapbase*.dat': 'nombres de depuración; la NDS los deja en japonés o inglés de desarrollo',
    'logic/ScoutSpCode.dat': 'contraseñas que el jugador escribe con el teclado kana; depende del teclado',
    'logic/usearch.dat': 'claves de búsqueda por nombre (kana) tecleadas por el jugador; depende del teclado; '
                         'el campo visible es «？？？»',
    'logic/fmt.pkb': 'nombres de formación numéricos (４－４－２) y etiquetas de depuración; idéntico a la NDS',
    'logic/fmtsm.dat, gloveinfo.dat, script/mr*obj.dat': 'falsos positivos (datos binarios)',
    '*.TXT, INAZUMA.INI': 'ficheros de depuración',
    'logic/clubinfo.dat[0], livetalk.dat[0], ClearCondition.dat[12], ShopName.dat[0]': 'la NDS los deja en japonés',
    'otros agentes': 'unitbase, command, item, rpgtitle, JinmyakuData, fieldinf, games, eve/mch, CRO',
    'sin texto': 'uschool, shop, i_detail, missinfo, SetEndrollBG, SystemMenuOrder, TokkunData, ScoutData, '
                 'HeadhuntData, TradeData, PracticeData, wearset, script/help.pkb (tutorial sin texto), '
                 'script/act.pkb (sin frases), treasurebox, dgn*, rpgencount*',
    'no existen en 3DS': 'sp_binder (sin equivalente), tácticas (IE2 no tiene supertácticas)',
}


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    por_id, por_nds = equipos()
    schinfo(por_nds)
    binder(por_id)
    tabla('logic/teamtitle.dat', 'teamtitle', 32, 32, (0, 26), (0, 26), [((26, 32), (26, 32))], 'teamtitle')
    tabla('logic/clubinfo.dat', 'clubinfo', 32, 32, (0, 19), (0, 31), [], 'clubinfo')
    tabla('logic/livetalk.dat', 'livetalk', 16, 16, (0, 16), (0, 16), [], 'livetalk')
    tabla('logic/ClearCondition.dat', 'clear', 81, 81, (1, 80), (1, 80), [((0, 1), (0, 1))], 'clearcondition')
    shopname()
    gamerule()
    movie_view()
    blogpost()
    blogres()

    inv = survey.inventario()
    por_fichero = {}
    for c in cambios:
        d = por_fichero.setdefault(c['fichero'], {'literal': 0, 'recortado': 0, 'sin_nds': 0, 'nombre_team': 0})
        d[c['estado']] += 1
    for s in sin_traducir:
        d = por_fichero.setdefault(s['fichero'], {'literal': 0, 'recortado': 0, 'sin_nds': 0, 'nombre_team': 0})
        d['japones'] = d.get('japones', 0) + 1
    informe = {
        'base': str(K.BASE_V02.relative_to(K.ROOT)),
        'metodo': 'texto oficial NDS emparejado por ID/índice (ver alineado); recortes solo por límite, quitando '
                  'palabras (manual.json); ancho completo con comun_v03.transportar; sin bigramas',
        'limites': {k: {'caracteres': v[0], 'origen': v[1]} for k, v in LIM.items()},
        'alineado': alineado,
        'recuento': por_fichero,
        'inventario': inv,
        'no_traducidos': NO_TRADUCIDOS,
        'sin_traducir': sin_traducir,
        'sin_nds': [c for c in cambios if c['estado'] == 'sin_nds'],
        'recortados': [c for c in cambios if c['estado'] == 'recortado'],
        'pendiente_emulador': [
            'ShopName.dat: el nombre va tras el literal かう/うる del CRO (ina_main2 0x83c58); ancho del rótulo sin medir',
            'blogpost/blogres: ancho de caja sin medir (se usa el del japonés, 16/17)',
            'ClearCondition/gamerule: ancho sin medir (22)',
            'clubinfo: el japonés tiene 3 caracteres como mucho; «Hokkaido» usa 8',
            'livetalk: bocadillo de partido con 7 caracteres (el japonés usa 5)',
        ],
        'cambios': cambios,
        'salidas': sorted(str(p.relative_to(HERE)).replace('\\', '/') for p in EXTRA.rglob('*') if p.is_file()),
    }
    (HERE / 'informe.json').write_text(json.dumps(informe, ensure_ascii=False, indent=1), encoding='utf-8')
    for f, d in sorted(por_fichero.items()):
        print(f, d)
    print(len(cambios), 'textos;', len(sin_traducir), 'sin traducir')


if __name__ == '__main__':
    main()
