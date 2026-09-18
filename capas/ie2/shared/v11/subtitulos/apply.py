"""IE2 v11 · subtítulos españoles INCRUSTADOS en las cinemáticas. No construye candidata ni instala.

Por qué: probe_ie2_v10 (vídeos de v07 sin el japonés + movie/txt/*.dat en español) no enseña ningún subtítulo en
Azahar. Diagnóstico en informe.json: el lector de movie/txt está vivo y sin puerta de idioma y nuestros .dat
tienen el formato japonés, pero el texto se pinta en la VRAM DS emulada, que el 3DS no muestra sobre el vídeo
(por eso el 3DS japonés lo lleva incrustado). Los .dat de v07 se quedan como están (inocuos).

Proceso por cinemática (35; op00 solo Fuego):
1. Fuente = la misma de v07/media/videos.procesar (MOFLEX 3DS; a2m14 = vídeo NDS; op00 = línea de tiempo NDS con
   logotipo español; a2m06/a2m20b con rótulos NDS), con la banda limpia. Se regenera desde el japonés: una sola
   compresión.
2. Se quema el texto NDS español (comun_sub: estilo medido del japonés, ticks de 30 Hz sin retraso).
3. mobipeg, mismo ajuste que v07 (QP 12; op00 QP 14; layout 0x16).
4. Descodificación completa y control: fotogramas, fps, tamaño, layout, PSNR de imagen y de banda, texto
   presente en cada trozo y banda plana sin subtítulo.
5. tiras/<n>.png con fotogramas DESCODIFICADOS del .moflex (lo que se ve en el juego).
Salida: extra/inazuma2/data_iz/movie/<n>.moflex (op00 en work/ie2/tormenta_de_fuego/capas/v11/subtitulos),
informe.json (texto del juego: no publicar). Uso: python -X utf8 apply.py [nombres...]
"""
from __future__ import annotations

import json
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np

import comun_sub as S

C, V = S.C, S.V
INFORME = S.SALIDA / 'informe.json'

DIAGNOSTICO = dict(
    conclusion='El 3DS no dibuja movie/txt/*.dat de forma visible sobre el vídeo; nuestros .dat son correctos. '
               'Solución: subtítulo incrustado en el vídeo, como el japonés 3DS.',
    evidencias=[
        'Lector vivo: ina_main2.cro 0xf4e04 (arranca el hilo 0x8f44 que lee "/data_iz/movie/txt/%s.dat", '
        'literal 0x9120; referencia del hilo en 0xf4e58) se llama desde iz2_CMainTitleScreen (0x13c250, con "op00") '
        'y desde otras 3 escenas (0x640f4, 0x906f0, 0x16ffc0).',
        'Dibujante vivo: 0xe8430 (tick = ms*30/1000 en 0xe84bc) es el método de vblank de iz2_CMainTitleScreen '
        '(0x13c210), iz2_CMainAdventureScreen (0x17f55c) y otras (0xa227c; 0x16f8bc si estado == 6).',
        'Sin puerta de idioma: el lector solo formatea el nombre y lee el fichero; las únicas condiciones del '
        'dibujante son [seg3+0x4dec]+0x1ec != 0 (reproductor activo), VCOUNT (registro DS emulado +6) >= 0xC0, '
        'registro siguiente != 0 y tick >= inicio.',
        'Destino del dibujo: 0x1208e8 -> gestor FONT12 -> cGameTextSystem::DrawTextHintOnVram, es decir, la VRAM '
        'del DS emulado (DISPCNT BG0|BG3 o BG0|BG2), no la capa del vídeo MOFLEX.',
        'Los 35 .dat japoneses del 3DS existen con el MISMO texto que el vídeo japonés lleva incrustado '
        '(v07 incrustados.json: 704/773 bordes alineados +-1 fotograma). Si el juego los enseñara, el japonés '
        'se vería duplicado: en el 3DS esa capa no se ve durante el vídeo.',
        'Formato de nuestros .dat idéntico al japonés (a2m03: mismos inicio/fin, tamaños múltiplos de 4, NUL, '
        'relleno, terminador 0xFFFFFFFF, Shift-JIS de 2 B) y el candidato probe_ie2_v10 los lleva instalados '
        '(archive.fa == v07 extra). Prueba del usuario en Azahar: ningún subtítulo en op00 ni en las cinemáticas.',
        'No se vacían los .dat: con solo el terminador, el lector tomaría inicio = 0xFFFFFFFF y la comparación '
        'con signo (blt) lo daría por vencido. Los de v07 se quedan (no se ven).',
    ])


