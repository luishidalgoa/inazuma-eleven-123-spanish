"""IE2 v03 · tablas A (logic/*.STR y tablas de texto) · utilidades comunes.

Formatos IE2 3DS (inazuma2/data_iz/logic/) y su pareja NDS ES (data_iz/logic/sp, logic, logic01/sp):
  command.dat/.STR  registros de 28 B en ambas; punteros u16 (x32) nombre +20, descripción +22.
  item.dat/.STR     3DS 36 B (nombre +0..+19, puntero de descripción u16 +34);
                    NDS 48 B (nombre +0..+31, puntero +46). Mismo índice; la cola 3DS +20..+36 es la NDS +32..+48.
  rpgtitle.STR      huecos de 32 B (búfer de 18 B: 9 caracteres); rpgtitle.dat +30 = índice.
  JinmyakuData.dat  variante `wide` (u16) en 3DS y NDS; sucesos por `kind`, pistas por `id`.
  fieldinf.dat      registros de 384 B, nombre +144 (20 B sin NUL); clave = mapa +0 (8 B) + nombre japonés
                    del NDS japonés (logic/fieldinf.dat), traducción en logic01/sp/fieldinf.dat.
  games.STR         objetivos de pachanga (32 B + pool); el NDS ES los dejó en japonés.
  gamerule.dat      registros de 288 B, objetivo +32 (hasta +288). El NDS ES los trae traducidos (mismo índice).
Uso como módulo.
"""
from __future__ import annotations

import csv
import json
import re
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import comun_v03 as K  # noqa: E402

ROOT = K.ROOT
LOGIC = K.LOGIC
NDS = K.NDS
EXTRA = HERE / 'extra' / LOGIC
IE1 = ROOT / 'work/ie1'

MAX_LINEA = 20        # caracteres por línea (ajuste v20 aprobado en IE1: avance 11, ancho 220; japonés IE2 máx. 18)
MAX_LINEAS = 2        # japonés IE2: 1-2 líneas en item/command; IE1 usó 2
MAX_NOMBRE_TEC = 15   # hueco de 32 B con NUL
MAX_OBJETO = 9        # 18 B + NUL (lección v47)
MAX_TITULO = 9        # búfer de 18 B (IE1 v46)
MAX_CAMPO = 10        # fieldinf +144, 20 B sin NUL
MAX_OBJETIVO = 18     # japonés más largo del campo = 17; IE1 aprobó 18 («¡Protege el balón!») en gamerule

FURI = re.compile(r'\[([^/\]]+)/[^\]]+\]')
JAPO = re.compile('[぀-ヿ㐀-鿿ｦ-ﾟ]')
# Sin glifo en la fuente o sin código Shift-JIS: se sustituyen a la forma española más cercana.
EXTRA_SUST = {'Ü': 'U', 'ä': 'a', 'ö': 'o', 'ª': 'a', 'º': 'o', '«': '', '»': '', '—': ' ', '–': '−',
              '　': ' ', '“': '', '”': '', '‘': '', '’': ''}
PROHIBIDOS = set('\'"[]{}<>|~^`_@#$&*=\\')

at = lambda d, p: bytes(d[p:]).split(b'\0')[0]


# ------------------------------------------------------------------ lectura
def base(nombre):
    return K.base()(f'{LOGIC}/{nombre}')


def original(nombre):
    return K.abrir(K.JP)(f'{LOGIC}/{nombre}')


def nds(nombre, carpeta='logic/sp'):
    return (NDS / carpeta / nombre).read_bytes()


def jp(b: bytes) -> str:
    return FURI.sub(r'\1', b.decode('cp932'))


def oficial(b: bytes) -> str | None:
    """Texto NDS normalizado; None si no decodifica o sigue en japonés."""
    t = K.dec_nds(bytes(b).replace(bytes([0xB5]), b'a'))   # 0xB5 = «ä» (FORMATOS.md), sin glifo: «Doppelganger» como IE1
    if t is None:
        return None
    t = limpiar(t.replace(' n.~', ' '))      # «n.º» (0x7E en el NDS) no tiene glifo: IE1 usó «Pingüino emp. 2»
    return None if (not t or JAPO.search(t)) else t


