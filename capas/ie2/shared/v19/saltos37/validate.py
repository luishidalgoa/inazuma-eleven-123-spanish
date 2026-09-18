"""IE2 v19 · validación de probe_ie2_v18 con el modelo del motor (37 × 3, dibujo 448 px, página 131 B).

Sobre TODOS los registros de diálogo de eve y mch del archive de la candidata:
- ninguna página pasa de 131 B, ninguna página pasa de 3 líneas, ninguna línea de 37 caracteres y el
  dibujo (0x1C0) no parte ninguna línea -> el motor no inserta ni un salto propio;
- ningún registro pasa de 247 B;
- palabra por palabra idéntico a la base v17: nada se ha acortado ni cambiado, solo los saltos;
- los `%s`/`%d` de cada registro se conservan y no hay caracteres sin glifo en FONT12;
- lo que no es diálogo (rótulos 0x4037, objetivos 0x402F, bytecode, resto de registros) es idéntico;
- el resto del archive (CRO, sonidos, vídeos) es idéntico al de v17.
Uso: python -X utf8 work/ie2/shared/capas/v19/saltos37/validate.py  -> validacion.json
"""
from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import comun19 as C  # noqa: E402

M = C.M
W = C.ROOT / 'work'
BASE = W / 'shared/candidatas/probe_ie2_v17/archive.fa'
CAND = W / 'shared/candidatas/probe_ie2_v18'
SALIDA = {'eve': HERE / 'ie2/eve', 'mch': HERE / 'ie2/mch'}


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    res, fallos = {}, []

    def ok(nombre, cond, detalle=None):
        res[nombre] = dict(ok=bool(cond), detalle=detalle)
        if not cond:
            fallos.append(nombre)

    v17 = M.Archivo(BASE)
    v18 = M.Archivo(CAND / 'archive.fa')
    cont = Counter()
    malos, acortados, mayores, raros = [], [], [], []
    for pk in ('eve', 'mch'):
        ids = v17.ids(pk)
        ok(f'{pk}_mismos_ids', ids == v18.ids(pk))
        capa = {int(p.stem) for p in SALIDA[pk].glob('*.ssd')}
        for eid in ids:
            a, b = v17.evento(pk, eid), v18.evento(pk, eid)
            if eid in capa:
                if b != (SALIDA[pk] / f'{eid}.ssd').read_bytes():
                    raros.append((pk, eid, 'distinto de la capa'))
            elif a != b:
                raros.append((pk, eid, 'cambiado sin estar en la capa'))
            end, ins, ra, dl = M.dialogos(a)
            _, ins2, rb = M.S.parse(b)
            if ins2 != ins or len(ra) != len(rb) or b[32:end] != a[32:end]:
                raros.append((pk, eid, 'bytecode'))
                continue
            for j, (r1, r2) in enumerate(zip(ra, rb)):
                if j not in dl and r1.raw != r2.raw:
                    raros.append((pk, eid, j, 'registro que no es diálogo'))
            for i in dl:
                x, y = ra[i].body, rb[i].body
                cont['registros'] += 1
                pg = C.paginas(y)
                cont['paginas_antes'] += len(C.paginas(x))
                cont['paginas_despues'] += len(pg)
                p = C.problemas(y)
                if p:
                    malos.append((pk, eid, i, p))
                if len(y) > C.MAX_BYTES:
                    mayores.append((pk, eid, i, len(y)))
                if x == y:
                    continue
                cont['cambiados'] += 1
                cont['paginas_cambiadas'] += len(pg)
                # palabra por palabra: nada acortado, nada reescrito
                if C.palabras(C.espanol(x)) != C.palabras(C.espanol(y)):
                    acortados.append((pk, eid, i, C.espanol(x), C.espanol(y)))
                    continue
                if M.pct(y.decode('cp932')) != M.pct(x.decode('cp932')):
                    raros.append((pk, eid, i, '%s/%d'))
                if M.sin_glifo(y):
                    raros.append((pk, eid, i, 'sin glifo ' + ''.join(M.sin_glifo(y))))
                if C.reajusta(y):
                    raros.append((pk, eid, i, 'el motor reajusta'))
    ok('paginas_131_lineas_3_y_37_caracteres', not malos, malos[:20])
    ok('registros_247', not mayores, mayores[:20])
    ok('texto_identico_palabra_a_palabra', not acortados, acortados[:10])
    ok('cambios_limpios', not raros, raros[:20])
    res['cuentas'] = dict(cont)

    # todo lo que no es eve/mch, idéntico a v17
    sal = {'inazuma2/data_iz/script/eve.pkh', 'inazuma2/data_iz/script/eve.pkb',
           'inazuma2/data_iz/script/mch.pkh', 'inazuma2/data_iz/script/mch.pkb'}
    n1 = {p for p, _, _ in v17.arc.entries}
    ok('mismas_rutas', n1 == {p for p, _, _ in v18.arc.entries})
    distintos = [p for p in sorted(n1 - sal) if v17.get(p) != v18.get(p)]
    ok('resto_del_archive_igual_a_v17', not distintos, distintos[:20])

    for n in ('ina_main1.cro', 'ina_main2.cro'):
        ok(f'cro_{n}', (CAND / 'romfs/cro' / n).read_bytes()
           == (W / 'shared/candidatas/probe_ie2_v17/romfs/cro' / n).read_bytes())
    cro2 = (CAND / 'romfs/cro/ina_main2.cro').read_bytes()
    ok('cro_parches_v15', [cro2[a:a + 4].hex() for a in (0x66a24, 0x4cabc, 0x4d6a0)]
       == ['1a1ea0e3', '1a2ea0e3', '072da0e3'])

    inf = json.loads((W / 'ie2/shared/capas/v11/subtitulos/informe.json').read_text(encoding='utf-8'))
    vid = {v['nombre']: v['sha256'] for v in inf['videos']}
    ok('videos_35', len(vid) == 35, len(vid))
    mal = [n for n, h in vid.items()
           if hashlib.sha256(v18.get(f'inazuma2/data_iz/movie/{n}.moflex')).hexdigest() != h]
    ok('videos_sha256', not mal, mal)

    res['sha256_archive'] = hashlib.sha256((CAND / 'archive.fa').read_bytes()).hexdigest()
    out = dict(ok=not fallos, fallos=fallos, comprobaciones=res)
    (HERE / 'validacion.json').write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str),
                                          encoding='utf-8')
    print('OK' if not fallos else f'FALLOS: {fallos}', json.dumps(res['cuentas']), res['sha256_archive'])
    return 0 if not fallos else 1


if __name__ == '__main__':
    sys.exit(main())
