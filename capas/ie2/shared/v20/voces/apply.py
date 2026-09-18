"""IE2 v20 · voces (issue #77): gritos de gol / gol encajado (3D_003_*) con la voz española de la NDS
y restauración de las muestras 16/17 de 3D_901 que v13 dejó en silencio.

Parte del sound.pb de v13/voz_titulo (idéntico al instalado en probe_ie2_v18), así este sound.pb
incluye los cambios de v13 más los de aquí. No construye candidata ni instala.

3D_003_* (36 pares, mismos nombres en 3DS y en la NDS española):
- Mismas muestras (ids) en los dos SWD; la NDS las guarda en IMA 4 bits a 32728 Hz (la frecuencia de la
  3DS: no hace falta remuestrear). Cada muestra se decodifica y se codifica en DSP-ADPCM con la cabecera
  CWAV japonesa de esa muestra (v13: cwav/swd_nuevo); wavi/prgi japoneses intactos, pcmd recolocado.
  Se exige que el mapa tecla->muestra de prgi sea igual en las dos versiones.
- SED: el de la NDS española (mismo formato de pistas; sus notas son más largas para las frases
  españolas) con la versión/fecha de cabecera japonesa (0x0c-0x1f).
- Ojo: el SWD NDS alinea sus chunks a 16 B (sonido.chunks_nds de v13 no lo hacía; aquí se corrige).
3D_901 (voz del título): v13 puso en silencio 9, 16 y 17 y rehízo seq2 = 8+10+11. La NDS no tiene
  16/17 (solo existen en 3DS; la NDS quitó la 9). Se restauran los CWAV japoneses de 16 y 17 y
  seq2 = 8 (español) + 16 + 17 con las duraciones japonesas (la 9, subtítulo japonés, sigue fuera).
Salida: romfs_mod/inazuma2/data_iz/sound/sound.pb, sound.ph, sound.ph_, informe.json, escucha/.
Uso: python -X utf8 apply.py
"""
from __future__ import annotations

import hashlib
import json
import shutil
import struct
import sys
import wave
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
V13 = HERE.parents[1] / 'v13' / 'voz_titulo'
sys.path.insert(0, str(V13))
import importlib.util  # noqa: E402
_spec = importlib.util.spec_from_file_location('v13_apply', V13 / 'apply.py')
V = importlib.util.module_from_spec(_spec)  # v13: cwav, swd_nuevo, escribir_wav
_spec.loader.exec_module(V)
import sonido as SN  # noqa: E402

W = V.W
SONIDO_JP = V.SONIDO_JP
SONIDO_ES = V.SONIDO_ES
SONIDO_V13 = V13 / 'romfs_mod/inazuma2/data_iz/sound'
INSTALADO = W / 'shared/candidatas/probe_ie2_v18/romfs/inazuma2/data_iz/sound'
SALIDA = HERE / 'romfs_mod/inazuma2/data_iz/sound'

NOTA_16 = bytes.fromhex('7f677292 72'.replace(' ', ''))   # tecla 91 (muestra 16), 114 ticks, pausa 114
NOTA_17 = bytes.fromhex('7f696080')                        # tecla 93 (muestra 17), 96 ticks, pausa 1


def chunks_nds(d):
    out, p = {}, 0x50
    while p + 16 <= len(d):
        tag = d[p:p + 4]
        ln = struct.unpack_from('<I', d, p + 12)[0]
        out[tag.decode('latin1')] = (p + 16, ln)
        if tag not in (b'wavi', b'prgi', b'kgrp', b'pcmd'):
            break
        p += 16 + ln
        p += -p % 16
    return out


SN.chunks_nds = chunks_nds


def leer_ph(carpeta):
    return SN.leer_3ds(carpeta)


