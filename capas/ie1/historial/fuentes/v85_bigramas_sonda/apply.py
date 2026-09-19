"""v85 · SONDA de bigramas (glifos de dos letras en kanji que ningún juego usa). Autorización expresa del
usuario (2026-09-16): redibujar en font/FONT12.bcfnt kanji libres como pares de letras latinas, como hizo
v75 con el latín (mismo tamaño de fichero, CMAP intacto, code.bin intacto).

Qué hace (todo en work/, nada en tools/ ni docs/):
1. Registro fijo par -> código (registro.json). Los códigos salen de los kanji de nivel 2 de
   v83/bigramas/huecos.json (libre_total) que además pasan escaneo_kanji.py (0 apariciones en texto de los
   cuatro juegos), con un solo codepoint por glifo y el mismo valor en cp932 y shift_jis. Si registro.json
   ya existe se conservan sus asignaciones y solo se añaden pares nuevos (reutilizable en IE2/IE3: la
   fuente es compartida).
2. Dibujo de cada par en su kanji con el espaciado «natural+» de v83/bigramas/variante2.py (hueco
   proporcional de la fuente v75 y al menos 2 px de blanco entre las tintas).
   Métricas (modelo motor.py: x = lápiz + trunc((15 - advance)/2) + left):
     D = columna de la tinta en su casilla de paso fijo = (15 - ancho)//2 (par centrado; «x » pegado a la
         izquierda con D = 1; « x» pegado a la derecha con D = 15 - ancho - 1)
     width = ancho de tinta (<= 14)
     advance = D + ancho + R, con R = blanco natural tras la segunda letra (camino proporcional)
     left = D - trunc((15 - advance)/2)
3. Textos de la sonda (particiones «natural+», A se queda como glifo normal):
   - Aurelia: unitbase.dat registro 1153 (NPC 雷門中生徒女１, código せいお１９) +0 y +16, y el registro
     1614 (ダミー con el mismo nombre) +0 y +16.  A|ur|el|ia.
   - Sonda extra de la pestaña del hablante al principio del juego: Silvia (registro 14) +16, solo con
     los tres pares de Aurelia (S|i|l|v|ia).
   - Rótulos (eve.pkb 0x4037 arg 3, <= 10 casillas con los espacios de centrado):
       «Caseta»     -> «Caseta del club»  (10 casillas, sin centrado; zona del club, principio del juego)
       «Inst. Wild» -> «Instituto Wild»   (8 casillas + 2 espacios)
     («Zona de clubes» no cabe: con natural+ salen 11 casillas.)
     Mismas exclusiones que v79: 92010100..92010509, DONT_TOUCH, índices reutilizados.
Salida: registro.json, extra/font/FONT12.bcfnt, extra/inazuma1/data_iz/logic/unitbase.dat, events/*.ssd,
informe.json.
Uso: python -X utf8 work/ie1/capas/historial/fuentes/v85_bigramas_sonda/apply.py [--base .../probe_ie1_v84/archive.fa]
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shutil
import sys
import tempfile
from functools import lru_cache
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[5]


def _modulo(nombre, ruta):
    spec = importlib.util.spec_from_file_location(nombre, ruta)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


V79 = _modulo('v79_rotulos', ROOT / 'work/ie1/capas/historial/rotulos_objetivos/v79_rotulos/apply.py')
V75G = _modulo('v75_glifos_eu', ROOT / 'work/ie1/capas/fuentes/glifos_eu/apply.py')
C, S, decompress, parse_index = V79.C, V79.S, V79.decompress, V79.parse_index
a_texto, codificar, abrir = V79.a_texto, V79.codificar, V79.abrir
PROTEGIDOS, DONT_TOUCH, n_espacios, LIMITE_CAR = V79.PROTEGIDOS, V79.DONT_TOUCH, V79.n_espacios, V79.LIMITE_CAR
from fuentes import cargar, codepoint  # noqa: E402  (v73, ya en sys.path)
from motor import desplazamiento  # noqa: E402  (v74)

BASE = ROOT / 'work/shared/candidatas/probe_ie1_v84/archive.fa'
F12 = 'font/FONT12.bcfnt'
UNIT = 'inazuma1/data_iz/logic/unitbase.dat'
CELDA = 15
TINTA_MAX = 14
HUECOS = ROOT / 'work/ie1/capas/historial/fuentes/v83_bigramas/huecos.json'
ESCANEO = HERE / 'escaneo_base_v84.json'
REGISTRO = HERE / 'registro.json'
PARES_AURELIA = ['ur', 'el', 'ia']
NOMBRES = [  # (registro, campo, texto, pares permitidos o None = libres)
    (1153, 0, 'Aurelia', None), (1153, 16, 'Aurelia', None),
    (1614, 0, 'Aurelia', None), (1614, 16, 'Aurelia', None),
    (14, 16, 'Silvia', PARES_AURELIA),
]
ROTULOS = {'Caseta': 'Caseta del club', 'Inst. Wild': 'Instituto Wild'}


class Glifos:
    def __init__(self, fuente):
        self.F = fuente

    @lru_cache(None)
    def letra(self, ch):
        gi = self.F.gi(codepoint(ch))
        if gi is None:
            raise KeyError(ch)
        left, w, adv = self.F.metrics[gi]
        px = {(x, y): v for y, row in enumerate(self.F.bitmap(gi)) for x, v in enumerate(row) if v}
        return desplazamiento(CELDA, left, adv), w, adv, px, gi

    @lru_cache(None)
    def par(self, a, b):
        """(px con la tinta desde x=0, ancho, D, R) del par con el espaciado natural+ (variante2.par2)."""
        da, _, adva, pa, _ = self.letra(a)
        db, _, advb, pb, _ = self.letra(b)
        xa, xb = da, adva + db
        empuje = 0
        if pa and pb:
            a1 = max(x for x, _ in pa)
            b0 = min(x for x, _ in pb)
            if xb + b0 < xa + a1 + 3:
                empuje = xa + a1 + 3 - b0 - xb
                xb += empuje
        px = {}
        for (x, y), v in pa.items():
            px[(x + xa, y)] = v
        for (x, y), v in pb.items():
            px[(x + xb, y)] = max(v, px.get((x + xb, y), 0))
        x0 = min(x for x, _ in px)
        x1 = max(x for x, _ in px)
        ancho = x1 - x0 + 1
        fin_lapiz = adva + advb + empuje           # lápiz tras el par en el camino proporcional
        R = max(0, fin_lapiz - (x1 + 1))
        px = {(x - x0, y): v for (x, y), v in px.items()}
        if b == ' ':
            D = 1
        elif a == ' ':
            D = CELDA - ancho - 1
        else:
            D = (CELDA - ancho) // 2
        return px, ancho, D, R


def particion(t, gl, permitidos=None):
    """natural+ (variante2.particion_opt): mínimo de casillas; a igualdad, pares con más aire."""
    @lru_cache(None)
    def f(i):
        if i >= len(t):
            return (0, 0, ())
        c, s, r = f(i + 1)
        mejor = (c + 1, s, (t[i],) + r)
        if i + 1 < len(t):
            p = t[i:i + 2]
            if p != '  ' and (permitidos is None or p in permitidos):
                ancho = gl.par(p[0], p[1])[1]
                if ancho <= TINTA_MAX:
                    c, s, r = f(i + 2)
                    cand = (c + 1, s - (TINTA_MAX - ancho) ** 0.5, (p,) + r)
                    if cand[:2] < mejor[:2]:
                        mejor = cand
        return mejor
    return list(f(0)[2])


def elegir_codigos(fuente, n_necesarios, ya_usados):
    h = json.loads(HUECOS.read_text(encoding='utf-8'))
    esc = json.loads(ESCANEO.read_text(encoding='utf-8'))
    limpios = set(esc['limpios'])
    inverso = {}
    for cp, gi in fuente.cmap.items():
        inverso.setdefault(gi, []).append(cp)
    out = []
    if n_necesarios == 0:
        return out
    for c in h['libre_total_codigos']:
        code = int(c, 16)
        if not 0x989F <= code <= 0xEAA4 or c not in limpios or c in ya_usados:
            continue
        b = code.to_bytes(2, 'big')
        ch = b.decode('cp932')
        if b.decode('shift_jis', 'replace') != ch or ch.encode('cp932') != b:
            continue
        gi = fuente.gi(ord(ch))
        if gi is None or len(inverso[gi]) != 1:
            continue
        out.append(c)
        if len(out) == n_necesarios:
            return out
    raise SystemExit(f'faltan códigos limpios: {len(out)}/{n_necesarios}; ampliar escaneo_kanji.py --pool')


def codificar_celdas(celdas, registro):
    out = b''
    for c in celdas:
        if len(c) == 2:
            out += bytes.fromhex(registro[c]['sjis'])
        else:
            out += codificar(c)
    return out


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', type=Path, default=BASE)
    args = ap.parse_args()
    base = args.base.resolve()
    get = abrir(base)
    tmp = Path(tempfile.mkdtemp(prefix='ie123_v85_'))
    (tmp / 'FONT12.bcfnt').write_bytes(get(F12))
    antes = (tmp / 'FONT12.bcfnt').read_bytes()
    v75 = (ROOT / 'work/ie1/capas/fuentes/glifos_eu/extra' / F12).read_bytes()
    assert antes == v75, 'la FONT12 de la base no es la de v75/glifos_eu'
    fuente = cargar(tmp / 'FONT12.bcfnt')
    gl = Glifos(fuente)

    # --- particiones -------------------------------------------------------------------------------
    nombres = []
    for reg, campo, texto, perm in NOMBRES:
        cel = particion(texto, gl, frozenset(perm) if perm else None)
        nombres.append(dict(registro=reg, campo=campo, texto=texto, celdas=cel))
    assert nombres[0]['celdas'] == ['A', 'ur', 'el', 'ia'], nombres[0]['celdas']
    rotulos = {}
    for viejo, nuevo in ROTULOS.items():
        cel = particion(nuevo, gl)
        assert len(cel) <= LIMITE_CAR, (nuevo, cel)
        k = n_espacios(len(cel))
        assert 0 <= k and len(cel) + k <= LIMITE_CAR, (nuevo, cel, k)
        rotulos[viejo] = dict(nuevo=nuevo, celdas=cel, espacios=k)

    pares = list(PARES_AURELIA)
    for d in list(nombres) + list(rotulos.values()):
        for c in d['celdas']:
            if len(c) == 2 and c not in pares:
                pares.append(c)

    # --- registro ------------------------------------------------------------------------------------
    previo = json.loads(REGISTRO.read_text(encoding='utf-8')) if REGISTRO.exists() else {'bigramas': []}
    por_par = {e['par']: e for e in previo['bigramas']}
    nuevos = [p for p in pares if p not in por_par]
    codigos = elegir_codigos(fuente, len(nuevos), {e['sjis'] for e in previo['bigramas']})
    for p, c in zip(nuevos, codigos):
        ch = bytes.fromhex(c).decode('cp932')
        por_par[p] = dict(par=p, sjis=c, unicode=f'U+{ord(ch):04X}', kanji=ch)

    # --- dibujo --------------------------------------------------------------------------------------
    celdas = V75G.Celdas(fuente)
    for p in pares:
        e = por_par[p]
        gi = fuente.gi(int(e['unicode'][2:], 16))
        px, ancho, D, R = gl.par(p[0], p[1])
        assert ancho <= TINTA_MAX and D >= 0 and D + ancho <= CELDA, (p, ancho, D)
        adv = D + ancho + R
        left = D - int((CELDA - adv) / 2)
        assert -128 <= left <= 127 and 0 < adv <= 255
        assert desplazamiento(CELDA, left, adv) == D
        for y in range(fuente.sy):
            for x in range(fuente.sx):
                celdas.escribir(gi, x, y, 0)
        for (x, y), v in px.items():
            assert 0 <= x < CELDA and 0 <= y < fuente.sy - 1
            celdas.escribir(gi, 1 + x, 1 + y, v)
        viejo = list(fuente.metrics[gi])
        fuente.set_metrics(gi, left, ancho, adv)
        assert fuente.bitmap(gi) and {(x, y): v for y, row in enumerate(fuente.bitmap(gi))
                                      for x, v in enumerate(row) if v} == px
        e.update(glifo=gi, cwdh_kanji=viejo, cwdh=[left, ancho, adv], tinta_px=ancho, D=D, R=R,
                 pixeles_sha1=hashlib.sha1(json.dumps(sorted(px.items())).encode()).hexdigest())
    datos = fuente.data()
    assert len(datos) == len(antes)
    salida = HERE / 'extra' / F12
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_bytes(datos)

    usos = {p: [] for p in pares}
    for d in nombres:
        for c in d['celdas']:
            if len(c) == 2:
                usos[c].append(f"IE1 unitbase.dat reg {d['registro']} +{d['campo']} «{d['texto']}»")
    for viejo, d in rotulos.items():
        for c in d['celdas']:
            if len(c) == 2:
                usos[c].append(f"IE1 eve.pkb 0x4037 «{d['nuevo']}»")
    for p in pares:
        por_par[p]['uso'] = sorted(set(usos[p]))
    registro = dict(
        descripcion='Registro fijo de bigramas (par de letras -> kanji reasignado) de font/FONT12.bcfnt. '
                    'La fuente está en la raíz de archive.fa y la comparten IE1, IE2 e IE3: estos códigos '
                    'no pueden usarse como kanji en ningún juego y cualquier traducción futura debe '
                    'reutilizar este registro (añadir al final, no reasignar).',
        version='v85-sonda',
        fuente=F12,
        fuente_base_sha256=hashlib.sha256(antes).hexdigest(),
        fuente_resultado_sha256=hashlib.sha256(datos).hexdigest(),
        regla_codigos='kanji JIS nivel 2 (0x989F-0xEAA4) de v83/bigramas/huecos.json libre_total, con 0 '
                      'apariciones alineadas en texto (escaneo_kanji.py), un solo codepoint por glifo y '
                      'cp932 == shift_jis',
        regla_metricas='x = lapiz + trunc((15 - advance)/2) + left; D = (15 - ancho)//2 (par centrado; '
                       '«x » D = 1; « x» D = 14 - ancho); width = ancho <= 14; advance = D + ancho + R '
                       '(R = blanco natural tras la 2.a letra); left = D - trunc((15 - advance)/2)',
        espaciado='natural+ (v83/bigramas/variante2.py): hueco proporcional de la fuente v75, >= 2 px entre tintas',
        bigramas=[por_par[p] for p in por_par],
    )
    REGISTRO.write_text(json.dumps(registro, ensure_ascii=False, indent=1), encoding='utf-8')
    reg = {e['par']: e for e in registro['bigramas']}

    # --- unitbase ------------------------------------------------------------------------------------
    ub = bytearray(get(UNIT))
    cambios_ub = []
    for d in nombres:
        off = 96 + d['registro'] * 96 + d['campo']
        cuerpo = codificar_celdas(d['celdas'], reg)
        assert len(cuerpo) < 16, d
        antes_campo = bytes(ub[off:off + 16])
        ub[off:off + 16] = cuerpo + bytes(16 - len(cuerpo))
        cambios_ub.append(dict(d, antes=antes_campo.split(b'\0')[0].decode('cp932'), bytes=len(cuerpo),
                               hex=cuerpo.hex()))
    out_ub = HERE / 'extra' / UNIT
    out_ub.parent.mkdir(parents=True, exist_ok=True)
    out_ub.write_bytes(bytes(ub))

    # --- rótulos -------------------------------------------------------------------------------------
    ev_dir = HERE / 'events'
    if ev_dir.exists():
        shutil.rmtree(ev_dir)
    ev_dir.mkdir()
    pkb = get(C.PKB)
    aplicados, excluidos = [], []
    for eid, o, s in parse_index(get(C.PKH)):
        data = decompress(pkb[o:o + s])
        try:
            _, ops, recs = S.parse(data)
            refs = C.text_refs(data)
        except (ValueError, KeyError):
            continue
        cambios = {}
        for i, r in enumerate(recs):
            if ops.get(r.instruction) != 0x4037 or r.argument != 3:
                continue
            try:
                texto = a_texto(r.body)
            except UnicodeDecodeError:
                continue
            actual = texto.strip(' ')
            if actual not in rotulos:
                continue
            fila = dict(evento=eid, indice=i, antes=texto, bytes_antes=len(r.body))
            if eid in PROTEGIDOS or eid in DONT_TOUCH:
                excluidos.append(dict(fila, motivo='evento protegido'))
                continue
            otros = [x for x in refs.get(i, []) if (x[1], x[2]) != (0x4037, 3)]
            if otros:
                excluidos.append(dict(fila, motivo=f'índice reutilizado por {otros}'))
                continue
            d = rotulos[actual]
            cuerpo = V79.ESPACIO * d['espacios'] + codificar_celdas(d['celdas'], reg)
            assert len(cuerpo) <= 2 * LIMITE_CAR, (cuerpo, d)
            cambios[i] = cuerpo
            aplicados.append(dict(fila, despues=d['nuevo'], celdas=d['celdas'], espacios=d['espacios'],
                                  casillas=d['espacios'] + len(d['celdas']), bytes=len(cuerpo)))
        if cambios:
            nuevo = S.replace(data, cambios)
            _, ops2, recs2 = S.parse(nuevo)
            assert ops2 == ops and len(recs2) == len(recs)
            (ev_dir / f'{eid}.ssd').write_bytes(nuevo)

    informe = dict(base=str(base), escaneo_kanji=str(ESCANEO.relative_to(ROOT)),
                   registro=str(REGISTRO.relative_to(ROOT)), pares=pares,
                   nombres=cambios_ub, rotulos=rotulos, rotulos_aplicados=aplicados,
                   rotulos_excluidos=excluidos,
                   fuente_sha256=registro['fuente_resultado_sha256'],
                   unitbase_sha256=hashlib.sha256(bytes(ub)).hexdigest())
    (HERE / 'informe.json').write_text(json.dumps(informe, ensure_ascii=False, indent=1), encoding='utf-8')
    print('pares', [(p, reg[p]['kanji'], reg[p]['sjis'], reg[p]['cwdh'], reg[p]['D']) for p in pares])
    for d in nombres:
        print('nombre', d['registro'], d['campo'], '|'.join(d['celdas']))
    for v, d in rotulos.items():
        print('rotulo', v, '->', d['nuevo'], '|'.join(d['celdas']), 'espacios', d['espacios'])
    print('rotulos aplicados', len(aplicados), sorted({a['evento'] for a in aplicados}))
    print('excluidos', [(e['evento'], e['motivo']) for e in excluidos])
    print('FONT12', registro['fuente_resultado_sha256'])
    shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    main()
