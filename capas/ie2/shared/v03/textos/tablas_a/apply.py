"""IE2 v03 · tablas A · escribe los ficheros completos de inazuma2/data_iz/logic/ en extra/ e informe.json.

Entrada: worklist.json (preparar.py) sobre la base probe_ie2_v02 (logic/* = japonés original).
  command.STR / item.STR  texto en su hueco original si cabe; si no cabe en bytes (no en líneas), se reubica
                          en unidades de 32 B libres del mismo fichero y se cambian los punteros u16 de
                          command.dat (+20/+22) / item.dat (+34) que apuntaban al hueco. Tamaño igual.
  item.dat                nombre +0..+19 (máx. 18 B + NUL).
  rpgtitle.STR            hueco de 32 B (máx. 18 B).
  JinmyakuData.dat        reconstrucción de longitud variable (parser wide), solo cambian los textos.
  fieldinf.dat            +144..+163 (20 B, sin NUL).
  gamerule.dat            +32..+287.
  games.STR               hueco original (sin reubicar).
Sin bigramas. Saltos 0x0A. Uso: python -X utf8 apply.py  (regenera manual.json y worklist.json)
Después: python -X utf8 validate.py
"""
from __future__ import annotations

import collections
import json
import struct

import tablas as T

SALIDA = ('command.STR', 'command.dat', 'item.STR', 'item.dat', 'rpgtitle.STR', 'JinmyakuData.dat',
          'fieldinf.dat', 'gamerule.dat', 'games.STR')


def cuerpo(r):
    if r['tipo'] in ('desc', 'suceso', 'pista'):
        return T.cuerpo_multi(r['texto'], r.get('cifras', 0) if r['tipo'] == 'pista' else 0)[0]
    if r['tipo'] == 'objetivo' and r['fichero'] == 'gamerule.dat':
        b, filas = T.cuerpo_multi(r['texto'], 0)
        assert len(filas) == 1
        return b
    return T.cuerpo_linea(r['texto'])


