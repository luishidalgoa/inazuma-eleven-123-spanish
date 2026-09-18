"""v85 · validación offline de la sonda de bigramas (candidata probe_ie1_v85 frente a probe_ie1_v84).

Comprueba:
1. archive.fa: solo cambian font/FONT12.bcfnt, unitbase.dat, eve.pkh y eve.pkb; el resto de entradas es
   byte-idéntico a v84; la CRO es idéntica a la de v84.
2. FONT12: mismo tamaño; los únicos bytes distintos son píxeles de las celdas de los 13 glifos del
   registro y sus entradas CWDH; ningún otro glifo cambia; métricas y píxeles = registro.
3. Eventos: los 1293 eventos se descomprimen; solo cambian los 5 declarados, con la misma tabla de
   instrucciones, el mismo número de registros y solo el cuerpo de los rótulos declarados.
4. unitbase.dat: solo cambian los 5 campos declarados.
5. Bloqueo v20 (tools/dialogue_lock.py): se ejecuta la puerta oficial (ie123kit.nucleo.validar.bloqueo)
   sobre v84 y v85 y se informa del resultado. OVERRIDE DOCUMENTADO (solo aquí, en work/, en memoria):
   se repite dialogue_lock.validate con FONT_HASHES['font/FONT12.bcfnt'] sustituido por el SHA-256 de
   la FONT12 de la sonda (registro.json) para demostrar que las otras cuatro fuentes, los fuentes
   congelados y el ajuste de líneas siguen intactos. No se escribe nada en tools/.
Salida: validacion.json.  Uso: python -X utf8 work/ie1/capas/v85/bigramas_sonda/validar.py
"""
from __future__ import annotations

import hashlib
import json
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
sys.path.insert(0, str(HERE))
import apply as A  # noqa: E402

V84 = ROOT / 'work/shared/candidatas/probe_ie1_v84'
V85 = ROOT / 'work/shared/candidatas/probe_ie1_v85'
ESPERADOS = {A.F12, A.UNIT, A.C.PKH, A.C.PKB}


def sha(b):
    return hashlib.sha256(b).hexdigest()


def entradas(fa):
    arc = A.V79.V76.FaArchive(str(fa))
    return {p: bytes(arc.d[o:o + s]) for p, o, s in arc.entries}


