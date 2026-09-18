"""v92 · redump_eu3ds: utilidades comunes.

Fuentes:
- ORIGINAL: work/shared/base_3ds/romfs/archive.fa (japonés, SSD v1).
- EU:       work/ie1/fuentes/3ds_eu/romfs/archive.fa, prefijo `es/` (port europeo, SSD v2).
- BASE:     work/shared/candidatas/probe_ie2_v05/archive.fa (texto actual del juego, SSD v1).

Formato SSD v2 (EU): la cabecera de 32 B y las instrucciones son como en v1 (u16 id, u16 longitud,
u16 opcode, u8 argc, u8 ?; nibbles de tipo; u32 por argumento). Solo cambia la tabla de textos:
  u16 id de instrucción, u16 nº de argumento, u16 longitud (cabecera de 8 B incluida, múltiplo de 4),
  u16 índice (1-based; es el valor de los argumentos de tipo 3) + texto terminado en NUL.
Sin furigana: el 0x301d europeo lleva un solo argumento de tipo 3; el japonés, uno más por lectura.

Texto EU: Shift-JIS en el que los katakana de medio ancho (0xA1..0xDF, 1 byte) son las letras
europeas (misma tabla que la NDS española: 0xB2 á, 0xDF ¡, 0xA5 ¿...). Los pares SJIS que quedan
son signos (comillas, notas) o nombres japoneses sin traducir.
"""
from __future__ import annotations

import difflib
import pickle
import struct
import sys
from functools import lru_cache
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'v82/saltos_dialogo'))
import comun82 as M  # noqa: E402

K = M.K
ROOT = K.ROOT
sys.path.insert(0, str(ROOT / 'tools/src'))
from ie123kit._legado import ds_official as D  # noqa: E402
from ie123kit.nucleo.eventos.alineado_ids import tabla_nds, tabla_3ds, emparejar  # noqa: E402
from ie123kit.nucleo.texto.nds_latin import DS_TABLE, NDS_DEC  # noqa: E402
from fa_unpack import FaArchive  # noqa: E402
from pkb_unpack import parse_index  # noqa: E402
from lz10 import decompress  # noqa: E402
sys.path.insert(0, str(ROOT / 'work/ie1/capas/v88/bigramas_total'))
import comun88  # noqa: E402

ORIGINAL = K.ORIGINAL
EU = ROOT / 'work/ie1/fuentes/3ds_eu/romfs/archive.fa'
BASE = ROOT / 'work/shared/candidatas/probe_ie2_v05/archive.fa'
CACHE = Path.home() / 'AppData/Local/Temp/ie123_v92_cache'
SCRIPT = {'eve': 'inazuma1/data_iz/script/eve', 'mch': 'inazuma1/data_iz/script/mch'}
PROTEGIDOS = K.PROTEGIDOS
DONT_TOUCH = K.DONT_TOUCH
OP_DIALOGO = 0x301D

# 1 byte EU -> letra (0xA1..0xDF). Tabla NDS + las que aparecen en el port (ver informe).
EU_TABLA = dict(NDS_DEC)


_ABIERTOS = {}


def _abrir(fa):
    """Lector mmap de archive.fa (comun88), compartido por ruta: no carga 1,6 GB en memoria."""
    if fa not in _ABIERTOS:
        _ABIERTOS[fa] = comun88.abrir(fa)
    return _ABIERTOS[fa]


def fuente12(fa=None):
    """FONT12.bcfnt de un archive.fa cargada con el cargador de v77 (para el Medidor)."""
    import tempfile
    tmp = Path(tempfile.mkdtemp(prefix='ie123_v92_f12_')) / 'FONT12.bcfnt'
    tmp.write_bytes(_abrir(fa or BASE)(K.F12))
    return K.cargar(tmp)


