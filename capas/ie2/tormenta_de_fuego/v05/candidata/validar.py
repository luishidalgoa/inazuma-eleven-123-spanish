"""Validación offline de probe_ie2_v05 frente a probe_ie2_v03 (runtime_verified=false)."""
import hashlib, json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[5]
W = ROOT / 'work'
G = W / 'ie2/shared/capas/v03/graficos'
sys.path.insert(0, str(G))
import comun as K  # noqa: E402


SNAP = W / 'ie2/shared/capas/v05/graficos_snapshot'
FONT = W / 'ie1/capas/v90/cro_restantes/extra'
CAND = W / 'shared/candidatas/probe_ie2_v05'
h = lambda b: hashlib.sha256(b).hexdigest()
prob = []
a = K.Archivo(W / 'shared/candidatas/probe_ie2_v03/archive.fa')
b = K.Archivo(CAND / 'archive.fa')
ea = set(a.idx); eb = set(b.idx)
if ea != eb: prob.append('tabla de entradas distinta')
decl = {}
for capa in (FONT, SNAP / 'extra'):
    for p in capa.rglob('*'):
        if p.is_file(): decl[p.relative_to(capa).as_posix()] = p.read_bytes()
distintas = set()
for p in sorted(ea):
    x, y = a.get(p), b.get(p)
    if x != y: distintas.add(p)
    if p in decl and y != decl[p]: prob.append(f'{p}: no coincide con la capa')
nodecl = sorted(distintas - set(decl))
if nodecl: prob.append(f'difieren sin declarar: {nodecl[:10]}')
iguales = sorted(set(decl) - distintas)  # declaradas pero ya iguales a v03
for n, src in (('ina_main1.cro', W / 'ie1/capas/v90/cro_restantes/romfs/cro'),
               ('ina_main2.cro', W / 'ie2/shared/capas/v04/cro_restantes/romfs/cro')):
    if (CAND / 'romfs/cro' / n).read_bytes() != (src / n).read_bytes(): prob.append(f'{n} distinta de la capa')
extra_romfs = sorted(str(p.relative_to(CAND)) for p in (CAND / 'romfs').rglob('*') if p.is_file())
# códec: textura cambiada decodifica y recodifica igual (sobre lo que hay en la candidata)
inf = json.loads((SNAP / 'informe.json').read_text(encoding='utf-8'))
tex = 0
for r in inf:
    if r['clase'] != 'textura': continue
    raw = K.U.unwrap(b.get(r['ruta']))
    orig = K.U.unwrap(K.jp().get(r['ruta']))
    if K.U.entries(raw) != K.U.entries(orig): prob.append(f"{r['ruta']}: ARCV"); continue
    for off, ln, _ in K.U.entries(raw):
        y = raw[off:off + ln]
        if y == orig[off:off + ln] or y[:4] != b'CTPK': continue
        tex += 1
        if K.T.encode(y, K.T.decode(y)) != y: prob.append(f"{r['ruta']}: códec")
res = dict(entradas=len(eb), distintas=len(distintas), declaradas=len(decl), declaradas_sin_cambio=len(iguales),
           texturas_codec=tex, romfs=extra_romfs, problemas=prob,
           resultado='PASS' if not prob else 'FAIL', runtime_verified=False)
(HERE / 'validacion.json').write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding='utf-8')
print(json.dumps(res, ensure_ascii=False, indent=1)); sys.exit(1 if prob else 0)
