"""IE2 v17 · páginas de diálogo de <= 131 B (búfer de pila de 0x4d638) sobre probe_ie2_v16.

1. 22500101 y 22500102 (sonda de ancho): cada registro 0x301d arg 1 en español se reparte de nuevo con
   `comun17.repartir` (texto oficial íntegro de v16, <= 37 caracteres por línea, <= 3 líneas y
   <= 131 B por página, cortes de página preferentemente al final de frase, sin cortar palabras).
2. Todos los demás registros de diálogo de IE2 (eve y mch, incluidos los de inicio de v16): se
   conserva la disposición actual y solo se cambia un `\\n` por `\\f` donde una página del motor
   pasaría de 131 B (`comun17.partir_paginas`; mismo tamaño).
Nada se acorta: las palabras de cada registro se comprueban iguales antes y después.
Salida: ie2/eve/*.ssd, ie2/mch/*.ssd, informe.json.
Uso: python -X utf8 work/ie2/shared/capas/v17/paginas/apply.py
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
import comun17 as C  # noqa: E402

M = C.M
W = C.ROOT / 'work'
BASE = W / 'shared/candidatas/probe_ie2_v16/archive.fa'
SONDA = {22500101, 22500102}
SALIDA = {'eve': HERE / 'ie2/eve', 'mch': HERE / 'ie2/mch'}
JAPONES = re.compile(r'[぀-ヿ一-鿿]')


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def espanol(b: bytes) -> str:
    return M.normalizar(M.K.a_espanol(b).replace('－', '−').replace('～', '〜'))


def es_espanol(b: bytes) -> bool:
    t = espanol(b)
    return bool(re.search(r'[A-Za-zÁÉÍÓÚáéíóúñÑ]', t)) and not JAPONES.search(t)


def palabras(t: str):
    return t.replace(C.SALTO, ' ').replace(C.PAGINA, ' ').split()


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    arc = M.Archivo(BASE)
    for d in SALIDA.values():
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)
    tot = Counter()
    inf = dict(base=str(BASE), sonda={}, cortes=[], no_resueltos=[], mayores_247=[], sin_decodificar=[])
    for pk in ('eve', 'mch'):
        for eid in arc.ids(pk):
            data = arc.evento(pk, eid)
            end, ins, recs, dl = M.dialogos(data)
            cambios = {}
            for i in dl:
                body = recs[i].body
                tot[f'{pk}:registros'] += 1
                if len(body) > M.MAX_BYTES:
                    inf['mayores_247'].append(dict(paquete=pk, evento=eid, indice=i, bytes=len(body), cuando='v16'))
                if pk == 'eve' and eid in SONDA and es_espanol(body):
                    antes = espanol(body)
                    texto = C.repartir(antes)
                    nuevo = M.transportar(texto)
                    assert palabras(espanol(nuevo)) == palabras(antes), (eid, i)
                    assert M.pct(nuevo.decode('cp932')) == M.pct(body.decode('cp932')), (eid, i)
                    assert not M.sin_glifo(nuevo), (eid, i)
                    assert not C.reajusta(nuevo), (eid, i, texto)
                    inf['sonda'].setdefault(str(eid), []).append(dict(
                        indice=i, antes=antes, despues=texto, bytes=[len(body), len(nuevo)],
                        paginas=[len(p) for p in C.paginas(nuevo)]))
                    if nuevo != body:
                        cambios[i] = nuevo
                        tot['sonda:cambiados'] += 1
                    continue
                if not any(len(p) > C.PAGINA_MAX for p in C.paginas(body)):
                    continue
                try:
                    t = body.decode('cp932')
                except UnicodeDecodeError:
                    inf['sin_decodificar'].append(dict(paquete=pk, evento=eid, indice=i))
                    continue
                t2, n = C.partir_paginas(t)
                nuevo = t2.encode('cp932')
                assert len(nuevo) == len(body) and nuevo.replace(b'\\f', b'\\n') == body.replace(b'\\f', b'\\n')
                tot['paginas_partidas'] += n
                tot['registros_partidos'] += 1 if n else 0
                inf['cortes'].append(dict(paquete=pk, evento=eid, indice=i, cortes=n,
                                          antes=[len(p) for p in C.paginas(body)],
                                          despues=[len(p) for p in C.paginas(nuevo)],
                                          texto=espanol(nuevo) if es_espanol(nuevo) else None))
                if n:
                    cambios[i] = nuevo
            # comprobación del modelo sobre el resultado
            final = {i: cambios.get(i, recs[i].body) for i in dl}
            for i, b in final.items():
                p = C.problemas(b)
                if p:
                    inf['no_resueltos'].append(dict(paquete=pk, evento=eid, indice=i, problemas=p))
                if len(b) > M.MAX_BYTES and i in cambios:
                    inf['mayores_247'].append(dict(paquete=pk, evento=eid, indice=i, bytes=len(b), cuando='v17'))
            if not cambios:
                continue
            nuevo_ev = M.S.replace(data, cambios)
            end2, ins2, recs2 = M.S.parse(nuevo_ev)
            assert nuevo_ev[32:end] == data[32:end] and ins2 == ins and len(recs2) == len(recs)
            for j, (a, b) in enumerate(zip(recs, recs2)):
                assert (a.instruction, a.argument) == (b.instruction, b.argument)
                assert b.raw == a.raw if j not in cambios else b.body == cambios[j]
            if re.search(rb'%\d+F', data) or eid >= 90000000:
                assert len(nuevo_ev) <= len(data), (pk, eid)
            (SALIDA[pk] / f'{eid}.ssd').write_bytes(nuevo_ev)
            tot[f'{pk}:eventos_cambiados'] += 1
    inf['total'] = dict(tot)
    inf['eventos'] = {pk: {p.stem: sha(p.read_bytes()) for p in sorted(d.glob('*.ssd'))} for pk, d in SALIDA.items()}
    (HERE / 'informe.json').write_text(json.dumps(inf, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(dict(total=dict(tot), no_resueltos=len(inf['no_resueltos']),
                          mayores_247=inf['mayores_247'], sin_decodificar=len(inf['sin_decodificar'])),
                     ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