class Pool:
    """Pool .STR con huecos de 32 B y punteros u16 en su .dat."""

    def __init__(self, strb, datb, rec, campos):
        self.orig = bytes(strb)
        self.s = bytearray(strb)
        self.d = bytearray(datb)
        self.orig_dat = bytes(datb)
        self.rec, self.campos = rec, campos
        self.refs = collections.defaultdict(list)          # unidad -> [(pos en .dat)]
        for i in range(len(datb) // rec):
            for c in campos:
                p = struct.unpack_from('<H', datb, i * rec + c)[0]
                if p:
                    self.refs[p].append(i * rec + c)
        self.pend = []
        self.movidos = []
        self.escritos = []                                   # (inicio, fin) en .STR

    def escribir(self, off, cap, body, key):
        if len(body) + 1 <= cap:
            self.s[off:off + cap] = body.ljust(cap, b'\0')
            self.escritos.append((off, off + cap))
            return 'en su hueco'
        self.s[off:off + cap] = bytes(cap)                   # se vacía; se reubica al final
        self.escritos.append((off, off + cap))
        self.pend.append((off, body, key))
        return 'reubicado'

    def reubicar(self, vivo):
        """Destino: unidades a cero sin ningún puntero; si no hay, unidades a cero a las que solo apuntan
        registros sin nombre (técnicas/objetos que no existen). `vivo(i)`: el registro i tiene nombre."""
        n = len(self.s) // 32
        vivas = {p for p, poss in self.refs.items() if any(vivo(pos // self.rec) for pos in poss)}
        # unidad libre: a cero y sin el NUL de la cadena anterior (una cadena de 32k B termina en la unidad siguiente)
        cero = [u > 0 and not any(self.s[u * 32 - 1:(u + 1) * 32]) for u in range(n)]
        estricto = [cero[u] and u not in self.refs for u in range(n)]
        flexible = [cero[u] and u not in vivas for u in range(n)]
        for off, body, key in sorted(self.pend, key=lambda x: -len(x[1])):
            k = (len(body) + 1 + 31) // 32
            regla = 'sin punteros'
            u = next((u for u in range(1, n - k + 1) if all(estricto[u:u + k])), None)
            if u is None:
                regla = 'solo punteros de registros sin nombre'
                u = next((u for u in range(1, n - k + 1) if all(flexible[u:u + k])), None)
            if u is None:
                raise SystemExit(f'{key}: sin espacio libre para reubicar {len(body)} B')
            for x in range(u, u + k):
                estricto[x] = flexible[x] = False
            self.s[u * 32:u * 32 + len(body)] = body
            self.escritos.append((u * 32, u * 32 + k * 32))
            for pos in self.refs[off // 32]:
                struct.pack_into('<H', self.d, pos, u)
            self.movidos.append(dict(key=key, desde=off, hasta=u * 32, bytes=len(body) + 1,
                                     punteros=len(self.refs[off // 32]), destino=regla,
                                     punteros_muertos_en_destino=sum(len(self.refs.get(x, [])) for x in range(u, u + k))))


def main():
    # cadena completa y reproducible: manual_base.py (manual.json) -> preparar.py (worklist.json) -> aquí
    T.K.comun88.modulo('ie2_v03_tablas_a_manual', T.HERE / 'manual_base.py').main()
    T.K.comun88.modulo('ie2_v03_tablas_a_preparar', T.HERE / 'preparar.py').main()
    wl = json.loads((T.HERE / 'worklist.json').read_text(encoding='utf-8'))
    filas = wl['filas']
    por = collections.defaultdict(list)
    for r in filas:
        por[r['fichero']].append(r)
    out, slots, errores = {}, collections.defaultdict(list), []

    def activo(r):
        return r['texto'] is not None and r['fuente'] in ('oficial', 'recorte', 'manual')

    # ---------------------------------------------------------------- command
    pc = Pool(T.base('command.STR'), T.base('command.dat'), 28, (20, 22))
    for r in por['command.STR']:
        if activo(r):
            r['escritura'] = pc.escribir(r['offset'], r['capacidad'], cuerpo(r), r['key'])
    cs0 = T.base('command.STR')
    pc.reubicar(lambda i: bool(cs0[struct.unpack_from('<H', pc.orig_dat, i * 28 + 20)[0] * 32]))
    out['command.STR'], out['command.dat'] = bytes(pc.s), bytes(pc.d)
    slots['command.STR'] = pc.escritos
    slots['command.dat'] = [(p, p + 2) for m in pc.movidos for p in pc.refs[m['desde'] // 32]]

    # ---------------------------------------------------------------- item
    pi = Pool(T.base('item.STR'), T.base('item.dat'), 36, (34,))
    for r in por['item.STR']:
        if activo(r):
            r['escritura'] = pi.escribir(r['offset'], r['capacidad'], cuerpo(r), r['key'])
    pi.reubicar(lambda i: bool(pi.orig_dat[i * 36]))
    for r in por['item.dat']:
        if activo(r):
            b = cuerpo(r)
            assert len(b) <= 18, r['key']
            o = r['offset']
            pi.d[o:o + 20] = b.ljust(20, b'\0')
            slots['item.dat'].append((o, o + 20))
    slots['item.dat'] += [(p, p + 2) for m in pi.movidos for p in pi.refs[m['desde'] // 32]]
    out['item.STR'], out['item.dat'] = bytes(pi.s), bytes(pi.d)
    slots['item.STR'] = pi.escritos

    # ---------------------------------------------------------------- rpgtitle
    rs = bytearray(T.base('rpgtitle.STR'))
    for r in por['rpgtitle.STR']:
        if activo(r):
            b = cuerpo(r)
            assert len(b) <= 18, r['key']
            rs[r['offset']:r['offset'] + 32] = b.ljust(32, b'\0')
            slots['rpgtitle.STR'].append((r['offset'], r['offset'] + 32))
    out['rpgtitle.STR'] = bytes(rs)

    # ---------------------------------------------------------------- Jinmyaku
    base_j = T.base('JinmyakuData.dat')
    doc = T.jparse(base_j)
    ev = {r['kind']: r for r in doc['records'] if 'text' in r}
    hi = {h['id']: h for h in doc['hints']}
    for r in por['JinmyakuData.dat']:
        if not activo(r):
            continue
        b = cuerpo(r)
        if r['tipo'] == 'suceso':
            fin = b'\0' if ev[r['id']]['text'].endswith(b'\0') else b''
            ev[r['id']]['text'] = b + fin
        else:
            assert T.pct(hi[r['id']]['text']) == T.pct(b), r['key']
            hi[r['id']]['text'] = b
    out['JinmyakuData.dat'] = T.jbuild(doc)

    # ---------------------------------------------------------------- fieldinf / gamerule / games
    fi = bytearray(T.base('fieldinf.dat'))
    for r in por['fieldinf.dat']:
        if activo(r):
            b = cuerpo(r)
            assert len(b) <= 20, r['key']
            fi[r['offset']:r['offset'] + 20] = b.ljust(20, b'\0')
            slots['fieldinf.dat'].append((r['offset'], r['offset'] + 20))
    out['fieldinf.dat'] = bytes(fi)
    gr = bytearray(T.base('gamerule.dat'))
    for r in por['gamerule.dat']:
        if activo(r):
            b = cuerpo(r)
            gr[r['offset']:r['offset'] + 256] = b.ljust(256, b'\0')
            slots['gamerule.dat'].append((r['offset'], r['offset'] + 256))
    out['gamerule.dat'] = bytes(gr)
    gs = bytearray(T.base('games.STR'))
    for r in por['games.STR']:
        if activo(r):
            b = cuerpo(r)
            assert len(b) + 1 <= r['capacidad'], r['key']
            gs[r['offset']:r['offset'] + r['capacidad']] = b.ljust(r['capacidad'], b'\0')
            slots['games.STR'].append((r['offset'], r['offset'] + r['capacidad']))
    out['games.STR'] = bytes(gs)

    # ---------------------------------------------------------------- escritura
    T.EXTRA.mkdir(parents=True, exist_ok=True)
    ficheros = {}
    for f in SALIDA:
        b = out[f]
        base = T.base(f)
        if f != 'JinmyakuData.dat':
            assert len(b) == len(base), f
        (T.EXTRA / f).write_bytes(b)
        ficheros[f'{T.LOGIC}/{f}'] = dict(tamano=len(b), tamano_base=len(base), sha256=T.K.sha(b),
                                          sha256_base=T.K.sha(base), cambia=b != base)
    (T.HERE / 'slots.json').write_text(json.dumps({k: v for k, v in slots.items()}), encoding='utf-8')

    # ---------------------------------------------------------------- informe
    res = collections.defaultdict(collections.Counter)
    for r in filas:
        clave = {'oficial': 'traducido_oficial', 'recorte': 'recortado', 'manual': 'recortado',
                 'sin_nds': 'japones_sin_nds', 'pendiente': 'japones_no_cabe'}[r['fuente']]
        if r['fuente'] == 'manual' and r['tipo'] == 'pista' and 'repone' in (r['motivo'] or ''):
            clave = 'adaptado_pct'
        res[r['fichero']][clave] += 1
    recortes = [dict(clave=r['key'], japones=r['jp'], oficial=r['oficial'], texto=r['texto'], limite=r['limite'],
                     motivo=r['motivo'], origen=r['fuente']) for r in filas if r['fuente'] in ('recorte', 'manual')]
    sin_nds = [dict(clave=r['key'], japones=r['jp'], motivo=r['motivo']) for r in filas if r['fuente'] == 'sin_nds']
    pendientes = [dict(clave=r['key'], oficial=r['oficial'], motivo=r['motivo']) for r in filas
                  if r['fuente'] == 'pendiente']
    nombres = collections.defaultdict(list)
    for r in por['item.dat']:
        if activo(r):
            nombres[r['texto']].append(f"{r['id']}:{r['oficial']}")
    duplicados = {k: v for k, v in nombres.items() if len({x.split(':', 1)[1] for x in v}) > 1}
    informe = dict(
        capa='IE2 v03 · textos · tablas_a (inazuma2/data_iz/logic)',
        base=str(T.K.BASE_V02.relative_to(T.ROOT)).replace('\\', '/'),
        norma='volcado del NDS ES; recorte solo por límite duro y con el cambio mínimo (2026-09-17)',
        emparejado=wl['verificacion'],
        limites={
            'descripciones (command/item.STR), sucesos y pistas': f'{T.MAX_LINEAS} líneas x {T.MAX_LINEA} caracteres, '
            'salto 0x0A. Japonés IE2: máx. 18 caracteres y 2 líneas; IE1 aprobó en juego el ajuste v20 '
            '(avance 11, ancho 220 = 20 caracteres, 2 líneas). Se elige 20.',
            'nombres de técnica': f'{T.MAX_NOMBRE_TEC} caracteres (hueco de 32 B con NUL)',
            'nombres de objeto': f'{T.MAX_OBJETO} caracteres (18 B + NUL; lección v47)',
            'títulos (rpgtitle)': f'{T.MAX_TITULO} caracteres (búfer de 18 B, IE1 v46)',
            'campos (fieldinf +144)': f'{T.MAX_CAMPO} caracteres (20 B sin NUL)',
            'objetivos (gamerule +32)': f'{T.MAX_OBJETIVO} caracteres, 1 línea',
            'objetivos (games.STR)': 'mínimo de 18 y el hueco (32 B = 15 caracteres)',
            'pistas con %s': 'cifras según JinmyakuData (regla lib.py de IE1): máximo real de los nodos o 5',
        },
        por_fichero={f: dict(c) for f, c in sorted(res.items())},
        ficheros=ficheros,
        reubicados=dict(command=pc.movidos, item=pi.movidos),
        abreviaturas_fijas={'Regate': 'R.', 'Tornado': 'Tor.'},
        nombres_objeto_repetidos=duplicados,
        sin_texto_nds=sin_nds,
        no_caben=pendientes,
        recortes=recortes,
        fuera_de_alcance={
            'unitbase.STR': 'descripciones de jugador: capa propia con bigramas (comun_v03 «descripcion»)',
            'fieldinf.dat': 'el NDS ES solo trae en español los registros heredados de IE1 (0-44); los de IE2 '
                            'siguen en japonés en la propia ROM española',
        },
    )
    (T.HERE / 'informe.json').write_text(json.dumps(informe, ensure_ascii=False, indent=1), encoding='utf-8')
    for f, c in sorted(res.items()):
        print(f, dict(c))
    print('reubicados: command', len(pc.movidos), 'item', len(pi.movidos))
    for f, h in ficheros.items():
        print(f, h['tamano'], 'B', 'modificado' if h['cambia'] else 'igual')


if __name__ == '__main__':
    main()
