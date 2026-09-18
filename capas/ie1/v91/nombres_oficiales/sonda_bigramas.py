"""Decodifica (aprox.) objetivos y rótulos con el registro v90 y lista sus palabras."""
import json, re, sys, collections
import comun91 as C
sys.stdout.reconfigure(encoding='utf-8')
reg = json.load(open(C.ROOT / 'work/ie1/capas/v90/cro_restantes/registro.json', encoding='utf-8'))
cod = {bytes.fromhex(e['sjis']): e.get('clave', e['par']) for e in reg['bigramas']}
def texto(b):
    out, i = [], 0
    while i < len(b):
        x = b[i]
        if (0x81 <= x <= 0x9F or 0xE0 <= x <= 0xFC):
            t = b[i:i+2]; i += 2
            out.append(cod[t] if t in cod else C.K.a_espanol(t))
        else:
            out.append(chr(x)); i += 1
    return ''.join(out)
F = C.Fuentes()
pat = re.compile(sys.argv[1], re.I) if len(sys.argv) > 1 else None
for eid in sorted(F.cand.indice):
    try:
        _, ops, recs = C.K.S.parse(F.cand.evento(eid))
    except ValueError:
        continue
    for i, r in enumerate(recs):
        op = ops.get(r.instruction)
        if (op, r.argument) in ((0x402f, 2), (0x402f, 3), (0x4037, 3)) and r.body:
            t = texto(r.body)
            if pat is None or pat.search(t):
                print(eid, i, hex(op), r.argument, t)
