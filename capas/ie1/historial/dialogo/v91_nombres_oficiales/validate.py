"""v91 · validación de la capa nombres_oficiales (sin construir candidata).

Comprueba, contra la base (probe_ie2_v05, eve.pkb de inazuma1):
  1. events/ = eventos de informe.json; todos del índice IE1; ninguno protegido.
  2. Misma tabla de instrucciones, mismos registros e identidades; solo cambian los registros declarados,
     todos de diálogo (0x301d); los de objetivos/rótulos (bigramas) quedan byte a byte iguales.
  3. Cada registro cambiado: <= 247 B, mismos códigos %, texto = informe «despues», glifos presentes,
     sin nombres no oficiales; con ajuste de diálogo: <= 22 caracteres por línea, <= 3 líneas por página y
     el motor no inserta saltos (comun82.respeta_motor); con maquetado propio (menú de depuración): mismos
     saltos que antes.
  4. Tras la capa, en todo el diálogo IE1 solo quedan los nombres listados en informe «sin_cambio» y las
     palabras de «no_nombres».
  5. translation/ie1/dialogo.csv: las filas oficial/glosario de esta capa llevan el texto del informe.
Salida: validacion.json. Código de salida 1 si hay errores.
"""
from __future__ import annotations

import csv
import json
import re
import sys

import importlib.util

import comun91 as C
import nombres as N

