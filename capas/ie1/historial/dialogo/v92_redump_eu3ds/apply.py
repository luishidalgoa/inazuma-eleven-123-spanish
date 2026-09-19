"""v92 · redump_eu3ds: pone el texto OFICIAL (port europeo de 3DS; NDS si falta) en los registros de
diálogo de clase b (hay oficial y el juego dice otra cosa, normalmente traducción de IA).

Entrada: clasificacion.pkl (clasificar.py) y la base probe_ie2_v05 (eve.pkb y mch.pkb de inazuma1).
Si work/ie1/capas/historial/dialogo/v91_nombres_oficiales/events{,_mch}/<eid>.ssd existe, se parte de ese evento (v91 no
se modifica; esta capa va DESPUÉS de v91 y su evento completo la sustituye, con los cambios de v91
en los demás registros conservados). Los registros que v91 cambió y esta capa reemplaza se anotan
en informe.json («solape_v91»).

Reglas (las mismas que v84 y el bloqueo v20):
- solo 0x301d arg 1; eventos 92010100..92010509 y 81000040 intactos;
- transporte de ancho completo cp932 con portadores de acento (`encode_fullwidth`);
- ajuste de v84: voraz por palabras, <= 22 caracteres por línea y 3 líneas por página, sin cortar
  palabras, conservando los `\\f` del texto oficial y sin tinta de más de 290 px; en líneas con `%s`
  (se expande antes del ajuste del motor) se reserva el ancho de un nombre de 9 caracteres (`%d`, 5);
- registro <= 247 B (lo que no quepa va a no_caben, no se trunca);
- `%s`/`%d` iguales que en el japonés;
- sin glifo: apóstrofo y comillas fuera («O'Reilly» -> «OReilly», como v36), guion -> espacio (como v55),
  «⇒» fuera; cualquier otro carácter sin glifo en FONT12 descarta el registro;
- crecimiento: prohibido en eventos que aún llevan marcas %NF y en eventos de sistema (>= 90000000)
  que la base conserva al tamaño japonés; ahí solo entran los registros que no hacen crecer el evento.

Salida: events/, events_mch/, informe.json, no_caben.json.
Uso: python -X utf8 work/ie1/capas/historial/dialogo/v92_redump_eu3ds/apply.py
"""
from __future__ import annotations

import collections
import json
import pickle
import re
import shutil
import sys

import comun92 as C

K, M = C.K, C.M
HERE = C.HERE
sys.path.insert(0, str(C.ROOT / 'tools'))
from dialogue_typography import encode_fullwidth  # noqa: E402

V91 = C.ROOT / 'work/ie1/capas/historial/dialogo/v91_nombres_oficiales'
CARPETA = {'eve': 'events', 'mch': 'events_mch'}
SALTO, PAGINA, LINEAS = M.SALTO, M.PAGINA, M.LINEAS
PCT = re.compile(r'%[0-9]*[A-EG-Za-z]')
EXTRA_PCT = {'s': 9 - 2, 'd': 5 - 2}          # caracteres que añade la expansión sobre el token
SUSTITUIR = [("'", ''), ('’', ''), ('‘', ''), ('"', ''), ('“', ''), ('”', ''), ('-', ' '), ('⇒', '')]


def limpiar(t: str) -> str:
    for a, b in SUSTITUIR:
        t = t.replace(a, b)
    return t


def coste(linea: str) -> int:
    extra = sum(EXTRA_PCT.get(m[-1], 9) for m in PCT.findall(linea))
    return len(M.transportar(linea)) + extra


