"""IE2 Fuego v13 · inicio: validación offline de events/ (checks de v02 validar.py + los de esta capa).

Por evento (22010100, 22010200, 22010300, 22010500):
- bytecode (32..fin) y tabla de instrucciones idénticos al japonés; mismo número e identidad de registros;
- solo cambian registros 0x301d argumento 1 (lecturas, 0x3070, 0x3017, 0x402f... byte a byte);
  respecto a probe_ie2_v10 solo cambian esos mismos registros;
- ningún registro de diálogo sigue en japonés (texto visible sin kana ni kanji, leyendo los portadores
  de acentos con a_espanol) y ninguno lleva marcas %NF;
- cada registro cambiado lo referencia solo 0x301d argumento 1.
Por registro cambiado: <= 247 B, %s/%d como el japonés, glifo en FONT12.bcfnt, el motor no reajusta,
<= 22 caracteres y <= 3 líneas por caja, sin líneas vacías, igual a v02 preparar(texto NDS o condensado)
y mismas palabras que la fuente (los condensados solo quitan palabras de la fuente).
Emparejado: ordinales NDS crecientes en el orden de los registros (1, 2, 3...) y, en las frases con
voz, el mismo ID NDS que la auditoría v07 (auditoria_voces.json).
Salida: validacion.json. Código 1 si falla algo.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter

import apply as A

M = A.M
AUDITORIA = A.ROOT / 'work/ie2/shared/capas/v07/media/auditoria_voces.json'
JAPONES = re.compile(r'[぀-ヿ㐀-鿿]')


def plano(t):
    return ' '.join(re.sub(r'\\[nf]', ' ', M.FURI.sub('', M.normalizar(t))).split())


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    jp = M.Archivo(M.JP)
    base = M.Archivo(A.BASE)
    informe = json.loads((A.HERE / 'informe.json').read_text(encoding='utf-8'))
    audit = {e['evento']: {l['id_juego']: l.get('id_nds') for l in e['lineas'] if 'id_juego' in l}
             for e in json.loads(AUDITORIA.read_text(encoding='utf-8'))['eventos']}
    fallos, ejemplos = Counter(), {}
    res = dict(eventos={})

    def fallo(k, x):
        fallos[k] += 1
        ejemplos.setdefault(k, str(x)[:300])

    for eid in A.EVENTOS:
        da, dv = jp.evento('eve', eid), base.evento('eve', eid)
        db = (A.HERE / 'events' / f'{eid}.ssd').read_bytes()
        ea, oa, ra = M.S.parse(da)
        eb, ob, rb = M.S.parse(db)
        _, _, rv = M.S.parse(dv)
        if da[32:ea] != db[32:eb] or oa != ob or len(ra) != len(rb):
            fallo('bytecode', eid)
            continue
        refs = A.referencias(db)
        info = informe['eventos'][str(eid)]
        filas = {f['indice']: f for f in info['registros']}
        cambiados, voz_ok = [], 0
        for i, (x, y, v) in enumerate(zip(ra, rb, rv)):
            op = oa.get(x.instruction)
            if (x.instruction, x.argument) != (y.instruction, y.argument):
                fallo('identidad', (eid, i))
            es_dialogo = op == M.OP_DIALOGO and x.argument == 1
            if es_dialogo:
                t = M.K.a_espanol(y.body) if y.body != x.body else x.body.decode('cp932')
                if JAPONES.search(M.FURI.sub('', t)):
                    fallo('queda_japones', (eid, i, t))
                if re.search(rb'%[0-9]*F', y.body):
                    fallo('furigana', (eid, i))
            if x.raw == y.raw:
                if v.raw != x.raw and (eid, i) != A.SONDA_V01:
                    fallo('v10_distinto', (eid, i))
                continue
            cambiados.append(i)
            if not es_dialogo:
                fallo('no_dialogo', (eid, i, hex(op or 0), x.argument))
                continue
            if v.raw != x.raw and (eid, i) != A.SONDA_V01:
                fallo('v10_distinto', (eid, i))
            if refs.get(i) != {(M.OP_DIALOGO, 1)}:
                fallo('referencias', (eid, i, refs.get(i)))
            t = y.body.decode('cp932')
            if len(y.body) > M.MAX_BYTES:
                fallo('excede_247', (eid, i))
            if M.pct(t) != M.pct(x.body.decode('cp932')):
                fallo('pct', (eid, i))
            if M.sin_glifo(y.body):
                fallo('sin_glifo', (eid, i, M.sin_glifo(y.body)))
            if not M.respeta_motor(y.body):
                fallo('motor_reajusta', (eid, i))
            for pg in M.paginas(y.body):
                if not 0 < len(pg) <= M.LINEAS:
                    fallo('mas_de_3_lineas', (eid, i))
                for ln in pg:
                    if len(ln) > M.MAX_CAR:
                        fallo('mas_de_22', (eid, i, ln))
                    if not ln.strip():
                        fallo('linea_vacia', (eid, i))
            f = filas.get(i)
            if f is None or f.get('estado') != 'traducido':
                fallo('no_declarado', (eid, i))
                continue
            fuente = f.get('condensado', f['nds'])
            cuerpo, texto = A.A02.preparar(x.body.decode('cp932'), fuente)
            if y.body != cuerpo or texto != f['texto']:
                fallo('no_es_lo_aplicado', (eid, i))
            if plano(texto) != plano(fuente):
                fallo('palabras', (eid, i))
            if 'condensado' in f:
                quitadas = Counter(plano(f['nds']).split()) - Counter(plano(fuente).split())
                nuevas = Counter(plano(fuente).split()) - Counter(plano(f['nds']).split())
                if not quitadas or sum(quitadas.values()) > 2 or any(w.lower() not in
                                                                      {p.lower() for p in plano(f['nds']).split()}
                                                                      for w in nuevas):
                    fallo('condensado_no_minimo', (eid, i, dict(quitadas), dict(nuevas)))
            if f['voz']:
                esperado = audit.get(eid, {}).get(f['id'])
                if esperado is not None and esperado != f['id_nds']:
                    fallo('voz_id_nds', (eid, i, esperado, f['id_nds']))
                voz_ok += esperado == f['id_nds']
        ordinales = [filas[i]['ordinal'] for i in sorted(filas)]
        if ordinales != sorted(ordinales) or len(set(ordinales)) != len(ordinales):
            fallo('ordinales', (eid, ordinales))
        declarados = sorted(i for i, f in filas.items() if f.get('estado') == 'traducido')
        if cambiados != declarados:
            fallo('cambios_no_declarados', (eid, cambiados, declarados))
        res['eventos'][eid] = dict(registros_cambiados=len(cambiados), bytes_jp=len(da), bytes=len(db),
                                   crece=len(db) - len(da), voces_con_id_de_auditoria=voz_ok,
                                   ordinales=ordinales)
    res['fallos'] = dict(fallos)
    res['ejemplos'] = ejemplos
    res['resultado'] = 'PASS' if not fallos else 'FAIL'
    (A.HERE / 'validacion.json').write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return 0 if not fallos else 1


if __name__ == '__main__':
    sys.exit(main())
