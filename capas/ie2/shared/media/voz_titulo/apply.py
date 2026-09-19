"""IE2 v13 · voz_titulo: grito del título (banco 3D_901 de sound.pb) con la voz española de la NDS.

Hallazgos (comprobados en esta capa; detalle en informe.json):
- El título lo canta el banco 3D_901 (SED+SWD). ina_menu.cro carga 3D_900/3D_901 como en IE1, donde
  el grito es la muestra 3 de 3D_901 (la 3DS europea solo cambió esa muestra y quitó la 4).
- 3D_901.SED de IE2 3DS tiene 4 secuencias. Tras los efectos (teclas 0x3c-0x41, muestras 12-15), en
  la octava 7 suenan: seq0 = 8, 9, 10 (Fire); seq1 = 8, 9, 11 (Blizzard); seq2 = 8, 9, 16, 17 y
  seq3 = 8, 9 (las dos últimas solo existen en 3DS).
- La NDS española (sound/sp/sound.pkb) cambió las muestras 8, 10 y 11 («¡Inazuma Eleven 2!»,
  «¡Tormenta de Fuego!», «¡Ventisca Eterna!», IMA 4 bits a 24546 Hz), quitó la 9 (el subtítulo
  japonés) y alargó las notas: seq0 = 8 (255 ticks) + 10 (175); seq1 = 8 (255) + 11 (193).
  Las muestras 12-15 son las mismas que en 3DS (correlación 0,997 tras decodificar ambas).
- El SWD de 3DS (versión 0x480) guarda cada muestra como CWAV DSP-ADPCM a 32728 Hz; el de NDS (0x415)
  es IMA. Un SWD de DS no sirve tal cual: se reconstruye el SWD 3DS cambiando solo los CWAV.

Qué hace (solo el par 3D_901; las otras 864 entradas de sound.pb quedan idénticas):
- SWD: muestras 8/10/11 = PCM de la NDS (IMA decodificado) remuestreado ×4/3 (24546 -> 32728 Hz) y
  codificado en DSP-ADPCM con la misma cabecera CWAV que la japonesa. Muestras 9/16/17 = silencio
  corto (no queda japonés; wavi/prgi y sus teclas no cambian). Se recolocan las posiciones (+0x24 de
  wavi), la longitud de pcmd y el tamaño del fichero.
- SED: seq0/seq1 = pistas de la NDS española byte a byte; seq2 = 8 + 10 + 11 (mismas duraciones que
  la NDS); seq3 = 8. Cabecera, cabeceras de secuencia y eoc japoneses; tabla de punteros y tamaños
  recalculados.
- Salida LayeredFS: romfs_mod/inazuma2/data_iz/sound/sound.pb, sound.ph y sound.ph_ (índice idéntico
  en .ph y .ph_, como la base). También se deja el par suelto en par/ y las escuchas en escucha/.

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
from scipy.signal import resample_poly

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[5]
sys.path.insert(0, str(HERE))
import dsp_adpcm as D  # noqa: E402
import sonido as SN  # noqa: E402

W = ROOT / 'work'
SONIDO_JP = W / 'shared/base_3ds/romfs/inazuma2/data_iz/sound'
SONIDO_ES = W / 'ie2/tormenta_de_fuego/fuentes/nds_es/data_iz/sound/sp'
CANDIDATA = W / 'shared/candidatas/probe_ie2_v10'
SALIDA = HERE / 'romfs_mod/inazuma2/data_iz/sound'
BANCO = '3D_901'
RATE_ES, RATE_3DS = 24546, 32728
VOCES = {8: 8, 10: 10, 11: 11}          # muestra 3DS <- muestra NDS española
SILENCIO = (9, 16, 17)
N_SILENCIO = 700                          # 21 ms

# Pistas: prefijo japonés hasta «a0 07» (octava 7) + notas españolas.
NOTA_8 = bytes.fromhex('7f60ff92ff')      # tecla 0x54 (muestra 8), 255 ticks + pausa 255
NOTA_10 = bytes.fromhex('7f64af92af')     # tecla 0x58 (muestra 10), 175 ticks (NDS)
NOTA_11 = bytes.fromhex('7f65c192c1')     # tecla 0x59 (muestra 11), 193 ticks (NDS)
FIN = b'\x98'


def pcm_es(swd_es, sid):
    _, ents = SN.muestras_nds(swd_es)
    e = next(x for x in ents if x['id'] == sid)
    assert e['fmt'] == 0x200 and e['rate'] == RATE_ES, (sid, e['fmt'], e['rate'])
    pcm = np.array(SN.ima_nds(e['data']), dtype=np.float64)
    up = resample_poly(pcm, 4, 3)
    return np.clip(np.round(up), -32768, 32767).astype(np.int16), len(pcm)


def cwav(plantilla: bytes, pcm) -> bytes:
    """CWAV mono DSP-ADPCM con la cabecera de `plantilla` (la japonesa de la misma muestra)."""
    muestras = [int(v) for v in pcm]
    datos, coefs, ps = D.codificar(muestras)
    cuerpo = datos + b'\0' * (-len(datos) % 4)
    total = 0xE0 + len(cuerpo)
    b = bytearray(plantilla[:0xE0])
    assert b[:4] == b'CWAV' and b[0x40:0x44] == b'INFO' and b[0xC0:0xC4] == b'DATA'
    assert b[0x48] == 2 and b[0x49] == 0
    struct.pack_into('<I', b, 0x0C, total)
    struct.pack_into('<I', b, 0x28, total - 0xC0)            # referencia al bloque DATA (0x7001, 0xC0, tamaño)
    struct.pack_into('<IIII', b, 0x4C, RATE_3DS, 0, len(muestras), 0)
    for k, (c1, c2) in enumerate(coefs):
        struct.pack_into('<hh', b, 0x7C + 4 * k, c1, c2)
    struct.pack_into('<Hhh', b, 0x9C, ps, 0, 0)              # contexto inicial
    struct.pack_into('<Hhh', b, 0xA2, ps, 0, 0)              # contexto de bucle (sin bucle: igual)
    struct.pack_into('<I', b, 0xC4, total - 0xC0)
    return bytes(b) + cuerpo


def swd_nuevo(swd_jp: bytes, cwavs: dict) -> bytes:
    ch, ents = SN.muestras_3ds(swd_jp)
    po, pl = ch['pcmd']
    wo, _ = ch['wavi']
    pcmd = bytearray()
    out = bytearray(swd_jp[:po])
    for e in sorted(ents, key=lambda x: x['pos']):
        blob = cwavs.get(e['id'], e['cwav'])
        pos = len(pcmd)
        pcmd += blob + b'\0' * (-len(blob) % 32)
        struct.pack_into('<I', out, wo + e['ptr'] + 0x24, pos)
    struct.pack_into('<I', out, 0x08, po + len(pcmd))
    struct.pack_into('<I', out, 0x40, len(pcmd))
    fila = SN.fila_chunk(swd_jp, b'pcmd')
    struct.pack_into('<I', out, fila + 12, len(pcmd))
    return bytes(out) + bytes(pcmd)


def sed_nuevo(sed_jp: bytes, sed_es: bytes) -> bytes:
    seq_jp = SN.secuencias(sed_jp)
    seq_es = SN.secuencias(sed_es)
    assert len(seq_jp) == 4 and len(seq_es) == 2
    pistas = []
    for k, s in enumerate(seq_jp):
        ev = s['eventos']
        corte = ev.index(bytes.fromhex('a007')) + 2          # octava 7: empiezan las voces
        pref = ev[:corte]
        if k < 2:
            nuevo = seq_es[k]['eventos']
            assert nuevo[:corte] == pref, k                   # mismos efectos que la japonesa
        elif k == 2:
            nuevo = pref + NOTA_8 + NOTA_10 + NOTA_11 + FIN
        else:
            nuevo = pref + NOTA_8 + FIN
        pistas.append(nuevo)
    return SN.montar_sed(sed_jp, seq_jp, pistas)


def escribir_wav(ruta, pcm, rate):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(ruta), 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(np.asarray(pcm, dtype='<i2').tobytes())


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    # la candidata instalada no debe traer ya un sound.pb propio (esta capa parte de la base)
    assert not (CANDIDATA / 'romfs/inazuma2/data_iz/sound/sound.pb').exists()
    idx_jp, jp = SN.leer_3ds(SONIDO_JP)
    es = SN.leer_nds(SONIDO_ES)
    nombres = {n: b for n, b in jp}
    sed_jp, swd_jp = nombres[BANCO + '.SED'], nombres[BANCO + '.SWD']
    sed_es, swd_es = es[BANCO + '.SED'], es[BANCO + '.SWD']
    _, ents_jp = SN.muestras_3ds(swd_jp)
    por_id = {e['id']: e for e in ents_jp}

    cwavs, info = {}, {}
    for sid, sid_es in VOCES.items():
        pcm, n_es = pcm_es(swd_es, sid_es)
        cwavs[sid] = cwav(por_id[sid]['cwav'], pcm)
        escribir_wav(HERE / 'escucha' / f'{BANCO}_{sid:02d}_es_32728.wav', pcm, RATE_3DS)
        np.save(HERE / 'escucha' / f'{BANCO}_{sid:02d}_fuente.npy', pcm)
        info[sid] = dict(origen=f'NDS ES {BANCO}.SWD muestra {sid_es}', muestras_nds=n_es,
                         muestras_3ds=len(pcm), segundos=round(len(pcm) / RATE_3DS, 3),
                         segundos_jp=round(por_id[sid]['muestras'] / RATE_3DS, 3),
                         bytes_cwav=len(cwavs[sid]), md5_jp=hashlib.md5(por_id[sid]['cwav']).hexdigest())
    for sid in SILENCIO:
        cwavs[sid] = cwav(por_id[sid]['cwav'], np.zeros(N_SILENCIO, dtype=np.int16))
        info[sid] = dict(origen='silencio', muestras_3ds=N_SILENCIO,
                         segundos_jp=round(por_id[sid]['muestras'] / RATE_3DS, 3),
                         md5_jp=hashlib.md5(por_id[sid]['cwav']).hexdigest())

    swd = swd_nuevo(swd_jp, cwavs)
    sed = sed_nuevo(sed_jp, sed_es)

    # sound.pb / .ph con solo el par cambiado (mismo orden, contiguo, como bancos.probar de v07)
    pb, ph = bytearray(), bytearray()
    for n, b in jp:
        b = {BANCO + '.SED': sed, BANCO + '.SWD': swd}.get(n, b)
        ph += n.encode('ascii').ljust(24, b'\0') + struct.pack('<II', len(pb), len(b))
        pb += b
    assert len(ph) == len(idx_jp)
    if (HERE / 'romfs_mod').exists():
        shutil.rmtree(HERE / 'romfs_mod')
    SALIDA.mkdir(parents=True)
    (SALIDA / 'sound.pb').write_bytes(pb)
    (SALIDA / 'sound.ph').write_bytes(ph)
    (SALIDA / 'sound.ph_').write_bytes(ph)
    par = HERE / 'par'
    par.mkdir(exist_ok=True)
    (par / f'{BANCO}.SED').write_bytes(sed)
    (par / f'{BANCO}.SWD').write_bytes(swd)
    for n, b in ((f'{BANCO}_jp.SED', sed_jp), (f'{BANCO}_jp.SWD', swd_jp), (f'{BANCO}_nds.SED', sed_es),
                 (f'{BANCO}_nds.SWD', swd_es)):
        (par / n).write_bytes(b)

    informe = dict(
        banco=BANCO, muestras=info,
        secuencias_jp=[SN.notas(s['eventos']) for s in SN.secuencias(sed_jp)],
        secuencias_nds=[SN.notas(s['eventos']) for s in SN.secuencias(sed_es)],
        secuencias_nuevas=[SN.notas(s['eventos']) for s in SN.secuencias(sed)],
        bytes=dict(sed_jp=len(sed_jp), sed=len(sed), swd_jp=len(swd_jp), swd=len(swd),
                   pb_jp=sum(len(b) for _, b in jp), pb=len(pb)),
        sha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(SALIDA.iterdir())},
        instalar='LayeredFS: copiar romfs_mod/inazuma2/data_iz/sound/{sound.pb,sound.ph,sound.ph_} a '
                 'romfs/inazuma2/data_iz/sound/ de la candidata (junto a los SAD de v07).',
        riesgo='seq2 (8, 9, 16, 17) solo existe en 3DS; 16/17 no se pudieron identificar sin escucharlas. '
               'Se canta 8 + 10 + 11. Probar el título de Fuego y el menú de la recopilación.')
    (HERE / 'informe.json').write_text(json.dumps(informe, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(dict(bytes=informe['bytes'], nuevas=informe['secuencias_nuevas']), ensure_ascii=False))


if __name__ == '__main__':
    main()
