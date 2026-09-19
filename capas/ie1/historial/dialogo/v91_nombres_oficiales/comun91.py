"""v91 · utilidades: candidata, japonés original, NDS española y emparejado por ID."""
from __future__ import annotations

import struct
import sys
from functools import lru_cache
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / 'historial/dialogo/v82_saltos_dialogo'))
import comun82 as M  # noqa: E402

K = M.K
ROOT = K.ROOT
sys.path.insert(0, str(ROOT / 'tools/src'))
from ie123kit._legado import ds_official as D  # noqa: E402
from ie123kit.nucleo.eventos.alineado_ids import tabla_nds, tabla_3ds, emparejar  # noqa: E402

BASE = ROOT / 'work/shared/candidatas/probe_ie2_v05/archive.fa'


def entradas_nds(buf):
    """{(id, tipo): bytes} con todas las entradas de un evento NDS."""
    out, p = {}, 4
    while p + 8 <= len(buf):
        sid, typ, ln = struct.unpack_from('<HHI', buf, p)
        if ln < 8 or p + ln > len(buf):
            break
        out.setdefault((sid, typ), buf[p + 8:p + ln].split(b'\0')[0])
        p += ln
    return out


class Fuentes:
    def __init__(self, base=BASE):
        self.cand = K.Archivo(base)
        self.orig = K.Archivo(K.ORIGINAL)
        self.nds = D.load_ds_events('game1')

    @lru_cache(maxsize=None)
    def pareo(self, eid):
        """(mapa id3ds->idnds, entradas nds) o (None, None)."""
        if eid not in self.nds or eid not in self.orig.indice:
            return None, None
        a = tabla_3ds(self.orig.evento(eid))
        if a is None:
            return None, None
        m, _, _ = emparejar(a, tabla_nds(self.nds[eid]))
        return m, entradas_nds(self.nds[eid])

    @lru_cache(maxsize=None)
    def primeros(self, eid):
        """{id: argumento de su primera entrada} en el evento 3DS original."""
        _, _, recs = K.S.parse(self.orig.evento(eid))
        out = {}
        for r in recs:
            out.setdefault(r.instruction, r.argument)
        return out

    def oficial(self, eid, sid, arg):
        """Texto NDS español (frase, tipo 1) del registro o None.

        Como tools/audit_dialogo_ids.py: la PRIMERA entrada del id 3DS es la frase (su argumento
        puede ser 1 o 2) y le corresponde la entrada de tipo 1 del id NDS emparejado."""
        m, ent = self.pareo(eid)
        if not m or sid not in m or self.primeros(eid).get(sid) != arg:
            return None
        b = ent.get((m[sid], 1))
        return None if b is None else D.decode_ds(b)

    def japones(self, eid, idx):
        _, _, recs = K.S.parse(self.orig.evento(eid))
        r = recs[idx]
        return r, r.body.decode('cp932', 'replace')
