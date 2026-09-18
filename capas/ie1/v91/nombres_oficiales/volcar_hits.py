import re, sys, json
import comun91 as C
sys.stdout.reconfigure(encoding='utf-8')
PAT = re.compile(r"\b(Mikage|Seino|Imperial|Senbayama|Iga|Igajima|Ikari|Biruda|Daisuke|Handa|Goro|Onigawara|Minayam|Endo|Muto|Soichiro|Souichirou|Fuyukai|Akagi|Shourinji|Mamoru|Reiji|Amano|Semimaru|Hoteki|Akane|Furukawa|Mako|Winter|Natan|Krim|Sarp|Senpai|Sweeth|Raijin|Pochi|Sally|Tonkotsu|Ghost|Dosukoi|Muca|Cicos|Granja|Akagi|Kasamino|Occultu|Teikoku|Kidou|Gouenji|Endou|Kazemaru|Someoka|Kabeyama|Matsuno|Kageno|Kurimatsu|Megane|Otonashi|Natsumi|Haruna|Kino|Aki|Hibiki|Kageyama|Sakuma|Genda|Terumi|Aphrodi|Afuro|Inazuma-machi|Inazumamachi|Shuuyou|Shuyo|Nosaka|Domon|Ichinose|Tsuchi)\b")
F = C.Fuentes()
out = []
for eid in sorted(F.cand.indice):
    try:
        _, ops, recs = C.K.S.parse(F.cand.evento(eid))
    except ValueError:
        continue
    for i, r in enumerate(recs):
        if ops.get(r.instruction) != 0x301d:
            continue
        try:
            t = C.K.a_espanol(r.body)
        except Exception:
            continue
        m = PAT.findall(re.sub(r"\\[nf]", " ", t))
        if not m:
            continue
        _, jp = F.japones(eid, i)
        of = F.oficial(eid, r.instruction, r.argument)
        out.append(dict(evento=eid, indice=i, nombres=m, actual=t, jp=jp, nds=of))
        print(f'== {eid}#{i} {m}\n  ES: {t}\n  JP: {jp}\n  NDS: {of}')
json.dump(out, open(C.HERE / 'hits_crudos.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(len(out))
