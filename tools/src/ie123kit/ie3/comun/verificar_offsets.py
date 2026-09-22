"""COMPROBACION OBLIGATORIA antes de construir una ROM de IE3.

Uso:  python tools/ie3_verificar_offsets.py work/archive_es_vNNN.fa

Invariante definitivo: cada DIALOGO del japones sigue empezando en su offset.

Se toman los offsets de los dialogos (cabezas de grupo) del bloque ORIGINAL y se
comprueba que en el bloque nuevo hay un registro que empieza exactamente ahi.
No depende de como agrupe el bloque nuevo, que al no tener marcadores agrupa
distinto.
"""
import sys

from ie123kit.ie3.comun.b123 import B123Archive
from ie123kit.ie3.comun.ssd import group_ruby, parse_flat_text
from ie123kit.ie3.comun.text import TextTable
from ie123kit.nucleo.config.raiz import find_root
from ie123kit.nucleo.eventos import packnum


def inicios(bloque):
    out, pos = set(), 0
    while pos + 4 <= len(bloque):
        tam = bloque[pos + 3]
        if tam < 4:
            break
        out.add(pos)
        pos += tam
    return out


def main(argv=None):
    """Comprueba que cada diálogo conservó su offset de inicio."""
    argv = sys.argv[1:] if argv is None else argv
    root = find_root()
    base = B123Archive(root / 'work/shared/base_3ds/romfs/archive.fa')
    nuevo = B123Archive(argv[0] if argv else root / 'work/archive_es_v106.fa')
    tabla = TextTable.identity()
    todo_ok = True
    for folder in ('inazuma3', 'inazuma3_ogre'):
        hb = base.read(f'{folder}/data_iz/script/evet.pkh')
        pb = base.read(f'{folder}/data_iz/script/evet.pkb')
        hn = nuevo.read(f'{folder}/data_iz/script/evet.pkh')
        pn = nuevo.read(f'{folder}/data_iz/script/evet.pkb')
        ib = {e: (o, s) for e, o, s in packnum.parse_index(hb) if e != 0xFFFFFFFF}
        ino = {e: (o, s) for e, o, s in packnum.parse_index(hn) if e != 0xFFFFFFFF}
        dialogos = perdidos = 0
        ejemplo = None
        for eid, (o1, s1) in ib.items():
            o2, s2 = ino[eid]
            cabezas = [h.offset for h, _ in group_ruby(parse_flat_text(pb[o1:o1 + s1], tabla))]
            arranques = inicios(pn[o2:o2 + s2])
            for off in cabezas:
                dialogos += 1
                if off not in arranques:
                    perdidos += 1
                    ejemplo = ejemplo or (eid, off)
        print(f'  {folder:15}: {dialogos:7,} dialogos | sin registro en su offset: {perdidos}')
        if ejemplo:
            print(f'      ejemplo: evento {ejemplo[0]}, offset 0x{ejemplo[1]:X}')
        todo_ok &= perdidos == 0
    print('\nINVARIANTE:', 'todos los dialogos empiezan donde empezaban'
          if todo_ok else 'HAY DIALOGOS DESPLAZADOS')
    return 0 if todo_ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
