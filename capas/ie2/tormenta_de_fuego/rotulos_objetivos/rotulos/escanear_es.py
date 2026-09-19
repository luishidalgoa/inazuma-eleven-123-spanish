"""IE2 Fuego v03 · rótulos: cadenas NDS ES con latín del DS (acentos) de arm9.dec y overlays.
Salida: cadenas_es.txt («fichero\toffset\ttexto»). Uso: python -X utf8 escanear_es.py"""
from pathlib import Path
import sys
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[5]
sys.path.insert(0, str(ROOT / 'tools/src'))
from ie123kit.nucleo.texto.nds_latin import NDS_DEC  # noqa: E402
BIN = ROOT / 'work/ie2/tormenta_de_fuego/fuentes/nds_es/bin'

def dec(c):
    if 0x20 <= c < 0x7F: return chr(c)
    if c == 0x0A: return '\n'
    v = NDS_DEC.get(c) if isinstance(NDS_DEC, dict) else None
    return v if isinstance(v, str) else None

def cadenas(nombre, d):
    out, i, n = [], 0, len(d)
    while i < n:
        j, s = i, []
        while j < n:
            c = d[j]
            if (0x81 <= c <= 0x9F or 0xE0 <= c <= 0xEF) and j + 1 < n:
                try:
                    s.append(d[j:j+2].decode('cp932')); j += 2; continue
                except UnicodeDecodeError:
                    pass
            ch = dec(c)
            if ch is None: break
            s.append(ch); j += 1
        if j < n and d[j] == 0 and len(s) >= 3:
            out.append(f'{nombre}\t{hex(i)}\t{"".join(s)}'); i = j + 1
        else:
            i = max(j, i + 1)
    return out

def main():
    out = []
    for p in sorted(BIN.glob('*.dec')):
        out += cadenas(p.stem, p.read_bytes())
    (HERE / 'cadenas_es.txt').write_text('\n'.join(out) + '\n', encoding='utf-8')
    print(len(out))
if __name__ == '__main__':
    main()
