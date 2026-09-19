"""Validación de la línea v20/teclado (issue #77).

Comprueba, para MMName.SPF_ y MMProfd.SPF_ de extra/:
* LZ10 válido y SFP con la MISMA tabla de nombres/tamaños que la base v18;
* fuera de FCODE0/1/2.TXT, los bytes descomprimidos son idénticos a la base;
* FCODE0/1/2 = patch_map(japonés) y, en MMName, idénticos a los fcode latinos de IE1 de la candidata v18
  (inazuma1/data_iz/fcodeN.txt, la tabla aprobada en juego);
* ninguna celda de letra sigue en kana.
Uso: python -X utf8 work/ie2/shared/capas/teclado/teclado/validate.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import apply as A  # noqa: E402


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    arc = A.FaArchive(str(A.BASE))
    fallos, res = [], {}
    for ruta in A.PAQUETES:
        base = A.lz10.decompress(arc.read(ruta))
        nuevo = A.lz10.decompress((HERE / 'extra' / ruta).read_bytes())
        eb, en = A.sfp_entradas(base), A.sfp_entradas(nuevo)
        if eb != en or len(base) != len(nuevo):
            fallos.append(f'{ruta}: tabla SFP distinta')
            continue
        tocado = set()
        for nombre, modo in A.MODOS.items():
            off, tam = en[nombre]
            tocado |= set(range(off, off + tam))
            esperado = A.patch_map(base[off:off + tam], modo)
            if nuevo[off:off + tam] != esperado:
                fallos.append(f'{ruta}:{nombre} no es patch_map')
            if ruta.endswith('MMName.SPF_') and nuevo[off:off + tam] != arc.read(A.IE1[nombre]):
                fallos.append(f'{ruta}:{nombre} distinto de la tabla latina de IE1 en la candidata')
            texto = nuevo[off:off + tam].decode('cp932', 'replace')
            if any('ぁ' <= ch <= 'ヿ' for ch in texto if ch not in 'ー'):
                fallos.append(f'{ruta}:{nombre} conserva kana')
        otros = [i for i in range(len(base)) if base[i] != nuevo[i] and i not in tocado]
        if otros:
            fallos.append(f'{ruta}: {len(otros)} bytes cambiados fuera de FCODE')
        res[ruta] = dict(bytes_fuera_de_fcode_cambiados=len(otros))
    salida = dict(ok=not fallos, fallos=fallos, paquetes=res)
    (HERE / 'validacion.json').write_text(json.dumps(salida, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(salida, ensure_ascii=False, indent=1))
    sys.exit(0 if not fallos else 1)


if __name__ == '__main__':
    main()
