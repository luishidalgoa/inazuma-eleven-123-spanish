"""Validación offline de probe_ie2_v10 (build.py). No instala nada. Escribe validacion.json.

Comprueba: entradas cambiadas frente a v05 = solo las declaradas; ficheros de capa idénticos; eventos
(tabla de instrucciones, número/identidad de registros, protegidos, crecimiento, registros <= 247 B,
fusión v91/v92 + v08 registro a registro); CRO y fuentes; glifos de subtítulos v07 dentro de la FONT12
de v08; SAD LayeredFS (IE1 = mod instalado, IE2 = v07) y su descodificación; fotogramas de los vídeos.
Uso: python -X utf8 validar.py
"""
from __future__ import annotations

import collections
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build as B  # noqa: E402

W = B.W
sys.path.insert(0, str(B.V08))
import comun08 as K  # noqa: E402

C, S, FaArchive = B.C, B.S, B.FaArchive
CAND = B.SALIDA_DIR
VGM = W / 'shared/herramientas/media_tools/vgmstream-nightly-win64/vgmstream-cli.exe'
MOD_IE1 = Path(os.environ['APPDATA']) / 'Azahar/load/mods/00040000000BB800/romfs/inazuma1'
FONTS = ('font/FONT12.bcfnt', 'font/FONT8.bcfnt', 'font/FONT12T.bcfnt')


