"""v91 · nombres oficiales en lugar de romanizaciones japonesas en el diálogo de IE1.

Queja del usuario (Azahar): Axel dice «Mikage fue subcampeón regional, pero perdió contra…»; 御影専農 es
«Brain» en la versión europea (translation/shared/glossary/equipos.csv).

Base: work/shared/candidatas/probe_ie2_v05/archive.fa (inazuma1/data_iz/script/eve.pkb = texto IE1 actual).
Para cada registro de diálogo (0x301d) con un nombre no oficial (nombres.DETECTAR):
  1) línea oficial NDS emparejada por ID (comun91.Fuentes.oficial, como tools/audit_dialogo_ids.py),
     limpiada (comillas ?h y apóstrofos no tienen glifo), si cabe: ajuste v84 (22 caracteres, 3 líneas,
     sin cortar palabras), registro <= 247 B, mismos códigos %, glifos presentes, motor sin saltos extra,
     sin nombres no oficiales;
  2) si no hay par NDS utilizable o no cabe: se cambia solo el nombre (nombres.REGLAS) sobre el texto
     actual y se reajusta con la misma regla.
Eventos protegidos (92010100-92010509, 81000040) intactos. Ningún registro de bigramas (objetivos
0x402f / rótulos 0x4037 con el registro v90) contiene nombres (sonda_bigramas.py): no se recodifica
ninguno y quedan byte a byte iguales. Los eventos pueden crecer (solo cambian registros de diálogo; la
regla «eventos <= v87» de v88/v89 se refería a sus propios objetivos/rótulos). Los registros con
maquetado propio (menú de depuración 90000000, líneas > 22) solo cambian el nombre, sin reajustar.

Salida: events/*.ssd, informe.json. Con --csv actualiza translation/ie1/dialogo.csv (oficial / glosario).
Uso: python -X utf8 work/ie1/capas/historial/dialogo/v91_nombres_oficiales/apply.py [--seco] [--csv | --solo-csv]
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import shutil
import sys
from collections import Counter

import comun91 as C
import nombres as N

M, K, HERE, ROOT = C.M, C.K, C.HERE, C.ROOT
sys.path.insert(0, str(ROOT / 'tools'))
from dialogue_typography import encode_fullwidth  # noqa: E402

SALTO, PAGINA = M.SALTO, M.PAGINA
CSV = ROOT / 'translation/ie1/dialogo.csv'
REG90 = ROOT / 'work/ie1/capas/historial/menus_cro/v90_cro_restantes/registro.json'
OPS_BIGRAMAS = {(0x402f, 2), (0x402f, 3), (0x4037, 3)}

# Pares NDS que no se usan (revisados a mano).
RECHAZAR_NDS = {
    (92081450, 49): 'la línea NDS emparejada es otra frase (no menciona el pase a Constant)',
}


def limpiar_nds(t: str) -> str:
    # comillas (?h) y apóstrofo sin glifo; el guion no se codifica en shift_jis: «9-0» -> «9 a 0»
    t = t.replace('?h', '').replace("'", '')
    t = re.sub(r'(\d)-(\d)', r'\1 a \2', t)
    return re.sub(r' +', ' ', t).strip()


def nds_valida(t: str) -> bool:
    return t.count('?') <= t.count('¿') and not re.search(r'[ÚÑ]\?|\?[ÚÑ]', t)


def plano(t: str) -> str:
    return re.sub(r'\\[nf]', ' ', t)


def fuente_glosario(actual: str) -> str:
    """Texto actual con los nombres cambiados. Une páginas partidas a mitad de frase."""
    pags = [re.sub(r'\s+', ' ', p.replace(SALTO, ' ')).strip() for p in actual.split(PAGINA)]
    unidas = []
    for p in pags:
        if unidas and not re.search(r'[.!?…]$', unidas[-1]):
            unidas[-1] += ' ' + p
        else:
            unidas.append(p)
    return PAGINA.join(N.sustituir(p) for p in unidas)


class Rechazo(Exception):
    pass


def maquetado_propio(actual: str) -> bool:
    """True si el registro no sigue el ajuste de diálogo (menús de depuración: opciones «Sí :»/«No :» o
    líneas de más de 22 caracteres)."""
    if re.search(r'(^|\\n)(Sí|No) ?(:|=>)', actual):
        return True
    return any(len(M.transportar(f)) > M.MAX_CAR for pg in actual.split(PAGINA) for f in pg.split(SALTO))


def ancho_max(actual: str) -> int:
    return max(len(M.transportar(f)) for pg in actual.split(PAGINA) for f in pg.split(SALTO))


def preparar_in_situ(actual: str, cuerpo_viejo: bytes, med, tope: int) -> tuple[str, str, bytes]:
    """Cambia el nombre línea a línea sin reajustar (mismos saltos). `tope`: línea más larga que el mismo
    menú ya muestra (registros de maquetado propio del evento)."""
    es = PAGINA.join(SALTO.join(N.sustituir(f) for f in pg.split(SALTO)) for pg in actual.split(PAGINA))
    body = encode_fullwidth(es)
    if len(body) > 247:
        raise Rechazo(f'{len(body)} B > 247')
    if body.count(b'%') != cuerpo_viejo.count(b'%'):
        raise Rechazo('códigos % distintos')
    for pg in es.split(PAGINA):
        for f in pg.split(SALTO):
            if len(M.transportar(f)) > tope:
                raise Rechazo(f'línea más larga que la original ({tope}): {f}')
            if med.sin_glifo(M.transportar(f)):
                raise Rechazo('sin glifo')
    if N.detectar(plano(es)):
        raise Rechazo(f'quedan nombres: {N.detectar(plano(es))}')
    return es, es, body


def preparar(texto: str, cuerpo_viejo: bytes, med) -> tuple[str, bytes]:
    try:
        es = M.ajustar(texto, med.ancho_es)
    except ValueError as exc:
        raise Rechazo(str(exc))
    body = encode_fullwidth(es)
    if len(body) > 247:
        raise Rechazo(f'{len(body)} B > 247')
    if body.count(b'%') != cuerpo_viejo.count(b'%'):
        raise Rechazo('códigos % distintos')
    if b'%' not in body and not M.respeta_motor(body):
        raise Rechazo('el motor insertaría saltos')
    for pg in es.split(PAGINA):
        filas = pg.split(SALTO)
        if not 0 < len(filas) <= M.LINEAS:
            raise Rechazo('página de más de 3 líneas')
        for f in filas:
            if len(M.transportar(f)) > M.MAX_CAR:
                raise Rechazo(f'línea de más de {M.MAX_CAR}: {f}')
            if med.sin_glifo(M.transportar(f)):
                raise Rechazo(f'sin glifo: {med.sin_glifo(M.transportar(f))}')
    if N.detectar(plano(es)):
        raise Rechazo(f'quedan nombres: {N.detectar(plano(es))}')
    return es, body


def eventos_con_bigramas(F):
    reg = json.loads(REG90.read_text(encoding='utf-8'))
    codigos = {bytes.fromhex(e['sjis']) for e in reg['bigramas']}
    out = set()
    for eid in F.cand.indice:
        try:
            _, ops, recs = K.S.parse(F.cand.evento(eid))
        except ValueError:
            continue
        for r in recs:
            if (ops.get(r.instruction), r.argument) in OPS_BIGRAMAS:
                b, i = r.body, 0
                while i < len(b):
                    if 0x81 <= b[i] <= 0x9F or 0xE0 <= b[i] <= 0xFC:
                        if b[i:i + 2] in codigos:
                            out.add(eid)
                        i += 2
                    else:
                        i += 1
    return out


def _decodifica(b):
    try:
        K.a_espanol(b)
        return True
    except UnicodeDecodeError:
        return False


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser()
    ap.add_argument('--seco', action='store_true', help='no escribe events/ ni informe')
    ap.add_argument('--csv', action='store_true', help='actualiza translation/ie1/dialogo.csv')
    ap.add_argument('--solo-csv', action='store_true', help='solo el CSV, con el informe.json existente')
    args = ap.parse_args()
    if args.solo_csv:
        actualizar_csv(json.loads((HERE / 'informe.json').read_text(encoding='utf-8')))
        return
    F = C.Fuentes()
    med = K.Medidor(F.cand.fuente())
    con_bigramas = eventos_con_bigramas(F)
    informe = dict(base=str(C.BASE.relative_to(ROOT)).replace('\\', '/'), cambios=[], sin_cambio=[],
                   no_nombres=[], eventos=[])
    total = Counter()
    por_evento = {}
    for eid in sorted(F.cand.indice):
        data = F.cand.evento(eid)
        try:
            _, ops, recs = K.S.parse(data)
        except ValueError:
            continue
        cambios, pendientes = {}, {}
        propios = [K.a_espanol(r.body) for r in recs if ops.get(r.instruction) == K.OP_DIALOGO
                   and _decodifica(r.body) and maquetado_propio(K.a_espanol(r.body))]
        tope_evento = max(map(ancho_max, propios), default=0)
        for i, r in enumerate(recs):
            if ops.get(r.instruction) != K.OP_DIALOGO:
                continue
            try:
                actual = K.a_espanol(r.body)
            except UnicodeDecodeError:
                continue
            hits = N.detectar(plano(actual))
            if not hits:
                continue
            nombres = [h for h in hits if h in N.OFICIAL]
            for h in hits:
                if h in N.NO_NOMBRES:
                    informe['no_nombres'].append(dict(evento=eid, indice=i, palabra=h, motivo=N.NO_NOMBRES[h],
                                                      texto=actual))
                    total[f'no_nombre:{h}'] += 1
            if not nombres:
                continue
            _, jp = F.japones(eid, i)
            fila = dict(evento=eid, indice=i, id=r.instruction, arg=r.argument, nombres=nombres,
                        oficiales={h: N.OFICIAL[h][1] for h in nombres}, japones=jp, antes=actual)
            if eid in K.PROTEGIDOS or eid in K.DONT_TOUCH:
                fila['motivo'] = 'evento protegido'
                informe['sin_cambio'].append(fila)
                continue
            nds = F.oficial(eid, r.instruction, r.argument)
            fila['nds'] = nds
            opciones = []
            motivos = []
            if nds is None:
                motivos.append('sin par NDS')
            elif (eid, i) in RECHAZAR_NDS:
                motivos.append('NDS rechazada: ' + RECHAZAR_NDS[(eid, i)])
            elif not nds_valida(limpiar_nds(nds)):
                motivos.append('NDS ilegible')
            else:
                try:
                    es, body = preparar(limpiar_nds(nds), r.body, med)
                    opciones.append(('oficial', es, body, limpiar_nds(nds)))
                except Rechazo as exc:
                    motivos.append(f'NDS no cabe: {exc}')
            try:
                if maquetado_propio(actual):
                    src, es, body = preparar_in_situ(actual, r.body, med, tope_evento)
                    fila['in_situ'] = True
                else:
                    src = fuente_glosario(actual)
                    es, body = preparar(src, r.body, med)
                opciones.append(('glosario', es, body, src))
            except Rechazo as exc:
                motivos.append(f'glosario: {exc}')
            if not opciones:
                fila['motivo'] = '; '.join(motivos)
                informe['sin_cambio'].append(fila)
                continue
            pendientes[i] = (fila, opciones, motivos, r)
        if not pendientes:
            continue
        eleccion = {i: 0 for i in pendientes}

        def construir():
            return K.S.replace(data, {i: pendientes[i][1][k][2] for i, k in eleccion.items()})

        # Crecer es válido (SSD.replace recalcula tamaños; la build valida estructura). La regla
        # «eventos <= v87» de v88/v89 era solo para sus propios cambios en objetivos/rótulos; aquí los
        # registros de bigramas quedan byte a byte iguales.
        nuevo = construir()
        for i, k in sorted(eleccion.items()):
            fila, opciones, motivos, r = pendientes[i]
            fuente, es, body, src = opciones[k]
            descartes = list(motivos)
            fila.update(fuente=fuente, despues=es, bytes_antes=len(r.body), bytes=len(body),
                        descartado=descartes or None, csv_texto=src)
            cambios[i] = body
            informe['cambios'].append(fila)
            total[fuente] += 1
            for h in fila['nombres']:
                total[f'nombre:{h}'] += 1
        if not cambios:
            continue
        assert nuevo == K.S.replace(data, cambios)
        _, ops2, recs2 = K.S.parse(nuevo)
        assert ops2 == ops and len(recs2) == len(recs)
        for j, (a, b) in enumerate(zip(recs, recs2)):
            assert (a.instruction, a.argument) == (b.instruction, b.argument)
            if j not in cambios:
                assert a.raw == b.raw
        if eid in con_bigramas:
            _, _, rb = K.S.parse(data)
            for j, (a, b) in enumerate(zip(rb, recs2)):
                if (ops.get(a.instruction), a.argument) in OPS_BIGRAMAS:
                    assert a.raw == b.raw, (eid, j)
        por_evento[eid] = nuevo
        informe['eventos'].append(dict(evento=eid, registros=sorted(cambios), bytes_antes=len(data),
                                       bytes=len(nuevo), con_bigramas=eid in con_bigramas))
    for f in informe['sin_cambio']:
        total['sin_cambio'] += 1
    informe['total'] = dict(total)
    print(json.dumps(informe['total'], ensure_ascii=False))
    if args.seco:
        for f in informe['cambios']:
            print(f"{f['evento']}#{f['indice']} [{f['fuente']}] {f['nombres']}\n  - {f['antes']}\n  + {f['despues']}"
                  + (f"\n    ({f['descartado']})" if f['descartado'] else ''))
        for f in informe['sin_cambio']:
            print(f"SIN CAMBIO {f['evento']}#{f['indice']} {f['nombres']}: {f['motivo']}\n  {f['antes']}")
        return
    out = HERE / 'events'
    if out.exists():
        shutil.rmtree(out)
    out.mkdir()
    for eid, datos in por_evento.items():
        (out / f'{eid}.ssd').write_bytes(datos)
    (HERE / 'informe.json').write_text(json.dumps(informe, ensure_ascii=False, indent=1), encoding='utf-8')
    print('eventos', len(por_evento), 'registros', len(informe['cambios']))
    if args.csv:
        actualizar_csv(informe)


def actualizar_csv(informe):
    raw = CSV.read_bytes()
    texto = raw.decode('utf-8')
    salto = '\r\n' if '\r\n' in texto else '\n'
    filas = list(csv.reader(io.StringIO(texto, newline='')))
    cab = filas[0]
    ie, ij, ies, iest = (cab.index(c) for c in ('event_id', 'japones', 'es_final', 'estado'))
    por_clave = {}
    for f in informe['cambios']:
        por_clave.setdefault((str(f['evento']), f['japones']), f)
    tocadas = Counter()
    for row in filas[1:]:
        f = None
        for (e, jp), g in por_clave.items():
            if row[ie] == e and (row[ij] == jp or row[ij].endswith(jp)):
                f = g
                break
        if f is not None:
            pref = row[ij][:len(row[ij]) - len(f['japones'])]
            nuevo = f['csv_texto'] if f['fuente'] == 'oficial' else f['despues']
            if pref and row[ies].startswith(pref):
                nuevo = pref + nuevo
            if row[ies] != nuevo or row[iest] != f['fuente']:
                row[ies], row[iest] = nuevo, f['fuente']
                tocadas[f['fuente']] += 1
            continue
        # filas sin registro de diálogo (lecturas kana, etc.) con nombres romanizados
        hits = N.detectar(plano(row[ies]))
        if hits and not all(h in N.NO_NOMBRES for h in hits):
            v = row[ies]
            nuevo = None
            for k in range(3):     # prefijo basura de 0-2 caracteres (byte de tamaño mal decodificado)
                if v[k:] in N.NOMBRE_SUELTO:
                    nuevo = v[:k] + N.NOMBRE_SUELTO[v[k:]]
                    break
            if nuevo is None:
                nuevo = N.sustituir(v)
            if nuevo != row[ies] and not N.detectar(plano(nuevo)):
                row[ies], row[iest] = nuevo, 'glosario'
                tocadas['glosario_sin_registro'] += 1
    buf = io.StringIO(newline='')
    csv.writer(buf, lineterminator=salto).writerows(filas)
    CSV.write_bytes(buf.getvalue().encode('utf-8'))
    print('CSV', dict(tocadas))
    informe['csv'] = dict(tocadas)
    (HERE / 'informe.json').write_text(json.dumps(informe, ensure_ascii=False, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()