def fuente(n: str):
    """Réplica de v07 videos.procesar hasta antes de codificar: (Y, U, V, meta)."""
    tmp = C.Temporal()
    try:
        Yj, Uj, Vj = V.leer_yuv(tmp.moflex(n + '.moflex'))
    finally:
        tmp.cerrar()
    ok, motivos, base = V.banda_ok(Yj, Uj, Vj)
    meta = dict(fotogramas_jp=len(Yj), bytes_jp=len(C.archivo_jp().get(C.RUTA_MOVIE + n + '.moflex')))
    if n == 'a2m14':
        Y, U, Vv = V.fuente_a2m14()
        ok, motivos, _ = V.banda_ok(Y, U, Vv, negro=16)
        V.limpiar(Y, U, Vv)
        meta['fuente'] = 'NDS ES movie/a2m14.mods (otro montaje)'
    elif n == 'op00':
        V.limpiar(Yj, Uj, Vj, base)
        Y, U, Vv, extra = V.fuente_op00(Yj, Uj, Vj)
        V.limpiar(Y, U, Vv)
        meta['fuente'] = 'MOFLEX 3DS en la línea de tiempo NDS + logotipo NDS ES (v07)'
    elif n in V.ROTULOS:
        V.limpiar(Yj, Uj, Vj, base)
        Y, U, Vv, extra = V.fuente_rotulos(n, Yj, Uj, Vj)
        V.limpiar(Y, U, Vv, base)
        meta['fuente'] = 'MOFLEX 3DS + rótulos NDS ES (v07)'
    else:
        Y, U, Vv = Yj, Uj, Vj
        V.limpiar(Y, U, Vv, base)
        meta['fuente'] = 'MOFLEX 3DS'
    if not ok:
        raise RuntimeError(f'{n}: banda no limpiable {motivos}')
    return Y, U, Vv, meta


