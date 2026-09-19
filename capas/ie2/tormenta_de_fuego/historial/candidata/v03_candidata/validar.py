"""IE2 Fuego v03 · paso 3: validación offline de probe_ie2_v03 frente a probe_ie2_v02.

Comprueba:
1. Entradas del archive distintas = ficheros de las capas + eve/mch pk{h,b}; cada una igual a su capa.
2. Fuentes (font/*.bcfnt, inazuma2/**/*.NFTR) idénticas a v02; ina_main1.cro idéntica; ina_main2.cro = capa,
   mismo tamaño que el original japonés.
3. eve/mch: solo cambian los eventos preparados y, dentro, solo los registros declarados en eventos.json
   (misma tabla de instrucciones, mismos registros); ningún registro > 247 B; rótulos <= 20 B.
4. Sin crecer: ficheros de tamaño fijo con el mismo tamaño que en v02 (solo JinmyakuData/pkb pueden variar).
5. Bigramas: rótulos (FONT8, paso 10) y nombres (FONT8 paso 10, FONT12T paso 15) sin solapes; ningún código
   del registro v89 aparece en texto de IE2 que no sea un campo con bigramas (registros de eventos no
   declarados como rótulo/objetivo, ficheros de datos distintos de unitbase, ina_main2.cro).
Salida: validacion.json. Uso: python -X utf8 validar.py
"""
from __future__ import annotations

import collections
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[6]
sys.path.insert(0, str(ROOT / 'work/ie2/shared/capas/historial/nombres/v03_textos'))
sys.path.insert(0, str(HERE))
import comun_v03 as K  # noqa: E402
import importlib.util  # noqa: E402
_spec = importlib.util.spec_from_file_location('v03_build', HERE / 'build.py')
BLD = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(BLD)

M = K.M
VAR_TAM = {'inazuma2/data_iz/logic/JinmyakuData.dat', 'inazuma2/data_iz/logic/team.pkb',
           'inazuma2/data_iz/logic/team.pkh', 'inazuma2/data_iz/logic/fmt.pkb', 'inazuma2/data_iz/logic/fmt.pkh',
           'inazuma2/data_iz/script/help.pkb', 'inazuma2/data_iz/script/help.pkh',
           'inazuma2/data_iz/script/act.pkb', 'inazuma2/data_iz/script/act.pkh',
           'inazuma2/data_iz/script/mch.pkb', 'inazuma2/data_iz/script/mch.pkh',   # PackNum reempaquetado
           # lista de líneas de texto (65 líneas, como la NDS); RIESGO: búfer de carga del fichero sin medir
           'inazuma2/data_iz/logic/ShopName.dat'}
BIGRAMA_OK = {'inazuma2/data_iz/logic/unitbase.dat', 'inazuma2/data_iz/logic/unitbase.STR'}


