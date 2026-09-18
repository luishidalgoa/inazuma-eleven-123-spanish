"""Validación de v20/textos (issue #77): CRO, unitbase, item.dat y fuentes frente a la base v18.
Uso: python -X utf8 work/ie2/shared/capas/v20/textos/validate.py
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
    fallos = []
    base = A.CRO_BASE.read_bytes()
    jp = A.CRO_JP.read_bytes()
    nuevo = (HERE / 'romfs/cro/ina_main2.cro').read_bytes()
    permitidos = set()
    for off, j, _ in A.LISTA + A.CAJA:
        n = len(j.encode('cp932'))
        permitidos |= set(range(off, off + n))
        if nuevo[off + n] != 0 or 0 in nuevo[off:off + n]:
            fallos.append(f'{hex(off)}: longitud distinta del japonés')
    g_off, g = A.LISTA[-1][0], len(A.LISTA[-1][1].encode('cp932'))
    permitidos |= set(range(A.ESPEJO_GUARDAR, A.ESPEJO_GUARDAR + g))
    if nuevo[A.ESPEJO_GUARDAR:A.ESPEJO_GUARDAR + g + 1] != nuevo[g_off:g_off + g + 1]:
        fallos.append('0xbd35c no coincide con la entrada de guardar')
    fuera = [i for i in range(len(base)) if base[i] != nuevo[i] and i not in permitidos]
    if fuera or len(base) != len(nuevo):
        fallos.append(f'CRO: {len(fuera)} bytes cambiados fuera de los literales (parches de ancho intactos: no)')
    # parches de ancho de la v18 conservados (difieren del japonés igual que en la base)
    parches = [i for i in range(len(jp)) if jp[i] != base[i] and i not in permitidos]
    if any(nuevo[i] != base[i] for i in parches):
        fallos.append('parches de la v18 alterados')
    get = A.K.comun88.abrir(A.ARCHIVE)
    ub0, ub = get(A.UNIT), (HERE / 'extra' / A.UNIT).read_bytes()
    for i in range(A.NREG + 1):
        a, b = ub0[i * 96:(i + 1) * 96], ub[i * 96:(i + 1) * 96]
        if a[:32] != b[:32] or a[64:] != b[64:] or b[63] != 0:
            fallos.append(f'unitbase {i}: cambio fuera de +32 o sin NUL')
    it0, it = get(A.ITEM), (HERE / 'extra' / A.ITEM).read_bytes()
    if it0[20:] != it[20:] or it[19] != 0:
        fallos.append('item.dat: cambio fuera del registro 0')
    reg = json.loads((HERE / 'registro.json').read_text(encoding='utf-8'))
    sj = [e['sjis'] for e in reg['bigramas']]
    if len(sj) != len(set(sj)):
        fallos.append('registro: códigos duplicados')
    for f in A.K.FUENTES:
        p = HERE / 'extra' / f
        d = p.read_bytes() if p.exists() else get(f)
        if A.sha(d) != reg['fuentes_dibujadas'][f]:
            fallos.append(f'{f}: sha distinto del registro')
    out = dict(ok=not fallos, fallos=fallos, parches_v18_conservados=len(parches))
    (HERE / 'validacion.json').write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(out, ensure_ascii=False, indent=1))
    sys.exit(0 if not fallos else 1)


if __name__ == '__main__':
    main()
