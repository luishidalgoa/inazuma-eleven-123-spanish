"""v84 frente a v81: comprueba TODOS los registros cambiados (22 car./línea, 3 líneas/página, sin palabras
cortadas, mismos bytes de registro/evento, códigos de control, %NF y %s intactos, solo 0x301d arg 1)."""
import hashlib, json, re, sys
from collections import Counter
from pathlib import Path
import comun82 as M
import importlib.util
K = M.K
spec = importlib.util.spec_from_file_location('a77', M.V77 / 'apply.py'); A77 = importlib.util.module_from_spec(spec); spec.loader.exec_module(A77)
C = K.ROOT / 'work/shared/candidatas'
a, b = K.Archivo(C / 'probe_ie1_v81/archive.fa'), K.Archivo(C / 'probe_ie1_v84/archive.fa')
PILOTO = set(A77.PILOTO)
fallos = Counter(); ejemplos = {}
def fallo(k, x):
    fallos[k] += 1; ejemplos.setdefault(k, x)
def codigos(body):
    t = body.decode('cp932')
    return (Counter(re.findall(r'%[^%]*?[A-Za-z]|%%', t)), Counter(re.findall(r'\[^nf]', t)))
res = dict(archivos_distintos=[], eventos_cambiados=0, registros_cambiados=0, paginas_antes=0, paginas_despues=0)
for p in sorted(set(a.por) | set(b.por)):
    if p not in a.por or p not in b.por or a.get(p) != b.get(p):
        res['archivos_distintos'].append(p)
for eid in sorted(a.indice):
    da, db = a.evento(eid), b.evento(eid)
    if da == db:
        continue
    res['eventos_cambiados'] += 1
    if eid in K.PROTEGIDOS or eid in K.DONT_TOUCH: fallo('evento_protegido', eid)
    if len(da) != len(db): fallo('evento_crece', eid)
    ea, oa, ra = K.S.parse(da); eb, ob, rb = K.S.parse(db)
    if da[32:ea] != db[32:eb] or oa != ob or len(ra) != len(rb): fallo('bytecode', eid)
    for i, (x, y) in enumerate(zip(ra, rb)):
        if x.raw == y.raw: continue
        res['registros_cambiados'] += 1
        if ob.get(x.instruction) != K.OP_DIALOGO or x.argument != 1 or (x.instruction, x.argument) != (y.instruction, y.argument):
            fallo('no_dialogo', (eid, i)); continue
        if len(x.raw) != len(y.raw) or len(x.body) != len(y.body): fallo('registro_crece', (eid, i))
        if codigos(x.body) != codigos(y.body): fallo('codigos', (eid, i))
        if A77.palabras(x.body.decode('cp932')) != A77.palabras(y.body.decode('cp932')): fallo('palabras', (eid, i))
        tiene_pct = b'%' in y.body
        if tiene_pct and eid not in PILOTO: fallo('pct_cambiado', (eid, i))
        es = K.a_espanol(y.body)
        res['paginas_antes'] += len(K.a_espanol(x.body).split(K.PAGINA)); res['paginas_despues'] += len(es.split(K.PAGINA))
        if tiene_pct: continue
        if not M.respeta_motor(y.body): fallo('motor_reajusta', (eid, i))
        for pg in M.paginas_motor(y.body):
            if len(pg) > 3: fallo('mas_de_3_lineas', (eid, i))
            for ln in pg:
                if len(ln) > M.MAX_CAR: fallo('mas_de_22', (eid, i, ln))
                if not ln.strip(): fallo('linea_vacia', (eid, i))
res['cro_igual'] = (C / 'probe_ie1_v81/romfs/cro/ina_main1.cro').read_bytes() == (C / 'probe_ie1_v84/romfs/cro/ina_main1.cro').read_bytes()
res['fallos'] = dict(fallos); res['ejemplos'] = {k: str(v) for k, v in ejemplos.items()}
res['ok'] = not fallos and res['cro_igual'] and set(res['archivos_distintos']) <= {'inazuma1/data_iz/script/eve.pkb', 'inazuma1/data_iz/script/eve.pkh'}
res['sha256_v84'] = hashlib.sha256((C / 'probe_ie1_v84/archive.fa').read_bytes()).hexdigest()
print(json.dumps(res, indent=1, ensure_ascii=False))
(Path(__file__).parent / 'validacion.json').write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding='utf-8')
