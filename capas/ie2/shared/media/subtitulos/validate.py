"""IE2 v11 · subtítulos incrustados: validación offline. No construye ni instala.

- Ficheros: extra/ común = los 34 .moflex sin op00; Fuego = solo op00.moflex; ningún .dat ni otro fichero.
  Cada uno coincide con el sha256 de informe.json.
- Contenedor: ffprobe cuenta los mismos fotogramas que el vídeo de v07 (op00 2328, a2m14 914), 24 fps,
  240x320, layout 0x16 en todos los descriptores.
- Texto y tiempos: los trozos se regeneran igual (comun_sub.pistas), unidos dan el texto oficial NDS, son
  contiguos y cubren exactamente su intervalo, caben en 300 px, y ningún fin pasa del final del vídeo (+2 ticks).
- Descodificación COMPLETA de cada vídeo:
  * cada trozo tiene fotogramas y en todos ellos su tinta (cobertura > 200) sale > 150 en >= 98 %;
  * lejos del texto (a > 3 px de su tinta) la banda sigue plana (|d| <= 24 con el halo del códec);
  * sin subtítulo, las columnas 0-27 de la banda están planas (|d| <= 6: residuo tenue del códec);
  * la imagen (columnas >= 36) coincide con la de v07 (PSNR >= 38).
Salida: validate.json. Uso: python -X utf8 validate.py
"""
from __future__ import annotations

import json
import sys

import numpy as np
from scipy.ndimage import binary_dilation

import comun_sub as S

C, V = S.C, S.V


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    errores, filas = [], []
    inf = json.loads((S.SALIDA / 'informe.json').read_text(encoding='utf-8'))
    v07 = {v['nombre']: v for v in json.loads((C.SALIDA / 'videos.json').read_text(encoding='utf-8'))['videos']}
    tiempos = json.loads((C.SALIDA / 'tiempos.json').read_text(encoding='utf-8'))
    todos = [p['pista'][:-4] for p in tiempos['pistas']]
    videos = {v['nombre']: v for v in inf['videos']}
    if sorted(videos) != sorted(todos):
        errores.append(f'informe incompleto: faltan {sorted(set(todos) - set(videos))}')

    comun = sorted(p.relative_to(S.SALIDA / 'extra').as_posix() for p in (S.SALIDA / 'extra').rglob('*') if p.is_file())
    fuego = sorted(p.relative_to(S.SALIDA_FUEGO / 'extra').as_posix() for p in (S.SALIDA_FUEGO / 'extra').rglob('*')
                   if p.is_file())
    esperado_comun = sorted(f'inazuma2/data_iz/movie/{n}.moflex' for n in todos if n != 'op00')
    if comun != esperado_comun:
        errores.append(f'extra común distinto: sobran {sorted(set(comun) - set(esperado_comun))}, '
                       f'faltan {sorted(set(esperado_comun) - set(comun))}')
    if fuego != ['inazuma2/data_iz/movie/op00.moflex']:
        errores.append(f'extra Fuego distinto: {fuego}')

    for n in todos:
        v = videos.get(n)
        if v is None:
            continue
        e = []
        ruta = S.destino(n)
        if not ruta.exists():
            errores.append(f'{n}: falta {ruta}')
            continue
        datos = ruta.read_bytes()
        if C.sha(datos) != v['sha256']:
            e.append('sha256 distinto del informe')
        info = C.ffprobe_video(ruta)
        n_fot = v07[n]['fotogramas']
        if info['fotogramas'] != n_fot or info['fps'] != 24 or (info['ancho'], info['alto']) != (V.W, V.H):
            e.append(f"contenedor {info} (v07 {n_fot} fotogramas)")
        lay = [hex(x) for x in V.layouts(ruta)]
        if lay != ['0x16']:
            e.append(f'layout {lay}')

        subs = S.pistas(n)
        if subs != v['subtitulos']:
            e.append('los trozos regenerados no coinciden con el informe')
        for k, s in enumerate(C.leer_dat((C.TXT_ES / f'{n}.dat').read_bytes())):
            trozos = [x for x in subs if x['registro_nds'] == k]
            if ' '.join(x['texto'] for x in trozos) != S.texto_nds(s.cuerpo):
                e.append(f'registro {k}: el texto no es el oficial NDS')
            if not trozos or trozos[0]['inicio'] != s.inicio or trozos[-1]['fin'] != s.fin or any(
                    a['fin'] != b['inicio'] for a, b in zip(trozos, trozos[1:])):
                e.append(f'registro {k}: tramos no contiguos o fuera de [{s.inicio}, {s.fin})')
        for s in subs:
            if S.ancho(s['texto']) > S.ANCHO_MAX:
                e.append(f"demasiado ancho: {s['texto']!r}")
            if s['fin'] > n_fot / 24 * 30 + 2:
                e.append(f"fin {s['fin']} tras el final del vídeo")

        Yo, Uo, Vo = V.leer_yuv(ruta)
        idx = S.por_fotograma(subs, len(Yo))
        banda = Yo[:, :, :S.ALTO].astype(np.int16)
        base = np.median(banda[:, :, :6].reshape(len(Yo), -1), axis=1).astype(np.int16)
        d = np.abs(banda - base[:, None, None])
        sin = idx < 0
        plano = int(d[sin, :, :S.ALTO - 4].max()) if sin.any() else 0
        if plano > 6:   # residuo tenue del códec tras un subtítulo
            e.append(f'banda sin subtítulo no plana ({plano})')
        halo_max = 0
        for i, s in enumerate(subs):
            ks = np.where(idx == i)[0]
            if not len(ks):
                e.append(f'trozo {i} sin fotogramas')
                continue
            a = S.a_columnas(S.alfa(s['texto']))
            tinta = a > 200
            lejos = ~binary_dilation(a > 0, iterations=3)
            for k in ks:
                if (Yo[k, :, :S.ALTO][tinta] > 150).mean() < 0.98:
                    e.append(f'trozo {i} ilegible en el fotograma {k}')
                    break
            halo_max = max(halo_max, int(d[ks][:, lejos].max()))
        if halo_max > 24:
            e.append(f'manchas lejos del texto ({halo_max})')
        ruta07 = (C.SALIDA_FUEGO if n == 'op00' else C.SALIDA) / V.RUTA_VIDEOS / f'{n}.moflex'
        Y7 = V.leer_yuv(ruta07)[0]
        p = V.psnr(Y7[:, :, 36:], Yo[:, :, 36:]) if len(Y7) == len(Yo) else 0
        if p < 38:
            e.append(f'imagen distinta de v07 (PSNR {p})')
        filas.append(dict(nombre=n, fotogramas=len(Yo), trozos=len(subs), banda_plana_max=plano,
                          halo_lejos_max=halo_max, psnr_imagen_vs_v07=p, errores=e))
        errores += [f'{n}: {x}' for x in e]
        print(n, len(Yo), len(subs), plano, halo_max, p, e, flush=True)

    out = dict(ok=not errores, errores=errores, videos=filas)
    (S.SALIDA / 'validate.json').write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
    print('OK' if not errores else f'{len(errores)} errores')
    return 0 if not errores else 1


if __name__ == '__main__':
    sys.exit(main())
