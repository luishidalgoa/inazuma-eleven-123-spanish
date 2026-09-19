"""IE2 v22 · validación offline de menus_objetivos (issue #77). No construye ni instala.

Comprueba, contra la candidata probe_ie2_v21:
1. ina_main2.cro: solo cambian los bloques declarados y la copia de guardar; parches de ancho v15 intactos;
   cada lista se lee con strlen+1 con el número de entradas del japonés; nada del hueco usado (salvo el inicio)
   es destino de ADR/LDR/relocalización; copia de 0xbd35c == entrada de guardar; «？？？？» de 0xbd364 intacto.
2. Fuentes: sha del registro; solo cambian los glifos (mapa y métricas) de los códigos nuevos.
3. Casillas de los menús medidas en la fuente de salida: primera tinta en la columna 0-1, ningún hueco de 0 px
   (FONT12 con cualquier tinta, FONT8 con el núcleo) y todas las letras del texto.
4. Eventos: cada .ssd se analiza, solo cambian registros de objetivo (0x2017/18/1c/23 arg 3), cada uno <= 40 B
   y se decodifica con el registro al texto del informe; el resto del evento es idéntico.
5. Ningún objetivo del juego (con los eventos de salida) pasa de 40 B.
Salida: validacion.json. Uso: python -X utf8 work/ie2/shared/capas/rotulos_objetivos/menus_objetivos/validate.py
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import apply as P  # noqa: E402

C, K, A88, A89, MI = P.C, P.K, P.A88, P.A89, P.MI


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    fallos, notas = [], {}

    def ok(cond, msg):
        if not cond:
            fallos.append(msg)

    inf = json.loads((HERE / 'informe.json').read_text(encoding='utf-8'))
    reg_doc = json.loads((HERE / 'registro.json').read_text(encoding='utf-8'))
    reg = reg_doc['bigramas']
    por_sjis = {e['sjis']: e for e in reg}

    # ---- 1. CRO ----------------------------------------------------------------------------------------------
    v21 = P.CRO_BASE.read_bytes()
    jp = P.CRO_JP.read_bytes()
    out = (HERE / 'romfs/cro/ina_main2.cro').read_bytes()
    ok(len(out) == len(v21), 'CRO de otro tamaño')
    X = P.Cro(jp)
    permitidos = set(range(P.ESPEJO, P.ESPEJO_FIN + 1))
    for ini, fin, *_ in P.BLOQUES.values():
        permitidos |= set(range(ini, fin + 1))
    otros = [hex(i) for i in range(len(out)) if out[i] != v21[i] and i not in permitidos]
    ok(not otros, f'bytes cambiados fuera de los bloques: {otros[:10]}')
    for a, w in P.ANCHO.items():
        ok(int.from_bytes(out[a:a + 4], 'little') == w, f'parche de ancho {hex(a)} alterado')
    entradas = {}
    for nombre, (ini, fin, max_e, f, lista) in P.BLOQUES.items():
        occ = X.ocupados(ini, fin)
        ok(set(occ) == {ini}, f'{nombre}: destinos dentro del bloque {occ}')
        o, vals = ini, []
        for _ in lista:
            e = out.index(b'\0', o)
            vals.append(out[o:e])
            o = e + 1
        ok(o - 1 <= fin, f'{nombre}: la última entrada acaba en {hex(o - 1)} > {hex(fin)}')
        ok(set(out[o:fin + 1]) <= {0}, f'{nombre}: basura tras la lista')
        for (jpn, _), v in zip(lista, vals):
            ok(0 < len(v) <= max_e, f'{nombre} {jpn}: {len(v)} B')
        entradas[nombre] = vals
    guardar = entradas['menu_campo'][5]
    ok(out[P.ESPEJO:P.ESPEJO + len(guardar) + 1] == guardar + b'\0', 'copia de guardar distinta de la entrada')
    ok(len(guardar) + 1 <= P.ESPEJO_FIN - P.ESPEJO + 1, 'la copia de guardar invade 0xbd364')
    ok(out[P.ESPEJO_FIN + 1:P.ESPEJO_FIN + 10] == '？？？？'.encode('cp932') + b'\0', '«？？？？» alterado')

    # ---- 2. fuentes -----------------------------------------------------------------------------------------
    get = K.comun88.abrir(P.ARCHIVE)
    reg20 = json.loads(P.REGISTRO.read_text(encoding='utf-8'))
    F0, _, tmp = P.cargar_fuentes(get, reg20)
    F1 = {}
    for f in K.FUENTES:
        p = HERE / 'extra' / f
        d = p.read_bytes() if p.exists() else get(f)
        ok(hashlib.sha256(d).hexdigest() == reg_doc['fuentes_dibujadas'][f], f'{f}: sha distinto del registro')
        (tmp / ('v22_' + Path(f).name)).write_bytes(d)
        F1[f] = A88.cargar(tmp / ('v22_' + Path(f).name))
    nuevos = {}
    for e in inf['casillas_nuevas']:
        for f in e['fuentes']:
            nuevos.setdefault(f, set()).add(F1[f].gi(ord(bytes.fromhex(e['sjis']).decode('cp932'))))
    for f in K.FUENTES:
        dif = [gi for gi in set(F0[f].cmap.values())
               if F0[f].metrics.get(gi) != F1[f].metrics.get(gi) or F0[f].bitmap(gi) != F1[f].bitmap(gi)]
        ok(set(dif) <= nuevos.get(f, set()), f'{f}: glifos cambiados que no son códigos nuevos: {sorted(set(dif) - nuevos.get(f, set()))[:10]}')
        notas[f'glifos_cambiados_{Path(f).stem}'] = len(dif)

    # ---- 3. casillas de los menús ----------------------------------------------------------------------------
    Mo = P.modelos(F1)
    medidas = {}
    for nombre, (ini, fin, max_e, f, lista) in P.BLOQUES.items():
        M = Mo[f]
        for (jpn, alts), body, e in zip(lista, entradas[nombre], inf['bloques'][nombre]['entradas']):
            toks, i = [], 0
            while i < len(body):
                if 0x81 <= body[i] <= 0x9F or 0xE0 <= body[i] <= 0xFC:
                    toks.append(body[i:i + 2])
                    i += 2
                else:
                    toks.append(body[i:i + 1])
                    i += 1
            prev, huecos, primera = None, [], None
            for k, t in enumerate(toks):
                gi = F1[f].gi(ord(t.decode('cp932')))
                p = M.perfil(M.columnas(gi))
                if prev is not None:
                    huecos.append(M.paso + p[0] - prev - 1)
                else:
                    primera = p[0]
                huecos += p[2]
                prev = p[1]
            plano = A89.Codec(reg).texto(body)
            ok(plano == e['texto'], f'{nombre}: {plano!r} != {e["texto"]!r}')
            ok(primera in (0, 1), f'{nombre} {e["texto"]}: primera columna {primera}')
            ok(min(huecos) >= 1, f'{nombre} {e["texto"]}: letras que se tocan {huecos}')
            ok(e['texto'] in alts, f'{nombre}: texto fuera de las alternativas')
            medidas[e['texto']] = dict(huecos=huecos, primera_columna=primera, bytes=len(body))

    # ---- 4/5. eventos ------------------------------------------------------------------------------------------
    A = MI.Archivo(P.ARCHIVE)
    codec = A89.Codec(reg)
    por_ev = {(r['paquete'], r['evento'], r['indice']): r for r in inf['objetivos']['detalle']}
    textos = {}
    for d in inf['objetivos']['detalle']:
        textos[d['antes']] = d['texto']
    n_ev = n_reg = 0
    salida = {}
    for pk in ('eve', 'mch'):
        for p in sorted((HERE / 'ie2' / pk).glob('*.ssd')):
            eid = int(p.stem)
            salida[(pk, eid)] = p.read_bytes()
    for (pk, eid), nuevo in salida.items():
        n_ev += 1
        ok(eid not in MI.PROTEGIDOS, f'evento protegido {eid}')
        viejo = A.evento(pk, eid)
        _, ins, recs = MI.S.parse(viejo)
        _, ins2, recs2 = MI.S.parse(nuevo)
        ok(ins == ins2 and len(recs) == len(recs2), f'{pk} {eid}: estructura distinta')
        for i, (a, b) in enumerate(zip(recs, recs2)):
            if a.raw == b.raw:
                continue
            n_reg += 1
            op = ins.get(a.instruction)
            ok(op in P.OPS_OBJ and a.argument == 3 and (a.instruction, a.argument) == (b.instruction, b.argument),
               f'{pk} {eid} #{i}: cambia un registro que no es objetivo')
            ok(len(b.body) <= P.LIMITE_OBJ, f'{pk} {eid} #{i}: {len(b.body)} B')
            antes = codec.texto(a.body)
            ok(codec.texto(b.body) == textos.get(antes), f'{pk} {eid} #{i}: texto inesperado')
    ok(n_reg == inf['objetivos']['cambiados'], f'registros cambiados {n_reg} != informe {inf["objetivos"]["cambiados"]}')
    largos = []
    for pk in ('eve', 'mch'):
        for eid in A.ids(pk):
            data = salida.get((pk, eid)) or A.evento(pk, eid)
            try:
                _, ins, recs = MI.S.parse(data)
            except ValueError:
                continue
            for i, r in enumerate(recs):
                if ins.get(r.instruction) in P.OPS_OBJ and r.argument == 3 and len(r.body) > P.LIMITE_OBJ:
                    largos.append((pk, eid, i, len(r.body)))
    ok(not largos, f'objetivos de más de 40 B: {largos[:10]}')

    res = dict(ok=not fallos, fallos=fallos, eventos=n_ev, registros_objetivo_cambiados=n_reg,
               objetivos_mas_de_40B=len(largos), menus=medidas, **notas,
               runtime_verified=False)
    (HERE / 'validacion.json').write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(res, ensure_ascii=False, indent=1)[:3000])
    sys.exit(0 if not fallos else 1)


if __name__ == '__main__':
    main()
