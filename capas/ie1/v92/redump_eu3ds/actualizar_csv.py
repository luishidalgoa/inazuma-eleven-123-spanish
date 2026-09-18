"""v92 · actualiza translation/ie1/dialogo.csv con el resultado de la capa.

Cada fila (event_id, japones) se asocia a su registro con la clave antigua de alineado_ids.tabla_3ds
(la que usaba ds_official/reinsert: byte de tipo + longitud + texto). Solo eventos de eve.pkb (el CSV no
tiene pachangas).
- registro reemplazado por v92 (o que v91 ya dejó igual al oficial): es_final = texto oficial LITERAL
  (EU 3DS, o NDS si faltaba; con sus saltos; la capa lo reajusta a 22x3 y quita los signos sin glifo),
  estado «oficial»;
- filas cuya clave japonesa es de una lectura de furigana, un rótulo u otra instrucción: sin cambios;
  claves repetidas en un evento: se asignan en orden si hay tantas filas como registros, o si todos los
  registros candidatos tienen el mismo oficial; si no, se dejan («ambiguo»);
- clase c (sin oficial en EU 3DS ni NDS): estado «sin_fuente» (el texto no cambia).
Uso: python -X utf8 work/ie1/capas/v92/redump_eu3ds/actualizar_csv.py
"""
from __future__ import annotations

import collections
import csv
import io
import json
import pickle
import sys

import comun92 as C
from ie123kit.nucleo.texto.nds_latin import decode_cadena

HERE = C.HERE
CSV = C.ROOT / 'translation/ie1/dialogo.csv'


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    filas = pickle.loads((HERE / 'clasificacion.pkl').read_bytes())
    por_id = {(x['evento'], x['id']): x for x in filas if x['tipo'] == 'eve'}
    inf = json.loads((HERE / 'informe.json').read_text(encoding='utf-8'))
    nuevo = {}
    for ev in inf['eventos']:
        if ev['tipo'] != 'eve':
            continue
        for r in ev['registros']:
            if r['tipo_registro'] == 'dialogo':
                nuevo[(ev['evento'], r['indice'])] = (r['oficial'], r['despues'])
    for r in inf['iguales_en_v91']:
        if r['tipo'] == 'eve' and not r['objetivo']:
            nuevo[(r['evento'], r['indice'])] = (r['oficial'], r['texto'])
    jp = C.Guion(C.ORIGINAL, 'eve')
    textos = {}                                   # eid -> [(sid, texto)] de las frases 0x301d arg 1
    for eid, d in jp.eventos().items():
        _, ops, recs = C.K.S.parse(d)
        vistos, lista = set(), []
        for r in recs:
            if ops.get(r.instruction) == C.OP_DIALOGO and r.argument == 1 and r.instruction not in vistos:
                vistos.add(r.instruction)
                lista.append((r.instruction, decode_cadena(r.body, 'sjis')))
        textos[eid] = lista

    def candidatos(eid, k):
        """sids cuya frase japonesa corresponde a la clave antigua k (byte de longitud delante,
        a veces fundido con el primer carácter en un «�»)."""
        out = []
        for sid, t in textos.get(eid, ()):
            if k == t or k[1:] == t or (len(t) > 4 and any(k[j:] == t[i:] for j in (1, 2, 3) for i in (1, 2))):
                out.append(sid)
        return out
    raw = CSV.read_bytes()
    bom = raw.startswith(b'\xef\xbb\xbf')
    texto = raw.decode('utf-8-sig')
    lector = csv.DictReader(io.StringIO(texto, newline=''))
    campos = lector.fieldnames
    filas_csv = list(lector)
    st = collections.Counter()
    vez = collections.Counter()
    total_clave = collections.Counter((r['event_id'], r['japones']) for r in filas_csv)
    for row in filas_csv:
        eid = int(row['event_id'])
        cands = candidatos(eid, row['japones'])
        if not cands:
            st['sin_registro'] += 1
            continue
        clave = (row['event_id'], row['japones'])
        n = vez[clave]
        vez[clave] += 1
        if len(cands) == 1:
            sid = cands[0]
        elif total_clave[clave] == len(cands):
            sid = cands[n]                         # filas repetidas en el orden de los registros
        else:
            ofis = {(por_id[(eid, c)]['clase'], por_id[(eid, c)]['oficial_eu3ds'] or por_id[(eid, c)]['oficial_nds'])
                    for c in cands if (eid, c) in por_id}
            if len(ofis) != 1:
                st['ambiguo'] += 1
                continue
            sid = cands[0]
        x = por_id.get((eid, sid))
        if x is None:
            st['sin_registro'] += 1
            continue
        k = (eid, x['indice'])
        if k in nuevo:
            texto_final = nuevo[k][0]
        elif x['clase'] == 'c':
            if row['estado'] != 'sin_fuente':
                row['estado'] = 'sin_fuente'
                st['marcado_sin_fuente'] += 1
            continue
        else:
            st[f"clase_{x['clase']}_sin_cambio{'_protegido' if x['protegido'] else ''}"] += 1
            continue
        if row['es_final'] != texto_final or row['estado'] != 'oficial':
            st[f"a_oficial_desde_{row['estado']}"] += 1
            row['es_final'] = texto_final
            row['estado'] = 'oficial'
    salida = io.StringIO(newline='')
    w = csv.DictWriter(salida, fieldnames=campos, lineterminator='\r\n' if b'\r\n' in raw[:2000] else '\n')
    w.writeheader()
    w.writerows(filas_csv)
    datos = salida.getvalue().encode('utf-8')
    CSV.write_bytes((b'\xef\xbb\xbf' if bom else b'') + datos)
    print(dict(st), collections.Counter(r['estado'] for r in filas_csv))
    (HERE / 'actualizar_csv.json').write_text(json.dumps(dict(st), ensure_ascii=False, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()
