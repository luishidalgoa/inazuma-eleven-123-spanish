"""IE2 v19 · rehacer TODOS los saltos del diálogo de IE2 con los límites de la CRO parcheada.

La v17 solo rehizo la sonda (22500101/22500102) y en el resto se limitó a partir páginas de más de
131 B con la maqueta antigua de 22 caracteres. Aquí se rehace **todo** el diálogo de eve y mch
(incluidos los 4 eventos de apertura protegidos de la v16) con el reparto por coste de la v17:

- 37 caracteres por línea como máximo, 3 líneas por página, 131 B por página, 247 B por registro;
- nunca se corta una palabra y **nunca se cambia el texto**: solo los saltos (Norma 3);
- los cortes de página se prefieren al final de frase y se penalizan las páginas huérfanas.

Reglas de seguridad:
- Solo se rehacen los registros de diálogo 0x301d argumento 1 (`comun_ie2.dialogos`). Los rótulos
  (0x4037) y objetivos (0x402F) tienen su propia codificación y no se tocan.
- Un registro solo se rehace si `espanol()`/`transportar()` lo reproducen byte a byte (red para
  bigramas y codificaciones especiales). Si no, se conserva y, si alguna página pasa de 131 B, se
  aplica el corte mínimo `\\n` -> `\\f` de la v17.
- Los registros que pasen de 247 B se informan; **no se acortan**.

Base: work/shared/candidatas/probe_ie2_v17/archive.fa
Salida: ie2/eve/*.ssd, ie2/mch/*.ssd, informe.json
Uso: python -X utf8 work/ie2/shared/capas/v19/saltos37/apply.py
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import comun19 as C  # noqa: E402

M = C.M
ROOT = C.ROOT
W = ROOT / 'work'
BASE = W / 'shared/candidatas/probe_ie2_v17/archive.fa'
SALIDA = {'eve': HERE / 'ie2/eve', 'mch': HERE / 'ie2/mch'}


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    arc = M.Archivo(BASE)
    for d in SALIDA.values():
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)
    tot = Counter()
    inf = dict(base=str(BASE), limites=dict(caracteres=C.MAX_CAR, lineas=C.LINEAS,
                                            pagina=C.PAGINA_MAX, registro=C.MAX_BYTES),
               no_rehechos=[], mayores_247=[], cortes_minimos=[], sin_resolver=[], eventos_revertidos=[])
    for pk in ('eve', 'mch'):
        for eid in arc.ids(pk):
            data = arc.evento(pk, eid)
            end, ins, recs, dl = M.dialogos(data)
            cambios = {}
            for i in dl:
                body = recs[i].body
                tot['registros'] += 1
                tot['paginas_antes'] += len(C.paginas(body))
                nuevo, info = C.reparte(body)
                if nuevo is None:
                    inf['no_rehechos'].append(dict(paquete=pk, evento=eid, indice=i, motivo=info))
                    tot['no_rehechos'] += 1
                    # red de la v17: cortar solo donde la página pasaría de 131 B
                    if any(len(p) > C.PAGINA_MAX for p in C.paginas(body)):
                        try:
                            t2, n = C.partir_paginas(body.decode('cp932'))
                        except UnicodeDecodeError:
                            inf['sin_resolver'].append(dict(paquete=pk, evento=eid, indice=i,
                                                            motivo='no decodifica cp932'))
                            tot['paginas_despues'] += len(C.paginas(body))
                            continue
                        nuevo = t2.encode('cp932')
                        assert len(nuevo) == len(body)
                        assert nuevo.replace(b'\\f', b'\\n') == body.replace(b'\\f', b'\\n')
                        if n:
                            cambios[i] = nuevo
                            tot['cortes_minimos'] += n
                            inf['cortes_minimos'].append(dict(paquete=pk, evento=eid, indice=i, cortes=n))
                    else:
                        nuevo = body
                else:
                    tot['rehechos'] += 1
                    if nuevo != body:
                        cambios[i] = nuevo
                        tot['cambiados'] += 1
                tot['paginas_despues'] += len(C.paginas(nuevo))
                p = C.problemas(nuevo)
                if p:
                    inf['sin_resolver'].append(dict(paquete=pk, evento=eid, indice=i, problemas=p))
                if len(nuevo) > C.MAX_BYTES:
                    inf['mayores_247'].append(dict(paquete=pk, evento=eid, indice=i,
                                                   bytes_v17=len(body), bytes_v19=len(nuevo),
                                                   texto=C.espanol(nuevo) if C.es_espanol(nuevo) else None))
            if not cambios:
                continue
            nuevo_ev = M.S.replace(data, cambios)
            end2, ins2, recs2 = M.S.parse(nuevo_ev)
            assert nuevo_ev[32:end] == data[32:end] and ins2 == ins and len(recs2) == len(recs)
            for j, (a, b) in enumerate(zip(recs, recs2)):
                assert (a.instruction, a.argument) == (b.instruction, b.argument)
                assert b.raw == a.raw if j not in cambios else b.body == cambios[j]
            # eventos con furigana o de depuración: no pueden crecer (regla de la v17)
            if (re.search(rb'%\d+F', data) or eid >= 90000000) and len(nuevo_ev) > len(data):
                inf['eventos_revertidos'].append(dict(paquete=pk, evento=eid,
                                                      bytes=[len(data), len(nuevo_ev)]))
                tot['eventos_revertidos'] += 1
                continue
            (SALIDA[pk] / f'{eid}.ssd').write_bytes(nuevo_ev)
            tot[f'{pk}:eventos_cambiados'] += 1
    inf['total'] = dict(tot)
    inf['eventos'] = {pk: {p.stem: sha(p.read_bytes()) for p in sorted(d.glob('*.ssd'))}
                      for pk, d in SALIDA.items()}
    (HERE / 'informe.json').write_text(json.dumps(inf, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(dict(total=dict(tot), no_rehechos=len(inf['no_rehechos']),
                          mayores_247=len(inf['mayores_247']), sin_resolver=len(inf['sin_resolver']),
                          revertidos=len(inf['eventos_revertidos'])), ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
