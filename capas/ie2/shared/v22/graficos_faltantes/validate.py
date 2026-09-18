"""Valida v22/graficos_faltantes: el .arc de salida solo cambia la textura objetivo respecto a la
base (v05 = probe_ie2_v21), conserva medidas/formato y la textura ya no es la japonesa."""
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'v03' / 'graficos'))
import comun as C  # noqa: E402
import importlib.util as _u
_s = _u.spec_from_file_location("apply_v22", HERE / "apply.py"); _m = _u.module_from_spec(_s); _s.loader.exec_module(_m)
ARC, TEX, BASE_ARC = _m.ARC, _m.TEX, _m.BASE_ARC

base = {n: b for n, _, _, b in C.texturas(C.U.unwrap((BASE_ARC / ARC).read_bytes()))}
nuevo_raw = (HERE / 'extra' / ARC).read_bytes()
nuevo = {n: b for n, _, _, b in C.texturas(C.U.unwrap(nuevo_raw))}
err = []
if set(base) != set(nuevo): err.append('conjunto de texturas distinto')
for n in base:
    if n == TEX:
        if base[n] == nuevo[n]: err.append('textura objetivo sin cambios')
        if C.T.metadata(base[n]) != C.T.metadata(nuevo[n]): err.append('metadatos cambiados')
    elif base[n] != nuevo[n]: err.append(f'textura ajena cambiada: {n}')
res = {'ok': not err, 'errores': err, 'texturas': len(nuevo), 'sha1': C.sha(nuevo_raw)}
json.dump(res, open(HERE / 'validate.json', 'w'), indent=1)
print(res); sys.exit(1 if err else 0)
