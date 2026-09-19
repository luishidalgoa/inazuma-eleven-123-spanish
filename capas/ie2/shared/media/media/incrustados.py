"""IE2 v07 · media: ¿el MOFLEX japonés lleva los subtítulos japoneses incrustados en la imagen? (issue #74)

Se descodifica cada fotograma y se guarda la banda inferior (vídeo 3DS 240x320 girado: columnas 0-39 =
y 200-239 en pantalla; NDS 256x192: filas 160-191, plano Y nativo).
- Transiciones: para cada inicio/fin de subtítulo japonés se busca, en +-4 fotogramas alrededor de
  ceil(tick x fps / 30), el fotograma con mayor cambio en la banda. Si el texto está en el vídeo, el cambio
  cae en el desfase 0 o +-1 (redondeo de ceil) (y confirma la unidad de 30 Hz con fotogramas reales).
- Contraste con la NDS: la misma medida en el .mods (la DS pinta el texto aparte: no debería alinearse).
Salida: incrustados.json. Uso: python -X utf8 incrustados.py
"""
from __future__ import annotations

import collections
import json
import subprocess
import sys

import numpy as np

import comun_media as C

VENTANA = 4


def bandas(video, ancho, alto, nds):
    p = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', str(video), '-f', 'rawvideo', '-'],
                         stdout=subprocess.PIPE)
    y = ancho * alto
    tam = y * 3 // 2          # yuv420p nativo: solo se usa el plano Y
    out = []
    while True:
        buf = p.stdout.read(tam)
        if len(buf) < tam:
            break
        f = np.frombuffer(buf[:y], np.uint8).reshape(alto, ancho)
        out.append((f[160:192, :] if nds else f[:, 0:40]).astype(np.int16))
    p.wait()
    return np.stack(out)


def transiciones(b, subs, fps):
    cambio = np.zeros(len(b))
    cambio[1:] = np.abs(np.diff(b, axis=0)).mean(axis=(1, 2))
    desf = collections.Counter()
    for s in subs:
        for t in (s.inicio, s.fin):
            f = int(np.ceil(t * fps / C.TICKS))
            if VENTANA <= f < len(b) - VENTANA:
                zona = cambio[f - VENTANA:f + VENTANA + 1]
                desf[int(np.argmax(zona)) - VENTANA] += 1
    total = sum(desf.values())
    return dict(bordes=total, en_0=desf[0], en_0_o_1=desf[0] + desf[-1] + desf[1],
                reparto={k: desf[k] for k in sorted(desf)})


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    tmp = C.Temporal()
    filas = []
    try:
        for dat in sorted(C.TXT_ES.glob('*.dat')):
            n = dat.stem
            jp = C.leer_dat(C.dat_jp(dat.name))
            v = tmp.moflex(n + '.moflex')
            info = C.ffprobe_video(v)
            b = bandas(v, info['ancho'], info['alto'], nds=False)
            fila = dict(pista=dat.name, fotogramas=len(b),
                        moflex_jp_30hz=transiciones(b, jp, info['fps']),
                        moflex_jp_ticks_como_fotogramas=transiciones(b, jp, C.TICKS))
            mods = C.MODS / 'sp' / (n + '.mods')
            mods = mods if mods.exists() else C.MODS / (n + '.mods')
            if mods.exists():
                im = C.ffprobe_video(mods)
                bn = bandas(mods, im['ancho'], im['alto'], nds=True)
                fila['mods_nds_30hz'] = transiciones(bn, jp, im['fps'])
            filas.append(fila)
            a = fila['moflex_jp_30hz']
            print(n, a['en_0'], '/', a['bordes'], '| como fotogramas', fila['moflex_jp_ticks_como_fotogramas']['en_0'],
                  '| nds', fila.get('mods_nds_30hz', {}).get('en_0'))
    finally:
        tmp.cerrar()

    def suma(clave, campo):
        return sum(f[clave][campo] for f in filas if clave in f)
    resumen = {k: dict(bordes=suma(k, 'bordes'), en_0=suma(k, 'en_0'), en_0_o_1=suma(k, 'en_0_o_1'))
               for k in ('moflex_jp_30hz', 'moflex_jp_ticks_como_fotogramas', 'mods_nds_30hz')}
    resumen['conclusion'] = ('texto japonés incrustado en el MOFLEX y alineado con ticks de 30 Hz'
                             if resumen['moflex_jp_30hz']['en_0_o_1'] > 0.8 * resumen['moflex_jp_30hz']['bordes']
                             and resumen['mods_nds_30hz']['en_0_o_1'] < 0.4 * resumen['mods_nds_30hz']['bordes']
                             else 'sin evidencia clara de texto incrustado')
    (C.SALIDA / 'incrustados.json').write_text(json.dumps(dict(resumen=resumen, pistas=filas), ensure_ascii=False,
                                                          indent=1), encoding='utf-8')
    print(json.dumps(resumen, ensure_ascii=False))


if __name__ == '__main__':
    main()
