"""IE2 Fuego v02 · paso 2: texto español oficial NDS en los registros de diálogo emparejados por ID.

Por registro emparejado (pares.json, solo 0x301d argumento 1; 0x4037/0x402f quedan para su tanda):
1. texto NDS -> `normalizar` (sin comillas ni apóstrofos, sin glifo en NFTR; práctica de IE1);
2. `ajustar`: cajas de 3 líneas × 22 caracteres por frases, sin cortar palabras (%s/%d con su hueco);
3. `transportar`: ancho completo cp932 con portadores de acentos (dialogue_typography);
4. se quitan los marcadores %NF (el español no los lleva); las lecturas (argumentos 2..N) se quedan
   intactas, como en IE1 v88 (el motor no las consume si no hay marcador);
5. comprobaciones: glifo en FONT12.bcfnt, registro <= 247 B, %s/%d iguales al japonés, el modelo del
   motor (comun82) no inserta ni convierte saltos, <= 22 caracteres y <= 3 líneas por caja.
Lo que falla va a no_caben.json con el motivo; no se trunca nada.

Protegidos (PROTEGIDOS): no se tocan. Excepción: 22010100 lleva exactamente el evento de la sonda v01
(una frase sin furigana ya vista en juego).

Salida: events/ (eve), events_mch/ (mch), aplicado.json, no_caben.json.
Uso: python -X utf8 apply.py
"""
from __future__ import annotations

import json
import shutil
import sys
from collections import Counter, defaultdict

import comun_ie2 as M


def preparar(jt: str, es: str):
    """(cuerpo, texto ajustado) o lanza ValueError con el motivo."""
    es = M.normalizar(es)
    try:
        texto = M.ajustar(es)
    except ValueError as exc:
        raise ValueError(f'ajuste: {exc}') from None
    try:
        cuerpo = M.transportar(texto)
    except UnicodeEncodeError as exc:
        raise ValueError(f'sin_glifo: {texto[exc.start:exc.end]!r}') from None
    faltan = M.sin_glifo(cuerpo)
    if faltan:
        raise ValueError(f'sin_glifo: {"".join(faltan)!r}')
    if len(cuerpo) > M.MAX_BYTES:
        raise ValueError(f'excede_247: {len(cuerpo)} B')
    if M.pct(cuerpo.decode('cp932')) != M.pct(jt):
        raise ValueError('pct')
    if M.FURI.search(cuerpo.decode('cp932')):
        raise ValueError('furigana')
    if not M.respeta_motor(cuerpo):
        raise ValueError('motor_reajusta')
    for pg in M.paginas(cuerpo):
        if not 0 < len(pg) <= M.LINEAS or any(len(x) > M.MAX_CAR or not x.strip() for x in pg):
            raise ValueError(f'caja: {pg}')
    return cuerpo, texto


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    jp = M.Archivo(M.JP)
    pares = json.loads((M.HERE / 'pares.json').read_text(encoding='utf-8'))
    por_pk = defaultdict(dict)
    for k, filas in pares.items():
        pk, eid = k.split(':')
        por_pk[pk][int(eid)] = filas
    salidas = {'eve': M.HERE / 'events', 'mch': M.HERE / 'events_mch'}
    for d in salidas.values():
        if d.exists():
            shutil.rmtree(d)
        d.mkdir()
    informe = {'eventos': {}, 'total': {}}
    no_caben = []
    total = Counter()
    for pk, eventos in por_pk.items():
        for eid, filas in sorted(eventos.items()):
            assert eid not in M.PROTEGIDOS, eid
            data = jp.evento(pk, eid)
            end, ins, recs, dl = M.dialogos(data)
            cambios, reg = {}, []
            cnt = Counter()
            for f in filas:
                i = f['indice']
                r = recs[i]
                assert i in dl and r.instruction == f['id'] and r.body.decode('cp932') == f['jp'], (eid, i)
                try:
                    cuerpo, texto = preparar(f['jp'], f['es'])
                except ValueError as exc:
                    motivo = str(exc)
                    cnt['no_cabe'] += 1
                    cnt['no_cabe:' + motivo.split(':')[0]] += 1
                    no_caben.append(dict(paquete=pk, evento=eid, indice=i, id=f['id'], id_nds=f['id_nds'],
                                         motivo=motivo, jp=f['jp'], es=f['es']))
                    continue
                cambios[i] = cuerpo
                cnt['traducidos'] += 1
                cnt[f['clase']] += 1
                reg.append(dict(indice=i, id=f['id'], id_nds=f['id_nds'], clase=f['clase'], texto=texto,
                                bytes=len(cuerpo), cajas=len(M.paginas(cuerpo))))
            total.update({f'{pk}:{k}': v for k, v in cnt.items()})
            if not cambios:
                continue
            nuevo = M.S.replace(data, cambios)
            end2, ins2, recs2 = M.S.parse(nuevo)
            assert nuevo[32:end] == data[32:end] and ins2 == ins and len(recs2) == len(recs)
            for j, (a, b) in enumerate(zip(recs, recs2)):
                assert (a.instruction, a.argument) == (b.instruction, b.argument)
                assert j in cambios or a.raw == b.raw
            (salidas[pk] / f'{eid}.ssd').write_bytes(nuevo)
            informe['eventos'][f'{pk}:{eid}'] = dict(**cnt, crece=len(nuevo) - len(data), registros=reg)
    # protegido con la frase de la sonda v01
    v01 = (M.V01_EVENTOS / '22010100.ssd').read_bytes()
    orig = jp.evento('eve', 22010100)
    _, _, ra = M.S.parse(orig)
    _, _, rb = M.S.parse(v01)
    distintos = [i for i, (a, b) in enumerate(zip(ra, rb)) if a.raw != b.raw]
    assert len(ra) == len(rb) and len(distintos) == 1, distintos
    shutil.copyfile(M.V01_EVENTOS / '22010100.ssd', salidas['eve'] / '22010100.ssd')
    informe['protegido_v01'] = dict(evento=22010100, registro=distintos[0],
                                    texto=M.K.a_espanol(rb[distintos[0]].body))
    informe['total'] = dict(total)
    (M.HERE / 'aplicado.json').write_text(json.dumps(informe, ensure_ascii=False, indent=1), encoding='utf-8')
    (M.HERE / 'no_caben.json').write_text(json.dumps(no_caben, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(dict(total), ensure_ascii=False, indent=1))
    print('eventos eve', len(list(salidas['eve'].glob('*.ssd'))), 'mch', len(list(salidas['mch'].glob('*.ssd'))))


if __name__ == '__main__':
    main()
