import sys
sys.stdout.reconfigure(encoding='utf-8')
import comun91 as C
F = C.Fuentes()
eid = int(sys.argv[1])
_, ops, rc = C.K.S.parse(F.cand.evento(eid))
_, ops0, ro = C.K.S.parse(F.orig.evento(eid))
print(len(rc), len(ro))
for i in map(int, sys.argv[2:]):
    for j in range(i-3, i+3):
        a, b = rc[j], ro[j]
        print(j, a.instruction, a.argument, b.instruction, b.argument, '|', C.K.a_espanol(a.body)[:60], '|', b.body.decode('cp932','replace')[:40], '|', F.oficial(eid, b.instruction, b.argument))