def sha(b):
    return hashlib.sha256(b).hexdigest()


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    errores, avisos, res = [], [], {}

    def err(m):
        errores.append(m)
        if len(errores) < 40:
            print('ERROR', m)

    base = FaArchive(str(B.BASE))
    cand = FaArchive(str(CAND / 'archive.fa'))
    pb = {p: (o, s) for p, o, s in base.entries}
    pc = {p: (o, s) for p, o, s in cand.entries}

    def gb(p):
        o, s = pb[p]
        return bytes(base.d[o:o + s])

    def gc(p):
        o, s = pc[p]
        return bytes(cand.d[o:o + s])

    # ------------------------------------------------------------ entradas y capas
    if set(pb) != set(pc) or [p for p, _, _ in base.entries] != [p for p, _, _ in cand.entries]:
        err('lista de entradas distinta de v05')
    ganador = {}
    for capa in B.CAPAS:
        for f in sorted(capa.rglob('*')):
            if f.is_file():
                ganador[f.relative_to(capa).as_posix()] = f
    pks = {r for rs in B.PK.values() for r in rs}
    declaradas = set(ganador) | pks
    cambiadas = {p for p in pc if gc(p) != gb(p)}
    fuera = sorted(cambiadas - declaradas)
    if fuera:
        err(f'entradas cambiadas no declaradas: {fuera[:10]}')
    for rel, f in ganador.items():
        if gc(rel) != f.read_bytes():
            err(f'{rel}: distinto de su capa {f}')
    res['entradas'] = dict(total=len(pc), cambiadas=len(cambiadas), declaradas=len(declaradas),
                           ficheros_de_capa=len(ganador), capa_iguales_a_v05=len(set(ganador) - cambiadas),
                           paquetes_cambiados=sorted(pks & cambiadas))
    if 'inazuma2/data_iz/script/mch.pkb' in cambiadas:
        err('mch de IE2 cambiado (no hay capa)')

    # ------------------------------------------------------------ eventos
    cambios08 = json.loads((B.V08 / 'cambios_registros.json').read_text(encoding='utf-8'))['registros']
    reg08 = collections.defaultdict(dict)
    for r in cambios08:
        reg08[(r['juego'], r['evento'])][r['indice']] = r
    capa_fich = {}
    for capa, sub, pk in ((B.V91, 'events', 'eve'), (B.V92, 'events', 'eve'), (B.V92, 'events_mch', 'mch')):
        for f in sorted((capa / sub).glob('*.ssd')) if (capa / sub).is_dir() else []:
            capa_fich[('ie1', pk, int(f.stem))] = f
    jp_arc = FaArchive(str(B.BASE_JP))
    ev_res = {}
    for (juego, pk), rutas in B.PK.items():
        gbase = B.eventos_base(base, rutas)
        gcand = B.eventos_base(cand, rutas)
        gjp = B.eventos_base(jp_arc, rutas)
        idx_b = [e for e, _, _ in B.parse_index(gb(rutas[0]))]
        idx_c = [e for e, _, _ in B.parse_index(gc(rutas[0]))]
        if idx_b != idx_c:
            err(f'{juego}/{pk}: índice con otros ids u orden')
        st = collections.Counter()
        for eid in idx_b:
            a, n = gbase(eid), gcand(eid)
            clave = (juego, pk, eid)
            v08 = reg08.get((juego, eid)) if pk == 'eve' else None
            if clave not in capa_fich and not v08:
                if a != n:
                    err(f'{juego}/{pk} {eid}: cambiado sin capa')
                continue
            st['declarados'] += 1
            if eid in B.PROT[juego] and a != n:
                err(f'{juego}/{pk} {eid}: protegido cambiado')
            try:
                _, ops_a, ra = S.parse(a)
                end_n, ops_n, rn = S.parse(n)
            except ValueError as e:
                err(f'{juego}/{pk} {eid}: {e}')
                continue
            if ops_a != ops_n or a[32:S.parse(a)[0]] != n[32:end_n]:
                err(f'{juego}/{pk} {eid}: tabla de instrucciones cambiada')
            if len(ra) != len(rn) or any((x.instruction, x.argument) != (y.instruction, y.argument)
                                         for x, y in zip(ra, rn)):
                err(f'{juego}/{pk} {eid}: registros con otro número o identidad')
                continue
            if any(len(y.raw) > 252 for y in rn):
                err(f'{juego}/{pk} {eid}: registro de más de 247 B')
            # fusión: capa de fichero (v92 > v91) en todos los registros salvo los de v08
            ref = S.parse(capa_fich[clave].read_bytes())[2] if clave in capa_fich else ra
            for i, (x, y) in enumerate(zip(ref, rn)):
                if v08 and i in v08:
                    if y.body.hex() != v08[i]['cuerpo']:
                        err(f'{juego}/{pk} {eid} #{i}: rótulo v08 no aplicado')
                    elif ra[i].body.hex() != v08[i]['cuerpo_antes']:
                        err(f'{juego}/{pk} {eid} #{i}: v05 no es el cuerpo_antes de v08')
                    st['registros_v08'] += 1
                elif x.raw != y.raw:
                    err(f'{juego}/{pk} {eid} #{i}: registro distinto de su capa')
            if clave in capa_fich and v08:
                st['fusionados_registro_a_registro'] += 1
                if capa_fich[clave].read_bytes() == n:
                    err(f'{juego}/{pk} {eid}: la fusión no aplicó v08')
                # los registros de diálogo de v92 siguen ahí
                st['registros_capa_conservados'] += sum(1 for i, (x, y) in enumerate(zip(ref, rn))
                                                        if i not in v08 and x.raw != ra[i].raw)
            elif clave in capa_fich and capa_fich[clave].read_bytes() != n:
                err(f'{juego}/{pk} {eid}: distinto del fichero de su capa')
            elif v08 and not clave in capa_fich:
                f08 = B.V08 / juego / 'events' / f'{eid}.ssd'
                if f08.read_bytes() != n:
                    err(f'{juego}/{pk} {eid}: distinto del fichero de v08')
            fijo = B.NF.search(a) or (eid >= B.SISTEMA and len(a) == len(gjp(eid)))
            if len(n) > len(a):
                st['crecen'] += 1
                if fijo:
                    err(f'{juego}/{pk} {eid}: evento fijo que crece')
            elif len(n) < len(a):
                st['menguan'] += 1
            if eid >= B.SISTEMA:
                st['sistema_declarados'] += 1
                st['sistema_fijos'] += bool(fijo)
                st['sistema_fijos_mismo_tamano'] += bool(fijo) and len(n) == len(a)
            st['registros_cambiados'] += sum(1 for x, y in zip(ra, rn) if x.raw != y.raw)
        ev_res[f'{juego}/{pk}'] = dict(eventos=len(idx_b), **st)
    solape92 = sorted(e for (j, e) in reg08 if ('ie1', 'eve', e) in capa_fich
                      and capa_fich[('ie1', 'eve', e)].parent.parent.parent.name == 'v92')
    solape91 = sorted(e for (j, e) in reg08 if j == 'ie1'
                      and (B.V91 / 'events' / f'{e}.ssd').exists())
    ev_res['solape_v08_v92'] = len(solape92)
    ev_res['solape_v08_v91'] = solape91
    ev_res['solape_v08_v91_dentro_de_v92'] = all(e in solape92 for e in solape91)
    res['eventos'] = ev_res

    # ------------------------------------------------------------ CRO y fuentes
    for nombre, capa in (('ina_main1.cro', B.CRO1), ('ina_main2.cro', B.CRO2)):
        if (CAND / 'romfs/cro' / nombre).read_bytes() != capa.read_bytes():
            err(f'{nombre} distinta de {capa}')
    crodir = sorted(p.name for p in (CAND / 'romfs/cro').iterdir())
    if crodir != ['ina_main1.cro', 'ina_main2.cro']:
        err(f'CRO inesperadas: {crodir}')
    for f in FONTS:
        if gc(f) != (B.V08 / 'extra' / f).read_bytes():
            err(f'{f} distinta de v08')
    reg08f = json.loads((B.V08 / 'registro.json').read_text(encoding='utf-8'))
    if reg08f['fuentes_dibujadas'] != {f: sha(gc(f)) for f in FONTS}:
        err('fuentes distintas de registro.json de v08')
    # glifos de subtítulos v07 en la FONT12 de v08, glifo a glifo
    reg07 = json.loads(K.REG07.read_text(encoding='utf-8'))
    tmp = Path(tempfile.mkdtemp(prefix='ie2_v10_val_'))
    (tmp / 'v07.bcfnt').write_bytes((B.MEDIA / 'extra' / K.F12).read_bytes())
    (tmp / 'v10.bcfnt').write_bytes(gc(K.F12))
    F7, F10 = K.A88.cargar(tmp / 'v07.bcfnt'), K.A88.cargar(tmp / 'v10.bcfnt')
    en08 = {e['sjis']: e for e in reg08f['bigramas']}
    sub = distintos = 0
    for e in reg07['bigramas']:
        info = e['fuentes'].get(K.F12)
        if not info or 'subtitulos_ie2' not in e.get('campos', []):
            continue
        sub += 1
        gi = info['glifo']
        if F7.bitmap(gi) != F10.bitmap(gi) or list(F7.metrics[gi]) != list(F10.metrics[gi]):
            distintos += 1
            err(f"FONT12: glifo de subtítulo {e['sjis']} ({e['par']!r}) cambiado en v08")
        if en08.get(e['sjis'], {}).get('par') != e['par']:
            err(f"registro v08: {e['sjis']} ya no es {e['par']!r}")
    todos_dist = sum(1 for gi in range(len(F7.metrics))
                     if F7.metrics[gi] != F10.metrics[gi] or F7.bitmap(gi) != F10.bitmap(gi))
    import shutil
    shutil.rmtree(tmp, ignore_errors=True)
    res['fuentes'] = dict(v08_iguales=True, glifos_subtitulo_v07=sub, glifos_subtitulo_cambiados=distintos,
                          glifos_font12_distintos_v07_v08=todos_dist)

    # ------------------------------------------------------------ LayeredFS
    romfs = CAND / 'romfs'
    fich = sorted(p for p in romfs.rglob('*') if p.is_file() and p.parent.name != 'cro')
    sad = collections.Counter(p.relative_to(romfs).parts[0] for p in fich if p.suffix.upper() == '.SAD')
    otros = collections.Counter(p.suffix.upper() for p in fich if p.suffix.upper() != '.SAD')
    # IE2: cada SAD = su capa v07
    for p in (romfs / 'inazuma2').rglob('*'):
        if p.is_file():
            rel = p.relative_to(romfs)
            src = [r / rel for r in (B.MEDIA / 'romfs_mod', B.MEDIA_F / 'romfs_mod') if (r / rel).exists()]
            if len(src) != 1 or src[0].read_bytes() != p.read_bytes():
                err(f'{rel}: no coincide con una única capa v07')
    # IE1: igual que el mod instalado (70 SAD + bancos v57)
    ie1 = {p.relative_to(romfs / 'inazuma1').as_posix(): p for p in (romfs / 'inazuma1').rglob('*') if p.is_file()}
    inst = {p.relative_to(MOD_IE1).as_posix(): p for p in MOD_IE1.rglob('*') if p.is_file()} if MOD_IE1.is_dir() else {}
    if set(ie1) != set(inst):
        err(f'IE1 LayeredFS distinto del mod instalado: {sorted(set(ie1) ^ set(inst))[:10]}')
    else:
        for k, p in ie1.items():
            if p.read_bytes() != inst[k].read_bytes():
                err(f'IE1 {k}: distinto del instalado')
    jp_sad = {p.name for p in (W / 'shared/base_3ds/romfs/inazuma2/data_iz/sound').glob('*.SAD')}
    fd, wav = tempfile.mkstemp(suffix='.wav')
    os.close(fd)
    decod = 0
    try:
        for p in fich:
            if p.suffix.upper() != '.SAD':
                continue
            if p.relative_to(romfs).parts[0] == 'inazuma2' and p.name not in jp_sad:
                err(f'{p.name}: no es un SAD de la RomFS IE2')
            r = subprocess.run([str(VGM), '-o', wav, str(p)], capture_output=True, text=True)
            if r.returncode != 0 or os.path.getsize(wav) <= 44:
                err(f'{p.name}: vgmstream no lo descodifica')
            else:
                decod += 1
    finally:
        os.unlink(wav)
    if sad != {'inazuma1': 70, 'inazuma2': 477}:
        err(f'recuento de SAD: {dict(sad)}')
    res['layeredfs'] = dict(sad=dict(sad), sad_descodificados=decod, otros=dict(otros),
                            ie1_igual_al_mod_instalado=set(ie1) == set(inst), ficheros=len(fich) + len(crodir))

    # ------------------------------------------------------------ vídeos
    videos = {v['nombre']: v for v in json.loads((B.MEDIA / 'videos.json').read_text(encoding='utf-8'))['videos']}
    movies = [p for p, _, _ in cand.entries if p.endswith('.moflex')]
    tmpv = Path(tempfile.mkdtemp(prefix='ie2_v10_mov_'))
    fotos, capa_v = {}, 0
    try:
        for p in movies:
            f = tmpv / 'v.moflex'
            f.write_bytes(gc(p))
            try:
                r = subprocess.run(['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0',
                                    '-show_entries', 'stream=nb_read_frames,r_frame_rate,width,height',
                                    '-of', 'json', str(f)], capture_output=True, text=True, check=True)
                s0 = json.loads(r.stdout)['streams'][0]
                n = int(s0['nb_read_frames'])
            except (subprocess.CalledProcessError, KeyError, IndexError, ValueError) as e:
                err(f'{p}: no se descodifica ({e})')
                continue
            fotos[p] = n
            if n <= 0:
                err(f'{p}: 0 fotogramas')
            nombre = p.rsplit('/', 1)[-1][:-7]
            if p in ganador:
                capa_v += 1
                v = videos.get(nombre)
                if not v or n != v['fotogramas'] or sha(gc(p)) != v['sha256']:
                    err(f'{p}: {n} fotogramas / sha frente a videos.json')
    finally:
        shutil.rmtree(tmpv, ignore_errors=True)
    res['videos'] = dict(total=len(movies), descodificados=len(fotos), de_capa_v07=capa_v,
                         por_juego=dict(collections.Counter(p.split('/')[0] for p in fotos)),
                         fotogramas=fotos)
    dats = [r for r in ganador if r.startswith('inazuma2/data_iz/movie/txt/')]
    res['subtitulos_dat'] = len(dats)
    if capa_v != 35 or len(dats) != 35:
        err(f'vídeos/subtítulos de capa: {capa_v}/{len(dats)} (se esperaban 35/35)')

    salida = dict(ok=not errores, errores=errores, avisos=avisos,
                  archive_sha256=sha((CAND / 'archive.fa').read_bytes()),
                  cro_sha256={p.name: sha(p.read_bytes()) for p in (CAND / 'romfs/cro').iterdir()},
                  resultados=res, runtime_verified=False)
    (HERE / 'validacion.json').write_text(json.dumps(salida, ensure_ascii=False, indent=1), encoding='utf-8')
    r2 = {k: v for k, v in res.items() if k != 'videos'}
    print(json.dumps(r2, ensure_ascii=False, indent=1))
    print('videos', {k: v for k, v in res['videos'].items() if k != 'fotogramas'})
    print('OK' if not errores else f'{len(errores)} errores')
    return 0 if not errores else 1


if __name__ == '__main__':
    sys.exit(main())
