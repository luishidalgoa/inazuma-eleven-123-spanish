"""IE2 v03 · traducción de los literales japoneses de romfs/cro/ina_main2.cro.

Entrada: work/shared/base_3ds/romfs/cro/ina_main2.cro (probe_ie2_v02 no lo modifica) y la tabla a mano
literales.json. Salida: romfs/cro/ina_main2.cro junto a este script e informe.json.

Reglas (skill volcado-rom-nds §4b): solo ancho completo (encode_fullwidth), texto codificado <= bytes del
literal japonés (búfer del juego) o del hueco acotado, relleno NUL, nunca vacío, mismos %s/%d en el mismo
orden, sin referencias dentro del hueco, glifo en FONT12.NFTR de inazuma2. No se tocan instrucciones,
punteros ni tablas de relocación.

Uso: python -X utf8 apply.py   (después: python -X utf8 validate.py)
"""
from __future__ import annotations

import json
import sys
from collections import Counter

import comun_cro as C


def comprobar(e, base: bytes, refs) -> tuple[int, bytes, list[str]]:
    o = int(e['offset'], 16)
    jp = C.jp_bytes(e)
    assert base[o:o + len(jp)] == jp, f'{e["offset"]}: el japonés no coincide con la base'
    cap = C.capacidad(e)
    if 'capacidad' not in e:
        assert base[o + len(jp)] == 0, f'{e["offset"]}: el literal japonés no termina en NUL'
    dentro = sorted(t for t in refs.targets | refs.reltargets if o < t < o + cap - 1)
    assert not dentro, f'{e["offset"]}: referencias dentro del hueco {[hex(t) for t in dentro]}'
    es = e['espanol']
    assert es.strip() or es == ' ', f'{e["offset"]}: vacío'
    enc = C.codificar(e)
    assert enc, f'{e["offset"]}: vacío'
    assert len(enc) <= C.limite(e), f'{e["offset"]}: {len(enc)} B > {C.limite(e)} B ({es!r})'
    assert C.FMT.findall(es) == C.FMT.findall(e['japones']), f'{e["offset"]}: especificadores distintos'
    assert not C.MARCA.search(es), f'{e["offset"]}: marcador furigana en el español'
    assert not (set(es) & C.PROHIBIDOS), f'{e["offset"]}: carácter prohibido en {es!r}'
    assert set(C.ascii_sueltos(enc)) <= ({' '} if e.get('clase') == 'formato' else set()), \
        f'{e["offset"]}: ASCII suelto {C.ascii_sueltos(enc)}'
    avisos = []
    malos = C.sin_glifo(enc)
    assert not malos, f'{e["offset"]}: sin glifo en {C.NFTR}: {malos}'
    lj, le = C.lineas_jp(e['japones']), [len(x) for x in es.split('\n')]
    if len(le) > max(len(lj), 3):
        avisos.append(f'{len(le)} líneas (japonés {len(lj)})')
    if max(le) > max(max(lj), 22):
        avisos.append(f'línea de {max(le)} casillas (japonés {max(lj)}, caja 22)')
    return o, enc + b'\0' * (cap - len(enc)), avisos


def main():
    base = C.BASE.read_bytes()
    t = C.tabla()
    assert t['archivo'] == C.REL
    refs = C.Refs(base)
    out = bytearray(base)
    aplicados, avisos, vistos = [], {}, set()
    for e in t['literales']:
        o, datos, av = comprobar(e, base, refs)
        assert all(not (o <= x < o + len(datos)) for x in vistos), f'{e["offset"]}: solapa con otro hueco'
        vistos.update(range(o, o + len(datos)))
        out[o:o + len(datos)] = datos
        if av:
            avisos[e['offset']] = av
        aplicados.append(dict(offset=e['offset'], hueco=len(datos), bytes=len(datos.rstrip(b'\0'))))
    assert len(out) == len(base)
    C.OUT.parent.mkdir(parents=True, exist_ok=True)
    C.OUT.write_bytes(bytes(out))

    lits = t['literales']
    por_origen = Counter(e['origen'] for e in lits)
    sin_fuente = [dict(offset=e['offset'], japones=e['japones'], espanol=e['espanol'], motivo=e.get('recorte', ''))
                  for e in lits if e['origen'] in ('sin_fuente', 'relleno')]
    recortados = [dict(offset=e['offset'], espanol=e['espanol'], fuente=e.get('fuente'), motivo=e['recorte'])
                  for e in lits if e.get('recorte') and e['origen'] not in ('sin_fuente', 'relleno')]
    informe = dict(
        archivo=C.REL,
        base=str(C.BASE.relative_to(C.ROOT)).replace('\\', '/'),
        base_sha256=C.sha(base),
        salida=str(C.OUT.relative_to(C.ROOT)).replace('\\', '/'),
        salida_sha256=C.sha(bytes(out)),
        tamano=len(out),
        candidatos_referenciados=len(lits) + len(t['omitidos']),
        literales_japoneses_encontrados=len(lits) + sum(e['categoria'] != 'binario' for e in t['omitidos']),
        traducidos=len(lits),
        por_origen=dict(por_origen),
        reutilizados_ie1=por_origen['ie1_v89'],
        nuevos=len(lits) - por_origen['ie1_v89'],
        omitidos_por_categoria=dict(Counter(e['categoria'] for e in t['omitidos'])),
        omitidos=t['omitidos'],
        sin_fuente_nds_ni_ie1=sin_fuente,
        recortados=recortados,
        avisos_maquetacion=avisos,
        aplicados=aplicados,
        nota='Validación offline; pendiente de prueba en emulador según PROTOCOLO_QA.',
    )
    C.INFORME.write_text(json.dumps(informe, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps({k: informe[k] for k in ('literales_japoneses_encontrados', 'traducidos', 'por_origen',
                                              'omitidos_por_categoria', 'salida', 'salida_sha256')},
                     ensure_ascii=False, indent=1))
    print('sin fuente:', len(sin_fuente), '· recortados:', len(recortados), '· avisos:', len(avisos))


if __name__ == '__main__':
    sys.exit(main())
