"""v89 · literales en code.bin y CRO: busca cada código candidato (alineado a partir de cualquier inicio
posible) dentro de una cadena NUL-terminada formada solo por ASCII imprimible/\n y dobles bytes Shift-JIS
válidos. Cualquier aparición así (aunque sea un kanji suelto, sin kana) descarta el código.
Complementa el escaneo estricto de v88 (que en binarios solo contaba rachas con kana).
Uso: python -X utf8 escaneo_literales.py <codigos.json> <salida.json>"""
import json, re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / 'tools/src'))
base = ROOT / 'work/shared/base_3ds'
fuentes = {}
for f in sorted((base / 'romfs/cro').glob('*.cr?')):
    fuentes['base_3ds/cro/' + f.name] = f.read_bytes()
cand_cro = ROOT / 'work/shared/candidatas/probe_ie1_v88/romfs/cro'
for f in sorted(cand_cro.glob('*.cr?')):
    fuentes['v88/cro/' + f.name] = f.read_bytes()
code = (base / 'exefs/code.bin').read_bytes()
try:
    from ie123kit.nucleo.compresion import blz
    dec = blz.decompress(code)
except Exception as ex:
    print('code.bin sin BLZ', ex)
    dec = code
fuentes['code.bin'] = dec
print({k: len(v) for k, v in fuentes.items()})

def valido2(a, b):
    return (0x81 <= a <= 0x9F or 0xE0 <= a <= 0xFC) and (0x40 <= b <= 0xFC and b != 0x7F)

def en_cadena(buf, p):
    """¿p (inicio de código) está en una cadena C: desde el byte siguiente a un NUL (<= 256 B atrás) hasta
    el NUL siguiente (<= 512 B), todo ASCII imprimible/\t/\n o doble byte Shift-JIS válido, y p alineado?"""
    z = buf.rfind(b'\0', max(0, p - 256), p)
    if z < 0:
        return False
    i = z + 1
    while i < p:
        b = buf[i]
        if 0x20 <= b <= 0x7E or b in (0x0A, 0x09):
            i += 1
        elif i + 1 < len(buf) and valido2(b, buf[i + 1]):
            i += 2
        else:
            return False
    if i != p:
        return False
    j = p
    while j < len(buf) and j - p < 512:
        b = buf[j]
        if b == 0:
            return True
        if 0x20 <= b <= 0x7E or b in (0x0A, 0x09):
            j += 1
        elif j + 1 < len(buf) and valido2(b, buf[j + 1]):
            j += 2
        else:
            return False
    return False

import numpy as np
codigos = json.loads(Path(sys.argv[1]).read_text())
cand = np.array(sorted(int(c, 16) for c in codigos), dtype=np.uint16)
res = {c: {} for c in codigos}
for nombre, buf in fuentes.items():
    a = np.frombuffer(buf, dtype=np.uint8).astype(np.uint16)
    w = (a[:-1] << 8) | a[1:]
    pos = np.nonzero(np.isin(w, cand))[0]
    n = 0
    for p in pos.tolist():
        if en_cadena(buf, p):
            c = f'{w[p]:04X}'
            res[c][nombre] = res[c].get(nombre, 0) + 1
            n += 1
    print(nombre, 'apariciones', len(pos), 'en cadena', n, flush=True)
Path(sys.argv[2]).write_text(json.dumps(res, indent=1))
print('con literales', sum(1 for v in res.values() if v), 'de', len(res))
