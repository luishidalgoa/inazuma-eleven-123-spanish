"""IE2 Fuego v03 · textos de los registros de diálogo que v02 dejó sin traducir.

Grupos:
- arg2:     registros cuya cabecera dice 0x301d argumento 2 (o distinto de 1) pero que una instrucción
            0x301d referencia como argumento 1 (frases reales). Emparejado igual que v02/emparejar.py.
- no_caben: los registros de v02/no_caben.json; texto NDS recortado (recortes.json).
- pct:      los registros pct_distinto de v02 (el NDS tiene otros %s/%d); SIN fuente NDS: texto escrito
            desde el japonés (condensados.json), listado en informe.json.

REGLA (volcado): el texto NDS va literal si cabe. Si no, solo se QUITAN palabras o incisos del oficial:
recortes.json = {texto NDS o "<paquete>:<evento>:<indice>": [operación, ...]}, operación = subcadena a
borrar o "a=>b" (b = a sin palabras, con mayúscula de inicio). Se comprueba que las palabras resultantes
son una subsecuencia de las del NDS. Excepciones (condensados.json): alargamientos de letras acortados
porque la palabra pasa de 22 caracteres (sin fuente de otro tipo) y los pct.
Todo "es" pasa v02/apply.preparar. Salida: textos.json, informe.json (y pendientes.json con lo que falta).
Uso: python -X utf8 build_textos.py
"""
from __future__ import annotations

import json
import re
import struct
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
V02 = HERE.parents[1] / 'v02' / 'dialogo'
sys.path.insert(0, str(V02))
import comun_ie2 as M  # noqa: E402
import importlib.util  # noqa: E402
_spec = importlib.util.spec_from_file_location('apply_v02', V02 / 'apply.py')
A = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(A)

JPRE = re.compile(r'[぀-ヿ一-鿿]')


def instructions(data: bytes):
    """id -> (opcode, [(kind, valor)]) (copia de work/ie1/capas/v33/eve_labels/common.py)."""
    head = b'SSD\0' + data[4:32]
    _, _, _, count, _, _, _, _, _ = struct.unpack_from('<4sIIHHIIII', head)
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


def text_refs(data: bytes):
    refs = {}
    for ident, (opcode, args) in instructions(data).items():
        for p, (kind, value) in enumerate(args, 1):
            if kind == 3:
                refs.setdefault(value, []).append((ident, opcode, p))
    return refs


def kana_only(text: str) -> bool:
    core = [c for c in text if c not in ' 　']
    return bool(core) and all(0x3040 <= ord(c) <= 0x30FF for c in core)


PALABRA = re.compile(r'\w+')


def recortar(es: str, ops) -> str:
    t = es.replace(M.SALTO, ' ')
    for op in ops:
        a, _, b = op.partition('=>')
        assert a in t, (op, t)
        t = t.replace(a, b, 1)
    return ' '.join(t.split(' ')).replace('  ', ' ').strip()


def subsecuencia(es: str, nds: str) -> bool:
    def pal(t):
        return PALABRA.findall(t.replace(M.SALTO, ' ').replace(M.PAGINA, ' ').lower())
    it = iter(pal(nds))
    return all(w in it for w in pal(es))