class Guion:
    """Eventos (descomprimidos, con caché) de eve o mch en un archive.fa."""

    def __init__(self, fa: Path, tipo: str, prefijo: str = ''):
        self.fa, self.tipo, self.prefijo = Path(fa), tipo, prefijo
        self.get = _abrir(self.fa)
        pkh = self.get(prefijo + SCRIPT[tipo] + '.pkh')
        self.indice = {e: (o, s) for e, o, s in parse_index(pkh)}
        self._pkb = None
        st = self.fa.stat()
        clave = f'{self.fa.parent.name}_{tipo}_{prefijo.strip("/") or "jp"}_{st.st_size}_{int(st.st_mtime)}'
        self._cache = CACHE / (clave + '.pkl')
        self._ev = None

    def eventos(self):
        if self._ev is None:
            if self._cache.exists():
                self._ev = pickle.loads(self._cache.read_bytes())
            else:
                pkb = self.get(self.prefijo + SCRIPT[self.tipo] + '.pkb')
                self._ev = {e: decompress(pkb[o:o + s]) for e, (o, s) in self.indice.items()}
                CACHE.mkdir(parents=True, exist_ok=True)
                self._cache.write_bytes(pickle.dumps(self._ev))
        return self._ev

    def evento(self, eid):
        return self.eventos()[eid]


def instrucciones(d):
    """[(id, opcode, argc)] en orden."""
    _, _, _, count, _, cs, _, _, _ = struct.unpack_from('<4sIIHHIIII', b'SSD\0' + d[4:])
    pos, out = 32, []
    for _ in range(count):
        ident, length, op, argc, _u = struct.unpack_from('<HHHBB', d, pos)
        out.append((ident, op, argc))
        pos += length
    return out


def textos_v2(d):
    """[(id, argumento, índice, bytes)] del SSD v2 europeo."""
    cs = struct.unpack_from('<I', d, 16)[0]
    p, out = 32 + cs, []
    while p < len(d):
        sid, arg, ln, idx = struct.unpack_from('<HHHH', d, p)
        if ln < 8:
            raise ValueError('registro v2 vacío')
        out.append((sid, arg, idx, d[p + 8:p + ln].split(b'\0')[0]))
        p += ln
    return out


def decodificar_eu(b: bytes) -> str:
    """Texto EU -> Unicode. Controles `\\n`/`\\f`/`%s` quedan literales."""
    out, i = [], 0
    while i < len(b):
        c = b[i]
        if 0x81 <= c <= 0x9F or 0xE0 <= c <= 0xFC:
            out.append(b[i:i + 2].decode('cp932', 'replace'))
            i += 2
            continue
        if 0xA1 <= c <= 0xDF:
            out.append(EU_TABLA.get(c, f'<{c:02X}>'))
        elif c == 0x7E:
            out.append('º')
        elif c >= 0x80:
            out.append(f'<{c:02X}>')
        else:
            out.append(chr(c))
        i += 1
    return ''.join(out)


def mapa_ids(ins_a, ins_b):
    """ids de a -> ids de b alineando la secuencia de opcodes (directo si coinciden)."""
    ida = {i: op for i, op, _ in ins_a}
    idb = {i: op for i, op, _ in ins_b}
    if ida == idb:
        return {i: i for i in ida}, True
    sa = [op for _, op, _ in ins_a]
    sb = [op for _, op, _ in ins_b]
    sm = difflib.SequenceMatcher(None, sa, sb, autojunk=False)
    m = {}
    for i, j, n in sm.get_matching_blocks():
        for k in range(n):
            m[ins_a[i + k][0]] = ins_b[j + k][0]
    return m, False


@lru_cache(maxsize=None)
def _nada():
    return None


def norm(t: str) -> str:
    """Comparación: sin saltos, sin espacios repetidos, sin %NF, apóstrofo/comillas fuera."""
    t = K.sin_marcas(t).replace(r'\n', ' ').replace(r'\f', ' ')
    for a, b in (('’', "'"), ('“', '"'), ('”', '"'), ('　', ' '), ('…', '...')):
        t = t.replace(a, b)
    t = t.replace("'", '').replace('"', '')
    return ' '.join(t.split())
