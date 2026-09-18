"""v84 · (copia de v82 extendida a TODO IE1 con --todos) saltos de diálogo: piloto CORREGIDO con el límite real del motor (22 caracteres, 3 líneas).

El piloto v77 (tinta <= 290 px) daba líneas de hasta 37 caracteres, y el motor (ina_main1.cro
0x424f4, ver comun82.py) las vuelve a partir por carácter a los 22 y corta la página a mitad de
palabra (81000090 #406 en Azahar). Esta capa reescribe SOLO los registros de diálogo (0x301d arg 1)
de los eventos indicados, sobre la base dada (por defecto v81, que ya lleva el piloto v77):

- modo por defecto: `comun82.ajustar` (voraz por palabras, <= 22 caracteres transportados y <= 290 px de
  tinta, 3 líneas por página, conserva los `\\f` del fuente);
- registros con `%` (p. ej. `%s`, que el motor expande antes de ajustar con una variable de longitud
  desconocida): se devuelven al ajuste v20;
- `--revertir`: todos los registros al ajuste v20 (texto de antes del piloto).

Texto fuente de cada registro (hace falta para saber qué `\\f` son del fuente):
  1) CSV del mismo evento cuyo ajuste v20 o v77 reproduce los bytes actuales;
  2) `inferir_fuente` (v77) sobre los bytes actuales si están con ajuste v20;
  3) en los eventos del piloto v77: el texto `antes` de v77/aplicado.json (v76, ajuste v20), con
     CSV o inferencia, exigiendo que el ajuste v77 del fuente reproduzca los bytes actuales.
Si nada lo identifica, el registro no se toca.

Invariantes: mismas palabras, misma longitud de registro, bytecode idéntico, páginas de 1 a 3 líneas,
y el modelo del motor no inserta ni convierte ningún salto (`comun82.respeta_motor`).

Uso: python apply.py [--base archive.fa] [--eventos ...] [--revertir] [--analizar [--todos]]
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections import Counter
from pathlib import Path

import comun82 as M

K = M.K
HERE = Path(__file__).resolve().parent
ROOT = K.ROOT
V77 = M.V77
sys.path.insert(0, str(ROOT / 'tools'))
import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location('apply_v77', V77 / 'apply.py')
A77 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(A77)
from build_ie1_probe import layout as layout_v20  # noqa: E402  (solo lectura)
from dialogue_lock import approved_layout  # noqa: E402
from dialogue_typography import encode_fullwidth  # noqa: E402

BASE_V81 = ROOT / 'work/shared/candidatas/probe_ie1_v81/archive.fa'
PILOTO = A77.PILOTO
SALTO, PAGINA, LINEAS = M.SALTO, M.PAGINA, M.LINEAS


def v20(t):
    return encode_fullwidth(approved_layout(t, layout_v20))


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', type=Path, default=BASE_V81)
    ap.add_argument('--eventos', type=int, nargs='+', default=PILOTO)
    ap.add_argument('--revertir', action='store_true', help='todo al ajuste v20')
    ap.add_argument('--analizar', action='store_true', help='no escribe events/')
    ap.add_argument('--todos', action='store_true', help='con --analizar: todos los eventos no protegidos')
    args = ap.parse_args()
    base = K.Archivo(args.base.resolve())
    med = K.Medidor(base.fuente())
    if args.todos:
        args.eventos = [e for e in sorted(base.indice) if e not in K.PROTEGIDOS and e not in K.DONT_TOUCH]
    malos = [e for e in args.eventos if e in K.PROTEGIDOS or e in K.DONT_TOUCH]
    if malos:
        ap.error(f'eventos protegidos: {malos}')
    fuentes = A77.fuentes_csv()
    antes_v77 = {}
    ap77 = V77 / 'aplicado.json'
    for e in json.loads(ap77.read_text(encoding='utf-8'))['eventos']:
        for r in e['registros']:
            antes_v77[(e['evento'], r['indice'])] = r['antes']

    def ajuste_v77(t):
        return encode_fullwidth(K.ajustar(t, med.ancho_es))

    def fuente_de(eid, i, cuerpo):
        """(fuente, método, disposición actual) o None."""
        for cand in sorted(fuentes.get(eid, ())):
            try:
                if v20(cand) == cuerpo:
                    return cand, 'csv', 'v20'
                if eid in PILOTO and ajuste_v77(cand) == cuerpo:
                    return cand, 'csv', 'v77'
            except ValueError:
                continue
        inf = A77.inferir_fuente(K.a_espanol(cuerpo), cuerpo)
        if inf:
            return inf[0], 'inferido', 'v20'
        if (eid, i) in antes_v77:
            cuerpo76 = encode_fullwidth(antes_v77[(eid, i)])
            cands = [c for c in sorted(fuentes.get(eid, ())) if _ok(lambda: v20(c) == cuerpo76)]
            inf = A77.inferir_fuente(antes_v77[(eid, i)], cuerpo76)
            for f, met in [(c, 'csv(v76)') for c in cands] + ([(inf[0], 'inferido(v76)')] if inf else []):
                if _ok(lambda: ajuste_v77(f) == cuerpo):
                    return f, met, 'v77'
        return None

    out = HERE / 'events'
    if not args.analizar:
        if out.exists():
            shutil.rmtree(out)
        out.mkdir()
    informe = dict(base=str(args.base), modo='revertir' if args.revertir else f'{M.MAX_CAR} caracteres',
                   max_caracteres=M.MAX_CAR, lineas_por_pagina=LINEAS, eventos=[])
    total = Counter()
    for eid in args.eventos:
        data = base.evento(eid)
        try:
            end, ops, recs = K.S.parse(data)
        except ValueError as exc:
            informe['eventos'].append(dict(evento=eid, error=str(exc)))
            continue
        cambios, filas, sin_fuente = {}, [], []
        cnt = Counter()
        for i, r in enumerate(recs):
            if ops.get(r.instruction) != K.OP_DIALOGO or r.argument != 1:
                continue
            actual = r.body.decode('cp932')
            if not any('Ａ' <= c <= 'ｚ' for c in actual):
                continue
            es_actual = K.a_espanol(r.body)
            fr = fuente_de(eid, i, r.body)
            if fr is None:
                sin_fuente.append(dict(indice=i, texto=es_actual))
                cnt['sin_fuente'] += 1
                continue
            fuente, metodo, disp = fr
            v20_es = approved_layout(fuente, layout_v20)
            pag_v20 = len(v20_es.split(PAGINA))
            con_pct = '%' in K.sin_marcas(fuente)
            if args.revertir or con_pct:
                nuevo_es, regla = v20_es, 'v20'
            else:
                nuevo_es, regla = M.ajustar(fuente, med.ancho_es), f'{M.MAX_CAR} car'
            nuevo = encode_fullwidth(nuevo_es)
            pag_nuevo = len(nuevo_es.split(PAGINA))
            cnt['identificados'] += 1
            cnt['paginas_v20'] += pag_v20
            cnt['paginas_nuevo'] += pag_nuevo
            cnt['con_pct'] += con_pct
            if not con_pct:
                cnt['paginas_v77'] += len(K.ajustar(fuente, med.ancho_es).split(PAGINA))
            if not con_pct and not M.respeta_motor(nuevo):
                raise AssertionError((eid, i, nuevo_es))
            if nuevo == r.body:
                cnt['sin_cambio'] += 1
                continue
            assert A77.palabras(nuevo.decode('cp932')) == A77.palabras(actual), (eid, i)
            assert len(nuevo) == len(r.body), (eid, i)
            assert nuevo.count(b'%') == r.body.count(b'%'), (eid, i)
            pags = nuevo_es.split(PAGINA)
            assert all(0 < len(pg.split(SALTO)) <= LINEAS for pg in pags), (eid, i)
            assert pag_nuevo <= pag_v20, (eid, i)
            anchos = [[med.ancho_es(x) for x in pg.split(SALTO)] for pg in pags]
            assert all(0 < w <= M.ANCHO_TINTA for fila in anchos for w in fila), (eid, i, anchos)
            assert all(len(M.transportar(x)) <= M.MAX_CAR for pg in pags for x in pg.split(SALTO)), (eid, i)
            assert not any(med.sin_glifo(M.transportar(pg)) for pg in pags), (eid, i)
            cambios[i] = nuevo
            cnt['cambiados'] += 1
            filas.append(dict(indice=i, fuente=metodo, disposicion_base=disp, regla=regla, antes=es_actual,
                              v20=v20_es, despues=nuevo_es, paginas_v20=pag_v20, paginas_antes=len(es_actual.split(PAGINA)),
                              paginas_despues=pag_nuevo, anchos_despues=anchos, bytes=len(nuevo)))
        total.update(cnt)
        ev = dict(evento=eid, **cnt, registros=filas, no_identificados=sin_fuente)
        if cambios:
            nuevo_evento = K.S.replace(data, cambios)
            end2, ops2, recs2 = K.S.parse(nuevo_evento)
            assert nuevo_evento[32:end] == data[32:end] and ops2 == ops and len(recs2) == len(recs)
            assert len(nuevo_evento) == len(data)
            for j, (a, b) in enumerate(zip(recs, recs2)):
                assert (a.instruction, a.argument) == (b.instruction, b.argument)
                if j not in cambios:
                    assert a.raw == b.raw
            ev['bytes_distintos'] = sum(1 for a, b in zip(data, nuevo_evento) if a != b)
            if not args.analizar:
                (out / f'{eid}.ssd').write_bytes(nuevo_evento)
        if args.todos and args.analizar:
            ev.pop('registros')
            ev['no_identificados'] = len(sin_fuente)
        else:
            print(eid, dict(cnt))
        informe['eventos'].append(ev)
    informe['total'] = dict(total)
    print('TOTAL', dict(total))
    if args.todos and args.analizar:
        (HERE / 'analisis_juego.json').write_text(json.dumps(informe, ensure_ascii=False, indent=1), encoding='utf-8')
    elif not args.analizar:
        (HERE / 'aplicado.json').write_text(json.dumps(informe, ensure_ascii=False, indent=1), encoding='utf-8')


def _ok(f):
    try:
        return f()
    except ValueError:
        return False


if __name__ == '__main__':
    main()
