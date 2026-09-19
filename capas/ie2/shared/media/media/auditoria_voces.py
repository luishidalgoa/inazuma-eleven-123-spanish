"""IE2 v07 · media: coherencia voz/texto de los eventos con voz (issue #74; método de IE1 v51).

Con el doblaje español instalado, la frase que acompaña a cada voz (vNNNNaNN.SAD) debe ser la oficial de
la NDS. Para cada evento de eve.pkb de la candidata que llama a una voz se empareja por ID de instrucción
con evet.pkb de la NDS (comun_ie2.emparejar_evento: saltos de ID + anclas ASCII, nunca por orden) y, para
cada voz, se compara la primera frase que la sigue en el 3DS con la primera frase española que sigue a la
misma voz en la NDS (texto normalizado: sin formato, acentos de transporte, bigramas, espacios ni
puntuación).
Clases: igual | distinta (traducción condensada o distinta) | japones (sin traducir) | protegido.
Salida: auditoria_voces.json (texto del juego: no publicar).
Uso: python -X utf8 auditoria_voces.py [archive.fa]   (por defecto probe_ie2_v05)
"""
from __future__ import annotations

import collections
import json
import re
import sys
import unicodedata
from pathlib import Path

import comun_media as C
from dialogue_typography import ACCENTS
from ie123kit.nucleo.eventos.alineado_ids import tabla_3ds

M = C.M
VOZ = re.compile(rb'^v\d{4}a\d{2}\.sad$', re.I)
INV = {v: k for k, v in ACCENTS.items()}


def bigramas():
    reg = json.loads((C.W / 'ie1/capas/historial/menus_cro/v90_cro_restantes/registro.json').read_text(encoding='utf-8'))
    out = {}
    for e in reg['bigramas']:
        par = C.R.texto(C.A89.clave_de(e))
        if par[:1] == '':
            par = par[1:]
        out[bytes.fromhex(e['sjis'])] = par
    return out


BIG = bigramas()


def texto_3ds(b: bytes) -> str:
    out, i = [], 0
    while i < len(b):
        c = b[i]
        if (0x81 <= c <= 0x9F or 0xE0 <= c <= 0xFC) and i + 1 < len(b):
            tok = b[i:i + 2]
            i += 2
            if tok in BIG:
                out.append(BIG[tok])
                continue
            try:
                ch = tok.decode('cp932')
            except UnicodeDecodeError:
                ch = '?'
            out.append(INV.get(ch, ch))
        else:
            out.append(chr(c))
            i += 1
    return ''.join(out)


def norm(t: str) -> str:
    t = re.sub(r'%[0-9]*[A-Za-z]|\\[nf]', '', t)
    t = unicodedata.normalize('NFKC', t).lower()
    return ''.join(ch for ch in t if ch.isalnum())


def japones(t: str) -> bool:
    return any('぀' <= ch <= 'ヿ' or '一' <= ch <= '鿿' for ch in re.sub(r'%[0-9]*F', '', t)) \
        and not any('a' <= ch <= 'z' for ch in unicodedata.normalize('NFKC', t).lower())


def frases_3ds(a, desde, hasta):
    out = []
    for sid in sorted(a):
        if desde < sid < hasta and a[sid][0] == 1:
            raw = a[sid][1]
            if raw and not VOZ.match(raw) and any(c >= 0x80 for c in raw) \
                    and not re.fullmatch(rb'[ -~]*[.][A-Za-z0-9_]+', raw):
                out.append(sid)
    return out


def frases_nds(b, desde, hasta):
    return [sid for sid in sorted(b) if desde < sid < hasta and b[sid][2] > 0 and b[sid][1]
            and not VOZ.match(b[sid][1])]


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    ruta = Path(sys.argv[1]) if len(sys.argv) > 1 else C.BASE_ACTUAL
    arc = M.Archivo(ruta)
    nds = M.nds_eventos('eve')
    informe, cuenta = [], collections.Counter()
    for eid in arc.ids('eve'):
        data = arc.evento('eve', eid)
        a = tabla_3ds(data)
        v3 = sorted(sid for sid, (t, bb, _) in a.items() if VOZ.match(bb or b''))
        if not v3 or eid not in nds:
            if v3:
                cuenta['evento_con_voz_sin_nds'] += 1
                informe.append(dict(evento=eid, protegido=eid in M.PROTEGIDOS, sin_nds=True,
                                    lineas=[dict(voz=a[x][1].decode(), clase='evento_sin_nds') for x in v3]))
            continue
        m, ok, mal, b = M.emparejar_evento(data, nds[eid])
        vn = sorted(sid for sid, (t, bb, _) in b.items() if VOZ.match(bb or b''))
        usados = set()
        filas = []
        for k, sid in enumerate(v3):
            voz = a[sid][1].decode()
            sig = v3[k + 1] if k + 1 < len(v3) else 10 ** 9
            f3 = frases_3ds(a, sid, sig)
            # la misma voz en la NDS (primera aparición aún no usada)
            nsid = next((x for x in vn if x not in usados and b[x][1].upper() == a[sid][1].upper()), None)
            if not f3:
                cuenta['voz_sin_frase_3ds'] += 1
                filas.append(dict(voz=voz, id_voz=sid, clase='voz_sin_frase_3ds'))
                continue
            if nsid is None:
                cuenta['voz_sin_par_nds'] += 1
                filas.append(dict(voz=voz, id_juego=f3[0], clase='sin_par_nds',
                                  juego=texto_3ds(a[f3[0]][1])))
                continue
            usados.add(nsid)
            nsig = min([x for x in vn if x > nsid] or [10 ** 9])
            fn = frases_nds(b, nsid, nsig)
            if not fn:
                cuenta['voz_sin_frase_nds'] += 1
                filas.append(dict(voz=voz, id_juego=f3[0], clase='voz_sin_frase_nds', juego=texto_3ds(a[f3[0]][1])))
                continue
            juego = texto_3ds(a[f3[0]][1])
            oficial = M.decode_nds(b[fn[0]][1]) or ''
            if eid in M.PROTEGIDOS:
                clase = 'protegido' if norm(juego) != norm(oficial) else 'igual'
            elif japones(juego):
                clase = 'japones'
            elif norm(juego) == norm(oficial):
                clase = 'igual'
            else:
                clase = 'distinta'
            cuenta[clase] += 1
            filas.append(dict(voz=voz, id_juego=f3[0], id_nds=fn[0], id_emparejado=m.get(f3[0]),
                              clase=clase, juego=juego, nds=oficial))
        if filas:
            informe.append(dict(evento=eid, protegido=eid in M.PROTEGIDOS, lineas=filas))
    resumen = dict(archivo=str(ruta), eventos_con_voz=len(informe), **cuenta)
    (C.SALIDA / 'auditoria_voces.json').write_text(
        json.dumps(dict(resumen=resumen, eventos=informe), ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(resumen, ensure_ascii=False))
    for e in informe:
        for f in e['lineas']:
            if f['clase'] not in ('igual',):
                print(e['evento'], f['clase'], f['voz'], '|', f.get('juego', '')[:70].replace('\n', ' '), '|',
                      (f.get('nds') or '')[:70].replace('\n', ' '))


if __name__ == '__main__':
    main()
