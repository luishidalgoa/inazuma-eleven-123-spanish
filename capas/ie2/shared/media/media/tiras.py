"""IE2 v07 · media: tira de control por cinemática (issue #74).

Una fila por subtítulo instalado: fotograma de inicio (miniatura), fotograma final con el subtítulo
simulado encima (tamaño real 320x240: vídeo 240x320 girado 90° a la izquierda, glifos de FONT12.bcfnt a
paso 11 x 1,25 = 13,75 px, centrado, arriba en y = 172 x 1,25 = 215) y los datos: ticks, segundos,
fotogramas 3DS y texto. Salida: tiras/<n>.png (op00 en la carpeta de Fuego). Uso: python -X utf8 tiras.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import comun_media as C

FUENTE = Path('C:/Windows/Fonts/arial.ttf')


def fotogramas(video: Path, numeros, ancho=240, alto=320):
    """{n: imagen girada} descodificando el vídeo completo por tubería (sin buscar)."""
    quiero = set(numeros)
    p = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', str(video), '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
                         stdout=subprocess.PIPE)
    tam = ancho * alto * 3
    out, n = {}, 0
    while True:
        buf = p.stdout.read(tam)
        if len(buf) < tam:
            break
        if n in quiero:
            out[n] = Image.frombytes('RGB', (ancho, alto), buf).rotate(90, expand=True)
        n += 1
    p.wait()
    assert p.returncode == 0 and quiero <= set(out), (video, sorted(quiero - set(out))[:5])
    return out


def pintar(T: C.Tipo, img: Image.Image, cel):
    px = img.load()
    n = len(cel)
    x_linea = (256 - n * C.AVANCE_DS) // 2
    y0 = int(172 * C.ESCALA)
    for i, c in enumerate(cel):
        base = int((x_linea + i * C.AVANCE_DS) * C.ESCALA)
        for (x, y), v in T.tinta(c).items():
            X, Y = base + x, y0 + y
            if 0 <= X < img.width and 0 <= Y < img.height:
                a = v / 15
                r, g, b = px[X, Y]
                px[X, Y] = (int(r * (1 - a) + 255 * a), int(g * (1 - a) + 255 * a), int(b * (1 - a) + 255 * a))


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    import json
    informe = json.loads((C.SALIDA / 'informe.json').read_text(encoding='utf-8'))
    T = C.Tipo(capa=True)
    letra = ImageFont.truetype(str(FUENTE), 13)
    tmp = C.Temporal()
    try:
        for pista in informe['subtitulos']['detalle']:
            n = Path(pista['nombre']).stem
            video = tmp.moflex(n + '.moflex')
            info = C.ffprobe_video(video)
            fps, total = info['fps'], info['fotogramas']
            filas = []
            for s in pista['subtitulos']:
                fi = min(total - 1, int(s['inicio'] / C.TICKS * fps))
                ff = min(total - 1, max(fi, -(-s['fin'] * fps // C.TICKS) - 1))
                filas.append((s, int(fi), int(ff)))
            cuadros = fotogramas(video, [f for _, a, b in filas for f in (a, b)], info["ancho"], info["alto"])
            alto, ancho = 250, 160 + 8 + 320 + 8 + 470
            hoja = Image.new('RGB', (ancho, 30 + alto * len(filas)), (18, 18, 24))
            d = ImageDraw.Draw(hoja)
            d.text((6, 8), f"{n}.moflex (JP)  {total} fotogramas @ {fps:g} fps = {info['segundos']} s   "
                           f"subtítulos: {len(filas)}   paso 13,75 px", fill=(230, 230, 230), font=letra)
            for k, (s, fi, ff) in enumerate(filas):
                y = 30 + k * alto
                hoja.paste(cuadros[fi].resize((160, 120)), (0, y))
                fin = cuadros[ff].copy()
                pintar(T, fin, s['casillas'].split('|'))
                hoja.paste(fin, (168, y))
                x = 168 + 320 + 8
                lineas = [
                    f"#{k}  (NDS #{s['registro_nds']})",
                    f"ticks {s['inicio']}-{s['fin']}  ({s['inicio'] / 30:.2f}-{s['fin'] / 30:.2f} s, "
                    f"{(s['fin'] - s['inicio']) / 30:.2f} s)",
                    f"fotogramas {fi}-{ff}",
                    f"casillas {s['n_casillas']}  huecos {s['hueco_min_px']}-{s['hueco_max_px']} px",
                    s['texto'],
                    ' | '.join(T.txt(c) for c in s['casillas'].split('|')),
                ]
                for j, t in enumerate(lineas):
                    d.text((x, y + 4 + j * 18), t, fill=(230, 230, 230), font=letra)
                d.text((0, y + 124), f'inicio f{fi}', fill=(160, 160, 160), font=letra)
            destino = (C.SALIDA_FUEGO if pista['fuego'] else C.SALIDA) / 'tiras' / f'{n}.png'
            destino.parent.mkdir(parents=True, exist_ok=True)
            hoja.save(destino, optimize=True)
            print(destino.relative_to(C.ROOT), len(filas))
    finally:
        tmp.cerrar()


if __name__ == '__main__':
    main()