def tira(n, Yo, Uo, Vo, subs, idx):
    from PIL import Image, ImageDraw, ImageFont
    f = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 12)
    celdas = []
    for i, s in enumerate(subs):
        ks = np.where(idx == i)[0]
        if not len(ks):
            continue
        k = int(ks[min(len(ks) - 1, 2)])
        img = Image.fromarray(V.yuv_a_rgb(Yo[k:k + 1], Uo[k:k + 1], Vo[k:k + 1])[0])
        celdas.append((img, f"{i}: ticks {s['inicio']}-{s['fin']} · fot {ks[0]}-{ks[-1]} · {s['texto']}"))
    cols = 3
    filas = (len(celdas) + cols - 1) // cols
    hoja = Image.new('RGB', (cols * 324, max(1, filas) * 260), (60, 60, 60))
    d = ImageDraw.Draw(hoja)
    for j, (img, cap) in enumerate(celdas):
        x, y = (j % cols) * 324 + 2, (j // cols) * 260 + 2
        hoja.paste(img, (x, y))
        d.text((x, y + 242), cap[:60], font=f, fill=(255, 255, 255))
    ruta = S.dir_tiras(n) / f'{n}.png'
    ruta.parent.mkdir(parents=True, exist_ok=True)
    hoja.save(ruta, optimize=True)
    return str(ruta.relative_to(S.ROOT)).replace('\\', '/')


def controlar(n, sal, Y, subs, idx):
    info = C.ffprobe_video(sal)
    Yo, Uo, Vo = V.leer_yuv(sal)
    errores = []
    if len(Yo) != len(Y) or info['fotogramas'] != len(Y):
        errores.append(f'fotogramas {len(Yo)} != {len(Y)}')
    if info['fps'] != 24 or (info['ancho'], info['alto']) != (V.W, V.H):
        errores.append('fps o tamaño distintos')
    lay = [hex(x) for x in V.layouts(sal)]
    if lay != ['0x16']:
        errores.append(f'layout {lay}')
    n_ = min(len(Yo), len(Y))
    esperado = Y[:n_, :, :S.ALTO].astype(np.int16)
    obtenido = Yo[:n_, :, :S.ALTO].astype(np.int16)
    sin = idx[:n_] < 0
    plano_max = int(np.abs(obtenido[sin, :, :S.ALTO - 4] - esperado[sin, :, :S.ALTO - 4]).max()) if sin.any() else 0
    if plano_max > 6:   # residuo tenue del códec tras un subtítulo (a2m41: 4-5 niveles sobre Y 25)
        errores.append(f'banda sin subtítulo no plana ({plano_max})')
    peor = 99.0
    for i, s in enumerate(subs):
        ks = np.where(idx[:n_] == i)[0]
        if not len(ks):
            errores.append(f'subtítulo {i} sin fotogramas: {s}')
            continue
        for k in ks:
            tinta = esperado[k] > 200
            if not tinta.any() or not (obtenido[k][tinta] > 150).mean() > 0.98:
                errores.append(f'subtítulo {i} ilegible en el fotograma {k}')
                break
        peor = min(peor, V.psnr(esperado[ks], obtenido[ks]))
    r = dict(bytes=sal.stat().st_size, fotogramas=len(Yo), fps=info['fps'], layout=lay,
             psnr_imagen=V.psnr(Y[:n_, :, 36:], Yo[:n_, :, 36:]), psnr_banda_texto_min=peor,
             banda_plana_max_desvio=plano_max)
    if peor < 30:
        errores.append(f'banda con texto degradada (PSNR {peor})')
    return r, errores, (Yo, Uo, Vo)


def procesar(n: str) -> dict:
    subs = S.pistas(n)
    Y, U, Vv, meta = fuente(n)
    idx = S.por_fotograma(subs, len(Y))
    S.quemar(Y, subs, idx)
    qp = V.QP.get(n, V.QP_DEFECTO)
    sal = S.destino(n)
    V.codificar(Y, U, Vv, sal, qp)
    ctl, errores, dec = controlar(n, sal, Y, subs, idx)
    r = dict(nombre=n, fuego=n == 'op00', qp=qp, **meta, **ctl, errores=errores,
             ruta=str(sal.relative_to(S.ROOT)).replace('\\', '/'), sha256=C.sha(sal.read_bytes()),
             bytes_v07=(C.SALIDA_FUEGO if n == 'op00' else C.SALIDA).joinpath(V.RUTA_VIDEOS, n + '.moflex').stat().st_size,
             fotogramas_con_texto=int((idx >= 0).sum()), subtitulos=subs,
             partidos=len(subs) - len({s['registro_nds'] for s in subs}))
    r['tira'] = tira(n, *dec, subs, idx)
    print(n, r['bytes_jp'], r['bytes_v07'], '->', r['bytes'], r['psnr_imagen'], r['psnr_banda_texto_min'], errores,
          flush=True)
    return r


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    tiempos = json.loads((C.SALIDA / 'tiempos.json').read_text(encoding='utf-8'))
    todos = [p['pista'][:-4] for p in tiempos['pistas']]
    nombres = sys.argv[1:] or todos
    previo = {}
    if INFORME.exists():
        previo = {v['nombre']: v for v in json.loads(INFORME.read_text(encoding='utf-8'))['videos']}
    with ProcessPoolExecutor(max_workers=4) as ex:
        for r in ex.map(procesar, nombres):
            previo[r['nombre']] = r
    videos = [previo[n] for n in todos if n in previo]
    resumen = dict(videos=len(videos), con_errores=[v['nombre'] for v in videos if v['errores']],
                   subtitulos=sum(len(v['subtitulos']) for v in videos),
                   partidos=sum(v['partidos'] for v in videos),
                   bytes_jp=sum(v['bytes_jp'] for v in videos), bytes_v07=sum(v['bytes_v07'] for v in videos),
                   bytes=sum(v['bytes'] for v in videos),
                   psnr_imagen_min=min(v['psnr_imagen'] for v in videos),
                   psnr_banda_texto_min=min(v['psnr_banda_texto_min'] for v in videos))
    resumen['cambio_frente_a_v07'] = resumen['bytes'] - resumen['bytes_v07']
    resumen['cambio_frente_a_jp'] = resumen['bytes'] - resumen['bytes_jp']
    informe = dict(capa='work/ie2/shared/capas/v11/subtitulos', fuego=str(S.SALIDA_FUEGO.relative_to(S.ROOT)),
                   nota='Contiene texto del juego: no publicar. Aplicar DESPUÉS de v07/media (sustituye sus .moflex).',
                   diagnostico=DIAGNOSTICO,
                   estilo=dict(fuente='Yu Gothic UI Semibold (YuGothB.ttc, índice 2)', px=S.TAM, linea_base_y=S.BASE_Y,
                               banda_y=[S.Y0, S.Y0 + S.ALTO - 1], blanco_Y=S.BLANCO, contorno=None,
                               ancho_max_px=S.ANCHO_MAX, centro_x=S.CENTRO,
                               medido_jp='blanco Y 235-242 sin contorno, kana y 214-228, centrado x 160, ancho <= 299 px'),
                   tiempos='ticks de 30 Hz del .dat NDS ES; visible si inicio <= floor(floor(k*1000/24)*30/1000) < fin',
                   resumen=resumen, videos=videos)
    INFORME.write_text(json.dumps(informe, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(resumen, ensure_ascii=False))


if __name__ == '__main__':
    main()
