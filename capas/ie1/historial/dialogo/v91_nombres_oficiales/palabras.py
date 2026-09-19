"""Palabras con mayúscula del texto IE1 de la candidata que no aparecen en la NDS ni en los glosarios."""
import collections, csv, re, sys, json
import comun91 as C
sys.stdout.reconfigure(encoding='utf-8')
F = C.Fuentes()
W = re.compile(r"[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñü\-]+")
ok = set()
for buf in F.nds.values():
    for b in C.entradas_nds(buf).values():
        ok.update(W.findall(C.D.decode_ds(b)))
for g in (C.ROOT / 'translation/shared/glossary').glob('*.csv'):
    for row in csv.reader(open(g, encoding='utf-8')):
        for c in row:
            ok.update(W.findall(c))
cont = collections.Counter(); ej = {}
for eid in sorted(F.cand.indice):
    try:
        _, ops, recs = C.K.S.parse(F.cand.evento(eid))
    except ValueError:
        continue
    for i, r in enumerate(recs):
        try:
            t = C.K.a_espanol(r.body)
        except Exception:
            continue
        for w in W.findall(t.replace('\n', ' ').replace('\f', ' ')):
            if w not in ok:
                cont[w] += 1; ej.setdefault(w, f'{eid}#{i} {t[:70]}')
for w, n in cont.most_common():
    print(n, w, '|', ej[w])