def ajustar(texto: str, ancho_linea) -> str:
    """comun82.ajustar con el coste de las expansiones de % y páginas vacías prohibidas."""
    texto = K.sin_marcas(texto)

    def cabe(linea):
        return coste(linea) <= M.MAX_CAR and ancho_linea(linea) <= M.ANCHO_TINTA

    paginas = []
    for bloque in texto.split(PAGINA):
        filas, actual = [], ''
        for p in ' '.join(bloque.replace(SALTO, ' ').split()).split():
            if not cabe(p):
                raise ValueError(f'palabra más larga que la línea: {p}')
            cand = f'{actual} {p}' if actual else p
            if actual and not cabe(cand):
                filas.append(actual)
                actual = p
            else:
                actual = cand
        if actual:
            filas.append(actual)
        if not filas:
            continue                                # \f sobrante del oficial: no se crean páginas vacías
        paginas.extend(SALTO.join(filas[i:i + LINEAS]) for i in range(0, len(filas), LINEAS))
    if not paginas:
        raise ValueError('texto vacío')
    return PAGINA.join(paginas)


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    filas = pickle.loads((HERE / 'clasificacion.pkl').read_bytes())
    base = {t: C.Guion(C.BASE, t) for t in CARPETA}
    orig = {t: C.Guion(C.ORIGINAL, t) for t in CARPETA}
    med = K.Medidor(C.fuente12())
    for t, d in CARPETA.items():
        if (HERE / d).exists():
            shutil.rmtree(HERE / d)
        (HERE / d).mkdir()
    st = collections.Counter()
    no_caben, solape, por_evento = [], [], collections.defaultdict(dict)
    for x in filas:
        if x['clase'] != 'b':
            continue
        st['clase_b'] += 1
        if x['protegido']:
            st['omitido_protegido'] += 1
            continue
        jp_pct = sorted(PCT.findall(K.sin_marcas(x['japones'])))
        fuente, texto = None, None
        for nombre, v in (('eu3ds', x['oficial_eu3ds']), ('nds', x['oficial_nds'])):
            if v and sorted(PCT.findall(v)) == jp_pct:
                fuente, texto = nombre, v
                break
        if texto is None:
            no_caben.append(dict(x, motivo='%s/%d distintos del japonés'))
            continue
        try:
            es = ajustar(limpiar(texto), med.ancho_es)
            body = encode_fullwidth(es)
        except (ValueError, UnicodeEncodeError) as e:
            no_caben.append(dict(x, motivo=str(e)[:120]))
            continue
        pags = es.split(PAGINA)
        faltan = sorted({c for pg in pags for c in med.sin_glifo(M.transportar(pg))} - {'\\'})
        if faltan:
            no_caben.append(dict(x, motivo=f'sin glifo: {"".join(faltan)}'))
            continue
        if len(body) + 5 > 252:
            no_caben.append(dict(x, motivo=f'{len(body)} B > 247'))
            continue
        assert all(0 < len(pg.split(SALTO)) <= LINEAS for pg in pags), x
        assert all(coste(ln) <= M.MAX_CAR and ln.strip() for pg in pags for ln in pg.split(SALTO)), x
        if not jp_pct:
            assert M.respeta_motor(body), x
        por_evento[(x['tipo'], x['evento'])][x['indice']] = (body, fuente, dict(x, oficial_usado=texto), es)
    # objetivos (0x402f arg 3): registro de bigramas v89
    sys.path.insert(0, str(HERE))
    import objetivos as O
    plan_obj, cambios_obj, rechazos_obj, sha_f12 = O.planificar(limpiar)
    for eid, cmb in plan_obj.items():
        for i, (body, info) in cmb.items():
            x = dict(tipo='eve', evento=eid, indice=i, id=None, texto_juego=info['antes'], objetivo=True)
            por_evento[('eve', eid)][i] = (body, 'eu3ds', x, info['despues'])
    st['objetivos_cambiados'] = sum(len(v) for v in plan_obj.values())
    informe = dict(base=str(C.BASE), eventos=[], total={})
    iguales_v91 = []
    for (tipo, eid), cambios in sorted(por_evento.items()):
        data = base[tipo].evento(eid)
        v91 = V91 / CARPETA[tipo] / f'{eid}.ssd'
        partida = v91.read_bytes() if v91.exists() else data
        _, ops, recs = K.S.parse(partida)
        _, _, recs_base = K.S.parse(data)
        for i in list(cambios):
            if cambios[i][0] == recs[i].body:          # v91 ya dejó exactamente este texto
                st['ya_igual_en_v91'] += 1
                iguales_v91.append(dict(tipo=tipo, evento=eid, indice=i, texto=cambios[i][3],
                                        oficial=cambios[i][2].get('oficial_usado'),
                                        objetivo=bool(cambios[i][2].get('objetivo'))))
                del cambios[i]
            elif recs[i].raw != recs_base[i].raw:
                solape.append(dict(tipo=tipo, evento=eid, indice=i, v91=K.a_espanol(recs[i].body),
                                   v92=cambios[i][3]))
        if not cambios:
            continue
        for i, v in cambios.items():
            esperado = (0x402F, 3) if v[2].get('objetivo') else (C.OP_DIALOGO, 1)
            assert (ops[recs[i].instruction], recs[i].argument) == esperado, (eid, i)
        fija = (any(re.search(rb'%\d+F', r.body) for r in recs)
                or (eid >= 90000000 and len(data) == len(orig[tipo].evento(eid))))
        repl = {i: v[0] for i, v in cambios.items()}
        if fija:
            # solo lo que no crece; si aún así el evento crece (no debería), se quita lo que más crece
            for i in list(repl):
                if ((4 + len(repl[i]) + 1 + 3) & ~3) > len(recs[i].raw):
                    no_caben.append(dict(cambios[i][2], motivo='el evento no puede crecer'))
                    del repl[i]
            while repl and len(K.S.replace(partida, repl)) > len(partida):
                i = max(repl, key=lambda j: len(repl[j]) - len(recs[j].body))
                no_caben.append(dict(cambios[i][2], motivo='el evento no puede crecer'))
                del repl[i]
        for i in cambios:
            if i not in repl:
                st['quitados_por_crecer'] += 1
        if not repl:
            continue
        nuevo = K.S.replace(partida, repl)
        end, ops2, recs2 = K.S.parse(nuevo)
        end1, _, _ = K.S.parse(partida)
        assert nuevo[32:end] == partida[32:end1] and ops2 == ops and len(recs2) == len(recs)
        for j, (a, b) in enumerate(zip(recs, recs2)):
            assert (a.instruction, a.argument) == (b.instruction, b.argument)
            if j not in repl:
                assert a.raw == b.raw
        (HERE / CARPETA[tipo] / f'{eid}.ssd').write_bytes(nuevo)
        st[f'eventos_{tipo}'] += 1
        st[f'registros_{tipo}'] += sum(1 for i in repl if not cambios[i][2].get('objetivo'))
        st['crece_bytes'] += len(nuevo) - len(partida)
        for i in repl:
            if not cambios[i][2].get('objetivo'):
                st[f'fuente_{cambios[i][1]}'] += 1
        informe['eventos'].append(dict(
            tipo=tipo, evento=eid, sobre_v91=v91.exists(), fijo=fija, bytes_antes=len(partida),
            bytes_despues=len(nuevo),
            registros=[dict(indice=i, tipo_registro='objetivo' if cambios[i][2].get('objetivo') else 'dialogo',
                            fuente=cambios[i][1], antes=cambios[i][2]['texto_juego'],
                            oficial=cambios[i][2].get('oficial_usado'), despues=cambios[i][3]) for i in sorted(repl)]))
    quitados_obj = {(n['evento'], n['indice']) for n in no_caben if n.get('objetivo')}
    informe['objetivos'] = dict(registro_bigramas='work/ie1/capas/fuentes/bigramas_ritmo/registro.json',
                                font12_base_sha256=sha_f12,
                                cambios=[c for c in cambios_obj if (c['evento'], c['indice']) not in quitados_obj],
                                rechazados=rechazos_obj)
    st['no_caben'] = len(no_caben)
    st['solape_v91'] = len(solape)
    informe['total'] = dict(st)
    informe['motivos_no_caben'] = dict(collections.Counter(re.sub(r'^\d+ B > 247$', '> 247 B', re.sub(r':.*', '', n['motivo']))
                                                           for n in no_caben))
    informe['solape_v91'] = solape
    informe['iguales_en_v91'] = iguales_v91
    informe['v91_events_presentes'] = any((V91 / d).exists() for d in CARPETA.values())
    (HERE / 'informe.json').write_text(json.dumps(informe, ensure_ascii=False, indent=1), encoding='utf-8')
    (HERE / 'no_caben.json').write_text(json.dumps(no_caben, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(informe['total'], ensure_ascii=False, indent=1))
    print(informe['motivos_no_caben'])


if __name__ == '__main__':
    main()