M, K, HERE, ROOT = C.M, C.K, C.HERE, C.ROOT
_spec = importlib.util.spec_from_file_location('apply_v91', HERE / 'apply.py')   # hay otros apply.py en sys.path
A = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(A)
OPS_BIGRAMAS, PAGINA, SALTO, plano, encode_fullwidth = A.OPS_BIGRAMAS, A.PAGINA, A.SALTO, A.plano, A.encode_fullwidth


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    errores = []

    def err(m):
        errores.append(m)
        print('ERROR', m)

    inf = json.loads((HERE / 'informe.json').read_text(encoding='utf-8'))
    base = K.Archivo(C.BASE)
    med = K.Medidor(base.fuente())
    ev_dir = HERE / 'events'
    ficheros = {int(p.stem): p for p in ev_dir.glob('*.ssd')}
    declarados = {e['evento']: set(e['registros']) for e in inf['eventos']}
    if set(ficheros) != set(declarados):
        err(f'events/ != informe: {sorted(set(ficheros) ^ set(declarados))}')
    cambios = {(c['evento'], c['indice']): c for c in inf['cambios']}
    nuevos = {}
    for eid, p in sorted(ficheros.items()):
        if eid not in base.indice:
            err(f'{eid}: no es un evento de inazuma1/eve.pkb')
            continue
        if eid in K.PROTEGIDOS or eid in K.DONT_TOUCH:
            err(f'{eid}: evento protegido')
        a, b = base.evento(eid), p.read_bytes()
        nuevos[eid] = b
        _, op1, r1 = K.S.parse(a)
        _, op2, r2 = K.S.parse(b)
        if op1 != op2 or len(r1) != len(r2) or b[:32 + (len(a) - 32 - sum(len(r.raw) for r in r1))] is None:
            err(f'{eid}: estructura')
            continue
        fin = len(a) - sum(len(r.raw) for r in r1)
        if a[4:8] != b[4:8] or a[32:fin] != b[32:len(b) - sum(len(r.raw) for r in r2)]:
            err(f'{eid}: bytecode distinto')
        for i, (x, y) in enumerate(zip(r1, r2)):
            if (x.instruction, x.argument) != (y.instruction, y.argument):
                err(f'{eid}#{i}: identidad')
            if x.raw == y.raw:
                continue
            if i not in declarados.get(eid, ()):
                err(f'{eid}#{i}: cambio sin declarar')
            if (op1.get(x.instruction), x.argument) in OPS_BIGRAMAS:
                err(f'{eid}#{i}: registro de bigramas modificado')
            if op1.get(x.instruction) != K.OP_DIALOGO:
                err(f'{eid}#{i}: no es diálogo')
            c = cambios.get((eid, i))
            if c is None:
                err(f'{eid}#{i}: sin entrada en informe')
                continue
            body = y.body
            es = K.a_espanol(body)
            if len(body) > 247:
                err(f'{eid}#{i}: {len(body)} B')
            if body.count(b'%') != x.body.count(b'%'):
                err(f'{eid}#{i}: códigos %')
            if es != c['despues'] or encode_fullwidth(c['despues']) != body:
                err(f'{eid}#{i}: texto distinto del informe')
            if N.detectar(plano(es)):
                err(f'{eid}#{i}: quedan nombres {N.detectar(plano(es))}')
            filas = [f for pg in es.split(PAGINA) for f in pg.split(SALTO)]
            if any(med.sin_glifo(M.transportar(f)) for f in filas):
                err(f'{eid}#{i}: sin glifo')
            if c.get('in_situ'):
                antes = K.a_espanol(x.body)
                if [len(pg.split(SALTO)) for pg in antes.split(PAGINA)] != [len(pg.split(SALTO)) for pg in es.split(PAGINA)]:
                    err(f'{eid}#{i}: saltos del menú cambiados')
            else:
                if any(len(M.transportar(f)) > M.MAX_CAR for f in filas):
                    err(f'{eid}#{i}: línea de más de {M.MAX_CAR}')
                if any(len(pg.split(SALTO)) > M.LINEAS for pg in es.split(PAGINA)):
                    err(f'{eid}#{i}: página de más de {M.LINEAS} líneas')
                if b'%' not in body and not M.respeta_motor(body):
                    err(f'{eid}#{i}: el motor insertaría saltos')
    for (eid, i) in cambios:
        if i not in declarados.get(eid, ()):
            err(f'{eid}#{i}: en cambios pero no en eventos')

    # 4. barrido completo tras la capa
    permitidos = {(s['evento'], s['indice']) for s in inf['sin_cambio']}
    permitidos |= {(s['evento'], s['indice']) for s in inf['no_nombres']}
    restantes = []
    for eid in sorted(base.indice):
        data = nuevos.get(eid) or base.evento(eid)
        try:
            _, ops, recs = K.S.parse(data)
        except ValueError:
            continue
        for i, r in enumerate(recs):
            if ops.get(r.instruction) != K.OP_DIALOGO:
                continue
            try:
                t = K.a_espanol(r.body)
            except UnicodeDecodeError:
                continue
            h = N.detectar(plano(t))
            if not h:
                continue
            restantes.append(dict(evento=eid, indice=i, nombres=h))
            solo_no_nombres = all(x in N.NO_NOMBRES for x in h)
            if (eid, i) not in permitidos and not solo_no_nombres:
                err(f'{eid}#{i}: nombres sin tratar {h}')

    # 5. CSV
    csv_ok = 0
    filas = list(csv.DictReader(open(ROOT / 'translation/ie1/dialogo.csv', encoding='utf-8', newline='')))
    por = {}
    for r in filas:
        por.setdefault(r['event_id'], []).append(r)
    for c in inf['cambios']:
        esperado = c['csv_texto'] if c['fuente'] == 'oficial' else c['despues']
        cand = [r for r in por.get(str(c['evento']), []) if r['japones'].endswith(c['japones'])]
        if not cand:
            continue
        if not any(r['es_final'].endswith(esperado) and r['estado'] == c['fuente'] for r in cand):
            err(f"CSV {c['evento']}#{c['indice']}: fila no actualizada")
        else:
            csv_ok += 1
    for r in filas:
        if N.detectar(plano(r['es_final'])) and r['estado'] not in ('revisar', 'auto-dup', 'oficial', 'pendiente'):
            if not all(x in N.NO_NOMBRES or x in N.SIN_OFICIAL for x in N.detectar(plano(r['es_final']))):
                err(f"CSV {r['event_id']}: {r['estado']} con nombres {N.detectar(plano(r['es_final']))}")

    res = dict(errores=errores, eventos=len(ficheros), registros=len(cambios), csv_filas_comprobadas=csv_ok,
               nombres_restantes=restantes)
    (HERE / 'validacion.json').write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding='utf-8')
    print('OK' if not errores else f'{len(errores)} errores', '· eventos', len(ficheros), '· registros',
          len(cambios), '· filas CSV', csv_ok, '· restantes', len(restantes))
    sys.exit(1 if errores else 0)


if __name__ == '__main__':
    main()
