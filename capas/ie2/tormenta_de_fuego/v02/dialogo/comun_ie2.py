"""IE2 Tormenta de Fuego v02 · diálogo completo: utilidades comunes (issue #69).

Reutiliza las herramientas de IE1 con parámetros, sin tocar tools/:
- emparejado por ID de instrucción: `ie123kit.nucleo.eventos.alineado_ids.emparejar` (patrón de saltos
  + anclas ASCII, el mismo de tools/audit_dialogo_ids.py). La tabla NDS de IE2 difiere de IE1:
  entrada {id u16, tipo u16, longitud u16, ordinal u16} (IE1: longitud u32). `ordinal` > 0 marca las
  frases españolas (1, 2, 3… por evento); ordinal 0 = cadenas de depuración japonesas.
- texto NDS: latín propio del DS (`nds_latin.DS_TABLE`) con pares Shift-JIS incrustados (comillas,
  paréntesis, ♪, espacio de ancho completo).
- transporte: `dialogue_typography.encode_fullwidth` (ancho completo cp932 + portadores de acentos).
- ajuste: `comun82` de v84 (22 caracteres por línea, 3 líneas por página, sin cortar palabras) con el
  modelo del motor (`comun82.motor`); IE2 usa los mismos valores (work/ie2/shared/capas/v01/limites_cro).
"""
from __future__ import annotations

import importlib.util
import re
import struct
import sys
from functools import lru_cache
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[5]
for p in ('tools/src', 'tools'):
    if str(ROOT / p) not in sys.path:
        sys.path.insert(0, str(ROOT / p))

from ie123kit.nucleo.compresion.lz10 import decompress  # noqa: E402
from ie123kit.nucleo.contenedores.fa import FaArchive  # noqa: E402
from ie123kit.nucleo.eventos import ssd as S  # noqa: E402
from ie123kit.nucleo.eventos.alineado_ids import emparejar, tabla_3ds  # noqa: E402
from ie123kit.nucleo.eventos.packnum import parse_index  # noqa: E402
from ie123kit.nucleo.texto.nds_latin import DS_TABLE  # noqa: E402


def _modulo(nombre, ruta):
    spec = importlib.util.spec_from_file_location(nombre, ruta)
    m = importlib.util.module_from_spec(spec)
    sys.modules[nombre] = m
    spec.loader.exec_module(m)
    return m


K82 = _modulo('comun82_v84', ROOT / 'work/ie1/capas/v84/saltos_dialogo_total/comun82.py')
K = K82.K                      # comun v77 (a_espanol, sin_marcas, Medidor, SALTO, PAGINA)
from dialogue_typography import encode_fullwidth  # noqa: E402

JP = ROOT / 'work/shared/base_3ds/romfs/archive.fa'
CAND = ROOT / 'work/shared/candidatas'
NDS = ROOT / 'work/ie2/tormenta_de_fuego/fuentes/nds_es/data_iz/script/sp'
V01_EVENTOS = ROOT / 'work/ie2/tormenta_de_fuego/capas/v01/sonda/events'
FUENTES_V01 = ROOT / 'work/ie2/shared/capas/v01/fuentes/extra'
NOMBRE_V01 = ROOT / 'work/ie2/shared/capas/v01/sonda_nombre/extra'

PK_EVE = ('inazuma2/data_iz/script/eve.pkh', 'inazuma2/data_iz/script/eve.pkb')
PK_MCH = ('inazuma2/data_iz/script/mch.pkh', 'inazuma2/data_iz/script/mch.pkb')
NDS_TEXTO = {'eve': 'evet', 'mch': 'mcht'}

OP_DIALOGO = 0x301D
OP_EXCLUIDOS = (0x4037, 0x402F)          # rótulos y objetivos: tanda propia
SALTO, PAGINA = K82.SALTO, K82.PAGINA
MAX_CAR, LINEAS = K82.MAX_CAR, K82.LINEAS    # 22 × 3
MAX_BYTES = 247
# %s se expande ANTES del ajuste del motor (FURIGANA_LECCIONES, saltos v81): se reserva su hueco.
ANCHO_PCT = {'%s': 12, '%d': 5}

