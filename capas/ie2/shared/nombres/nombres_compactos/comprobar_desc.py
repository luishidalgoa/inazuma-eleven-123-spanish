"""IE2 v08 · comprobación automática de TODAS las descripciones (unitbase.STR de IE1 e IE2) con la FONT12 y
los cuerpos finales de extra/ (o los de probe_ie2_v05 con --antes).

Simula el dibujo a paso 15 (x = lápiz + trunc((15 - advance)/2) + left; tinta sólida alfa >= 5) y marca:
  espacio_inicial   la línea empieza por espacio o su primera tinta está más allá de la columna 3;
  hueco_interno     un hueco dentro de palabra de más de 4 px (tolerancia aceptada por el usuario);
  palabras_pegadas  un hueco entre palabras de menos de 5 px, o no mayor que el hueco interno más grande
                    de la línea (no se distinguen); también si las palabras visibles (huecos >= 5 y
                    espacios dentro de una casilla) no coinciden con las del texto.
Uso: python -X utf8 comprobar_desc.py [--antes]  ->  comprobacion_desc.json (o comprobacion_desc_v05.json)
"""
from __future__ import annotations

import argparse
import collections
import json
import struct
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import comun08 as K  # noqa: E402

A88, A89 = K.A88, K.A89
STR = {'ie1': 'inazuma1/data_iz/logic/unitbase.STR', 'ie2': 'inazuma2/data_iz/logic/unitbase.STR'}
NL = 0x0A


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser()
    ap.add_argument('--antes', action='store_true')
    a = ap.parse_args()
    get = K.comun88.abrir(K.CAND)
    tmp = Path(tempfile.mkdtemp(prefix='ie2_v08c_'))
    if a.antes:
        reg = json.loads(K.REG07.read_text(encoding='utf-8'))
        fuente = K.W / 'ie1/capas/historial/menus_cro/v90_cro_restantes/extra/font/FONT12.bcfnt'
    else:
        reg = json.loads((HERE / 'registro.json').read_text(encoding='utf-8'))
        fuente = HERE / 'extra' / K.F12
    (tmp / 'f.bcfnt').write_bytes(fuente.read_bytes())
    F = A88.cargar(tmp / 'f.bcfnt')
    codec = A89.Codec(reg['bigramas'])
    avisos, total, lineas_tot = [], 0, 0
    cuenta = collections.Counter()
    for j in STR:
        ub = get(K.UNIT[j])
        st = get(STR[j]) if a.antes or not (HERE / 'extra' / STR[j]).exists() else (HERE / 'extra' / STR[j]).read_bytes()
        offs = {}
        for i in range((len(ub) - 96) // 96):
            p = struct.unpack_from('<H', ub, 96 + i * 96 + 94)[0] * 32
            if p and p < len(st) and not any(d in ub[96 + i * 96:96 + i * 96 + 32]
                                              for d in ('ダミー'.encode('cp932'), '未定'.encode('cp932'))):
                offs.setdefault(p, []).append(i)
        for off, regs in sorted(offs.items()):
            body = st[off:st.index(bytes(1), off)]
            toks = codec.tokens(body)
            if not toks or any(t is None and tok != bytes((NL,)) for tok, t in toks):
                continue
            total += 1
            lineas = [[]]
            for tok, t in toks:
                if tok == bytes((NL,)):
                    lineas.append([])
                else:
                    lineas[-1].append((tok, t))
            for li, lin in enumerate(lineas):
                if not lin:
                    continue
                lineas_tot += 1
                texto = ''.join(t for _, t in lin)
                celdas = []
                for k, (tok, t) in enumerate(lin):
                    cp = ord(tok.decode('cp932'))
                    gi = F.gi(cp)
                    left, _, adv = F.metrics[gi]
                    x0 = 15 * k + int((15 - adv) / 2) + left
                    xs = [x0 + x for row in F.bitmap(gi) for x, v in enumerate(row) if v >= 5]
                    celdas.append((t, min(xs) if xs else None, max(xs) if xs else None))
                motivos = []
                if texto.startswith(' ') or (celdas[0][1] is not None and celdas[0][1] > 3):
                    motivos.append(f'espacio_inicial (tinta en {celdas[0][1]})')
                internos, palabra = [], []
                prev, sep = None, False
                for t, x0, x1 in celdas:
                    if x0 is None:
                        sep = True
                        continue
                    lead = t.startswith(' ')
                    if prev is not None:
                        g = x0 - prev - 1
                        (palabra if (sep or lead) else internos).append(g)
                    prev, sep = x1, t.endswith(' ')
                maxi = max(internos) if internos else 0
                if any(g > 4 for g in internos):
                    motivos.append(f'hueco_interno {max(internos)}')
                if any(g < 5 or g <= maxi for g in palabra):
                    motivos.append(f'palabras_pegadas {min(palabra)} (interno máx. {maxi})')
                visibles = 1 + sum(1 for g in palabra if g >= 5) + sum(t.strip(' ').count(' ') for t, _, _ in celdas)
                if visibles != len(texto.split()):
                    motivos.append(f'palabras {len(texto.split())} / visibles {visibles}')
                for m in motivos:
                    cuenta[m.split(' ')[0]] += 1
                if motivos:
                    avisos.append(dict(juego=j, offset=off, registros=regs[:3], linea=li, texto=texto,
                                       huecos_internos=internos, huecos_palabra=palabra, motivos=motivos))
    salida = HERE / ('comprobacion_desc_v05.json' if a.antes else 'comprobacion_desc.json')
    salida.write_text(json.dumps(dict(
        nota='Comprobación automática (paso 15, alfa >= 5). ' + ('Estado de probe_ie2_v05.' if a.antes else 'Capa v08.'),
        descripciones=total, lineas=lineas_tot, lineas_con_aviso=len(avisos), por_motivo=dict(cuenta),
        detalle=avisos), ensure_ascii=False, indent=1), encoding='utf-8')
    print(salida.name, 'descripciones', total, 'líneas', lineas_tot, 'con aviso', len(avisos), dict(cuenta))


if __name__ == '__main__':
    main()
