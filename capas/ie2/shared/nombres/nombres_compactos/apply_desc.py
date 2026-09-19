"""IE2 v08 · descripciones de la ficha (unitbase.STR de IE1 e IE2) con casillas FONT12 a 15 px (desc12.py).

Se ejecuta DESPUÉS de apply.py (parte de su registro.json y de sus extra/font/*.bcfnt; añade al final).
Texto:
  IE1: descripción oficial del port europeo 3DS (eu08.py; mismo texto en todos los registros que comparten
       el hueco) si cabe en 2 líneas de 14 casillas (saltos oficiales o, si no, reajuste por palabras) y en su
       hueco de bytes; si no, el texto actual (NDS oficial de v88/v89) con el mismo maquetado.
  IE2: el texto actual (NDS oficial, v03).
Hueco: del puntero (+94 x 32) al siguiente puntero usado o al primer byte no nulo tras el NUL japonés
(regla de IE2 v03), con el NUL incluido.
Códigos: casillas (texto, D, g) cuyo dibujo ya existe se reutilizan; las nuevas salen del depósito que deja
apply.py y de los códigos que SOLO usaban las descripciones (uso_registro_v05.json: aparición en texto solo
en */unitbase.STR, ni en eventos de otras capas ni en literales) y que tras este reparto quedan sin uso:
se redibujan. Si no hay códigos para todo, se encarecen las casillas menos usadas y se repite.
Salida: registro.json y extra/ (actualizados), informe_desc.json, comprobacion_desc.json.
Uso: python -X utf8 work/ie2/shared/capas/nombres/nombres_compactos/apply_desc.py
"""
from __future__ import annotations

import collections
import hashlib
import json
import re
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import apply as A  # noqa: E402
import comun08 as K  # noqa: E402
import desc12 as DD  # noqa: E402
import eu08  # noqa: E402
import modelo8 as M8  # noqa: E402

A88, A89, R = K.A88, K.A89, K.R
F12 = K.F12
STR = {'ie1': 'inazuma1/data_iz/logic/unitbase.STR', 'ie2': 'inazuma2/data_iz/logic/unitbase.STR'}
USO = HERE / 'uso_registro_v05.json'
OTRAS_CAPAS = [K.W / 'ie1/capas/historial/dialogo/v91_nombres_oficiales', K.W / 'ie1/capas/historial/dialogo/v92_redump_eu3ds', K.W / 'ie2/shared/capas/media/media/extra',
               K.W / 'ie2/tormenta_de_fuego/capas/media/media', K.W / 'ie2/shared/capas/historial/graficos/v06_graficos']
MAX_RONDAS = 12
NL = bytes((0x0A,))


def sha(b):
    return hashlib.sha256(b).hexdigest()


