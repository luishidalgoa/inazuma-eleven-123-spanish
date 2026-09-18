"""IE2 v07 · media: validación offline de la capa (issue #74). No construye ni instala.

Voces
- Cada SAD instalado (común + Fuego) es idéntico byte a byte al de la NDS ES, su nombre existe en la RomFS
  3DS y vgmstream lo descodifica completo (a un WAV temporal que se borra).
- Aviso si la duración ES y JP de un mismo SAD difiere > 0,25 s (afecta a la sincronía de su escena).
Subtítulos
- Cada .dat instalado se relee y se reescribe igual (ida y vuelta), termina en 0xFFFFFFFF, tamaños múltiplos de 4.
- Tiempos: los trozos de cada registro NDS son contiguos y cubren exactamente su [inicio, fin); en las pistas
  cuyo NDS coincide con el japonés los tiempos resultantes caen dentro de los japoneses; ningún fin pasa del
  final del vídeo (tiempos.json) en más de 2 ticks.
- Texto: solo caracteres de 2 B (el analizador 0x3cc44 descarta los bytes sueltos y usa [ / ] como rubí),
  sin salto de línea, <= 21 casillas, todos los códigos con glifo en la FONT12.bcfnt actual, hueco de tinta
  >= 1 px a paso 13,75 y el texto decodificado es el oficial NDS normalizado.
Vídeos (videos.py)
- Los únicos .moflex de extra/ son los de videos.json (op00 solo en Fuego, el resto en la común), sin marcados;
  cada uno coincide con su sha256, ffprobe cuenta sus fotogramas (= 3DS; a2m14 = NDS 914), 24 fps, 240x320,
  layout 0x16 en todos los descriptores. Un vídeo marcado (banda no plana) no puede estar instalado.
Salida: validate.json. Uso: python -X utf8 validate.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import comun_media as C


def parser_3cc44(b: bytes) -> bytes:
    """Réplica de ina_main2.cro 0x3cc44 (solo el texto base)."""
    out, i, rubi = bytearray(), 0, False
    while i < len(b):
        c = b[i]
        s = c - 256 if c >= 128 else c
        if c == 0x0A:
            out.append(c)
        elif c == 0x2F:
            rubi = True
        elif c == 0x5B:
            pass
        elif c == 0x5D:
            rubi = False
        elif (s - 0x20) & 0xFFFFFFFF <= 0x5E or (s - 0xA1) & 0xFFFFFFFF <= 0x3E:
            pass
        else:
            if not rubi:
                out += b[i:i + 2]
            i += 1
        i += 1
    return bytes(out)


def plano(t: str) -> str:
    import unicodedata
    return ''.join(unicodedata.normalize('NFKC', t).replace('−', '-').split())


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    errores, avisos = [], []
    informe = json.loads((C.SALIDA / 'informe.json').read_text(encoding='utf-8'))
    tiempos = json.loads((C.SALIDA / 'tiempos.json').read_text(encoding='utf-8'))
    dur = {p['pista']: p['video_3ds']['segundos'] for p in tiempos['pistas']}
    dur['a2m14.dat'] = round(914 / 24, 3)   # se instala el vídeo NDS español (otro montaje)

    # ---------------------------------------------------------------- voces
    jp = {p.name for p in C.SONIDO_JP.glob('*.SAD')}
    escenas = {p.split('/')[-1].split('.')[0] for p in C.archivo_jp().por if p.startswith(C.RUTA_MOVIE)
               and p.endswith('.moflex')}
    instaladas = []
    for base in (C.SALIDA, C.SALIDA_FUEGO):
        instaladas += sorted((base / C.ROMFS_SONIDO).glob('*'))
    nombres = [p.name for p in instaladas]
    if len(nombres) != len(set(nombres)):
        errores.append('SAD repetido entre la carpeta común y la de Fuego')
    fd, wav = tempfile.mkstemp(suffix='.wav')
    os.close(fd)
    descodificados = 0
    try:
        for p in instaladas:
            if p.suffix != '.SAD' or p.name not in jp:
                errores.append(f'{p.name}: no es un SAD de la RomFS 3DS')
                continue
            fuente = next(q for q in C.SONIDO_ES.iterdir() if q.name.upper() == p.name.upper())
            if p.read_bytes() != fuente.read_bytes():
                errores.append(f'{p.name}: distinto de la NDS')
            r = subprocess.run([str(C.VGM), '-o', wav, str(p)], capture_output=True, text=True)
            if r.returncode != 0 or os.path.getsize(wav) <= 44:
                errores.append(f'{p.name}: vgmstream no lo descodifica')
            else:
                descodificados += 1
            if p.stem.lower() in escenas:
                ie, ij = C.info_sad(p), C.info_sad(C.SONIDO_JP / p.name)
                if abs(ie['segundos'] - ij['segundos']) > 0.25:
                    avisos.append(f"{p.name}: duración de escena ES {ie['segundos']} s frente a JP {ij['segundos']} s")
    finally:
        os.unlink(wav)
    fuego = [p.name for p in instaladas if p.parent.parent.parent.parent.parent == C.SALIDA_FUEGO]
    if set(fuego) != {n for n in nombres if n.upper() in C.SOLO_FUEGO_SAD}:
        errores.append(f'SAD de Fuego mal repartidos: {fuego}')

    # ---------------------------------------------------------------- subtítulos
    T = C.Tipo(capa=True)
    # fuente: solo cambian los glifos de las casillas nuevas; todo lo demás es la FONT12 v90 de la base
    import pathlib
    tmpf = pathlib.Path(tempfile.mkdtemp()) / 'base.bcfnt'
    tmpf.write_bytes(T.base_bytes)
    B = C.A88.cargar(tmpf)
    nuevos = [e for e in T.reg['bigramas'] if 'subtitulos_ie2' in e.get('campos', [])]
    gi_nuevos = {e['glifo'] for e in nuevos}
    reg90 = json.loads(C.REG90.read_text(encoding='utf-8'))
    if T.reg['bigramas'][:len(reg90['bigramas'])] != reg90['bigramas']:
        errores.append('el registro no conserva v90 intacto al principio')
    if len({e['sjis'] for e in T.reg['bigramas']}) != len(T.reg['bigramas']):
        errores.append('códigos repetidos en el registro')
    distintos = [gi for gi in B.metrics if (
        B.metrics[gi] != T.F.metrics[gi] or B.bitmap(gi) != T.F.bitmap(gi))]
    if set(distintos) - gi_nuevos:
        errores.append(f'glifos cambiados fuera de las casillas nuevas: {sorted(set(distintos) - gi_nuevos)[:10]}')
    for e in nuevos:
        c = e['clave']
        d = int(c.split(C.SUB)[1])
        px, _ = T.diseno(T.txt(c))
        if T.tinta(c) != {(x + d, y): v for (x, y), v in px.items()}:
            errores.append(f'casilla {T.txt(c)!r}: el dibujo leído no es el diseñado')
    pistas = 0
    for pista in informe['subtitulos']['detalle']:
        nombre = pista['nombre']
        base = C.SALIDA_FUEGO if pista['fuego'] else C.SALIDA
        ruta = base / C.EXTRA_TXT / nombre
        otra = (C.SALIDA if pista['fuego'] else C.SALIDA_FUEGO) / C.EXTRA_TXT / nombre
        if otra.exists():
            errores.append(f'{nombre}: está en las dos carpetas')
        datos = ruta.read_bytes()
        subs = C.leer_dat(datos)
        if C.escribir_dat(subs) != datos:
            errores.append(f'{nombre}: no hace ida y vuelta')
        if C.sha(datos) != pista['sha256']:
            errores.append(f'{nombre}: distinto del informe')
        nds = C.leer_dat((C.TXT_ES / nombre).read_bytes())
        jp_subs = C.leer_dat(C.dat_jp(nombre))
        filas = pista['subtitulos']
        if len(filas) != len(subs):
            errores.append(f'{nombre}: {len(subs)} registros frente a {len(filas)} en el informe')
        # cobertura de cada registro NDS
        for k, s in enumerate(nds):
            trozos = [subs[i] for i, f in enumerate(filas) if f['registro_nds'] == k]
            if not trozos or trozos[0].inicio != s.inicio or trozos[-1].fin != s.fin or any(
                    a.fin != b.inicio for a, b in zip(trozos, trozos[1:])) or any(t.fin <= t.inicio for t in trozos):
                errores.append(f'{nombre} #{k}: trozos no cubren [{s.inicio}, {s.fin})')
            if any(t.fin - t.inicio < C.DURACION_MIN for t in trozos) and len(trozos) > 1:
                avisos.append(f'{nombre} #{k}: trozo de menos de {C.DURACION_MIN} ticks')
            texto = C.M.normalizar(C.es_nds(s.cuerpo))
            juntado = ' '.join(T.texto(t.cuerpo) for t in trozos)
            if plano(juntado) != plano(texto):
                errores.append(f'{nombre} #{k}: texto {juntado!r} != {texto!r}')
        if [(s.inicio, s.fin) for s in nds] == [(s.inicio, s.fin) for s in jp_subs]:
            for s in subs:
                if not any(j.inicio <= s.inicio and s.fin <= j.fin for j in jp_subs):
                    errores.append(f'{nombre}: [{s.inicio}, {s.fin}) fuera de los tiempos japoneses')
        fin_max = max(s.fin for s in subs)
        if fin_max > dur[nombre] * C.TICKS + 2:
            errores.append(f'{nombre}: fin {fin_max} ticks tras el final del vídeo ({dur[nombre]} s)')
        for s, f in zip(subs, filas):
            b = s.cuerpo
            if parser_3cc44(b) != b or b'\n' in b:
                errores.append(f'{nombre} {s.inicio}: bytes que el analizador descarta o toma como rubí')
            if T.sin_glifo(b):
                errores.append(f'{nombre} {s.inicio}: sin glifo {T.sin_glifo(b)}')
            cel = f['casillas'].split('|')
            if T.codificar(cel) != b or len(cel) > C.MAX_CELDAS:
                errores.append(f'{nombre} {s.inicio}: casillas {len(cel)}')
            g = T.huecos_fases(cel)
            if g and min(g) < 1:
                errores.append(f'{nombre} {s.inicio}: tinta que se toca a 13,75 px')
            for av, esc in C.PASOS_REVISADOS:
                gg = [x for xl in range(4) for _, _, x in T.huecos(cel, av, esc, xl)]
                if gg and min(gg) < 0:
                    avisos.append(f'{nombre} {s.inicio}: solape a paso {av}x{esc} ({min(gg)} px)')
        pistas += 1
    # ---------------------------------------------------------------- vídeos
    import videos as VID
    vj = json.loads(VID.INFORME.read_text(encoding='utf-8'))
    esperados = {}
    for v in vj['videos']:
        if v.get('marcado'):
            avisos.append(f"{v['nombre']}.moflex marcado (banda): {v['banda_motivos'] or v.get('banda_nds_motivos')}")
            continue
        esperados[VID.destino(v['nombre'])] = v
    halladas = {p for base in (C.SALIDA, C.SALIDA_FUEGO) for p in (base / 'extra').rglob('*.moflex')}
    halladas |= {p for base in (C.SALIDA, C.SALIDA_FUEGO) for p in (base / 'romfs_mod').rglob('*.moflex')}
    if halladas != set(esperados):
        errores.append(f'vídeos inesperados o ausentes: {sorted(map(str, halladas ^ set(esperados)))}')
    nombres_3ds = {p.split('/')[-1] for p in C.archivo_jp().por if p.startswith(C.RUTA_MOVIE)}
    for ruta, v in esperados.items():
        if not ruta.exists():
            continue
        n = v['nombre']
        if ruta.name not in nombres_3ds:
            errores.append(f'{n}: no existe en la RomFS 3DS')
        if C.sha(ruta.read_bytes()) != v['sha256']:
            errores.append(f'{n}.moflex: distinto de videos.json')
        info = C.ffprobe_video(ruta)
        fot = 914 if n == 'a2m14' else v['fotogramas_jp']
        if (info['fotogramas'], info['fps'], info['ancho'], info['alto']) != (fot, 24.0, 240, 320):
            errores.append(f"{n}.moflex: {info} (se esperaban {fot} fotogramas a 24 fps, 240x320)")
        if set(VID.layouts(ruta)) != {0x16}:
            errores.append(f'{n}.moflex: layout {VID.layouts(ruta)}')
        if v.get('errores'):
            errores.append(f"{n}.moflex: {v['errores']}")
        if n != 'a2m14' and n in {Path(x).stem for x in dur} and abs(info['segundos'] - dur[n + '.dat']) > 0.05:
            errores.append(f"{n}.moflex: duración {info['segundos']} s frente a {dur[n + '.dat']} s")

    salida = dict(
        ok=not errores, errores=errores, avisos=avisos,
        voces=dict(instaladas=len(instaladas), descodificadas=descodificados, fuego=sorted(fuego)),
        subtitulos=dict(pistas=pistas, registros=informe['subtitulos']['registros_salida']),
        videos=dict(instalados=len(esperados), resumen=vj['resumen']),
        runtime_verified=False)
    (C.SALIDA / 'validate.json').write_text(json.dumps(salida, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps({k: (v if k != 'avisos' else len(v)) for k, v in salida.items()}, ensure_ascii=False)[:3000])
    for a in avisos:
        print('aviso:', a)
    sys.exit(0 if not errores else 1)


if __name__ == '__main__':
    main()
