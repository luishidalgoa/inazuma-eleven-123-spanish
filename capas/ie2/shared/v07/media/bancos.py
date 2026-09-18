"""IE2 v07 · media: bancos de sonido sound.pb (SED/SWD/SMD) — inventario y pruebas de par en par (issue #74).

No se sustituyen en bloque (skill volcado-rom-nds §10). Formatos:
- 3DS romfs/inazuma2/data_iz/sound/sound.ph (= sound.ph_): registros de 32 B = nombre 24 B + offset + tamaño
  en sound.pb (contiguos, sin relleno).
- NDS sound/sp/sound.pkh: registros de 16 B (hash, offset, tamaño, 0) en sound.pkb; cada registro agrupa
  1-2 ficheros tras una tabla (offset, tamaño) relativa; el nombre va en la cabecera SEDL/SWDL/SMDL (+0x20).
- Diferencias: SWDL versión 0x480 en 3DS frente a 0x415 en DS y los SWD 3DS pesan ~1,156x (recodificados).
  Por eso un SWD de la DS podría no cargar: probar primero un solo par.
Candidatos a voz localizada: los SWD cuya relación de tamaño 3DS/NDS se aparta de la mediana (el contenido
cambió, no solo la codificación): 3D_003_* (gritos/goles/técnicas) y 2D_020_*, más otros a revisar.

Uso:
  python -X utf8 bancos.py                      -> bancos.json (inventario y candidatos)
  python -X utf8 bancos.py --probar 3D_003_01   -> pruebas_bancos/3D_003_01/romfs_mod/.../sound.pb, .ph, .ph_
     (sustituye SOLO ese par SED/SWD por el de la NDS; no se instala ni se incluye en romfs_mod/)
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import struct
import sys

import comun_media as C


def leer_3ds():
    ph = (C.SONIDO_JP / 'sound.ph').read_bytes()
    pb = (C.SONIDO_JP / 'sound.pb').read_bytes()
    out = []
    for i in range(0, len(ph), 32):
        nombre = ph[i:i + 24].split(b'\0')[0].decode()
        o, s = struct.unpack_from('<II', ph, i + 24)
        out.append((nombre, pb[o:o + s]))
    return ph, out


def leer_nds():
    pkh = (C.SONIDO_ES / 'sound.pkh').read_bytes()
    pkb = (C.SONIDO_ES / 'sound.pkb').read_bytes()
    out = {}
    for i in range(0, len(pkh), 16):
        _h, o, s, _f = struct.unpack_from('<IIII', pkh, i)
        rec = pkb[o:o + s]
        for k in range(struct.unpack_from('<I', rec, 0)[0] // 8):
            so, ss = struct.unpack_from('<II', rec, 8 * k)
            blob = rec[so:so + ss]
            if blob[:4] not in (b'sedl', b'swdl', b'smdl'):
                raise ValueError(f'bloque desconocido en el registro {i // 16}')
            nombre = blob[0x20:0x30].split(b'\0')[0].split(b'\xff')[0].decode('ascii')
            out.setdefault(nombre.upper(), blob)
    return out


def version(b):
    return struct.unpack_from('<H', b, 0x0c)[0]


def inventario():
    _, jp = leer_3ds()
    nds = leer_nds()
    sw = [(n, b) for n, b in jp if n.upper().endswith('.SWD') and n.upper() in nds]
    rel = {n: len(b) / len(nds[n.upper()]) for n, b in sw}
    med = statistics.median(rel.values())
    cand = []
    for n, b in sw:
        r = rel[n]
        if abs(r / med - 1) > 0.05:
            base = n[:-4]
            tipo = ('gritos/goles (3D_003)' if base.upper().startswith('3D_003') else
                    'voces 2D (2D_020)' if base.upper().startswith('2D_020') else 'revisar')
            cand.append(dict(par=base, relacion=round(r, 3), tipo=tipo,
                             bytes_jp=len(b), bytes_nds=len(nds[n.upper()]),
                             swdl_version_jp=hex(version(b)), swdl_version_nds=hex(version(nds[n.upper()]))))
    orden = {'gritos/goles (3D_003)': 0, 'voces 2D (2D_020)': 1, 'revisar': 2}
    cand.sort(key=lambda c: (orden[c['tipo']], c['par']))
    nombres_jp = {n.upper() for n, _ in jp}
    return dict(
        entradas_3ds=len(jp), entradas_nds=len(nds),
        comunes=len(nombres_jp & set(nds)),
        identicas=sum(1 for n, b in jp if nds.get(n.upper()) == b),
        solo_3ds=sorted(n for n, _ in jp if n.upper() not in nds),
        solo_nds=sorted(set(nds) - nombres_jp),
        relacion_mediana_swd=round(med, 4),
        candidatos=cand,
        orden_de_prueba=[c['par'] for c in cand if c['tipo'] != 'revisar'][:3],
        nota='No instalar en bloque. Probar un par (SED+SWD) cada vez con --probar y escucharlo en su '
             'contexto (gol/técnica/grito) antes de pasar al siguiente.')


def probar(pares):
    ph, jp = leer_3ds()
    nds = leer_nds()
    pedidos = {p.upper() for p in pares}
    cambiados, pb, idx = [], bytearray(), bytearray()
    for n, b in jp:
        base = re.sub(r'\.(SED|SWD|SMD)$', '', n, flags=re.I).upper()
        nuevo = nds.get(n.upper()) if base in pedidos else None
        if nuevo is not None:
            cambiados.append(n)
            b = nuevo
        idx += n.encode('ascii').ljust(24, b'\0') + struct.pack('<II', len(pb), len(b))
        pb += b
    faltan = pedidos - {re.sub(r'\.(SED|SWD|SMD)$', '', c, flags=re.I).upper() for c in cambiados}
    if faltan:
        raise SystemExit(f'sin par en la NDS: {sorted(faltan)}')
    destino = C.SALIDA / 'pruebas_bancos' / '+'.join(sorted(pedidos)) / C.ROMFS_SONIDO
    destino.mkdir(parents=True, exist_ok=True)
    (destino / 'sound.pb').write_bytes(pb)
    (destino / 'sound.ph').write_bytes(idx)
    (destino / 'sound.ph_').write_bytes(idx)
    assert len(idx) == len(ph)
    print('sustituidos:', cambiados, '->', destino.relative_to(C.ROOT))


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser()
    ap.add_argument('--probar', help='pares separados por comas (p. ej. 3D_003_01)')
    a = ap.parse_args()
    if a.probar:
        probar(a.probar.split(','))
        return
    inv = inventario()
    (C.SALIDA / 'bancos.json').write_text(json.dumps(inv, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps({k: v for k, v in inv.items() if k != 'candidatos'}, ensure_ascii=False))
    print(len(inv['candidatos']), 'candidatos:', ' '.join(f"{c['par']}({c['relacion']})" for c in inv['candidatos']))


if __name__ == '__main__':
    main()