def limpiar(t: str) -> str:
    t = K.normalizar(t)
    for a, b in EXTRA_SUST.items():
        t = t.replace(a, b)
    return '\n'.join(' '.join(l.split()) for l in t.split('\n')).strip()


def plano(t: str) -> str:
    return ' '.join(t.split())


# ------------------------------------------------------------------ codificación y comprobación
def malos(t: str):
    return sorted({c for c in t.replace('%s', '').replace('%d', '') if c in PROHIBIDOS or c == '%'})


def envolver(texto: str, cifras: int = 0):
    """Líneas de <= MAX_LINEA caracteres por palabras; %s/%d cuentan `cifras` (mín. 1)."""
    filas, actual = [], ''
    ancho = lambda s: len(re.sub(r'%[sd]', 'X' * max(cifras, 1), s))
    for p in texto.split():
        if ancho(p) > MAX_LINEA:
            raise ValueError(f'palabra de más de {MAX_LINEA}: {p}')
        cand = f'{actual} {p}' if actual else p
        if actual and ancho(cand) > MAX_LINEA:
            filas.append(actual)
            actual = p
        else:
            actual = cand
    if actual:
        filas.append(actual)
    return filas


def cuerpo_linea(texto: str) -> bytes:
    """Una línea en ancho completo; comprueba glifos."""
    if malos(texto) or '\n' in texto or texto != texto.strip() or not texto:
        raise ValueError(f'{texto!r}: vacío, saltos, espacios extremos o caracteres vetados {malos(texto)}')
    b = K.transportar(texto)
    sg = K.M.sin_glifo(b)
    if sg:
        raise ValueError(f'{texto!r}: sin glifo {sg}')
    return b


def cuerpo_multi(texto: str, cifras: int = 0, max_lineas: int = MAX_LINEAS):
    """Texto de ventana: ajuste a MAX_LINEA con saltos 0x0A. Devuelve (bytes, líneas)."""
    if malos(texto):
        raise ValueError(f'{texto!r}: caracteres vetados {malos(texto)}')
    filas = envolver(plano(texto), cifras)
    if len(filas) > max_lineas:
        raise ValueError(f'{len(filas)} líneas > {max_lineas}: {filas}')
    b = b'\n'.join(K.transportar(f) for f in filas)
    sg = K.M.sin_glifo(b.replace(b'\n', b''))
    if sg:
        raise ValueError(f'{texto!r}: sin glifo {sg}')
    return b, filas


def cabe_multi(texto, cifras=0, capacidad=None):
    try:
        b, _ = cuerpo_multi(texto, cifras)
    except ValueError:
        return False
    return capacidad is None or len(b) + 1 <= capacidad


def pct(s) -> tuple:
    if isinstance(s, bytes):
        s = s.decode('cp932', 'replace')
    return (s.count('%s'), s.count('%d'))