def tokens_sjis(b: bytes):
    i = 0
    while i < len(b):
        c = b[i]
        if (0x81 <= c <= 0x9F or 0xE0 <= c <= 0xFC) and i + 1 < len(b):
            yield b[i:i + 2]
            i += 2
        else:
            i += 1


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    fallos = collections.defaultdict(list)
    v2 = M.Archivo(BLD.BASE_DIR / 'archive.fa')
    v3 = M.Archivo(BLD.SALIDA)
    jp = M.Archivo(M.JP)
    B = K.bigramas()
    codigos = {bytes.fromhex(e['sjis']) for e in B.reg}

    # 1-2-4 ficheros -------------------------------------------------------------------------------------
    capas = [BLD.CAPA_TABLAS] + ([BLD.EXTRA_MCH] if BLD.EXTRA_MCH.is_dir() else [])
    declarados = {}
    for c in capas:
        for p in c.rglob('*'):
            if p.is_file():
                declarados[p.relative_to(c).as_posix()] = p
    assert set(v2.por) == set(v3.por)
    distintos = sorted(k for k in v3.por if v2.por[k][1] != v3.por[k][1] or v2.get(k) != v3.get(k))
    esperado = set(declarados) | set(M.PK_EVE) | (set(M.PK_MCH) if BLD.EXTRA_MCH.is_dir() else set())
    for k in distintos:
        if k not in esperado:
            fallos['no_declarado'].append(k)
    for k, p in declarados.items():
        if v3.get(k) != p.read_bytes():
            fallos['capa_distinta'].append(k)
        if k not in VAR_TAM and len(v3.get(k)) != len(v2.get(k)):
            fallos['crece'].append((k, len(v2.get(k)), len(v3.get(k))))
    for k in v3.por:
        if k.startswith('font/') or k.upper().endswith('.NFTR'):
            if v2.get(k) != v3.get(k):
                fallos['fuente_cambiada'].append(k)
    cro1 = (BLD.SALIDA_DIR / 'romfs/cro/ina_main1.cro').read_bytes()
    if cro1 != (BLD.BASE_DIR / 'romfs/cro/ina_main1.cro').read_bytes():
        fallos['cro1'].append('ina_main1.cro distinta')
    cro2_jp = (ROOT / 'work/shared/base_3ds/romfs/cro/ina_main2.cro').read_bytes()
    cro2 = None
    if BLD.CRO2.is_file():
        cro2 = (BLD.SALIDA_DIR / 'romfs/cro/ina_main2.cro').read_bytes()
        if cro2 != BLD.CRO2.read_bytes() or len(cro2) != len(cro2_jp):
            fallos['cro2'].append('ina_main2.cro distinta de la capa o de otro tamaño')

    # 3 eventos -------------------------------------------------------------------------------------------
    ev = json.loads((HERE / 'eventos.json').read_text(encoding='utf-8'))
    decl = {(e['paquete'], e['evento']): set(e['registros']) for e in ev['detalle']}
    tipos = collections.defaultdict(dict)
    for pk in ('eve', 'mch'):
        for eid in v3.ids(pk):
            a, b = v2.evento(pk, eid), v3.evento(pk, eid)
            if a == b:
                if (pk, eid) in decl:
                    fallos['evento_sin_cambio'].append((pk, eid))
                continue
            if (pk, eid) not in decl:
                fallos['evento_no_declarado'].append((pk, eid))
                continue
            _, ia, ra = M.S.parse(a)
            _, ib, rb = M.S.parse(b)
            if ia != ib or len(ra) != len(rb):
                fallos['estructura'].append((pk, eid))
                continue
            cambiados = {i for i, (x, y) in enumerate(zip(ra, rb)) if x.raw != y.raw}
            if cambiados != decl[(pk, eid)]:
                fallos['registros'].append((pk, eid, sorted(cambiados ^ decl[(pk, eid)])))
            for i in cambiados:
                if len(rb[i].body) > M.MAX_BYTES:
                    fallos['registro_247'].append((pk, eid, i))
                op = ib.get(rb[i].instruction)
                if (op, rb[i].argument) == (0x4037, 3):
                    tipos[(pk, eid)][i] = 'rotulo'
                    if len(rb[i].body) > 20:
                        fallos['rotulo_20B'].append((eid, i))
                    cel = [c for c in B.codec.claves(rb[i].body.lstrip(K.ESPACIO)) if c]
                    if B._fallos(cel, [(K.F8, 10)]):
                        fallos['solape_rotulo'].append((eid, i))
                elif op in (0x402F, 0x2017, 0x2018, 0x201C, 0x2023):
                    tipos[(pk, eid)][i] = 'objetivo'
    # colisiones de códigos en texto de eventos no bigrama
    colisiones = collections.Counter()
    ejemplos = []
    for pk in ('eve', 'mch'):
        for eid in v3.ids(pk):
            d = v3.evento(pk, eid)
            try:
                _, ins, recs = M.S.parse(d)
            except ValueError:
                continue
            for i, r in enumerate(recs):
                if tipos.get((pk, eid), {}).get(i):
                    continue
                n = sum(1 for t in tokens_sjis(r.body) if t in codigos)
                if n:
                    colisiones[f'{pk}'] += n
                    if len(ejemplos) < 20:
                        ejemplos.append((pk, eid, i, r.body.decode('cp932', 'replace')[:40]))

    # 5 ficheros de datos y CRO
    for k in v3.por:
        if not k.startswith('inazuma2/') or k in BIGRAMA_OK or k in M.PK_EVE or k in M.PK_MCH:
            continue
        if not re.match(r'inazuma2/data_iz(_blizzard)?/(logic|script)/', k):
            continue
        n = sum(1 for t in tokens_sjis(v3.get(k)) if t in codigos)
        n0 = sum(1 for t in tokens_sjis(jp.get(k)) if t in codigos)
        if n != n0:
            colisiones[k] += n - n0
    if cro2 is not None:
        n = sum(1 for t in tokens_sjis(cro2) if t in codigos)
        n0 = sum(1 for t in tokens_sjis(cro2_jp) if t in codigos)
        if n != n0:
            colisiones['ina_main2.cro'] += n - n0
    # nombres: solapes y tamaño
    ub = v3.get('inazuma2/data_iz/logic/unitbase.dat')
    ub2 = v2.get('inazuma2/data_iz/logic/unitbase.dat')
    nombres = 0
    for r in range((len(ub) - 96) // 96):
        o = 96 + r * 96
        if ub[o:o + 96] == ub2[o:o + 96]:
            continue
        if ub[o + 32:o + 96] != ub2[o + 32:o + 96]:
            fallos['unitbase_fuera_de_nombres'].append(r)
        for campo in (0, 16):
            body = ub[o + campo:o + campo + 16]
            if b'\0' not in body:
                fallos['nombre_sin_nul'].append((r, campo))
                continue
            body = body.split(b'\0')[0]
            cel = B.codec.claves(body)
            if None in cel:
                continue
            nombres += 1
            if len(cel) > 7 or B._fallos(cel, [(K.F8, 10), (K.F12T, 15)]):
                fallos['nombre_solape_o_largo'].append((r, campo, B.texto(body)))
    res = dict(ok=not fallos, fallos={k: v[:50] for k, v in fallos.items()},
               n_fallos={k: len(v) for k, v in fallos.items()},
               archivos_distintos=distintos, eventos_cambiados=collections.Counter(p for p, _ in decl),
               registros=ev['registros'], nombres_revisados=nombres,
               colisiones_bigrama=dict(colisiones), colisiones_ejemplos=ejemplos,
               sha256_v02=BLD.sha(BLD.BASE_DIR / 'archive.fa'), sha256_v03=BLD.sha(BLD.SALIDA),
               sha256_ina_main2=BLD.sha(BLD.SALIDA_DIR / 'romfs/cro/ina_main2.cro') if cro2 is not None else None)
    (HERE / 'validacion.json').write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str),
                                          encoding='utf-8')
    print(json.dumps({k: v for k, v in res.items() if k not in ('colisiones_ejemplos',)}, ensure_ascii=False,
                     indent=1, default=str)[:4000])


if __name__ == '__main__':
    main()
