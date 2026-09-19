"""IE2 v13 · voz_titulo: validación de romfs_mod/.../sound.pb (solo cambia el par 3D_901).

Comprueba:
1. sound.ph == sound.ph_; mismo orden y nombres que la base; contiguo; 864 entradas idénticas.
2. SWD: cabecera, prgi, kgrp y entradas wavi iguales a la japonesa salvo tamaños y posiciones; tabla
   de chunks coherente; CWAV válidos (DSP-ADPCM mono, 32728 Hz, tamaños), alineados a 32 B y contiguos.
3. Ninguna muestra de voz japonesa (8, 9, 10, 11, 16, 17) sigue en el banco; efectos 12-15 idénticos.
4. Cada CWAV nuevo se decodifica con vgmstream con el número de muestras declarado y SNR >= 25 dB
   frente al PCM español remuestreado (y con el decodificador propio); los de silencio salen a cero.
5. SED: cabeceras y eoc japoneses; seq0/seq1 = pistas NDS españolas; todas las teclas de voz apuntan a
   muestras españolas (prgi); ninguna toca las teclas 0x56/0x5b/0x5d; cada nota de voz dura al menos
   lo que su muestra (96 ticks/s, la relación de las notas NDS: 175 ticks = 1,82 s).
Salida: validacion.json. Código 1 si algo falla.
Uso: python -X utf8 validate.py
"""
from __future__ import annotations

import hashlib
import json
import struct
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import apply as A  # noqa: E402
import dsp_adpcm as D  # noqa: E402
import sonido as SN  # noqa: E402

