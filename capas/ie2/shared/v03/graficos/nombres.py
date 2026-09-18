"""Textos oficiales para las texturas pintadas: técnicas (command.dat/STR, registros de 28 B, nombre en +20)
de la 3DS japonesa y de la NDS española de IE2. El número de textura bcNNN/tcNNN es el ID de técnica
(comprobado en IE1: bc022 = técnica 22 «ボレーシュート»).
"""
import re
import struct
import sys
from functools import lru_cache

import comun as C

sys.path.insert(0, str(C.ROOT / 'tools/src'))
from ie123kit.nucleo.texto.nds_latin import dec_es  # noqa: E402


def _tabla(dat, st, dec):
    out = {}
    for tid in range(len(dat) // 28):
        n = struct.unpack_from('<H', dat, tid * 28 + 20)[0] * 32
        if n and n < len(st):
            out[tid] = dec(st[n:st.index(b'\0', n)])
    return out


def _limpiar(t):
    t = re.sub(r'\[([^/\]]+)/[^\]]+\]', r'\1', t)
    t = t.replace('　', ' ')
    return t.strip()


@lru_cache(None)
def tecnicas_jp():
    j = C.jp()
    return _tabla(j.get('inazuma2/data_iz/logic/command.dat'), j.get('inazuma2/data_iz/logic/command.STR'),
                  lambda b: b.decode('cp932', 'replace'))


@lru_cache(None)
def tecnicas_es():
    return {k: _limpiar(v) for k, v in _tabla(C.nds('data_iz/logic/sp/command.dat'),
                                                 C.nds('data_iz/logic/sp/command.STR'), dec_es).items()}


def id_textura(nombre):
    m = re.search(r'_(?:bc|bg|bs|bd|tc|ts|tg|td)?(\d{3})\D*\.tga$', nombre)
    return int(m.group(1)) if m else None


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    for t in (1, 2, 22, 30, 60, 106, 130, 301):
        print(t, tecnicas_jp().get(t), '|', tecnicas_es().get(t))


def tecnica(tid):
    """Nombre oficial ES; si la NDS lo trae sin traducir, el de otra técnica con el mismo nombre japonés."""
    es, jp = tecnicas_es(), tecnicas_jp()
    t = es.get(tid)
    if t and '?' not in t:
        return t
    for k, v in jp.items():
        if v == jp.get(tid) and k != tid and es.get(k) and '?' not in es[k]:
            return es[k]
    raise KeyError(f'técnica {tid} sin nombre español')


@lru_cache(None)
def equipos():
    """{id de textura (u16 en +32 de team.pkb): (japonés, español NDS)} — registros de 320 B."""
    j, e = C.jp().get('inazuma2/data_iz/logic/team.pkb'), C.nds('data_iz/logic/sp/team.pkb')

    def tabla(d, dec):
        out = {}
        for i in range(len(d) // 320):
            t = struct.unpack_from('<H', d, i * 320 + 32)[0]
            out.setdefault(t, _limpiar(dec(d[i * 320:i * 320 + 32].split(b'\0')[0])))
        return out
    tj = tabla(j, lambda b: b.decode('cp932', 'replace'))
    te = tabla(e, dec_es)
    return {t: (tj[t], te.get(t)) for t in tj}


def equipo(tid):
    jp_, es = equipos()[tid]
    if not es or ('?' in es and set(es) != {'?'}):
        raise KeyError(f'equipo {tid} ({jp_}) sin nombre español')
    return es
