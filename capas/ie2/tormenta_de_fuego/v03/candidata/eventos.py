"""IE2 Fuego v03 · paso 1: eventos eve/mch con las tandas de texto v03 fusionadas sobre probe_ie2_v02.

Fuentes (todas en work/, se regeneran con su script):
- diálogo pendiente de v02: ../dialogo/textos.json (0x301d referenciados como arg 1 con cabecera arg 2,
  no_caben condensados a mano, %s/%d). Cuerpo = v02 apply.preparar (22 × 3 por frases, ancho completo).
- rótulos y objetivos: ../rotulos/textos.json. Rótulo (0x4037 arg 3) = comun_v03.Bigramas.rotulo
  (<= 10 casillas con centrado). Cabecera 0x402f arg 2 y objetivos (0x2017/0x2018/0x201c/0x2023 arg 3)
  = Bigramas.libre(texto, 'objetivo').
Cada registro solo se toca si en la base v02 sigue con el japonés original y si su índice lo referencia
únicamente la instrucción/argumento esperados. Eventos protegidos (comun_ie2.PROTEGIDOS): intactos.

Salida: events/ (eve) y events_mch/ (mch) con el SSD completo de cada evento cambiado; eventos.json.
Uso: python -X utf8 eventos.py
"""
from __future__ import annotations

import collections
import importlib.util
import json
import shutil
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[5]
sys.path.insert(0, str(ROOT / 'work/ie2/shared/capas/v03/textos'))
import comun_v03 as K  # noqa: E402

M = K.M
V03 = HERE.parent
DIALOGO = V03 / 'dialogo/textos.json'
ROTULOS = V03 / 'rotulos/textos.json'
OBJETIVO_OPS = (0x2017, 0x2018, 0x201C, 0x2023)
LIMITE_ROTULO_B = 20