# Protegidos de IE2 (equivalentes a 92010100..92010509 y 81000040 de IE1): la apertura que corre al
# crear partida y el tutorial de movimiento (lápiz, Botón B, destino, guardar). Ver emparejar.py.
PROTEGIDOS = {22010100, 22010200, 22010300, 22010500}

FURI = re.compile(r'%[0-9]*F')
TOKEN = re.compile(r'%[0-9]*[A-Za-z]|%%|\\[nf]')


class Archivo:
    """Lector de un archive.fa con los PackNum de IE2."""

    def __init__(self, ruta):
        self.ruta = Path(ruta)
        self.arc = FaArchive(str(self.ruta))
        self.por = {p: (o, s) for p, o, s in self.arc.entries}
        self._idx = {}

    def get(self, rel):
        o, s = self.por[rel]
        return bytes(self.arc.d[o:o + s])

    def indice(self, pk):
        if pk not in self._idx:
            rutas = PK_EVE if pk == 'eve' else PK_MCH
            pkh, pkb = self.get(rutas[0]), self.get(rutas[1])
            self._idx[pk] = (pkb, {e: (o, s) for e, o, s in parse_index(pkh)})
        return self._idx[pk]

    def ids(self, pk):
        return sorted(self.indice(pk)[1])

    def evento(self, pk, eid):
        pkb, idx = self.indice(pk)
        o, s = idx[eid]
        c = pkb[o:o + s]
        return decompress(c) if c[:1] == b'\x10' else c


def nds_eventos(pk):
    pkb = (NDS / f'{NDS_TEXTO[pk]}.pkb').read_bytes()
    out = {}
    for eid, o, s in parse_index((NDS / f'{NDS_TEXTO[pk]}.pkh').read_bytes()):
        c = pkb[o:o + s]
        if not c:
            continue
        out[eid] = decompress(c) if c[:1] == b'\x10' else c
    return out


def tabla_nds_ie2(buf):
    """{id: (tipo, bytes, ordinal)} con la primera entrada de cada id (NDS IE2, longitud u16)."""
    out, p = {}, 4
    while p + 8 <= len(buf):
        sid, typ, ln, orden = struct.unpack_from('<HHHH', buf, p)
        if ln < 8 or p + ln > len(buf):
            break
        out.setdefault(sid, (typ, buf[p + 8:p + ln].split(b'\0')[0], orden))
        p += ln
    return out


def decode_nds(b: bytes) -> str:
    """Latín del DS + pares Shift-JIS incrustados. Devuelve None si hay bytes desconocidos."""
    out, i = [], 0
    while i < len(b):
        c = b[i]
        if 0x81 <= c <= 0x9F or 0xE0 <= c <= 0xEF:
            out.append(b[i:i + 2].decode('cp932'))
            i += 2
            continue
        if c < 0x80:
            out.append(chr(c))
        elif c in DS_TABLE:
            out.append(DS_TABLE[c])
        else:
            return None
        i += 1
    return ''.join(out)


# Sustituciones de caracteres sin glifo útil (práctica de IE1: sin comillas ni apóstrofos).
# '-' y '~' no tienen ancho completo en shift_jis: − (0x817C, FF0D en la BCFNT y en la NFTR) y 〜 (0x8160, FF5E).
SUSTITUIR = {'”': '', '“': '', '"': '', "'": '', '’': '', '　': ' ', '-': '−', '~': '〜', '～': '〜'}


def normalizar(es: str) -> str:
    for a, b in SUSTITUIR.items():
        es = es.replace(a, b)
    return es


def pct(s: str):
    return (s.count('%s'), s.count('%d'))


def dialogos(data):
    """(end, ins, recs, [índices de registros 0x301d arg 1])."""
    end, ins, recs = S.parse(data)
    return end, ins, recs, [i for i, r in enumerate(recs) if ins.get(r.instruction) == OP_DIALOGO and r.argument == 1]


def es_frase_jp(body: bytes) -> bool:
    """Frase visible: tiene algún carácter japonés (no es nombre de fichero ni etiqueta ASCII)."""
    try:
        t = body.decode('cp932')
    except UnicodeDecodeError:
        return False
    t = FURI.sub('', t)
    return any(ord(c) > 0x7F for c in t) and not t.startswith(('■', '★', '●', '□', '◆'))


