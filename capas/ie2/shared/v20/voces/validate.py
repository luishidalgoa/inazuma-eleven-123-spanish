"""Valida v20/voces: índice coherente, entradas no tocadas idénticas a v13, .ph == .ph_, cada SWD
cambiado con sus CWAV decodificables (nº de muestras de la cabecera = PCM de origen, SNR frente a la
NDS) y SED con tamaño de cabecera correcto; 3D_901 con 16/17 japonesas y seq2 = 8 + 16 + 17."""
import json
import struct
import sys

import numpy as np

import apply as A

SN, V = A.SN, A.V
D = V.D


def dec(cw):
    coefs = [struct.unpack_from('<hh', cw, 0x7C + 4 * k) for k in range(8)]
    n = struct.unpack_from('<I', cw, 0x54)[0]
    return np.array(D.decodificar(cw[0xE0:], coefs, n), float)


def main():
    err = []
    ph = (A.SALIDA / 'sound.ph').read_bytes()
    if ph != (A.SALIDA / 'sound.ph_').read_bytes():
        err.append('ph != ph_')
    _, nuevo = SN.leer_3ds(A.SALIDA)
    _, v13 = SN.leer_3ds(A.SONIDO_V13)
    _, jp = SN.leer_3ds(A.SONIDO_JP)
    jd, vd = dict(jp), dict(v13)
    es = SN.leer_nds(A.SONIDO_ES)
    if [n for n, _ in nuevo] != [n for n, _ in v13]:
        err.append('orden/nombres del índice')
    snr, cambiados = {}, 0
    for n, b in nuevo:
        if b == vd[n]:
            continue
        cambiados += 1
        if not (n.startswith('3D_003_') or n.startswith('3D_901')):
            err.append(f'{n}: cambio no previsto')
        if struct.unpack_from('<I', b, 8)[0] != len(b):
            err.append(f'{n}: tamaño de cabecera')
        if n.endswith('.SWD'):
            _, ents = SN.muestras_3ds(b)
            _, ej = SN.muestras_3ds(jd[n])
            if [e['id'] for e in ents] != [e['id'] for e in ej]:
                err.append(f'{n}: ids')
            if n.startswith('3D_003_'):
                _, ee = SN.muestras_nds(es[n.upper()])
                for e, s in zip(ents, ee):
                    ref = np.array(SN.ima_nds(s['data']), float)
                    got = dec(e['cwav'])
                    if len(got) != len(ref):
                        err.append(f'{n}:{e["id"]}: {len(got)} != {len(ref)} muestras')
                        continue
                    r = 10 * np.log10((ref ** 2).sum() / max(((ref - got) ** 2).sum(), 1))
                    snr[f'{n}:{e["id"]}'] = round(r, 1)
                    if r < 15:
                        err.append(f'{n}:{e["id"]}: SNR {r:.1f} dB')
            else:
                c = {e['id']: e['cwav'] for e in ents}
                cj = {e['id']: e['cwav'] for e in ej}
                if c[16] != cj[16] or c[17] != cj[17]:
                    err.append('3D_901: 16/17 no son las japonesas')
        elif n == '3D_901.SED':
            notas = SN.notas(SN.secuencias(b)[2]['eventos'])
            teclas = [x[1] for x in notas if x[0] != 'fin' and x[1] >= 84]
            if teclas != [84, 91, 93]:
                err.append(f'3D_901 seq2 {teclas}')
    res = dict(cambiados=cambiados, snr_min=min(snr.values()) if snr else None, errores=err, ok=not err)
    (A.HERE / 'validacion.json').write_text(json.dumps(dict(res, snr=snr), indent=1), encoding='utf-8')
    print(json.dumps(res))
    sys.exit(1 if err else 0)


if __name__ == '__main__':
    main()