def huecos(ub_jp, st_jp, ub):
    """{offset: (fin, [registros])} de los punteros usados (x32)."""
    usados = collections.defaultdict(list)
    for i in range((len(ub) - 96) // 96):
        p = struct.unpack_from('<H', ub, 96 + i * 96 + 94)[0] * 32
        if p:
            usados[p].append(i)
    offs = sorted(usados)
    out = {}
    for k, off in enumerate(offs):
        sig = offs[k + 1] if k + 1 < len(offs) else len(st_jp)
        nul = st_jp.index(bytes(1), off)
        j = nul + 1
        while j < sig and st_jp[j] == 0:
            j += 1
        out[off] = (min(sig, j), usados[off])
    return out


def recoger(get, getjp, codec, eu):
    unidades = []
    for juego in ('ie1', 'ie2'):
        ub, st = get(K.UNIT[juego]), get(STR[juego])
        ubj, stj = getjp(K.UNIT[juego]), getjp(STR[juego])
        for off, (fin, regs) in huecos(ubj, stj, ub).items():
            if off >= len(st):
                continue
            nul = st.index(bytes(1), off)
            body = st[off:nul]
            if not body or any(st[nul:fin]):
                continue
            if all(any(d in ub[96 + i * 96:96 + i * 96 + 32] for d in A.DUMMY) for i in regs):
                continue
            segs = codec.segmentos(body)
            if any(k == 'o' and v != NL for k, v in segs):
                continue
            actual = ''.join(v if k == 't' else '\n' for k, v in segs)
            if not actual.strip():
                continue
            u = dict(juego=juego, offset=off, fin=fin, registros=regs, body=body, actual=actual, oficial_eu=None)
            if juego == 'ie1':
                txt = {eu.registro(i)['descripcion'] for i in regs}
                if len(txt) == 1 and None not in txt:
                    # el transporte de ancho completo ya convierte ( ) en （ ）: se normaliza a ASCII
                    u['oficial_eu'] = ''.join(chr(ord(c) - 0xFEE0) if 0xFF01 <= ord(c) <= 0xFF5E else c
                                              for c in txt.pop())
            unidades.append(u)
    return unidades


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    reg = json.loads((HERE / 'registro.json').read_text(encoding='utf-8'))
    if 'pares_ie2_v08_descripciones' in reg:
        raise SystemExit('registro.json ya tiene las descripciones: ejecutar antes apply.py')
    import tempfile
    tmp = Path(tempfile.mkdtemp(prefix='ie2_v08d_'))
    ruta12 = HERE / 'extra' / F12
    datos12 = ruta12.read_bytes()
    assert sha(datos12) == reg['fuentes_dibujadas'][F12]
    (tmp / 'FONT12.bcfnt').write_bytes(datos12)
    F = A88.cargar(tmp / 'FONT12.bcfnt')
    codec = A89.Codec(reg['bigramas'])
    get = K.comun88.abrir(K.CAND)
    getjp = K.comun88.abrir(K.BASE_JP)
    Dz = DD.Desc(reg, F, K.cp)
    eu = eu08.Eu()
    unidades = recoger(get, getjp, codec, eu)
    print('descripciones', len(unidades), collections.Counter(u['juego'] for u in unidades), flush=True)

    # ---- códigos liberables ----------------------------------------------------------------------------
    uso = json.loads(USO.read_text(encoding='utf-8'))
    otros_bytes = []
    for d in OTRAS_CAPAS:
        if d.exists():
            for p in d.rglob('*'):
                if p.is_file() and p.suffix.lower() in ('.ssd', '.dat', '.str', '.txt', '.cro', '.tbl', '.bin'):
                    try:
                        otros_bytes.append(p.read_bytes())
                    except OSError:
                        pass
    por_sjis = {e['sjis']: e for e in reg['bigramas']}
    campos_nuevos = set(reg.get('pares_ie2_v08', [])) | {x['sjis'] for x in reg.get('pares_ie2_v08_reutilizados', [])}
    liberables = []
    for e in reg['bigramas']:
        s = e['sjis']
        if s in campos_nuevos or any(c != 'descripcion' for c in e.get('campos', [])):
            continue
        rutas = [r for r, cnt in uso['apariciones_textuales'].get(s, []) if cnt.get('texto')]
        if not rutas or any(not r.endswith('/unitbase.STR') for r in rutas):
            continue
        b = bytes.fromhex(s)
        if any(b in x for x in otros_bytes):
            continue
        liberables.append(s)
    print('códigos solo de descripciones', len(liberables), flush=True)

    # ---- reparto ----------------------------------------------------------------------------------------
    def reparto(u):
        opciones = []
        if u['oficial_eu']:
            opciones.append(('eu', u['oficial_eu']))
        opciones.append(('actual', u['actual']))
        for origen, t in opciones:
            r = Dz.envolver(t)
            if r is None:
                continue
            cuerpo_prov = sum(2 * len(s) for s in r[2]) + (len(r[2]) - 1)
            if cuerpo_prov > u['fin'] - u['offset'] - 1:
                continue
            return origen, t, r
        return None

    libres_extra = json.loads((HERE / 'deposito_restante.json').read_text(encoding='utf-8'))
    claves_reg = {A89.clave_de(e): e['sjis'] for e in reg['bigramas']}
    permitidas = None                     # None: cualquier casilla nueva; si no, solo estas

    def calcular():
        Dz.linea.cache_clear()
        elegido, usoc = {}, collections.Counter()
        for u in unidades:
            r = reparto(u)
            elegido[id(u)] = r
            if r:
                peso = 1000 if u['juego'] == 'ie1' else 1       # la ficha de IE1 primero (queja del usuario)
                for sel in r[2][2]:
                    for c, _, _ in sel:
                        if c.startswith(DD.PREF):
                            usoc[c] += peso
        nuevas = [c for c in usoc if Dz.reutilizable(c, None) is None]
        usados_sjis = set()
        for u in unidades:
            r = elegido[id(u)]
            if r:
                for sel in r[2][2]:
                    usados_sjis |= {claves_reg[c] for c, _, _ in sel if c in claves_reg}
        for c in usoc:
            e = Dz.reutilizable(c, None)
            if e is not None:
                usados_sjis.add(e['sjis'])
        libres = [x for x in liberables if x not in usados_sjis] + list(libres_extra)
        return elegido, usoc, nuevas, libres

    demanda_inicial = None
    for ronda in range(MAX_RONDAS):
        elegido, usoc, nuevas, libres = calcular()
        if demanda_inicial is None:
            demanda_inicial = len(nuevas)
        print('ronda', ronda, 'casillas nuevas', len(nuevas), 'códigos', len(libres),
              'sin reparto', sum(1 for u in unidades if elegido[id(u)] is None), flush=True)
        if len(nuevas) <= len(libres):
            break
        if ronda < 3:
            for c in nuevas:
                Dz.coste[c] = 0.2 if usoc[c] >= 6 else (0.6 if usoc[c] >= 3 else 2.0)
            continue
        # sin códigos para todo: solo las casillas más usadas (el resto, con los dibujos existentes)
        orden = sorted(nuevas, key=lambda c: (-usoc[c], c))
        permitidas = set(orden[:len(libres)])
        Dz.coste_def = M8.INF
        Dz.coste = {c: (0.2 if c in permitidas else M8.INF) for c in set(Dz.coste) | set(nuevas)}
    else:
        raise SystemExit('sin códigos suficientes para las descripciones')
    recortadas = [] if permitidas is None else sorted(set(orden) - permitidas)

    # ---- asignación y dibujo ----------------------------------------------------------------------------
    registro = reg['bigramas']
    por_sjis = {e['sjis']: e for e in registro}
    esc = A88.V75G.Celdas(F)
    asign = {}
    redibujados, añadidos = [], []
    libres_iter = iter(libres)
    for c in sorted(nuevas, key=lambda c: (-usoc[c], c)):
        s = next(libres_iter)
        t, d, g = DD.de_clave(c)
        m = Dz.trozo(t, g)
        gi = F.gi(int(por_sjis[s]['unicode'][2:], 16)) if s in por_sjis else F.gi(ord(bytes.fromhex(s).decode('cp932')))
        viejo = list(F.metrics[gi])
        for y in range(F.sy):
            for x in range(F.sx):
                esc.escribir(gi, x, y, 0)
        for (x, y), v in m['px'].items():
            assert 0 <= x < F.sx - 1 and 0 <= y < F.sy - 1, (c, x, y)
            esc.escribir(gi, 1 + x, 1 + y, v)
        ancho = m['ancho']
        adv = d + ancho + (5 if t.endswith(' ') else 1)
        left = d - int((15 - adv) / 2)
        assert -128 <= left <= 127
        F.set_metrics(gi, left, ancho, adv)
        leido = {(x, y): v for y, row in enumerate(F.bitmap(gi)) for x, v in enumerate(row) if v}
        assert leido == m['px'], c
        px_sha = hashlib.sha1(json.dumps(sorted(m['px'].items())).encode()).hexdigest()
        info = dict(glifo=gi, cwdh_antes=viejo, cwdh=[left, ancho, adv], tinta_px=ancho, columna=d, hueco_interno=g,
                    pixeles_sha1=px_sha, maqueta='v08 descripciones (paso 15, columna libre)')
        if s in por_sjis:
            e = por_sjis[s]
            e.update(par=t, clave=c, variante=f'v08 descripción (tinta desde la columna {d})', glifo=gi,
                     cwdh=[left, ancho, adv], pixeles_sha1=px_sha, campos=['descripcion'],
                     redibujado_v08=dict(par_antes=e['par'], clave_antes=A89.clave_de(e),
                                         fuentes_antes=sorted(e['fuentes'])),
                     fuentes={F12: info})
            for k in ('D', 'R', 'tinta_px', 'cwdh_kanji', 'uso', 'origen_dibujo'):
                e.pop(k, None)
            redibujados.append(s)
        else:
            ch = bytes.fromhex(s).decode('cp932')
            e = dict(par=t, sjis=s, unicode=f'U+{ord(ch):04X}', kanji=ch, origen='v08_deposito', clave=c,
                     variante=f'v08 descripción (tinta desde la columna {d})', fuentes={F12: info}, glifo=gi,
                     cwdh=[left, ancho, adv], pixeles_sha1=px_sha, campos=['descripcion'])
            registro.append(e)
            por_sjis[s] = e
            añadidos.append(c)
        asign[c] = bytes.fromhex(s)

    codec2 = A89.Codec(registro)
    claves_reg = {A89.clave_de(e): bytes.fromhex(e['sjis']) for e in registro}

    def cod(c):
        if c in asign:
            return asign[c]
        if c.startswith(DD.PREF):
            return bytes.fromhex(Dz.reutilizable(c, None)['sjis'])
        if c in claves_reg and (len(c) > 1 or R.variante(c)):
            return claves_reg[c]
        return A88.V79.codificar(c)

    # ---- escribir ---------------------------------------------------------------------------------------
    sts = {j: bytearray(get(STR[j])) for j in STR}
    filas, sin = [], []
    for u in unidades:
        r = elegido[id(u)]
        if r is None:
            sin.append(dict(juego=u['juego'], offset=u['offset'], texto=u['actual']))
            continue
        origen, t, (cst, lineas, sels, modo) = r
        partes = [b''.join(cod(c) for c, _, _ in sel) for sel in sels]
        nuevo = NL.join(partes)
        cap = u['fin'] - u['offset']
        assert len(nuevo) <= cap - 1, u
        dec = codec2.texto(nuevo).replace('¤', '\n')
        assert dec == '\n'.join(lineas), (dec, lineas)
        sts[u['juego']][u['offset']:u['fin']] = nuevo + bytes(cap - len(nuevo))
        filas.append(dict(juego=u['juego'], offset=u['offset'], registros=u['registros'], origen=origen, modo=modo,
                          texto='\n'.join(lineas), oficial_eu=u['oficial_eu'], antes=u['actual'],
                          casillas=['|'.join(Dz.texto_de(c) for c, _, _ in s) for s in sels],
                          huecos=[[g for g, _ in Dz.huecos(s)] for s in sels],
                          primera_tinta=[s[0][1] for s in sels], bytes_antes=len(u['body']), bytes=len(nuevo),
                          hueco=cap))
    for j, b in sts.items():
        if bytes(b) != get(STR[j]):
            p = HERE / 'extra' / STR[j]
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(bytes(b))
    datos = F.data()
    assert len(datos) == len(datos12)
    ruta12.write_bytes(datos)
    reg['fuentes_dibujadas'][F12] = sha(datos)
    reg['pares_ie2_v08_descripciones'] = añadidos
    reg['codigos_ie2_v08_redibujados'] = redibujados
    reg['regla_descripciones_v08'] = ('FONT12 paso 15: trozos de 1-4 caracteres (2 px entre letras, 1 si no cabe; '
                                      'espacio interior 5) con la tinta en cualquier columna D de [0, 14]; '
                                      'advance = D + ancho + (5 si acaba en espacio, si no 1); left = D - trunc((15 - advance)/2)')
    (HERE / 'registro.json').write_text(json.dumps(reg, ensure_ascii=False, indent=1), encoding='utf-8')

    # ---- comprobación automática -----------------------------------------------------------------------
    avisos = []
    for f in filas:
        for li, (lin, hs, p0) in enumerate(zip(f['texto'].split('\n'), f['huecos'], f['primera_tinta'])):
            palabras = len(lin.split())
            sel_p = 1 + sum(1 for g in hs if g >= 4)
            motivos = []
            if lin != lin.strip(' ') or p0 > 3:
                motivos.append(f'espacio inicial (primera tinta en {p0})')
            if sel_p != palabras:
                motivos.append(f'palabras {palabras} vs separaciones visibles {sel_p}')
            internos = [g for g in hs if g < 4]
            if any(g > 4 for g in internos):
                motivos.append('hueco interno > 3')
            if motivos:
                avisos.append(dict(juego=f['juego'], offset=f['offset'], linea=li, texto=lin, huecos=hs, motivos=motivos))
    (HERE / 'comprobacion_desc.json').write_text(json.dumps(dict(
        nota='Comprobación automática de todas las descripciones (huecos en px a paso 15).',
        descripciones=len(filas), avisos=len(avisos), detalle=avisos), ensure_ascii=False, indent=1), encoding='utf-8')
    informe = dict(
        nota='Contiene texto del juego: no publicar. Validación offline.',
        descripciones=len(filas), sin_reparto=sin,
        por_origen=dict(collections.Counter(f"{f['juego']}_{f['origen']}" for f in filas)),
        eu_disponibles=sum(1 for u in unidades if u['oficial_eu']),
        eu_que_no_caben=sum(1 for f in filas if f['oficial_eu'] and f['origen'] != 'eu'),
        codigos=dict(casillas_nuevas=len(nuevas), nuevos=len(añadidos), redibujados=len(redibujados),
                     liberables=len(liberables), deposito_restante=len(libres_extra),
                     casillas_descartadas_por_falta_de_codigos=len(recortadas),
                     demanda_sin_limite=demanda_inicial),
        fuente_FONT12=reg['fuentes_dibujadas'][F12], filas=filas)
    (HERE / 'informe_desc.json').write_text(json.dumps(informe, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps({k: v for k, v in informe.items() if k not in ('filas', 'sin_reparto')}, ensure_ascii=False))
    print('sin reparto', len(sin), 'avisos', len(avisos))


if __name__ == '__main__':
    main()
