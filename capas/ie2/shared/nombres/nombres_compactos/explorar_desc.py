import sys, time, struct, collections, random
sys.path.insert(0, '.')
import comun08 as K, desc12 as DD, eu08
A89 = K.A89
reg, F, antes, tmp = K.cargar_fuentes()
codec = A89.Codec(reg['bigramas'])
get = K.comun88.abrir(K.CAND)
Dz = DD.Desc(reg, F[K.F12])
eu = eu08.Eu()
ub = get(K.UNIT['ie1']); st = get('inazuma1/data_iz/logic/unitbase.STR')
textos = []
for i in range(2399):
    r = eu.registro(i)
    if r['descripcion']:
        textos.append(r['descripcion'])
random.seed(1)
muestra = random.sample(textos, 150)
t0 = time.time()
ok = collections.Counter(); keys = collections.Counter()
for t in muestra:
    res = Dz.envolver(t)
    if res is None:
        ok['no cabe'] += 1; continue
    ok[res[3]] += 1
    for sel in res[2]:
        keys.update(c for c, _, _ in sel if c.startswith(DD.PREF))
print(ok, 'claves nuevas', len(keys), 'usos', sum(keys.values()), round(time.time() - t0, 1), 's')
for t in muestra[:5]:
    res = Dz.envolver(t)
    print(repr(t), res and res[3], res and ['|'.join((Dz.texto_de(c) + ('@%d' % DD.de_clave(c)[1] if c.startswith(DD.PREF) else '')) for c, _, _ in s) for s in res[2]], res and [Dz.huecos(s) for s in res[2]])