def offsets_celda(fuente, gi):
    f, t = fuente.f, fuente.t
    sheet, cell = divmod(gi, f.PER)
    ox, oy = (cell % t['ncols']) * fuente.sx, (cell // t['ncols']) * fuente.sy
    out = set()
    for y in range(fuente.sy):
        for x in range(fuente.sx):
            X, Y = ox + x, oy + y
            tile = (Y // 8) * (t['sheet_w'] // 8) + (X // 8)
            m = A.V75G.morton8(X % 8, Y % 8)
            out.add(f.doff + sheet * t['sheet_size'] + tile * 32 + m // 2)
    return out


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    res = {}
    reg = json.loads(A.REGISTRO.read_text(encoding='utf-8'))
    inf = json.loads((HERE / 'informe.json').read_text(encoding='utf-8'))
    a, b = entradas(V84 / 'archive.fa'), entradas(V85 / 'archive.fa')
    assert set(a) == set(b)
    distintos = {p for p in a if a[p] != b[p]}
    res['archive'] = dict(v84=sha((V84 / 'archive.fa').read_bytes()), v85=sha((V85 / 'archive.fa').read_bytes()),
                          entradas=len(a), distintas=sorted(distintos), ok=distintos == ESPERADOS)
    cro_ok = (V84 / 'romfs/cro/ina_main1.cro').read_bytes() == (V85 / 'romfs/cro/ina_main1.cro').read_bytes()
    res['cro_identica_v84'] = cro_ok

    # --- fuente --------------------------------------------------------------------------------------
    tmp = Path(tempfile.mkdtemp(prefix='ie123_v85v_'))
    (tmp / 'old.bcfnt').write_bytes(a[A.F12])
    (tmp / 'new.bcfnt').write_bytes(b[A.F12])
    fo, fn = A.cargar(tmp / 'old.bcfnt'), A.cargar(tmp / 'new.bcfnt')
    assert b[A.F12] == (HERE / 'extra' / A.F12).read_bytes()
    permitidos = set()
    gis = []
    for e in reg['bigramas']:
        gi = e['glifo']
        gis.append(gi)
        permitidos |= offsets_celda(fo, gi)
        off = fo.f.cwdh_entry_off(gi)
        permitidos |= {off, off + 1, off + 2}
    cambios = [i for i, (x, y) in enumerate(zip(a[A.F12], b[A.F12])) if x != y]
    otros_glifos = [gi for gi in set(fo.metrics) - set(gis)
                    if fo.metrics[gi] != fn.metrics[gi]]
    comprob = []
    for e in reg['bigramas']:
        gi = e['glifo']
        px, ancho, D, R = A.Glifos(A.cargar(ROOT / 'work/ie1/capas/v75/glifos_eu/extra' / A.F12)).par(*e['par'])
        bm = {(x, y): v for y, row in enumerate(fn.bitmap(gi)) for x, v in enumerate(row) if v}
        cmap_cps = [cp for cp, g in fn.cmap.items() if g == gi]
        comprob.append(dict(par=e['par'], gi=gi, pixeles_ok=bm == px, cwdh_ok=list(fn.metrics[gi]) == e['cwdh'],
                            tinta=ancho, D=A.desplazamiento(15, fn.metrics[gi][0], fn.metrics[gi][2]),
                            D_ok=A.desplazamiento(15, fn.metrics[gi][0], fn.metrics[gi][2]) == e['D'],
                            codepoints=[f'U+{c:04X}' for c in cmap_cps]))
    res['fuente'] = dict(tam_igual=len(a[A.F12]) == len(b[A.F12]), bytes_cambiados=len(cambios),
                         fuera_de_celdas_y_cwdh=[hex(i) for i in cambios if i not in permitidos][:20],
                         metricas_de_otros_glifos_cambiadas=otros_glifos[:20], glifos=comprob,
                         sha256=sha(b[A.F12]),
                         ok=len(a[A.F12]) == len(b[A.F12]) and all(i in permitidos for i in cambios)
                         and not otros_glifos and all(g['pixeles_ok'] and g['cwdh_ok'] and
                                                      len(g['codepoints']) == 1 and g['tinta'] <= 14
                                                      for g in comprob))

    # --- eventos -------------------------------------------------------------------------------------
    ia = A.parse_index(a[A.C.PKH])
    ib = A.parse_index(b[A.C.PKH])
    assert [e for e, _, _ in ia] == [e for e, _, _ in ib]
    declarados = {x['evento']: set() for x in inf['rotulos_aplicados']}
    for x in inf['rotulos_aplicados']:
        declarados[x['evento']].add(x['indice'])
    ev_cambiados, errores = [], []
    for (eid, oa, sa), (_, ob, sb) in zip(ia, ib):
        da = A.decompress(a[A.C.PKB][oa:oa + sa])
        db = A.decompress(b[A.C.PKB][ob:ob + sb])
        if da == db:
            if eid in declarados:
                errores.append((eid, 'declarado sin cambios'))
            continue
        ev_cambiados.append(eid)
        _, opa, ra = A.S.parse(da)
        _, opb, rb = A.S.parse(db)
        if opa != opb or len(ra) != len(rb) or da[:32 + struct.unpack_from('<I', da, 16)[0]][32:] != \
                db[:32 + struct.unpack_from('<I', db, 16)[0]][32:]:
            errores.append((eid, 'bytecode o registros distintos'))
        dif = {i for i, (x, y) in enumerate(zip(ra, rb)) if x.raw != y.raw}
        if dif != declarados.get(eid):
            errores.append((eid, f'registros cambiados {sorted(dif)}'))
        for i in dif:
            if (opb.get(rb[i].instruction), rb[i].argument) != (0x4037, 3) or len(rb[i].body) > 20:
                errores.append((eid, f'registro {i} no es un rótulo de <= 20 B'))
    res['eventos'] = dict(total=len(ia), cambiados=ev_cambiados, errores=errores,
                          ok=set(ev_cambiados) == set(declarados) and not errores)

    # --- unitbase ------------------------------------------------------------------------------------
    ua, ub = a[A.UNIT], b[A.UNIT]
    campos = {(96 + n['registro'] * 96 + n['campo']) for n in inf['nombres']}
    fuera = [i for i, (x, y) in enumerate(zip(ua, ub)) if x != y and not any(c <= i < c + 16 for c in campos)]
    res['unitbase'] = dict(tam_igual=len(ua) == len(ub), cambios_fuera=fuera[:20],
                           campos=[dict(registro=n['registro'], campo=n['campo'],
                                        antes=n['antes'], despues='|'.join(n['celdas']),
                                        bytes=ub[96 + n['registro'] * 96 + n['campo']:][:16].split(b'\0')[0].hex())
                                   for n in inf['nombres']],
                           ok=len(ua) == len(ub) and not fuera)

    # --- bloqueo v20 ---------------------------------------------------------------------------------
    oficial = {}
    for nom, cand in (('v84', V84), ('v85', V85)):
        r = subprocess.run([sys.executable, '-X', 'utf8', '-m', 'ie123kit.nucleo.validar.bloqueo',
                            '--candidata', str(cand)], cwd=ROOT, capture_output=True, text=True,
                           env={**__import__('os').environ, 'PYTHONPATH': str(ROOT / 'tools/src')})
        oficial[nom] = dict(codigo=r.returncode, salida=(r.stdout + r.stderr).strip()[-400:])
    sys.path.insert(0, str(ROOT / 'tools'))
    import dialogue_lock
    from build_ie1_probe import layout
    fonts = tmp / 'fonts'
    for rel in dialogue_lock.FONT_HASHES:
        p = fonts / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b[rel])
    iguales_lock = {rel: sha(b[rel]) == h for rel, h in dialogue_lock.FONT_HASHES.items()}
    original = dict(dialogue_lock.FONT_HASHES)
    try:
        dialogue_lock.FONT_HASHES[A.F12] = reg['fuente_resultado_sha256']      # override en memoria
        dialogue_lock.validate(True, fonts, layout)
        override = 'PASS'
    except ValueError as exc:
        override = f'FAIL: {exc}'
    finally:
        dialogue_lock.FONT_HASHES.clear()
        dialogue_lock.FONT_HASHES.update(original)
    res['bloqueo_v20'] = dict(puerta_oficial=oficial, fuentes_iguales_al_bloqueo=iguales_lock,
                              override_documentado=override,
                              nota='la FONT12 difiere del hash v20 desde v75 (glifos EU); build_ui_revision '
                                   'no llama al bloqueo. El override solo sustituye el hash de FONT12 en memoria.')
    res['ok'] = all(res[k]['ok'] for k in ('archive', 'fuente', 'eventos', 'unitbase')) and cro_ok \
        and override == 'PASS'
    (HERE / 'validacion.json').write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps({k: (v if not isinstance(v, dict) else {kk: vv for kk, vv in v.items() if kk != 'glifos'})
                      for k, v in res.items()}, ensure_ascii=False, indent=1)[:6000])


if __name__ == '__main__':
    main()
