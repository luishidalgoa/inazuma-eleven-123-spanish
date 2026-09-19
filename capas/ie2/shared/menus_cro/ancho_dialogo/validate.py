"""IE2 v15 · validación de la sonda de ancho (capa y, si existe, la candidata probe_ie2_v15).

CRO: solo 8 B distintos de la base (v09 = v10), en 0x66a24 y 0x4cabc; se desensamblan como
mov r1/r2,#0x1A0; ninguna entrada de las tablas de parches (0xF8, 0x128, 0x130) los cubre; líneas = 3.
Eventos: bytecode igual a v10 salvo cuerpos de 0x301d arg 1; mismas palabras; <= 247 B; glifos; %s/%d;
modelo del motor a 0x1A0 sin saltos añadidos; <= 37 caracteres y <= 3 líneas por caja.
Candidata: las CRO y los eventos IE2 del archive coinciden con la capa; el resto del PackNum igual a v10.
Uso: python -X utf8 work/ie2/shared/capas/menus_cro/ancho_dialogo/validate.py  -> validacion.json
"""
from __future__ import annotations

import json
import re
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import apply as A  # noqa: E402

M = A.M


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    res, fallos = {}, []

    def ok(nombre, cond, detalle=None):
        res[nombre] = bool(cond) if detalle is None else dict(ok=bool(cond), detalle=detalle)
        if not cond:
            fallos.append(nombre)

    # CRO
    base = A.CRO_BASE.read_bytes()
    nueva = A.CRO_OUT.read_bytes()
    difs = [i for i in range(len(base)) if base[i] != nueva[i]]
    ok('cro_mismo_tamano', len(base) == len(nueva))
    ok('cro_solo_parches', all(any(a <= i < a + 4 for a, *_ in A.PARCHES) for i in difs), [hex(i) for i in difs])
    md = A.Cs(A.CS_ARCH_ARM, A.CS_MODE_ARM)
    for a, w0, w1, _ in A.PARCHES:
        dis = [f'{i.mnemonic} {i.op_str}' for i in md.disasm(nueva[a:a + 4], a)]
        ok(f'cro_{a:#x}', A.u32(base, a) == w0 and A.u32(nueva, a) == w1 and dis[0].endswith(('#0x1a0', '#0x1c0')), dis)
    for a, w, _ in A.CONTEXTO:
        if w is not None:
            ok(f'cro_lineas_{a:#x}', A.u32(nueva, a) == w)
    reloc, tablas, _ = A.comprobar_reloc(nueva)
    ok('cro_sin_relocacion_encima', all(not v['choques'] for v in reloc.values()), reloc)
    ok('cro_tablas_leidas', tablas['relocacion_interna_0x128']['entradas'] > 0, tablas)

    v14 = A.W / 'ie2/shared/capas/historial/menus_cro/v14_ancho_dialogo'
    ok('eventos_iguales_v14', all((A.EV_OUT / f'{e}.ssd').read_bytes() == (v14 / f'ie2/events/{e}.ssd').read_bytes()
                                  for e in A.EVENTOS))
    d14 = (v14 / 'romfs/cro/ina_main2.cro').read_bytes()
    ok('cro_v14_mas_dibujo', [i for i in range(len(d14)) if d14[i] != nueva[i]] == [0x4d6a0, 0x4d6a1], None)

    # eventos
    arc = M.Archivo(A.BASE)
    pares = {}
    for eid in A.EVENTOS:
        v10 = arc.evento('eve', eid)
        v14 = (A.EV_OUT / f'{eid}.ssd').read_bytes()
        end, ins, recs, dl = M.dialogos(v10)
        end2, ins2, recs2 = M.S.parse(v14)
        ok(f'{eid}_bytecode', v14[32:end] == v10[32:end] and ins == ins2 and len(recs) == len(recs2))
        if re.search(rb'%\d+F', v10):
            ok(f'{eid}_no_crece', len(v14) <= len(v10), [len(v10), len(v14)])
        cambiados, malos = 0, []
        for j, (a, b) in enumerate(zip(recs, recs2)):
            if a.raw == b.raw:
                continue
            cambiados += 1
            if j not in dl or (a.instruction, a.argument) != (b.instruction, b.argument):
                malos.append((j, 'no_dialogo'))
                continue
            try:
                A.comprobar_cuerpo(b.body, a.body)
                assert A.palabras(A.espanol(b.body)) == A.palabras(A.espanol(a.body))
            except AssertionError as exc:
                malos.append((j, str(exc)))
        ok(f'{eid}_registros', not malos and cambiados > 0, dict(cambiados=cambiados, malos=malos))
        pares[eid] = v14

    # candidata
    cand = A.W / 'shared/candidatas/probe_ie2_v15'
    if (cand / 'archive.fa').is_file():
        ca = M.Archivo(cand / 'archive.fa')
        for eid, v14 in pares.items():
            ok(f'cand_{eid}', ca.evento('eve', eid) == v14)
        ids = arc.ids('eve')
        ok('cand_mismos_ids', ids == ca.ids('eve'))
        otros = [e for e in ids if e not in pares and ca.evento('eve', e) != arc.evento('eve', e)]
        ok('cand_resto_eve_igual_v10', not otros, otros[:10])
        ok('cand_cro2', (cand / 'romfs/cro/ina_main2.cro').read_bytes() == nueva)
        ok('cand_cro1', (cand / 'romfs/cro/ina_main1.cro').read_bytes()
           == (A.W / 'shared/candidatas/probe_ie2_v10/romfs/cro/ina_main1.cro').read_bytes())
        n10 = sum(1 for p in (A.W / 'shared/candidatas/probe_ie2_v10/romfs').rglob('*') if p.is_file())
        n14 = sum(1 for p in (cand / 'romfs').rglob('*') if p.is_file())
        ok('cand_romfs_completo', n10 == n14, [n10, n14])
    else:
        res['candidata'] = 'no construida'

    out = dict(ok=not fallos, fallos=fallos, comprobaciones=res)
    (HERE / 'validacion.json').write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str),
                                          encoding='utf-8')
    print('OK' if not fallos else f'FALLOS: {fallos}')
    return 0 if not fallos else 1


if __name__ == '__main__':
    sys.exit(main())