VGM = A.W / 'shared/herramientas/media_tools/vgmstream-nightly-win64/vgmstream-cli.exe'
TICKS_S = 96
TECLAS_JP = {0x56, 0x5B, 0x5D}


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    fallos, res = [], {}

    def ok(cond, msg):
        if not cond:
            fallos.append(msg)

    idx_jp, jp = SN.leer_3ds(A.SONIDO_JP)
    ph = (A.SALIDA / 'sound.ph').read_bytes()
    ok(ph == (A.SALIDA / 'sound.ph_').read_bytes(), 'ph != ph_')
    nuevo = SN.leer_3ds(A.SALIDA)[1]
    ok([n for n, _ in nuevo] == [n for n, _ in jp], 'orden/nombres distintos')
    pos = 0
    for i in range(0, len(ph), 32):
        o, s = struct.unpack_from('<II', ph, i + 24)
        ok(o == pos, f'no contiguo en {i // 32}')
        pos += s
    ok(pos == (A.SALIDA / 'sound.pb').stat().st_size, 'tamaño de sound.pb')
    distintos = [n for (n, a), (_, b) in zip(jp, nuevo) if a != b]
    ok(sorted(distintos) == ['3D_901.SED', '3D_901.SWD'], f'cambian {distintos}')
    res['entradas'] = len(jp)
    res['cambian'] = distintos
    J, N = dict(jp), dict(nuevo)
    swd_jp, swd = J['3D_901.SWD'], N['3D_901.SWD']
    sed_jp, sed = J['3D_901.SED'], N['3D_901.SED']

    # 2. estructura SWD --------------------------------------------------------------------------
    ch_jp, e_jp = SN.muestras_3ds(swd_jp)
    ch, e_new = SN.muestras_3ds(swd)
    po = ch['pcmd'][0]
    ok(po == ch_jp['pcmd'][0], 'pcmd movido')
    ok(struct.unpack_from('<I', swd, 0x08)[0] == len(swd), 'tamaño SWD')
    ok(struct.unpack_from('<I', swd, 0x40)[0] == ch['pcmd'][1] == len(swd) - po, 'tamaño pcmd')
    for k in ('wavi', 'prgi', 'kgrp'):
        a, b = ch_jp[k], ch[k]
        ok(a == b, f'chunk {k} movido')
        if k != 'wavi':      # wavi cambia solo en las posiciones (se compara abajo)
            ok(swd_jp[a[0]:a[0] + a[1]] == swd[b[0]:b[0] + b[1]], f'chunk {k} cambia')
    base = bytearray(swd[:po])
    for e in e_new:
        struct.pack_into('<I', base, ch['wavi'][0] + e['ptr'] + 0x24, 0)
    ref = bytearray(swd_jp[:po])
    for e in e_jp:
        struct.pack_into('<I', ref, ch_jp['wavi'][0] + e['ptr'] + 0x24, 0)
    for o in (0x08, 0x40, SN.fila_chunk(swd_jp, b'pcmd') + 12):
        struct.pack_into('<I', base, o, 0)
        struct.pack_into('<I', ref, o, 0)
    ok(base == ref, 'cabecera SWD distinta además de tamaños/posiciones')
    ok([(e['hueco'], e['id']) for e in e_new] == [(e['hueco'], e['id']) for e in e_jp], 'huecos wavi')
    esperado = 0
    for e in sorted(e_new, key=lambda x: x['pos']):
        ok(e['pos'] == esperado, f"posición muestra {e['id']}")
        cw = e['cwav']
        ok(cw[:4] == b'CWAV' and cw[0x40:0x44] == b'INFO' and cw[0xC0:0xC4] == b'DATA', f"CWAV {e['id']}")
        ok(cw[0x48] == 2 and cw[0x49] == 0 and e['rate'] == A.RATE_3DS, f"formato CWAV {e['id']}")
        ok(struct.unpack_from('<I', cw, 0x5C)[0] == 1, f"canales {e['id']}")
        ok(struct.unpack_from('<I', cw, 0x0C)[0] == len(cw), f"tamaño CWAV {e['id']}")
        ok(struct.unpack_from('<HHII', cw, 0x14) == (0x7000, 0, 0x40, 0x80), f"ref INFO {e['id']}")
        ok(struct.unpack_from('<HHIII', cw, 0x20) == (0x7001, 0, 0xC0, len(cw) - 0xC0, 0), f"ref DATA {e['id']}")
        ok(struct.unpack_from('<I', cw, 0xC4)[0] == len(cw) - 0xC0, f"bloque DATA {e['id']}")
        ok(cw[0x9C] == cw[0xE0] and cw[0xA2] == cw[0xE0], f"contexto inicial {e['id']}")
        nb = (e['muestras'] + 13) // 14 * 8
        ok(len(cw) == 0xE0 + nb + (-nb % 4), f"bytes ADPCM {e['id']}")
        esperado = e['pos'] + len(cw) + (-len(cw) % 32)
    ok(esperado == ch['pcmd'][1], 'final de pcmd')

    # 3. nada japonés ----------------------------------------------------------------------------
    md5 = lambda b: hashlib.md5(b).hexdigest()
    nuevos = {e['id']: e for e in e_new}
    viejos = {e['id']: e for e in e_jp}
    for sid in (8, 9, 10, 11, 16, 17):
        ok(md5(viejos[sid]['cwav']) not in {md5(e['cwav']) for e in e_new}, f'muestra japonesa {sid}')
    for sid in (12, 13, 14, 15):
        ok(nuevos[sid]['cwav'] == viejos[sid]['cwav'], f'efecto {sid} cambiado')

    # 4. decodificación --------------------------------------------------------------------------
    dec = {}
    with tempfile.TemporaryDirectory() as td:
        for sid in (8, 9, 10, 11, 16, 17):
            cw = nuevos[sid]['cwav']
            f = Path(td) / f'{sid}.bcwav'
            f.write_bytes(cw)
            r = subprocess.run([str(VGM), '-o', str(f.with_suffix('.wav')), str(f)], capture_output=True)
            ok(r.returncode == 0, f'vgmstream {sid}')
            with wave.open(str(f.with_suffix('.wav'))) as w:
                ok(w.getframerate() == A.RATE_3DS and w.getnchannels() == 1, f'wav {sid}')
                x = np.frombuffer(w.readframes(w.getnframes()), '<i2').astype(float)
            ok(len(x) == nuevos[sid]['muestras'], f'muestras vgmstream {sid}')
            coefs = [struct.unpack_from('<hh', cw, 0x7C + 4 * k) for k in range(8)]
            propio = np.array(D.decodificar(cw[0xE0:], coefs, nuevos[sid]['muestras']), float)
            ok(np.array_equal(propio, x), f'decodificador propio != vgmstream en {sid}')
            if sid in A.VOCES:
                src = np.load(HERE / 'escucha' / f'3D_901_{sid:02d}_fuente.npy').astype(float)
                ok(len(src) == len(x), f'longitud {sid}')
                snr = 10 * np.log10((src ** 2).sum() / max(((src - x) ** 2).sum(), 1e-9))
                ok(snr >= 25, f'SNR {sid} = {snr:.1f}')
                dec[sid] = dict(segundos=round(len(x) / A.RATE_3DS, 3), snr_db=round(float(snr), 1))
            else:
                ok(not np.any(x), f'silencio {sid} no es cero')
                dec[sid] = dict(silencio=len(x))
    res['decodificacion'] = dec

    # 5. SED -------------------------------------------------------------------------------------
    sj, sn = SN.secuencias(sed_jp), SN.secuencias(sed)
    se = SN.secuencias(SN.leer_nds(A.SONIDO_ES)['3D_901.SED'])
    ok(struct.unpack_from('<I', sed, 0x08)[0] == len(sed) == sn[-1]['fin'], 'tamaño SED')
    ok(sed[:0x08] + sed[0x0C:0x74A] == sed_jp[:0x08] + sed_jp[0x0C:0x74A], 'cabecera SED')
    ok(len(sn) == 4, 'número de secuencias')
    for a, b in zip(sj, sn):
        ok(a['cabecera'] == b['cabecera'] and a['eoc'] == b['eoc'] and a['preambulo'] == b['preambulo'],
           f"secuencia {a['ptr']:#x}")
        ok(a['trk'][:12] == b['trk'][:12], 'cabecera trk')
    for k in (0, 1):
        ok(sn[k]['eventos'] == se[k]['eventos'], f'seq{k} != NDS')
    teclas = SN.prgi_teclas(swd)
    ok(teclas == SN.prgi_teclas(swd_jp), 'prgi')
    dur_muestra = {e['id']: e['muestras'] / A.RATE_3DS for e in e_new}
    notas_res = []
    for k, s in enumerate(sn):
        ns = SN.notas(s['eventos'])
        voces = [n for n in ns if n[0] != 'fin' and n[1] >= 84]
        ok(voces and voces[0][1] == 0x54, f'seq{k} no empieza por la muestra 8')
        for t, tecla, vel, dur in voces:
            sid = teclas.get(tecla)
            ok(tecla not in TECLAS_JP, f'seq{k} toca la tecla japonesa {tecla:#x}')
            ok(sid in A.VOCES, f'seq{k} tecla {tecla:#x} -> muestra {sid}')
            ok(dur / TICKS_S + 0.01 >= dur_muestra[sid], f'seq{k} nota {sid} corta ({dur} ticks)')
        notas_res.append([dict(tick=n[0], tecla=hex(n[1]), muestra=teclas.get(n[1]), ticks=n[3])
                          for n in ns if n[0] != 'fin'])
    res['secuencias'] = notas_res
    res['sha256'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(A.SALIDA.iterdir())}
    res['fallos'] = fallos
    res['resultado'] = 'PASS' if not fallos else 'FAIL'
    (HERE / 'validacion.json').write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(dict(resultado=res['resultado'], fallos=fallos, decodificacion=dec), ensure_ascii=False))
    return 0 if not fallos else 1


if __name__ == '__main__':
    sys.exit(main())
