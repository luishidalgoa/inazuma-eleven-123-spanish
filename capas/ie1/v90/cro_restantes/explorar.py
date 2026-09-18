"""Exploración: para cada literal, referencias, función, __FILE__ y gestores de fuente cargados.

Uso: python -X utf8 explorar.py ie1|ie2 0xOFF [0xOFF...]   (o sin offsets: la lista pendiente)
"""
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
sys.path.insert(0, str(HERE))
from crodis import Cro  # noqa: E402

CROS = {
    'ie1': (ROOT / 'work/shared/base_3ds/romfs/cro/ina_main1.cro',
            {0x1ff2bc: 'FONT8', 0x1ff2c0: 'RUBI8', 0x1ff2c4: 'FONT12', 0x1ff2c8: 'FONT12T'}),
    'ie2': (ROOT / 'work/shared/base_3ds/romfs/cro/ina_main2.cro',
            {0x29b284: 'FONT8', 0x29b288: 'RUBI8', 0x29b28c: 'FONT12', 0x29b290: 'FONT12T'}),
}


def info(c, slots, o):
    out = []
    for t, a, p in c.refs(o):
        if a is None:
            out.append(f'  ptr@{p:#x} (tabla de datos)')
            continue
        f = c.fstart(a)
        e = c.fend(f)
        files, fonts = set(), set()
        for i in c.dis(f, e):
            v = c.pool(i)
            if v is None:
                v = c.adrval(i)
            if v in slots:
                fonts.add(slots[v])
            if v and c.text[1] <= v < len(c.d):
                s = c.cstr(v, 60)
                if s.endswith('.cpp'):
                    files.add(s.rsplit('/', 1)[-1])
        out.append(f'  {t}@{a:#x}{"" if p is None else f" pool {p:#x}"} fn {f:#x}-{e:#x} {sorted(files)} {sorted(fonts)}')
    return out


def main():
    juego = sys.argv[1]
    path, slots = CROS[juego]
    c = Cro(path.read_bytes())
    for x in sys.argv[2:]:
        o = int(x, 16)
        print(f'{o:#x} {c.cstr(o)!r}')
        print('\n'.join(info(c, slots, o)) or '  (sin referencias)')


if __name__ == '__main__':
    main()
