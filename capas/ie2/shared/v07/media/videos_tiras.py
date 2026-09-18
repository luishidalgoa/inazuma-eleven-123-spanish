"""IE2 v07 · media: tiras «como en el juego» de los vídeos limpios (issue #74).

Para cada subtítulo instalado: el fotograma del vídeo recodificado (videos.py) en la mitad de su intervalo, con el
subtítulo español pintado encima en su posición real y con la FONT12 de la capa (tiras.pintar, registro.json).
Salida: tiras/juego_<n>.png (op00 en la carpeta de Fuego). Uso: python -X utf8 videos_tiras.py [nombres...]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import comun_media as C
import tiras
import videos

POR_DEFECTO = ['a2m03', 'a2m14', 'a2m41', 'op00']
COLUMNAS = 3


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    nombres = sys.argv[1:] or POR_DEFECTO
    informe = {Path(p['nombre']).stem: p for p in
               json.loads((C.SALIDA / 'informe.json').read_text(encoding='utf-8'))['subtitulos']['detalle']}
    T = C.Tipo(capa=True)
    letra = ImageFont.truetype(str(tiras.FUENTE), 12)
    for n in nombres:
        video = videos.destino(n)
        info = C.ffprobe_video(video)
        total = info['fotogramas']
        subs = informe[n]['subtitulos']
        marcas = [min(total - 1, int((s['inicio'] + s['fin']) / 2 / C.TICKS * info['fps'])) for s in subs]
        cuadros = tiras.fotogramas(video, marcas)
        filas = -(-len(subs) // COLUMNAS)
        hoja = Image.new('RGB', (COLUMNAS * 326, 26 + filas * 262), (18, 18, 24))
        d = ImageDraw.Draw(hoja)
        d.text((6, 6), f'{n}.moflex (limpio, {total} fot.) + movie/txt/{n}.dat pintado con FONT12 '
                       f'(y = 215, paso 13,75 px)', fill=(230, 230, 230), font=letra)
        for k, (s, f) in enumerate(zip(subs, marcas)):
            x, y = (k % COLUMNAS) * 326, 26 + (k // COLUMNAS) * 262
            img = cuadros[f].copy()
            tiras.pintar(T, img, s['casillas'].split('|'))
            hoja.paste(img, (x, y))
            d.text((x, y + 243), f"#{k} f{f} ({f / info['fps']:.2f} s)  {s['texto'][:34]}", fill=(170, 170, 170),
                   font=letra)
        destino = (C.SALIDA_FUEGO if n == 'op00' else C.SALIDA) / 'tiras' / f'juego_{n}.png'
        destino.parent.mkdir(parents=True, exist_ok=True)
        hoja.save(destino, optimize=True)
        print(destino.relative_to(C.ROOT), len(subs))


if __name__ == '__main__':
    main()
