"""Compara v82 con v81: archivos, eventos, registros (solo 0x301d arg 1 de los 6 eventos) y modelo del motor."""
import hashlib, json, sys
from pathlib import Path
import comun82 as M
K = M.K
C = K.ROOT / 'work/shared/candidatas'
a, b = K.Archivo(C / 'probe_ie1_v81/archive.fa'), K.Archivo(C / 'probe_ie1_v82/archive.fa')
PILOTO = {81000090, 92040100, 92010520, 92010550, 92010620, 92010640}
res = dict(archivos_distintos=[], eventos_distintos=[], registros_no_dialogo_cambiados=[], motor_reajusta=[],
           rotulos_iguales=True, cambios_por_evento={})
for p in sorted(set(a.por) | set(b.por)):
    if p not in a.por or p not in b.por or a.get(p) != b.get(p):
        res['archivos_distintos'].append(p)
for eid in sorted(a.indice):
    da, db = a.evento(eid), b.evento(eid)
    if da == db:
        continue
    res['eventos_distintos'].append(eid)
    ea, oa, ra = K.S.parse(da); eb, ob, rb = K.S.parse(db)
    assert da[:eb] == db[:eb] and oa == ob and len(ra) == len(rb) and len(da) == len(db)
    n = 0
    for i, (x, y) in enumerate(zip(ra, rb)):
        if x.raw == y.raw:
            continue
        if oa.get(x.instruction) != K.OP_DIALOGO or x.argument != 1:
            res['registros_no_dialogo_cambiados'].append((eid, i))
            if oa.get(x.instruction) == 0x4037: res['rotulos_iguales'] = False
        n += 1
    res['cambios_por_evento'][eid] = n
    for i, y in enumerate(rb):
        if ob.get(y.instruction) == K.OP_DIALOGO and y.argument == 1 and b'%' not in y.body and not M.respeta_motor(y.body):
            res['motor_reajusta'].append((eid, i))
res['ok'] = (set(res['archivos_distintos']) <= {'inazuma1/data_iz/script/eve.pkb', 'inazuma1/data_iz/script/eve.pkh'}
             and set(res['eventos_distintos']) <= PILOTO and not res['registros_no_dialogo_cambiados']
             and not res['motor_reajusta'])
res['cro_igual'] = (C / 'probe_ie1_v81/romfs/cro/ina_main1.cro').read_bytes() == (C / 'probe_ie1_v82/romfs/cro/ina_main1.cro').read_bytes()
res['sha256_v82'] = hashlib.sha256((C / 'probe_ie1_v82/archive.fa').read_bytes()).hexdigest()
print(json.dumps(res, indent=1))
(Path(__file__).parent / 'validacion.json').write_text(json.dumps(res, indent=1), encoding='utf-8')