def candidatos():
    """Registros arg2 y pct_distinto, recalculados."""
    clas = json.loads((V02 / 'clasificacion.json').read_text(encoding='utf-8'))
    jp = M.Archivo(M.JP)
    arg2, pct, fuera = [], [], []
    for pk in ('eve', 'mch'):
        nds = M.nds_eventos(pk)
        det = clas[pk]['detalle']
        for eid in jp.ids(pk):
            data = jp.evento(pk, eid)
            try:
                _, ins, recs, dl = M.dialogos(data)
            except ValueError:
                continue
            refs = text_refs(data)
            extra = []
            for i, r in enumerate(recs):
                if ins.get(r.instruction) != M.OP_DIALOGO or r.argument == 1:
                    continue
                try:
                    t = r.body.decode('cp932')
                except UnicodeDecodeError:
                    continue
                if not JPRE.search(M.FURI.sub('', t)) or kana_only(M.FURI.sub('', t)):
                    continue
                if (M.OP_DIALOGO, 1) not in [(o, p) for _, o, p in refs.get(i, [])]:
                    continue
                extra.append(i)
            frases = [i for i in dl if M.es_frase_jp(recs[i].body)]
            if not extra and not frases:
                continue
            base = dict(paquete=pk, evento=eid)
            if eid in M.PROTEGIDOS:
                fuera += [dict(base, indice=i, motivo='protegido') for i in extra]
                continue
            if eid not in nds:
                fuera += [dict(base, indice=i, motivo='evento solo 3DS') for i in extra]
                continue
            m, ok, mal, tb = M.emparejar_evento(data, nds[eid])
            fiable = (mal <= ok or mal == 0) and det.get(str(eid), {}).get('clase') != 'distinto'
            for origen, lista in (('arg2', extra), ('pct', frases)):
                for i in lista:
                    r = recs[i]
                    jt = r.body.decode('cp932')
                    sn = m.get(r.instruction)
                    ent = tb.get(sn) if sn is not None else None
                    fila = dict(base, indice=i, id=r.instruction)
                    if ent is None or ent[0] != 1 or ent[2] == 0:
                        if origen == 'arg2':
                            fuera.append(dict(fila, motivo='sin par NDS', jp=jt))
                        continue
                    es = M.decode_nds(ent[1])
                    if es is None or not es.strip():
                        if origen == 'arg2':
                            fuera.append(dict(fila, motivo='texto NDS ilegible', jp=jt))
                        continue
                    igual = M.pct(jt) == M.pct(es)
                    if origen == 'pct' and igual:
                        continue
                    if origen == 'pct' and not (mal <= ok or mal == 0):
                        continue  # v02 no lo contó (evento no fiable)
                    if origen == 'arg2' and not fiable:
                        fuera.append(dict(fila, motivo='evento no fiable (v02 distinto)', jp=jt, es_nds=es))
                        continue
                    o = origen if (origen == 'pct' or igual) else 'arg2'
                    (pct if origen == 'pct' else arg2).append(dict(
                        fila, id_nds=sn, origen=o, jp=jt, es_nds=es, pct_distinto=not igual))
    return arg2, pct, fuera


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    cond = {}
    p = HERE / 'condensados.json'
    if p.exists():
        cond = json.loads(p.read_text(encoding='utf-8'))
    rec = json.loads((HERE / 'recortes.json').read_text(encoding='utf-8'))
    arg2, pct, fuera = candidatos()
    nc = json.loads((V02 / 'no_caben.json').read_text(encoding='utf-8'))
    filas = arg2 + [dict(paquete=f['paquete'], evento=f['evento'], indice=f['indice'], id=f['id'],
                         id_nds=f['id_nds'], origen='no_caben', jp=f['jp'], es_nds=f['es'],
                         pct_distinto=False) for f in nc] + pct
    textos, pendientes, especiales = [], [], {}
    cnt = Counter()
    for f in filas:
        clave = f"{f['paquete']}:{f['evento']}:{f['indice']}"
        propuestas = []
        ops = rec.get(clave, rec.get(f['es_nds']))
        tipo = None
        if f['origen'] == 'pct' or f['pct_distinto']:
            if clave in cond:
                propuestas.append(cond[clave])
            tipo = 'sin_fuente_nds'
        elif ops is not None:
            propuestas.append(recortar(f['es_nds'], ops))
            tipo = 'recorte'
        elif f['es_nds'] in cond:
            propuestas.append(cond[f['es_nds']])
            tipo = 'alargamiento_acortado'
        else:
            propuestas.append(f['es_nds'])
            tipo = 'literal'
        if tipo in ('recorte', 'literal') and not subsecuencia(propuestas[0], f['es_nds']):
            cnt['error_no_subsecuencia'] += 1
            pendientes.append(dict(clave=clave, motivo='no es subsecuencia del NDS', es=propuestas[0]))
            continue
        motivo = 'sin texto a mano'
        for es in propuestas:
            try:
                A.preparar(f['jp'], es)
            except ValueError as exc:
                motivo = str(exc)
                continue
            textos.append({k: f[k] for k in ('paquete', 'evento', 'indice', 'id', 'id_nds', 'origen', 'jp',
                                              'es_nds')} | {'es': es, 'tipo': tipo})
            if tipo != 'literal' or f['origen'] != 'arg2':
                especiales.setdefault(tipo, []).append(dict(clave=clave, es_nds=f['es_nds'], es=es))
            cnt[f['origen'] + ':ok'] += 1
            break
        else:
            cnt[f['origen'] + ':pendiente'] += 1
            pendientes.append(dict(clave=clave, origen=f['origen'], motivo=motivo, jp=f['jp'], es_nds=f['es_nds'],
                                   propuesta=propuestas[0] if propuestas else None))
    for x in fuera:
        cnt['arg2:fuera:' + x['motivo']] += 1
    (HERE / 'textos.json').write_text(json.dumps(textos, ensure_ascii=False, indent=1), encoding='utf-8')
    (HERE / 'informe.json').write_text(json.dumps(dict(
        cuentas=dict(cnt), arg2_candidatos=len(arg2) + len([x for x in fuera]),
        dejados_fuera=fuera, fallan=pendientes,
        sin_fuente_nds=especiales.get('sin_fuente_nds', []),
        alargamiento_acortado=especiales.get('alargamiento_acortado', []),
        por_tipo=dict(Counter(t['tipo'] for t in textos))), ensure_ascii=False, indent=1), encoding='utf-8')
    (HERE / 'pendientes.json').write_text(json.dumps(pendientes, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(dict(cnt), ensure_ascii=False, indent=1))
    print('textos', len(textos), 'pendientes', len(pendientes), 'fuera', len(fuera))


if __name__ == '__main__':
    main()
