"""IE2 v07 · media: comprobación de tiempos de los subtítulos frente al vídeo y a la voz (issue #74).

Para cada pista movie/txt/<n>.dat:
- vídeo 3DS japonés (se conserva): fotogramas y fps del MOFLEX (ffprobe); vídeo NDS <n>.mods: ídem.
- voz: <N>.SAD español (instalado) y japonés: duración (vgmstream).
- último fin de subtítulo (ticks / 30) <= duración del vídeo.
- actividad de voz = RMS por tick de (ES - JP) a 16364 Hz mono: música y efectos son comunes, así que la
  diferencia queda casi solo en los tramos hablados. Se correlaciona con la máscara de subtítulos para
  desfases de -2..+2 s y para tres lecturas de la unidad: ticks de 30 Hz (la del CRO), fotogramas del
  vídeo 3DS y fotogramas del vídeo NDS. La buena da el máximo con desfase ~0.
Salida: tiempos.json. Uso: python -X utf8 tiempos.py
"""
from __future__ import annotations

import json
import sys

import numpy as np

import comun_media as C

DESFASE = 60     # ticks


def mascara(subs, n, escala=1.0):
    m = np.zeros(n, dtype=np.float32)
    for s in subs:
        a, b = int(round(s.inicio * escala)), int(round(s.fin * escala))
        m[max(0, a):max(0, min(n, b))] = 1.0
    return m


def correlacion(m, v):
    """{desfase: r} con la máscara adelantada/retrasada respecto a la voz."""
    out = {}
    for d in range(-DESFASE, DESFASE + 1):
        mm = np.roll(m, d)
        if d > 0:
            mm[:d] = 0
        elif d < 0:
            mm[d:] = 0
        if mm.std() == 0:
            continue
        out[d] = float(np.corrcoef(mm, v)[0, 1])
    return out


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    tmp = C.Temporal()
    filas = []
    try:
        for dat in sorted(C.TXT_ES.glob('*.dat')):
            n = dat.stem
            subs = C.leer_dat(dat.read_bytes())
            subs_jp = C.leer_dat(C.dat_jp(dat.name))
            v3 = C.ffprobe_video(tmp.moflex(n + '.moflex'))
            mods = C.MODS / 'sp' / (n + '.mods')
            mods = mods if mods.exists() else C.MODS / (n + '.mods')
            vn = C.ffprobe_video(mods) if mods.exists() else None
            sad = n.upper() + '.SAD'
            es, jp = C.SONIDO_ES / sad, C.SONIDO_JP / sad
            fila = dict(pista=dat.name, video_3ds=v3, video_nds=vn,
                        ultimo_fin_s=round(max(s.fin for s in subs) / C.TICKS, 3),
                        cabe_en_video=max(s.fin for s in subs) / C.TICKS <= v3['segundos'] + 0.05)
            if es.exists() and jp.exists():
                ie, ij = C.info_sad(es), C.info_sad(jp)
                fila.update(sad_es=ie, sad_jp=ij)
                xe = C.envolvente(tmp.wav(es, 'es'))
                xj = C.envolvente(tmp.wav(jp, 'jp'))
                k = min(len(xe), len(xj))
                v = C.rms_ticks(xe[:k] - xj[:k])
                v = v / (np.median(v) + 1e-9)
                lecturas = {'ticks_30hz': 1.0, 'fotogramas_3ds': C.TICKS / v3['fps']}
                if vn:
                    lecturas['fotogramas_nds'] = C.TICKS / vn['fps']
                res = {}
                for nombre, esc in lecturas.items():
                    cor = correlacion(mascara(subs, len(v), esc), v)
                    mejor = max(cor, key=cor.get)
                    res[nombre] = dict(escala=round(esc, 4), r_desfase0=round(cor.get(0, float('nan')), 3),
                                       mejor_desfase_ticks=mejor, r_mejor=round(cor[mejor], 3))
                cor_jp = correlacion(mascara(subs_jp, len(v)), v)
                fila['voz'] = res
                fila['voz']['tiempos_jp_r_desfase0'] = round(cor_jp.get(0, float('nan')), 3)
                # Primer tramo hablado (voz > 4 x mediana durante >= 3 ticks) frente al primer subtítulo.
                act = np.convolve((v > 4).astype(int), np.ones(3, int), 'valid') >= 3
                fila['voz']['primer_tramo_voz_s'] = round(int(np.argmax(act)) / C.TICKS, 3) if act.any() else None
                fila['voz']['primer_subtitulo_s'] = round(subs[0].inicio / C.TICKS, 3)
                fila['duracion_sad_es_menos_video_s'] = round(ie['segundos'] - v3['segundos'], 3)
            filas.append(fila)
            vz = fila.get('voz', {})
            print(f"{n:7s} v3ds {v3['fotogramas']:5d}@{v3['fps']:g} nds {vn and vn['fotogramas']}@{vn and vn['fps']} "
                  f"fin {fila['ultimo_fin_s']:7.2f}/{v3['segundos']:7.2f} "
                  + ' '.join(f"{k}:{x['r_desfase0']:+.2f}/{x['mejor_desfase_ticks']:+d}" for k, x in vz.items()
                             if isinstance(x, dict)))
    finally:
        tmp.cerrar()
    resumen = dict(
        pistas=len(filas),
        caben_en_video=sum(f['cabe_en_video'] for f in filas),
        con_voz=sum('voz' in f for f in filas),
        mejor_lectura={k: sum(1 for f in filas if 'voz' in f and max(
            (x for x in f['voz'].values() if isinstance(x, dict)), key=lambda x: x['r_mejor']) is f['voz'].get(k))
            for k in ('ticks_30hz', 'fotogramas_3ds', 'fotogramas_nds')},
        desfase_ticks_30hz=sorted(f['voz']['ticks_30hz']['mejor_desfase_ticks'] for f in filas if 'voz' in f),
    )
    (C.SALIDA / 'tiempos.json').write_text(json.dumps(dict(resumen=resumen, pistas=filas), ensure_ascii=False,
                                                      indent=1), encoding='utf-8')
    print(json.dumps(resumen, ensure_ascii=False))


if __name__ == '__main__':
    main()
