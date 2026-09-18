"""v87 · Bigramas también en font/FONT8.bcfnt (sonda v85/v86 fallida: la pestaña mostraba «A亠仭伉»).

Por qué FONT8 (ina_main1.cro):
- iz_main.cpp 0x1bb0 crea cuatro gestores en data+160 (0x1ff2a0). En 0x24d8-0x24f8 escribe su
  FONT_TYPE en [gestor+0x24]: +0x1c (data+188) = r8 = 1 (FONT8, 0x1e5c), +0x20 (data+192) = r5 = 3
  (RUBI8, 0x1c40), +0x24 (data+196) = r6 = 0 (FONT12, 0x1e24), +0x28 (data+200) = 2 (FONT12T).
- 0x301a (0x5ca84) abre la ventana con el nombre (unitbase +16) en r1 -> 0xc2f28 -> 0xc2ff4
  carga el gestor data+188 -> 0xe6214 (cscenedirection.cpp:1379). La pestaña se dibuja con FONT8.
- El rótulo del minimapa (0x7a484/0x7a54c, CSubAdventureScreen.cpp) usa también data+188 -> FONT8.
Paso: pestaña (pantalla superior) trunc(6 * 1.5625) + 1 = 10 px (ITX FONT8_DISP_TOP_FORCE_CHAR_WIDTH = 6,
DSPosXTo3DSPosX_tbl[0] = 1.5625, [gestor+0x14] = 1); rótulo (inferior) trunc(k * 8 * 1.25) = 10 px.
Colocación: x = lápiz + trunc((11 - advance)/2) + left (FINF width = 11).

Dibujo (mismos códigos que el registro v85; no cambia CMAP ni tamaño):
- letras = glifos latinos de ancho completo de la propia FONT8 (núcleo = alfa >= 8, con 1 px de halo a
  cada lado), separadas por 1 px de blanco entre núcleos (el espaciado nativo proporcional de FONT8 es 0).
- núcleo del par <= 9 px (caja de 11 px con los halos); «ta» mide 10 y pierde el halo exterior derecho. Centrado en la columna 5 de la casilla como las
  letras nativas (s = 5 - (Wc-1)//2); «x »: s = 1; « x»: s = 10 - Wc.
- CWDH: width = Wc + 2, advance = Wc (+4 si lleva espacio), left = (s - 1) - trunc((11 - advance)/2).
También restaura 81000090 a la versión v84 (la sonda de ancho de v86 no es viable: el 0x301a de cada diálogo, 0x5cb8c-0x5cb9c, fija ancho 0xF0 y 3 líneas).
Uso: python -X utf8 work/ie1/capas/v87/bigramas_fuentes/apply.py
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]


def _modulo(nombre, ruta):
    spec = importlib.util.spec_from_file_location(nombre, ruta)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


V85 = _modulo('v85_bigramas', ROOT / 'work/ie1/capas/v85/bigramas_sonda/apply.py')
V75G = V85.V75G
cargar, codepoint, abrir = V85.cargar, V85.codepoint, V85.abrir
decompress, parse_index, S = V85.decompress, V85.parse_index, V85.S

BASE = ROOT / 'work/shared/candidatas/probe_ie1_v86/archive.fa'
V84 = ROOT / 'work/shared/candidatas/probe_ie1_v84/archive.fa'
F8 = 'font/FONT8.bcfnt'
F8_SHA = 'b05e64c84cb564a98bea87cbdc94454f14f3df17e78252edf5a32be43ce454dd'   # v20 (dialogue_lock)
REG_V85 = ROOT / 'work/ie1/capas/v85/bigramas_sonda/registro.json'
REGISTRO = HERE / 'registro.json'
W = 11          # FINF width de FONT8
CENTRO = 5      # columna central del núcleo de las letras nativas
MARCO = 9       # marco de centrado de un par
MAX_NUCLEO = 10  # núcleo máximo (con 10 px se recorta el halo exterior derecho, alfa <= 3)
SOLIDO = 8      # alfa mínimo del núcleo
EID = 81000090


def nucleo(bm):
    xs = [x for row in bm for x, v in enumerate(row) if v >= SOLIDO]
    return (min(xs), max(xs)) if xs else None


def letra(F, ch):
    gi = F.gi(codepoint(ch))
    assert gi is not None, ch
    bm = F.bitmap(gi)
    return {(x, y): v for y, row in enumerate(bm) for x, v in enumerate(row) if v}, nucleo(bm)


def par(F, a, b):
    """(px con el núcleo desde x=1, Wc, s)."""
    partes = [letra(F, c) for c in (a, b) if c != ' ']
    px, x = {}, 1
    for pl, (n0, n1) in partes:
        for (cx, cy), v in pl.items():
            k = (cx - n0 + x, cy)
            px[k] = max(v, px.get(k, 0))
        x += (n1 - n0 + 1) + 1
    wc = x - 2
    px = {k: v for k, v in px.items() if 0 <= k[0] <= W - 1}
    if a == ' ':
        s = CENTRO + MARCO // 2 + 1 - wc
    elif b == ' ':
        s = CENTRO - MARCO // 2
    else:
        s = CENTRO - (wc - 1) // 2
    return px, wc, s


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    get = abrir(BASE)
    tmp = Path(tempfile.mkdtemp(prefix='ie123_v87_'))
    antes = get(F8)
    assert hashlib.sha256(antes).hexdigest() == F8_SHA, 'FONT8 de la base no es la v20'
    (tmp / 'FONT8.bcfnt').write_bytes(antes)
    F = cargar(tmp / 'FONT8.bcfnt')
    assert F.t['fmt'] == 11 and F.t['cell_w'] == W
    celdas = V75G.Celdas(F)
    reg = json.loads(REG_V85.read_text(encoding='utf-8'))
    filas = []
    for e in reg['bigramas']:
        p = e['par']
        cp = int(e['unicode'][2:], 16)
        gi = F.gi(cp)
        assert gi is not None and [c for c, g in F.cmap.items() if g == gi] == [cp], p
        px, wc, s = par(F, p[0], p[1])
        assert 1 <= wc <= MAX_NUCLEO and 1 <= s and s + wc <= W, (p, wc, s)
        adv = wc + (4 if ' ' in p else 0)
        left = (s - 1) - (W - adv) // 2
        assert (W - adv) // 2 + left == s - 1 and -128 <= left <= 127
        assert max(x for x, _ in px) <= W - 1
        for y in range(F.sy):
            for x in range(F.sx):
                celdas.escribir(gi, x, y, 0)
        for (x, y), v in px.items():
            celdas.escribir(gi, 1 + x, 1 + y, v)
        viejo = list(F.metrics[gi])
        F.set_metrics(gi, left, min(wc + 2, W), adv)
        leido = {(x, y): v for y, row in enumerate(F.bitmap(gi)) for x, v in enumerate(row) if v}
        assert leido == px, p
        filas.append(dict(par=p, glifo=gi, cwdh_kanji=viejo, cwdh=[left, min(wc + 2, W), adv], nucleo_px=wc, s=s,
                          pixeles_sha1=hashlib.sha1(json.dumps(sorted(px.items())).encode()).hexdigest()))
    datos = F.data()
    assert len(datos) == len(antes)
    out = HERE / 'extra' / F8
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(datos)

    # registro ampliado: mismos códigos, ahora con la entrada de FONT8
    por_par = {f['par']: f for f in filas}
    for e in reg['bigramas']:
        e['fuentes'] = {'font/FONT12.bcfnt': dict(glifo=e['glifo'], cwdh=e['cwdh'], D=e['D'], R=e['R']),
                        F8: {k: v for k, v in por_par[e['par']].items() if k != 'par'}}
    reg['version'] = 'v87-sonda'
    reg['descripcion'] += (' v87: cada código se dibuja en FONT12 (listas, ficha +0) y en FONT8 (pestaña del '
                           'hablante y rótulo del minimapa, gestor data+188 con FONT_TYPE 1).')
    reg['fuentes_dibujadas'] = {'font/FONT12.bcfnt': reg.pop('fuente_resultado_sha256'),
                                F8: hashlib.sha256(datos).hexdigest()}
    reg['regla_metricas_FONT8'] = ('x = lapiz + trunc((11 - advance)/2) + left; paso 10 px (pestaña y rótulo); '
                                   'núcleo (alfa>=8) <= 9 px con 1 px entre letras; s = 5 - (Wc-1)//2 '
                                   '(«x » s = 1; « x» s = 10 - Wc); width = Wc + 2; advance = Wc (+4 con espacio); '
                                   'left = s - 1 - trunc((11 - advance)/2)')
    REGISTRO.write_text(json.dumps(reg, ensure_ascii=False, indent=1), encoding='utf-8')

    # 81000090: vuelta a v84 (sin arg4 = 0x1A0 ni las líneas de 37/38 caracteres)
    arc84 = abrir(V84)
    pkh, pkb = arc84('inazuma1/data_iz/script/eve.pkh'), arc84('inazuma1/data_iz/script/eve.pkb')
    ev84 = next(decompress(pkb[o:o + s]) for e, o, s in parse_index(pkh) if e == EID)
    pkh6, pkb6 = get('inazuma1/data_iz/script/eve.pkh'), get('inazuma1/data_iz/script/eve.pkb')
    ev86 = next(decompress(pkb6[o:o + s]) for e, o, s in parse_index(pkh6) if e == EID)
    _, ops84, r84 = S.parse(ev84)
    _, ops86, r86 = S.parse(ev86)
    assert ops84 == ops86 and len(r84) == len(r86)
    difs = [i for i, (a, b) in enumerate(zip(r84, r86)) if a.raw != b.raw]
    assert difs == [406, 581], difs
    assert ev84[0x1b24:0x1b28] == bytes(4) and ev86[0x1b24:0x1b28] == bytes.fromhex('a0010000')
    ev_dir = HERE / 'events'
    if ev_dir.exists():
        shutil.rmtree(ev_dir)
    ev_dir.mkdir()
    (ev_dir / f'{EID}.ssd').write_bytes(ev84)

    informe = dict(base=str(BASE), fuente=F8, fuente_base_sha256=F8_SHA,
                   fuente_resultado_sha256=hashlib.sha256(datos).hexdigest(), bigramas=filas,
                   evento_restaurado=dict(evento=EID, desde=str(V84), registros_revertidos=difs,
                                          arg4_0x1b24='0x1A0 -> 0'))
    (HERE / 'aplicado.json').write_text(json.dumps(informe, ensure_ascii=False, indent=1), encoding='utf-8')
    for f in filas:
        print(f['par'], f['glifo'], f['cwdh_kanji'], '->', f['cwdh'], 'Wc', f['nucleo_px'], 's', f['s'])
    print('FONT8', informe['fuente_resultado_sha256'])
    shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    main()