def hueco(raw_len: int) -> int:
    return ((raw_len + 1 + 31) // 32) * 32


# ------------------------------------------------------------------ JinmyakuData (copia de IE1 v33 lib.py, variante wide)
TEXT_KIND_MIN = 0x32


class _Lector:
    def __init__(self, d):
        self.d, self.p = d, 0

    def u8(self):
        self.p += 1
        return self.d[self.p - 1]

    def u16(self):
        self.p += 2
        return struct.unpack_from('<H', self.d, self.p - 2)[0]

    def raw(self, n):
        if self.p + n > len(self.d):
            raise ValueError('lectura fuera del archivo')
        self.p += n
        return bytes(self.d[self.p - n:self.p])


def jparse(data, wide=True):
    r = _Lector(data)
    recs = []
    for i in range(r.u16()):
        rec = {'index': i, 'chapter': r.u8(), 'kind': r.u8()}
        rec['b2'] = r.u16() if wide else r.u8()
        rec['b3'] = r.u16() if wide else r.u8()
        rec['x'], rec['y'], rec['unit'] = r.u16(), r.u16(), r.u16()
        if rec['unit'] == 0:
            rec['icon'], rec['mode'] = r.u16(), r.u16()
        rec['param'] = r.u16()
        if rec['unit'] == 0 and rec['kind'] >= TEXT_KIND_MIN:
            rec['text'] = r.raw(r.u16())
        recs.append(rec)
    edges = [(r.u8(), r.u8()) for _ in range(r.u16())]
    hints = []
    for _ in range(r.u8()):
        hid = r.u8()
        hints.append({'id': hid, 'text': r.raw(r.u8())})
    if r.p != len(data):
        raise ValueError(f'sobran {len(data) - r.p} B')
    return {'wide': wide, 'records': recs, 'edges': edges, 'hints': hints}


def jbuild(doc):
    wide = doc['wide']
    out = bytearray(struct.pack('<H', len(doc['records'])))
    for rec in doc['records']:
        out += bytes((rec['chapter'], rec['kind']))
        out += struct.pack('<HH' if wide else '<BB', rec['b2'], rec['b3'])
        out += struct.pack('<3H', rec['x'], rec['y'], rec['unit'])
        if rec['unit'] == 0:
            out += struct.pack('<2H', rec['icon'], rec['mode'])
        out += struct.pack('<H', rec['param'])
        if rec['unit'] == 0 and rec['kind'] >= TEXT_KIND_MIN:
            out += struct.pack('<H', len(rec['text'])) + rec['text']
    out += struct.pack('<H', len(doc['edges']))
    for a, b in doc['edges']:
        out += bytes((a, b))
    if len(doc['hints']) > 255:
        raise ValueError('más de 255 pistas')
    out.append(len(doc['hints']))
    for h in doc['hints']:
        if len(h['text']) > 255:
            raise ValueError(f'pista {h["id"]} > 255 B')
        out += bytes((h['id'], len(h['text']))) + h['text']
    return bytes(out)


def cifras_pista(doc):
    """Cifras máximas de %s por pista (regla IE1 lib.py): máximo real de los nodos o 5 si ninguno la usa."""
    d = {}
    for rec in doc['records']:
        if rec['kind'] < TEXT_KIND_MIN:
            d[rec['kind']] = min(5, max(d.get(rec['kind'], 1), len(str(rec['param']))))
    return d


# ------------------------------------------------------------------ reutilización de IE1
def _csv(p):
    with open(p, encoding='utf-8') as f:
        return list(csv.DictReader(f))


def ie1_cortos():
    """{(tipo, oficial_normalizado): texto aprobado en IE1}."""
    out = {}
    for fol, tipo in (('item_revision', 'item'), ('tech_revision', 'command')):
        F = IE1 / 'legacy' / fol
        wl = json.loads((F / 'worklist.json').read_text(encoding='utf-8'))
        tx = {}
        for c in sorted(F.glob('chunk_*.json')):
            tx.update(json.loads(c.read_text(encoding='utf-8')))
        for r in wl:
            k = f"{r['kind']}:{r['offset']}"
            if r['kind'] == 'description' and k in tx and r['official']:
                out[(tipo, 'desc', plano(limpiar(r['official'])))] = tx[k]
    for r in _csv(IE1 / 'capas/nombres/objetos/propuesta.csv'):
        if r['oficial'] and r['propuesta'] and 'REVISAR' not in r['criterio']:
            out.setdefault(('item', 'nombre', plano(limpiar(r['oficial']))), r['propuesta'])
    for r in _csv(ROOT / 'translation/shared/glossary/tecnicas.csv'):
        if r['espanol_oficial'] and r['nombre_3ds']:
            out.setdefault(('command', 'nombre', plano(limpiar(r['espanol_oficial']))), r['nombre_3ds'])
    # fieldinf: nombre NDS ES de IE1 (índice IE1) -> corto de v33
    T = json.loads((IE1 / 'capas/historial/nombres/v33_data/translations.json').read_text(encoding='utf-8'))
    f1 = (IE1 / 'fuentes/nds_es/data_iz/logic/sp/fieldinf.dat').read_bytes()
    for k, v in T['fieldinf'].items():
        o = oficial(f1[int(k) * 384 + 144:int(k) * 384 + 176])
        if o:
            out[('fieldinf', 'nombre', plano(o))] = v
    return out
