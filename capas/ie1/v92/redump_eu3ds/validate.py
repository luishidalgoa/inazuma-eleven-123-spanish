"""v92 · validación offline de events/ y events_mch/ frente a la base (o al evento de v91 si existe).

1. Eventos: ninguno protegido; mismo bytecode, instrucciones y nº de registros; solo cambian registros de
   diálogo (0x301d arg 1) u objetivo (0x402f arg 3); registros <= 247 B; eventos «fijos» sin crecer.
2. Diálogo: el texto es el oficial (EU 3DS o NDS) con las sustituciones de glifo, mismas palabras;
   el motor (comun82) no inserta saltos si no hay `%`; <= 22 caracteres por línea (con la reserva de `%s`),
   1-3 líneas por página, sin líneas vacías; `%s`/`%d` iguales que el japonés; todos los glifos en FONT12.
3. Objetivos: decodifican (registro v89) al oficial; sin códigos fuera del registro; hueco sólido >= 1 px
   (>= 4 entre palabras) y sin tinta débil solapada; <= 128 casillas.
Salida: validacion.json.  Uso: python -X utf8 work/ie1/capas/v92/redump_eu3ds/validate.py
"""
from __future__ import annotations

import collections
import json
import pickle
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import comun92 as C  # noqa: E402
import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location('apply_v92', HERE / 'apply.py')
A = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(A)
sys.path.insert(0, str(HERE))
import objetivos as O  # noqa: E402

K, M = C.K, C.M
errores = []


def err(m):
    errores.append(m)
    if len(errores) < 40:
        print('ERROR', m)


def palabras(t):
    return t.replace('\\n', ' ').replace('\\f', ' ').split()


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    filas = pickle.loads((HERE / 'clasificacion.pkl').read_bytes())
    oficial = {(x['tipo'], x['evento'], x['indice']): x for x in filas}
    inf = json.loads((HERE / 'informe.json').read_text(encoding='utf-8'))
    obj_decl = {(c['evento'], c['indice']): c for c in inf['objetivos']['cambios']}
    base = {t: C.Guion(C.BASE, t) for t in A.CARPETA}
    orig = {t: C.Guion(C.ORIGINAL, t) for t in A.CARPETA}
    med = K.Medidor(C.fuente12())
    ob = O.Objetivos()
    st = collections.Counter()
    for tipo, carpeta in A.CARPETA.items():
        for f in sorted((HERE / carpeta).glob('*.ssd')):
            eid = int(f.stem)
            st[f'eventos_{tipo}'] += 1
            if eid in C.PROTEGIDOS or eid in C.DONT_TOUCH:
                err(f'{eid} protegido')
            data = base[tipo].evento(eid)
            v91 = A.V91 / carpeta / f.name
            antes = v91.read_bytes() if v91.exists() else data
            nuevo = f.read_bytes()
            ea, oa, ra = K.S.parse(antes)
            eb, ob_, rb = K.S.parse(nuevo)
            if antes[32:ea] != nuevo[32:eb] or oa != ob_ or len(ra) != len(rb):
                err(f'{eid} bytecode/registros')
                continue
            _, _, rbase = K.S.parse(data)
            fija = (any(re.search(rb'%\d+F', r.body) for r in ra)
                    or (eid >= 90000000 and len(data) == len(orig[tipo].evento(eid))))
            if fija and len(nuevo) > len(antes):
                err(f'{eid} fijo y crece')
            st['bytes_crecidos'] += len(nuevo) - len(antes)
            for i, (x, y) in enumerate(zip(ra, rb)):
                if (x.instruction, x.argument) != (y.instruction, y.argument):
                    err(f'{eid}#{i} cabecera')
                if x.raw == y.raw:
                    continue
                if len(y.raw) > 252:
                    err(f'{eid}#{i} > 247 B')
                par = (oa[x.instruction], x.argument)
                if par == (0x402F, 3) and tipo == 'eve':
                    st['objetivos'] += 1
                    c = obj_decl.get((eid, i))
                    if c is None:
                        err(f'{eid}#{i} objetivo no declarado')
                        continue
                    if ob.codec.texto(y.body) != c['despues'] or '¤' in ob.codec.texto(y.body):
                        err(f'{eid}#{i} objetivo no decodifica')
                    cel = ob.codec.claves(y.body)
                    if None in cel or len(cel) > O.CASILLAS:
                        err(f'{eid}#{i} casillas')
                        continue
                    if any(g < (O.R.PAL_MIN if pal else 1) for g, pal in O.R.huecos(cel, ob.mq)):
                        err(f'{eid}#{i} solape (hueco sólido)')
                    d = ob.contacto_debil(cel)
                    if d is not None and d < 0:
                        err(f'{eid}#{i} tinta débil solapada')
                    continue
                if par != (C.OP_DIALOGO, 1):
                    err(f'{eid}#{i} registro no permitido {par}')
                    continue
                st[f'dialogo_{tipo}'] += 1
                if rbase[i].raw != x.raw:
                    st['solape_v91'] += 1
                o = oficial.get((tipo, eid, i))
                if o is None or o['clase'] != 'b':
                    err(f'{eid}#{i} sin clase b')
                    continue
                es = K.a_espanol(y.body)
                fuentes = [v for v in (o['oficial_eu3ds'], o['oficial_nds']) if v]
                ok = [v for v in fuentes if palabras(K.a_espanol(A.encode_fullwidth(A.limpiar(v)))) == palabras(es)]
                if not ok:
                    err(f'{eid}#{i} no es el texto oficial: {es!r}')
                    continue
                st['fuente_eu3ds' if ok[0] == o['oficial_eu3ds'] else 'fuente_nds'] += 1
                if sorted(A.PCT.findall(es)) != sorted(A.PCT.findall(K.sin_marcas(o['japones']))):
                    err(f'{eid}#{i} %')
                if '%' not in es and not M.respeta_motor(y.body):
                    err(f'{eid}#{i} el motor reajusta')
                for pg in es.split(A.PAGINA):
                    lineas = pg.split(A.SALTO)
                    if not 1 <= len(lineas) <= A.LINEAS:
                        err(f'{eid}#{i} líneas por página')
                    for ln in lineas:
                        if not ln.strip() or A.coste(ln) > M.MAX_CAR:
                            err(f'{eid}#{i} línea {ln!r}')
                    if med.sin_glifo(M.transportar(pg).replace('\\', '')):
                        err(f'{eid}#{i} sin glifo')
                if '%' not in es:
                    for pg in M.paginas_motor(y.body):
                        if len(pg) > 3 or any(len(ln) > M.MAX_CAR for ln in pg):
                            err(f'{eid}#{i} motor')
    res = dict(total=dict(st), errores=len(errores), ejemplos=errores[:40], ok=not errores,
               informe_total=inf['total'])
    (HERE / 'validacion.json').write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
