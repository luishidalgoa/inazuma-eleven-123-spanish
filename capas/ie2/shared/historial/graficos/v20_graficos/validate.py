"""Valida la capa v20/graficos: sprites decodificables con las medidas del japonés y .arc de la placa de
tiempo idéntico a probe_ie2_v18 salvo la textura ie02_battle_start_time_plt_t01 (metadata CTPK igual)."""
import json
import sys

import apply as A

C = A.C


def main():
    jp, cand, errores, n = C.jp(), C.Archivo(A.CAND), [], 0
    for f in sorted(A.EXTRA.rglob('*')):
        if not f.is_file():
            continue
        ruta = f.relative_to(A.EXTRA).as_posix()
        n += 1
        if ruta not in jp:
            errores.append(f'{ruta}: no existe en el archive')
            continue
        d = f.read_bytes()
        if ruta.endswith('.pac_'):
            try:
                a, b = A.dec(jp.get(ruta)), A.dec(d)
                if a.size != b.size:
                    errores.append(f'{ruta}: medidas {a.size} != {b.size}')
                if d[:1] != b'\x10':
                    errores.append(f'{ruta}: sin LZ10')
            except Exception as e:  # noqa: BLE001
                errores.append(f'{ruta}: {e}')
        else:
            r0, r1 = C.U.unwrap(cand.get(ruta)), C.U.unwrap(d)
            t0 = {x[0]: x for x in C.texturas(r0)}
            t1 = {x[0]: x for x in C.texturas(r1)}
            if len(r0) != len(r1) or t0.keys() != t1.keys():
                errores.append(f'{ruta}: estructura distinta')
                continue
            for k in t0:
                if C.T.metadata(t0[k][3]) != C.T.metadata(t1[k][3]):
                    errores.append(f'{ruta}:{k}: metadata')
                if k != A.TEX_T and t0[k][3] != t1[k][3]:
                    errores.append(f'{ruta}:{k}: cambio no previsto')
            if t0[A.TEX_T][3] == t1[A.TEX_T][3]:
                errores.append(f'{ruta}: la placa no cambió')
    res = dict(ficheros=n, errores=errores, ok=not errores)
    (A.HERE / 'validate.json').write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding='utf-8')
    print('OK' if not errores else errores, n, 'ficheros')
    sys.exit(1 if errores else 0)


if __name__ == '__main__':
    main()