def emparejar_evento(data3, datan):
    """{sid3: sidn}, anclas_ok, anclas_mal, tabla NDS."""
    a = tabla_3ds(data3)
    b = tabla_nds_ie2(datan)
    b2 = {k: (t, v) for k, (t, v, _) in b.items()}
    m, ok, mal = emparejar(a, b2)
    return m, ok, mal, b


# ------------------------------------------------------------------ ajuste y transporte

def largo(linea: str) -> int:
    """Caracteres que ocupa una línea en el motor, con %s/%d a su ancho máximo reservado."""
    n, i = 0, 0
    for m in re.finditer(r'%[sd]', linea):
        n += ANCHO_PCT[m.group()]
    return n + len(re.sub(r'%[sd]', '', linea))


def _envolver(bloque: str):
    filas, actual = [], ''
    for p in bloque.split():
        if largo(p) > MAX_CAR:
            raise ValueError(f'palabra más larga que la línea: {p}')
        cand = f'{actual} {p}' if actual else p
        if actual and largo(cand) > MAX_CAR:
            filas.append(actual)
            actual = p
        else:
            actual = cand
    if actual:
        filas.append(actual)
    return filas


def ajustar(texto: str) -> str:
    """Reparto en cajas de 3 × 22 por frases (v51 `por_frases` + v84 `comun82.ajustar`).

    Conserva los `\\f` del NDS; dentro de cada bloque junta frases completas mientras quepan en una caja
    y solo parte una frase entre cajas si ella sola pasa de 3 líneas. Nunca corta palabras."""
    texto = FURI.sub('', texto)
    cajas = []
    for bloque in texto.split(PAGINA):
        limpio = ' '.join(bloque.replace(SALTO, ' ').split())
        frases = [f for f in re.split(r'(?<=[.!?…])\s+', limpio) if f]
        actual, resto = [], False
        for f in frases:
            prueba = _envolver(' '.join(actual + [f]))
            if len(prueba) <= LINEAS:
                actual, resto = prueba, False
                continue
            if actual and not resto:
                cajas.append(actual)
                filas = _envolver(f)
            else:
                # la caja abierta es el final de una frase partida: la siguiente sigue en ella
                # (evita cajas de una o dos palabras, «Junta.»)
                filas = prueba
            resto = len(filas) > LINEAS
            while len(filas) > LINEAS:
                cajas.append(filas[:LINEAS])
                filas = _envolver(' '.join(filas[LINEAS:]))
            actual = filas
        if actual:
            cajas.append(actual)
    return PAGINA.join(SALTO.join(c) for c in cajas)


def transportar(texto_es: str) -> bytes:
    return encode_fullwidth(texto_es)


@lru_cache(maxsize=1)
def glifos():
    """Códigos con glifo en font/FONT12.bcfnt de la base (el diálogo se dibuja con él, como en v84)."""
    from ie123kit._legado.bcfnt import BCFNT
    a = Archivo(JP)
    b = BCFNT(a.get('font/FONT12.bcfnt'))
    cm = {}
    for c in b.cmaps():
        cm.update(c['entries'])
    return frozenset(cm)


def sin_glifo(cuerpo: bytes):
    t = re.sub(r'%[0-9]*[A-Za-z]|\\[nf]', '', cuerpo.decode('cp932'))
    return sorted({c for c in t if ord(c) not in glifos()})


def motor_simulado(cuerpo: bytes) -> bytes:
    """El motor expande %s/%d antes del ajuste: se simula con su ancho reservado."""
    t = cuerpo
    for k, n in ANCHO_PCT.items():
        t = t.replace(k.encode(), 'Ｘ'.encode('cp932') * n)
    return t


def paginas(cuerpo: bytes):
    """[[línea], ...] tal como las dibuja el motor (con %s/%d al ancho reservado)."""
    return K82.paginas_motor(motor_simulado(cuerpo))


def respeta_motor(cuerpo: bytes) -> bool:
    return K82.respeta_motor(motor_simulado(cuerpo))
