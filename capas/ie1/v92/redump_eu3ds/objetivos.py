"""v92 · objetivos de IE1 (eve.pkb 0x402f arg 3) con el texto oficial del port europeo de 3DS.

- Emparejado: el mismo que el diálogo (instrucción japonesa -> europea alineando opcodes) y registro (id', 3).
  El arg 2 es el rótulo «Objetivo»: el europeo lo deja en japonés (もくてき), así que no se toca.
- Codificación: registro de bigramas v89 (work/ie1/capas/v89/bigramas_ritmo/registro.json), SIN códigos nuevos.
  La FONT12 de la base (probe_ie2_v05) tiene los 847 glifos del registro idénticos a los de v89
  (se comprueba al cargar). Partición con ritmo.py de v89 (maqueta medida sobre esos glifos): hueco
  sólido >= 1 px dentro de palabra y >= 4 px entre palabras; además, sin contacto de tinta débil.
- Caja de 128 casillas (no hace falta abreviar). Se excluyen eventos protegidos e índices reutilizados
  (misma regla que v88: recoger). Rótulos 0x4037: sin texto oficial, no se tocan.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import tempfile
from pathlib import Path

import comun92 as C

V89 = C.ROOT / 'work/ie1/capas/v89/bigramas_ritmo'
V88 = C.ROOT / 'work/ie1/capas/v88/bigramas_total'
sys.path.insert(0, str(V89))
sys.path.insert(1, str(V88))
import comun88  # noqa: E402

A89 = comun88.modulo('v89_bigramas', V89 / 'apply.py')
A88, R = A89.A88, A89.R
CASILLAS = 128
JAPONES = re.compile(r'[぀-ヿ一-鿿]')


class Objetivos:
    def __init__(self, base=C.BASE):
        self.get = A89.K.abrir(base)
        self.reg = json.loads((V89 / 'registro.json').read_text(encoding='utf-8'))
        self.codec = A89.Codec(self.reg['bigramas'])
        tmp = Path(tempfile.mkdtemp(prefix='ie123_v92_'))
        (tmp / 'FONT12.bcfnt').write_bytes(self.get(A89.F12))
        self.F = A88.cargar(tmp / 'FONT12.bcfnt')
        Fv = A88.cargar(V89 / 'extra' / A89.F12)
        self.mq = A89.Maqueta(self.F, A88.codepoint)
        for e in self.reg['bigramas']:
            cp = int(e['unicode'][2:], 16)
            gb, gv = self.F.gi(cp), Fv.gi(cp)
            assert gb == gv and self.F.metrics[gb] == Fv.metrics[gv] and self.F.bitmap(gb) == Fv.bitmap(gv), e
            self.mq.fijos[A89.clave_de(e)] = A89.medir(self.F, gb)
        self.claves = set(self.codec.por_par)
        self.sha_font12 = hashlib.sha256(self.get(A89.F12)).hexdigest()

    def unidades(self):
        unidades, eventos, _, _, _ = A88.recoger(self.get, self.codec)
        return [u for u in unidades if u['tipo'] == 'objetivo'], eventos

    def contacto_debil(self, cel):
        """Menor distancia entre tintas (cualquier alfa) de casillas contiguas; None si no hay pares."""
        peor, prev = None, None
        for k, c in enumerate(cel):
            if c == ' ':
                continue
            gi = (self.F.gi(ord(self.codec.por_par[c].decode('cp932'))) if len(c) >= 2
                  else self.F.gi(A88.codepoint(c)))
            left, _, adv = self.F.metrics[gi]
            x0 = int((15 - adv) / 2) + left
            xs = [x + x0 for y, row in enumerate(self.F.bitmap(gi)) for x, v in enumerate(row) if v]
            if prev is not None and xs:
                gd = min(xs) + (k - prev[0]) * 15 - prev[1] - 1
                peor = gd if peor is None else min(peor, gd)
            if xs:
                prev = (k, max(xs))
        return peor

    def codificar(self, t):
        """(bytes, casillas) o ValueError."""
        coste, cel = R.particion(t, self.mq, lambda c: c in self.claves)
        if coste == R.INF:
            raise ValueError('sin partición sin solapes')
        cel = list(cel)
        if len(cel) > CASILLAS:
            raise ValueError(f'{len(cel)} casillas > {CASILLAS}')
        try:
            body = self.codec.codificar(cel)
        except (UnicodeEncodeError, UnicodeDecodeError, KeyError) as e:
            raise ValueError(f'no codificable: {e}')
        if self.codec.texto(body) != t:
            raise ValueError('no decodifica igual')
        if any(g < (R.PAL_MIN if pal else 1) for g, pal in R.huecos(cel, self.mq)):
            raise ValueError('hueco sólido insuficiente')
        d = self.contacto_debil(cel)
        if d is not None and d < 0:
            raise ValueError('tinta débil solapada')
        return body, cel


def planificar(limpiar):
    """{eid: {indice: (body, info)}}, lista de cambios, lista de rechazos."""
    ob = Objetivos()
    jp = C.Guion(C.ORIGINAL, 'eve')
    eu = C.Guion(C.EU, 'eve', 'es/')
    units, eventos = ob.unidades()
    plan, cambios, rechazos = {}, [], []
    for u in units:
        if u['arg'] != 3:
            continue
        eid = u['evento']
        antes = ob.codec.texto(u['body'])
        info = dict(evento=eid, indice=u['indice'], antes=antes)
        if u['excluido']:
            rechazos.append(dict(info, motivo=u['excluido']))
            continue
        if any(k != 't' for k, _ in u['segs']):
            rechazos.append(dict(info, motivo='lleva bytes opacos'))
            continue
        _, _, recs = C.K.S.parse(eventos[eid])
        sid = recs[u['indice']].instruction
        if eid not in eu.eventos():
            rechazos.append(dict(info, motivo='sin evento europeo'))
            continue
        jd, ed = jp.evento(eid), eu.evento(eid)
        m, _ = C.mapa_ids(C.instrucciones(jd), C.instrucciones(ed))
        ops_eu = {i: op for i, op, _ in C.instrucciones(ed)}
        if sid not in m or ops_eu.get(m[sid]) != 0x402F:
            rechazos.append(dict(info, motivo='instrucción sin pareja europea'))
            continue
        eb = next((b for s, a, _, b in C.textos_v2(ed) if (s, a) == (m[sid], 3)), None)
        if eb is None:
            rechazos.append(dict(info, motivo='sin registro europeo'))
            continue
        oficial = C.decodificar_eu(eb)
        # dos objetivos europeos llevan salto de línea; ningún objetivo japonés lo usa: se unen con espacio
        oficial_1l = oficial.replace('\\n', ' ')
        if not oficial_1l.strip() or JAPONES.search(oficial_1l) or '\\' in oficial_1l or '<' in oficial_1l:
            rechazos.append(dict(info, oficial=oficial, motivo='oficial no utilizable'))
            continue
        nuevo_t = ' '.join(limpiar(oficial_1l).split())
        if nuevo_t == antes:
            continue
        try:
            body, cel = ob.codificar(nuevo_t)
        except ValueError as e:
            rechazos.append(dict(info, oficial=oficial, motivo=str(e)))
            continue
        vista = '|'.join(R.texto(c) for c in cel)
        plan.setdefault(eid, {})[u['indice']] = (body, dict(info, despues=nuevo_t, oficial=oficial, casillas=vista,
                                                            bytes_antes=len(u['body']), bytes=len(body)))
        cambios.append(dict(info, despues=nuevo_t, casillas=vista, bytes_antes=len(u['body']), bytes=len(body)))
    return plan, cambios, rechazos, ob.sha_font12
