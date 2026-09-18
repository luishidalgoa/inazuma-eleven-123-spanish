"""IE2 Fuego v02 · paso 1: emparejar eve.pkb/mch.pkb 3DS con evet.pkb/mcht.pkb NDS por ID de instrucción.

Nunca por orden de líneas (FURIGANA_LECCIONES, issue #36). Método de tools/audit_dialogo_ids.py:
alinear la secuencia de saltos entre IDs con difflib y validar con anclas ASCII (comun_ie2.emparejar_evento).

Clases por REGISTRO de diálogo (0x301d arg 1 con texto japonés visible):
- igual:       emparejado con la entrada NDS del MISMO id.
- desplazado:  emparejado con otro id (la NDS tiene instrucciones de más o de menos).
- sin_par:     el id no se alinea o apunta a una entrada NDS que no es frase española.
- pct_distinto: emparejado pero %s/%d no coinciden con el japonés (no se usa).
- protegido:   evento protegido (no se toca).
Clases por EVENTO (solo eventos con diálogo):
- igual:      todos sus registros son «igual».
- desplazado: todos emparejados y al menos uno desplazado.
- editado:    el 3DS cambió el evento: unos registros emparejan y otros no.
- distinto:   ningún registro empareja, no existe en la NDS, o las anclas ASCII contradicen el alineado.
- protegido:  PROTEGIDOS (apertura al crear partida y tutorial).

Salida (work/, no se sube): pares.json, clasificacion.json.
Uso: python -X utf8 emparejar.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter

import comun_ie2 as M


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    jp = M.Archivo(M.JP)
    pares, resumen = {}, {}
    for pk in ('eve', 'mch'):
        nds = M.nds_eventos(pk)
        ids3 = jp.ids(pk)
        ev_cls, rec_cls = Counter(), Counter()
        detalle = {}
        for eid in ids3:
            data = jp.evento(pk, eid)
            try:
                _, _, recs, dl = M.dialogos(data)
            except ValueError:
                ev_cls['no_ssd'] += 1
                continue
            frases = [i for i in dl if M.es_frase_jp(recs[i].body)]
            if not frases:
                ev_cls['sin_dialogo'] += 1
                continue
            if eid in M.PROTEGIDOS:
                ev_cls['protegido'] += 1
                rec_cls['protegido'] += len(frases)
                detalle[eid] = dict(clase='protegido', registros=len(frases))
                continue
            if eid not in nds:
                ev_cls['distinto'] += 1
                rec_cls['sin_par'] += len(frases)
                detalle[eid] = dict(clase='distinto', motivo='solo 3DS', registros=len(frases))
                continue
            m, ok, mal, tb = M.emparejar_evento(data, nds[eid])
            cls = Counter()
            filas = []
            for i in frases:
                r = recs[i]
                sn = m.get(r.instruction)
                ent = tb.get(sn) if sn is not None else None
                if ent is None or ent[0] != 1 or ent[2] == 0:
                    cls['sin_par'] += 1
                    continue
                es = M.decode_nds(ent[1])
                jt = r.body.decode('cp932')
                if es is None or not es.strip():
                    cls['sin_par'] += 1
                    continue
                if M.pct(jt) != M.pct(es):
                    cls['pct_distinto'] += 1
                    continue
                c = 'igual' if sn == r.instruction else 'desplazado'
                cls[c] += 1
                filas.append(dict(indice=i, id=r.instruction, id_nds=sn, ordinal=ent[2], jp=jt, es=es, clase=c))
            fiable = mal <= ok or mal == 0
            n = len(frases)
            if not fiable or not filas:
                clase = 'distinto'
            elif cls['igual'] == n:
                clase = 'igual'
            elif cls['igual'] + cls['desplazado'] == n:
                clase = 'desplazado'
            else:
                clase = 'editado'
            if not fiable:
                cls = Counter(sin_par=n)
                filas = []
            ev_cls[clase] += 1
            rec_cls.update(cls)
            detalle[eid] = dict(clase=clase, registros=n, anclas_ok=ok, anclas_mal=mal, **cls)
            if filas:
                pares[f'{pk}:{eid}'] = filas
        solo_nds = sorted(set(nds) - set(ids3))
        resumen[pk] = dict(eventos_3ds=len(ids3), eventos_nds=len(nds), solo_nds=len(solo_nds),
                           eventos=dict(ev_cls), registros=dict(rec_cls), detalle=detalle)
        print(pk, dict(ev_cls), dict(rec_cls))
    (M.HERE / 'pares.json').write_text(json.dumps(pares, ensure_ascii=False, indent=0), encoding='utf-8')
    (M.HERE / 'clasificacion.json').write_text(json.dumps(resumen, ensure_ascii=False, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()