def _apply_v02():
    spec = importlib.util.spec_from_file_location('v02_apply', M.HERE / 'apply.py')
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def instrucciones(data: bytes):
    """ident -> (opcode, [(tipo, valor)]) (misma lectura que work/ie1/capas/v33/eve_labels/common.py)."""
    _, _, _, count, _, _, _, _, _ = struct.unpack_from('<4sIIHHIIII', b'SSD\0' + data[4:32])
    pos, out = 32, {}
    for _ in range(count):
        ident, length, opcode, argc, _ = struct.unpack_from('<HHHBB', data, pos)
        types = 4 * ((argc + 7) // 8)
        args = []
        for a in range(argc):
            kind = (data[pos + 8 + a // 2] >> (4 * (a % 2))) & 15
            args.append((kind, struct.unpack_from('<I', data, pos + 8 + types + 4 * a)[0]))
        out[ident] = (opcode, args)
        pos += length
    return out


def referencias(data: bytes):
    refs = collections.defaultdict(set)
    for _, (op, args) in instrucciones(data).items():
        for pos, (kind, val) in enumerate(args, 1):
            if kind == 3:
                refs[val].add((op, pos))
    return refs


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    A02 = _apply_v02()
    B = K.bigramas()
    jp = M.Archivo(M.JP)
    base = M.Archivo(K.BASE_V02)
    cambios = collections.defaultdict(dict)       # (pk, eid) -> {indice: (cuerpo, tipo, esperado)}
    informe = collections.Counter()
    rechazos = []

    def poner(pk, eid, i, cuerpo, tipo, ref):
        if eid in M.PROTEGIDOS:
            rechazos.append(dict(paquete=pk, evento=eid, indice=i, tipo=tipo, motivo='protegido'))
            return
        prev = cambios[(pk, eid)].get(i)
        assert prev is None or prev[0] == cuerpo, (pk, eid, i, tipo)
        cambios[(pk, eid)][i] = (cuerpo, tipo, ref)

    # diálogo -------------------------------------------------------------------------------------------
    if DIALOGO.exists():
        for f in json.loads(DIALOGO.read_text(encoding='utf-8')):
            cuerpo, _ = A02.preparar(f['jp'], f['es'])
            poner(f['paquete'], f['evento'], f['indice'], cuerpo, 'dialogo:' + f['origen'], {(0x301D, 1)})
    else:
        print('AVISO: falta', DIALOGO)

    # rótulos y objetivos ---------------------------------------------------------------------------------
    if ROTULOS.exists():
        T = json.loads(ROTULOS.read_text(encoding='utf-8'))
        cab = {k: B.libre(v, 'objetivo')[0] for k, v in T.get('cabecera', {}).items()}
        rot = {}
        for k, v in T.get('rotulos', {}).items():
            if v:
                rot[k] = B.rotulo(v)
                assert len(rot[k]) <= LIMITE_ROTULO_B, (k, v)
        obj = {(o['evento'], o['indice']): o for o in T.get('objetivos', [])}
        for eid in jp.ids('eve'):
            data = jp.evento('eve', eid)
            try:
                _, ins, recs = M.S.parse(data)
            except ValueError:
                continue
            for i, r in enumerate(recs):
                op = ins.get(r.instruction)
                if not r.body:
                    continue
                t = r.body.decode('cp932', 'replace')
                if (op, r.argument) == (0x4037, 3) and t in rot:
                    poner('eve', eid, i, rot[t], 'rotulo', {(0x4037, 3)})
                elif (op, r.argument) == (0x402F, 2) and t in cab:
                    poner('eve', eid, i, cab[t], 'objetivo_cabecera', {(0x402F, 2)})
                elif op in OBJETIVO_OPS and r.argument == 3 and (eid, i) in obj:
                    o = obj[(eid, i)]
                    assert o['jp'] == t, (eid, i)
                    cuerpo, n = B.libre(o['es'], 'objetivo')
                    # caja 0x402f de ina_main2.cro: búfer 64×128 de FONT12, como IE1 (128 casillas)
                    assert n <= 128, (eid, i, o['es'], n)
                    poner('eve', eid, i, cuerpo, 'objetivo', {(op, 3)})
        for eid in jp.ids('mch'):
            data = jp.evento('mch', eid)
            try:
                _, ins, recs = M.S.parse(data)
            except ValueError:
                continue
            for i, r in enumerate(recs):
                if (ins.get(r.instruction), r.argument) == (0x402F, 2) and r.body.decode('cp932', 'replace') in cab:
                    poner('mch', eid, i, cab[r.body.decode('cp932')], 'objetivo_cabecera', {(0x402F, 2)})
    else:
        print('AVISO: falta', ROTULOS)

    # escribir --------------------------------------------------------------------------------------------
    salidas = {'eve': HERE / 'events', 'mch': HERE / 'events_mch'}
    for d in salidas.values():
        if d.exists():
            shutil.rmtree(d)
        d.mkdir()
    eventos = []
    for (pk, eid), cmb in sorted(cambios.items()):
        orig = jp.evento(pk, eid)
        actual = base.evento(pk, eid)
        _, ins, recs_o = M.S.parse(orig)
        _, ins_a, recs_a = M.S.parse(actual)
        assert ins == ins_a and len(recs_o) == len(recs_a)
        refs = referencias(actual)
        aplicar = {}
        for i, (cuerpo, tipo, esperado) in sorted(cmb.items()):
            if recs_a[i].raw != recs_o[i].raw:
                rechazos.append(dict(paquete=pk, evento=eid, indice=i, tipo=tipo, motivo='ya cambiado en v02'))
                continue
            if refs.get(i, set()) != esperado:
                rechazos.append(dict(paquete=pk, evento=eid, indice=i, tipo=tipo,
                                     motivo=f'referencias {sorted(refs.get(i, set()))}'))
                continue
            aplicar[i] = cuerpo
            informe[tipo] += 1
        if not aplicar:
            continue
        nuevo = M.S.replace(actual, aplicar)
        end2, ins2, recs2 = M.S.parse(nuevo)
        assert ins2 == ins and len(recs2) == len(recs_a)
        for j, (a, b) in enumerate(zip(recs_a, recs2)):
            assert (a.instruction, a.argument) == (b.instruction, b.argument)
            assert (b.body == aplicar[j]) if j in aplicar else (a.raw == b.raw), (pk, eid, j)
        (salidas[pk] / f'{eid}.ssd').write_bytes(nuevo)
        eventos.append(dict(paquete=pk, evento=eid, registros=sorted(aplicar), bytes_v02=len(actual),
                            bytes=len(nuevo), max_registro=max(len(v) for v in aplicar.values())))
    res = dict(registros=dict(informe), eventos=len(eventos),
               eventos_por_paquete=dict(collections.Counter(e['paquete'] for e in eventos)),
               rechazos=rechazos, detalle=eventos)
    (HERE / 'eventos.json').write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(dict(registros=dict(informe), eventos=res['eventos_por_paquete'],
                          rechazos=collections.Counter(r['motivo'] for r in rechazos)), ensure_ascii=False))


if __name__ == '__main__':
    main()
