"""v86 · SONDA de ancho de ventana (ver informe.md). Base: probe_ie1_v85 (v84 + sonda de bigramas).

Solo evento 81000090 (idéntico en v84 y v85):
1. 0x301c ident #334 (SSD 0x1b08, 36 B): arg4 (SSD 0x1b24) 0 -> 0x1A0. arg5 sigue en 0.
2. #406 -> «Mark, ¿has hecho algo que pueda haber\\nsentado mal al grupo de gamberros?» (37 + 34 car).
3. Calibración: #581 (otro NPC del mismo evento, rumor del Occult) ->
   «Dicen que hay un equipo que maldice al\\nrival. Se llama Occult.» (38 + 23 car). Con 0x1A0 el
   modelo predice un corte ANTES de la «l» de «al»: «...maldice a» | «l» | «rival. Se llama Occult.».
Salida: events/81000090.ssd, aplicado.json.
Uso: python -X utf8 work/ie1/capas/historial/dialogo/v86_ancho_ventana/apply.py
"""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / 'historial/dialogo/v84_saltos_dialogo_total'))
import comun82 as M  # noqa: E402

K = M.K
from dialogue_typography import encode_fullwidth  # noqa: E402

BASE = K.ROOT / 'work/shared/candidatas/probe_ie1_v85/archive.fa'
EID = 81000090
INST_OFF, ARG4_OFF, ANCHO = 0x1b08, 0x1b24, 0x1A0
INST_ESPERADA = bytes.fromhex('4e012400 1c300601 11111100 04000000 02000000') + bytes(16)
# Texto de los registros: dato local (no se publica), en work/ie1/capas/historial/dialogo/v86_ancho_ventana/cambios.json
# formato {"id": [linea1, linea2, intacto]}.
CAMBIOS = {int(k): tuple(v) for k, v in json.loads(
    (K.ROOT / 'work/ie1/capas/historial/dialogo/v86_ancho_ventana/cambios.json').read_text('utf-8')).items()}


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    base = K.Archivo(BASE)
    data = base.evento(EID)
    end, ops, recs = K.S.parse(data)
    assert data[INST_OFF:INST_OFF + 36] == INST_ESPERADA, data[INST_OFF:INST_OFF + 36].hex()
    assert struct.unpack_from('<HHHBB', data, INST_OFF)[0] == 334
    med = K.Medidor(base.fuente())
    cambios, informe = {}, dict(base=str(BASE), evento=EID, arg4=hex(ANCHO), registros=[])
    for i, (l1, l2, intacto) in CAMBIOS.items():
        r = recs[i]
        assert ops[r.instruction] == K.OP_DIALOGO and r.argument == 1
        antes = K.a_espanol(r.body)
        nuevo = encode_fullwidth(l1 + K.SALTO + l2)
        assert len(nuevo) == len(r.body), (i, len(nuevo), len(r.body))
        assert antes.replace(K.SALTO, ' ').replace(K.PAGINA, ' ').split() == (l1 + ' ' + l2).split(), i
        assert not med.sin_glifo(M.transportar(l1 + l2))
        pre = M.preprocesar(nuevo)
        visto = M.motor(nuevo, ancho=ANCHO)
        assert (visto == pre) is intacto, (i, K.a_espanol(visto))
        n = [len(M.transportar(x)) for x in (l1, l2)]
        cambios[i] = nuevo
        informe['registros'].append(dict(
            indice=i, antes=antes, despues=l1 + K.SALTO + l2, caracteres=n,
            tinta=[med.ancho_es(x) for x in (l1, l2)], bytes=len(nuevo),
            motor_0x1A0=K.a_espanol(visto), motor_0xF0=K.a_espanol(M.motor(nuevo)),
            proposito='objetivo: debe verse intacto' if intacto else 'calibración: debe partirse en el car. 38'))
    nuevo_ev = bytearray(K.S.replace(data, cambios))
    nuevo_ev[ARG4_OFF:ARG4_OFF + 4] = struct.pack('<I', ANCHO)
    nuevo_ev = bytes(nuevo_ev)
    end2, ops2, recs2 = K.S.parse(nuevo_ev)
    assert len(nuevo_ev) == len(data) and ops2 == ops and end2 == end
    difs = [k for k in range(32, end) if data[k] != nuevo_ev[k]]
    assert difs and all(ARG4_OFF <= k < ARG4_OFF + 4 for k in difs), difs
    for j, (a, b) in enumerate(zip(recs, recs2)):
        assert (a.instruction, a.argument) == (b.instruction, b.argument)
        assert (a.raw == b.raw) == (j not in cambios), j
    out = HERE / 'events'
    out.mkdir(exist_ok=True)
    (out / f'{EID}.ssd').write_bytes(nuevo_ev)
    informe['bytes_distintos'] = sum(a != b for a, b in zip(data, nuevo_ev))
    (HERE / 'aplicado.json').write_text(json.dumps(informe, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(informe, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