def banco_003(nombre, jd, es, info):
    sed_jp, swd_jp = jd[nombre + '.SED'], jd[nombre + '.SWD']
    sed_es, swd_es = es[(nombre + '.SED').upper()], es[(nombre + '.SWD').upper()]
    _, ej = SN.muestras_3ds(swd_jp)
    _, ee = SN.muestras_nds(swd_es)
    assert [x['id'] for x in ej] == [x['id'] for x in ee], nombre
    assert SN.prgi_teclas(swd_jp) == SN.prgi_teclas(swd_es, nds=True), nombre
    cw, det = {}, {}
    for j, e in zip(ej, ee):
        assert e['fmt'] == 0x200 and e['rate'] == V.RATE_3DS, (nombre, e['id'], e['fmt'], e['rate'])
        pcm = np.array(SN.ima_nds(e['data']), dtype=np.int16)
        cw[j['id']] = V.cwav(j['cwav'], pcm)
        det[j['id']] = dict(seg_jp=round(j['muestras'] / V.RATE_3DS, 3), seg_es=round(len(pcm) / V.RATE_3DS, 3))
        if nombre in ('3D_003_01', '3D_003_31'):
            V.escribir_wav(HERE / 'escucha' / f'{nombre}_{j["id"]}.wav', pcm, V.RATE_3DS)
    swd = V.swd_nuevo(swd_jp, cw)
    sed = bytearray(sed_es)
    sed[0x0c:0x20] = sed_jp[0x0c:0x20]
    info[nombre] = dict(muestras=det, sed_jp=len(sed_jp), sed=len(sed), swd_jp=len(swd_jp), swd=len(swd))
    return bytes(sed), swd


def banco_901(v13, jd, info):
    sed_v, swd_v = v13['3D_901.SED'], v13['3D_901.SWD']
    _, ej = SN.muestras_3ds(jd['3D_901.SWD'])
    _, ev = SN.muestras_3ds(swd_v)
    jp = {x['id']: x['cwav'] for x in ej}
    cw = {x['id']: x['cwav'] for x in ev}
    cw[16], cw[17] = jp[16], jp[17]
    swd = V.swd_nuevo(swd_v, cw)
    seqs = SN.secuencias(sed_v)
    pistas = [s['eventos'] for s in seqs]
    corte = pistas[2].index(bytes.fromhex('a007')) + 2
    pistas[2] = pistas[2][:corte] + V.NOTA_8 + NOTA_16 + NOTA_17 + V.FIN
    sed = SN.montar_sed(sed_v, seqs, pistas)
    info['3D_901'] = dict(restauradas=[16, 17], seq2=SN.notas(SN.secuencias(sed)[2]['eventos']),
                          seq_jp2=SN.notas(SN.secuencias(jd['3D_901.SED'])[2]['eventos']))
    return sed, swd


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    for n in ('sound.pb', 'sound.ph'):
        assert (SONIDO_V13 / n).read_bytes() == (INSTALADO / n).read_bytes(), n
    idx_v, v13 = leer_ph(SONIDO_V13)
    _, jp = leer_ph(SONIDO_JP)
    jd, vd = dict(jp), dict(v13)
    es = SN.leer_nds(SONIDO_ES)
    info, nuevos = {}, {}
    for n in sorted({x[:-4] for x in jd if x.startswith('3D_003_')}):
        nuevos[n + '.SED'], nuevos[n + '.SWD'] = banco_003(n, jd, es, info)
    nuevos['3D_901.SED'], nuevos['3D_901.SWD'] = banco_901(vd, jd, info)

    pb, ph = bytearray(), bytearray()
    for n, b in v13:
        b = nuevos.get(n, b)
        ph += n.encode('ascii').ljust(24, b'\0') + struct.pack('<II', len(pb), len(b))
        pb += b
    assert len(ph) == len(idx_v)
    if (HERE / 'romfs_mod').exists():
        shutil.rmtree(HERE / 'romfs_mod')
    SALIDA.mkdir(parents=True)
    (SALIDA / 'sound.pb').write_bytes(pb)
    (SALIDA / 'sound.ph').write_bytes(ph)
    (SALIDA / 'sound.ph_').write_bytes(ph)
    informe = dict(bancos=info, cambiados=sorted(nuevos),
                   sha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(SALIDA.iterdir())},
                   riesgo='3D_901 16/17 vuelven a ser las japonesas (la NDS no las tiene). Sin identificar a oído '
                          'qué secuencia usa el anuncio: probar título de IE2, menú de la recopilación y un gol.')
    (HERE / 'informe.json').write_text(json.dumps(informe, ensure_ascii=False, indent=1), encoding='utf-8')
    print(len(nuevos), 'ficheros cambiados; pb', len(pb))


if __name__ == '__main__':
    main()
