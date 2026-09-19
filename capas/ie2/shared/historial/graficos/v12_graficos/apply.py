"""v12 · gráficos de IE2: logo europeo del título, «Volver» del título y teclado de nombre latino.

No construye candidata ni instala. Para cada textura de planes_v12.PLAN12 parte del .arc de v06 (si no,
v03; si no, japonés), aplica la función y reenvuelve con la envoltura del japonés.
Salida: extra/<ruta>, informe.json, previews/x4_<textura>.png (japonés | v06 | v12, ×4, sobre gris y
sobre los fondos reales cuando aplica) y previews/titulo_compuesto_{fuego,ventisca}.png.
Uso: python apply.py
"""
import json
import shutil
import sys

import numpy as np
from PIL import Image, ImageDraw

import base12 as B
import planes_v12 as P

C = B.C


def _sobre(im, color):
    bg = Image.new('RGBA', im.size, color)
    bg.alpha_composite(im)
    return bg


def preview(nombre, jp, antes, despues, escala):
    ims = [Image.fromarray(x, 'RGBA') for x in (jp, antes, despues)]
    filas = []
    for fondo in ((64, 64, 64, 255), (255, 0, 255, 255), (255, 255, 255, 255)):
        filas.append([_sobre(i, fondo).resize((i.width * escala, i.height * escala), Image.NEAREST) for i in ims])
    w, h = filas[0][0].size
    hoja = Image.new('RGBA', (3 * w + 40, 3 * h + 60 + 20), (20, 20, 28, 255))
    d = ImageDraw.Draw(hoja)
    for j, t in enumerate(('japones (original)', 'base v06/v03', 'v12')):
        d.text((10 + j * (w + 10), 4), f'{nombre} - {t}', fill=(255, 255, 255, 255))
    for i, fila in enumerate(filas):
        for j, im in enumerate(fila):
            hoja.paste(im, (10 + j * (w + 10), 20 + i * (h + 20)))
    hoja.save(B.PREVIEWS / f'x4_{nombre.removesuffix(".tga")}.png')


QNA_OFF = 1988608            # offset del QNA dentro del ARCV de title_t.arc
GRUPOS = {'ventisca': (11, 16), 'fuego': (16, 21)}   # partes de los grupos finales 6 y 7 del QNA


def compuesto(tex, version, arc_raw):
    """Pantalla superior (400x240) con las posiciones EXACTAS del QNA: cada parte = caja UV, tamaño
    (+16/+20), centro en pantalla (x=+32, y=-(+36)), escala (+40/+44). Orden: la primera parte del grupo
    queda encima (el fondo es la última). Los destellos ina_p y el subtítulo están vacíos en v12."""
    import struct
    d = arc_raw[QNA_OFF:]
    n_tex, _, n_partes = struct.unpack_from('<III', d, 8)
    nombres_off, _, partes_off = struct.unpack_from('<III', d, 36)
    nombres = [d[nombres_off + i * 32:nombres_off + i * 32 + 32].split(bytes(1))[0].decode() for i in range(n_tex)]
    lienzo = Image.new('RGBA', (400, 240), (0, 0, 0, 255))
    a, b = GRUPOS[version]
    for i in reversed(range(a, b)):
        o = partes_off + i * 128
        u0, v0, u1, v1, w, h = struct.unpack_from('<6f', d, o)
        x, y, sx, sy = struct.unpack_from('<4f', d, o + 32)
        t = struct.unpack_from('<I', d, o + 88)[0]
        pieza = tex[nombres[t] + '.tga'].crop((int(u0), int(v0), int(u1), int(v1)))
        pieza = pieza.resize((round(w * sx), round(h * sy)), Image.NEAREST)
        lienzo.alpha_composite(pieza, (round(x - pieza.width / 2), round(-y - pieza.height / 2)))
    return lienzo


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    shutil.rmtree(B.EXTRA, ignore_errors=True)
    shutil.rmtree(B.PREVIEWS, ignore_errors=True)
    B.PREVIEWS.mkdir(parents=True)
    informe = []
    titulo = {}
    for ruta, plan in sorted(P.PLAN12.items()):
        jp_orig = C.jp().get(ruta)
        base = B.base_arc(ruta)
        raw = bytearray(C.U.unwrap(base))
        jp_tex = B.texturas_de(jp_orig)
        cambios = []
        for nombre, off, ln, blob in C.texturas(bytes(raw)):
            if nombre not in plan:
                if ruta.endswith('title_t.arc'):
                    titulo[nombre] = C.decodificar(blob).convert('RGBA')
                continue
            jp = np.array(C.decodificar(jp_tex[nombre]).convert('RGBA'))
            antes = np.array(C.decodificar(blob).convert('RGBA'))
            if isinstance(plan[nombre], P.DeCapa):
                nuevo = plan[nombre].blob()
                assert C.T.metadata(nuevo) == C.T.metadata(blob) and len(nuevo) == len(blob)
            else:
                despues = plan[nombre](antes.copy(), jp)
                nuevo = C.codificar(blob, Image.fromarray(despues.astype(np.uint8), 'RGBA'))
            final = np.array(C.decodificar(nuevo).convert('RGBA'))
            if ruta.endswith('title_t.arc'):
                titulo[nombre] = Image.fromarray(final, 'RGBA')
            if nuevo == blob:
                continue
            raw[off:off + ln] = nuevo
            _, w, h, fmt, _, _ = C.T.metadata(blob)
            cambios.append(dict(textura=nombre, formato=fmt, tam=[w, h],
                                origen=('v13/cro_ranura' if isinstance(plan[nombre], P.DeCapa) else 'v12')))
            preview(nombre, jp, antes, final, 4 if max(w, h) <= 256 else 2)
        if not cambios:
            continue
        raw = bytes(raw)
        assert C.U.entries(raw) == C.U.entries(C.U.unwrap(jp_orig))
        datos = C.reenvolver(jp_orig, raw)
        destino = B.EXTRA / ruta
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(datos)
        informe.append(dict(ruta=ruta, base=B.origen_base(ruta), cambios=cambios,
                            sszl=jp_orig[:4] == b'SSZL', tam_original=len(jp_orig), tam_nuevo=len(datos)))
    for v in ('fuego', 'ventisca'):
        im = compuesto(titulo, v, C.U.unwrap(C.jp().get('inazuma2/data_iz/a_title/title_t.arc')))
        im.resize((800, 480), Image.LANCZOS).save(B.PREVIEWS / f'titulo_compuesto_{v}.png')
    salida = dict(ficheros=informe, fcode=P.NOTA_FCODE, runtime_verified=False)
    (B.HERE / 'informe.json').write_text(json.dumps(salida, ensure_ascii=False, indent=1), encoding='utf-8')
    print(len(informe), 'ficheros;', sum(len(r['cambios']) for r in informe), 'texturas')


if __name__ == '__main__':
    main()
