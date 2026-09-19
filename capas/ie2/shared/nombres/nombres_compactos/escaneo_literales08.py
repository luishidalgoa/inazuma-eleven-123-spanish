"""v08 · literales en code.bin y CRO (copia de work/ie1/capas/fuentes/bigramas_ritmo/escaneo_literales.py con las
CRO de probe_ie2_v05 en lugar de las de probe_ie1_v88): un código candidato que aparezca alineado dentro de
una cadena C (ASCII imprimible o Shift-JIS válido) queda descartado.
Uso: python -X utf8 escaneo_literales08.py <codigos.txt (coma)> <salida.json>"""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[5]
sys.path.insert(0, str(ROOT / 'tools/src'))
sys.path.insert(0, str(ROOT / 'work/ie1/capas/fuentes/bigramas_ritmo'))
base = ROOT / 'work/shared/base_3ds'
fuentes = {}
for f in sorted((base / 'romfs/cro').glob('*.cr?')):
    fuentes['base_3ds/cro/' + f.name] = f.read_bytes()
for f in sorted((ROOT / 'work/shared/candidatas/probe_ie2_v05/romfs/cro').glob('*.cr?')):
    fuentes['v05/cro/' + f.name] = f.read_bytes()
code = (base / 'exefs/code.bin').read_bytes()
try:
    from ie123kit.nucleo.compresion import blz
    code = blz.decompress(code)
except Exception as ex:
    print('code.bin sin BLZ', ex)
fuentes['code.bin'] = code


def valido2(a, b):
    return (0x81 <= a <= 0x9F or 0xE0 <= a <= 0xFC) and (0x40 <= b <= 0xFC and b != 0x7F)


def en_cadena(buf, p):
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


codigos = [c for c in Path(sys.argv[1]).read_text().split(',') if c]
cand = np.array(sorted(int(c, 16) for c in codigos), dtype=np.uint16)
res = {c: {} for c in codigos}
for nombre, buf in fuentes.items():
    a = np.frombuffer(buf, dtype=np.uint8).astype(np.uint16)
    w = (a[:-1] << 8) | a[1:]
    for p in np.nonzero(np.isin(w, cand))[0].tolist():
        if en_cadena(buf, p):
            c = f'{w[p]:04X}'
            res[c][nombre] = res[c].get(nombre, 0) + 1
Path(sys.argv[2]).write_text(json.dumps(res, indent=1))
print('con literales', sum(1 for v in res.values() if v), 'de', len(res))
