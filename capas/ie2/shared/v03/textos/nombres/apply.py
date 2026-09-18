"""IE2 v03 · nombres del hablante (unitbase.dat +0/+16) y descripciones (unitbase.STR).

Base: work/shared/candidatas/probe_ie2_v02/archive.fa. Fuente oficial: NDS ES (tormenta_de_fuego/fuentes/nds_es).
Convención de IE1 v89: +0 == +16 == nombre corto oficial (NDS +32) con bigramas (máx. 7 casillas).
+32 (kana completo, 32 B, issue #16) y los datos (+64..+96) no se tocan.

Emparejado 3DS <-> NDS: ambos ficheros son de 2399 registros de 96 B, pero la NDS tiene registros de más
(PNJ) y no van por índice. Se alinean con difflib la secuencia de firmas (los 16 u16 de +64 sin los
campos de identificador 1, 2, 5 ni el puntero de descripción 15) y los bloques 1:1 no iguales se aceptan
si coincide el identificador (u16 en +66). Después se comprueba que el identificador coincide en todos.

Descripciones: puntero u16 en +94 (3DS: x32 dentro de unitbase.STR, longitud variable; NDS: x128,
huecos fijos). Hueco 3DS = del offset al siguiente offset usado o al primer byte no nulo tras el NUL
japonés. Mismo número de líneas que el japonés y <= 28 casillas por línea (textura 14x2 de IE1).

Uso: python -X utf8 apply.py
Salida: extra/inazuma2/data_iz/logic/unitbase.{dat,STR} (solo si cambian), informe.json
"""
from __future__ import annotations

import bisect
import collections
import difflib
import json
import re
import shutil
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import comun_v03 as K  # noqa: E402

UNIT = f'{K.LOGIC}/unitbase.dat'
USTR = f'{K.LOGIC}/unitbase.STR'
IE1_V89 = K.ROOT / 'work/shared/candidatas/probe_ie1_v89/archive.fa'
IE1_UNIT = 'inazuma1/data_iz/logic/unitbase.dat'
MAX_LINEA = 28
REC = 96
NREG = 2399

# Volcado literal (regla del usuario): nombre corto NDS tal cual si cabe; si no, se quitan palabras del
# final; si ni la primera palabra cabe, prefijo más largo (convención IE1). Sin nombres por rol: todos los
# registros no ficticios tienen nombre NDS.
MANUAL: dict[int, list[str]] = {}


def jp_nombre(r: bytes) -> str:
    return r[:16].split(b'\0')[0].decode('cp932', 'replace')


def u16s(r: bytes):
    return struct.unpack('<16H', r[64:96])


def firma(r: bytes):
    return tuple(v for k, v in enumerate(u16s(r)) if k not in (1, 2, 5, 15))


def emparejar(J, D):
    sm = difflib.SequenceMatcher(None, [firma(r) for r in J], [firma(r) for r in D], autojunk=False)
    m = {}
    por_firma = 0
    for op, a0, a1, b0, b1 in sm.get_opcodes():
        if op == 'equal':
            for t in range(a1 - a0):
                m[a0 + t] = b0 + t
            por_firma += a1 - a0
        elif op == 'replace' and a1 - a0 == b1 - b0:
            for t in range(a1 - a0):
                if u16s(J[a0 + t])[1] == u16s(D[b0 + t])[1]:
                    m[a0 + t] = b0 + t
    por_id = {}
    for b, r in enumerate(D):
        por_id.setdefault(u16s(r)[1], []).append(b)
    corregidos = []
    for a, b in list(m.items()):
        ida = u16s(J[a])[1]
        if ida != u16s(D[b])[1] and len(por_id.get(ida, [])) == 1:
            m[a] = por_id[ida][0]
            corregidos.append(dict(tds=a, nds_difflib=b, nds_por_id=m[a], id=ida))
    ids_distintos = [(a, b) for a, b in m.items() if u16s(J[a])[1] != u16s(D[b])[1]]
    return m, dict(por_firma=por_firma, corregidos_por_id=corregidos, por_id_en_bloques_replace=len(m) - por_firma,
                   id_distinto=[dict(tds=a, nds=b, id_3ds=u16s(J[a])[1], id_nds=u16s(D[b])[1])
                                for a, b in ids_distintos])


def nombres_ie1(B):
    """{kanji IE1: nombre corto de IE1 v89} para reutilizar las abreviaturas de IE1."""
    jp = K.abrir(K.JP)(IE1_UNIT)
    v89 = K.abrir(IE1_V89)(IE1_UNIT)
    out = {}
    for i in range((len(jp) - REC) // REC):
        body = v89[REC + i * REC + 16:REC + i * REC + 32].split(b'\0')[0]
        if body == jp[REC + i * REC + 16:REC + i * REC + 32].split(b'\0')[0]:
            continue
        try:
            out.setdefault(jp_nombre(jp[REC + i * REC:]), B.texto(body))
        except Exception:
            pass
    return out


def igual(a, b):
    t = str.maketrans('（）！？％', '()!?¤')   # ％ (0x8193) es opaco para el codec
    return a.translate(t) == b.translate(t)


def cabe(B, t):
    try:
        return B.nombre(t)
    except ValueError:
        return None


def recortar(B, t):
    """Prefijo más largo que cabe (convención IE1: «Crackshot» -> «Cracksh»)."""
    for n in range(len(t) - 1, 0, -1):
        p = t[:n].rstrip(' .')
        if p and cabe(B, p):
            return p
    raise ValueError(t)


def partir_lineas(B, palabras, n):
    """Reparte palabras en n líneas de <= 28 casillas (voraz). None si no cabe."""
    lineas, act = [], ''
    for w in palabras:
        prueba = (act + ' ' + w) if act else w
        if B.libre(prueba)[1] <= MAX_LINEA:
            act = prueba
        else:
            if not act:
                return None
            lineas.append(act)
            act = w
    lineas.append(act)
    if len(lineas) > n:
        return None
    while len(lineas) < n:                    # mismo número de líneas que el japonés: partir la más larga
        k = max(range(len(lineas)), key=lambda j: B.libre(lineas[j])[1])
        ws = lineas[k].split()
        if len(ws) < 2:
            return None
        cortes = [(max(B.libre(' '.join(ws[:c]))[1], B.libre(' '.join(ws[c:]))[1]), c) for c in range(1, len(ws))]
        c = min(cortes)[1]
        lineas[k:k + 1] = [' '.join(ws[:c]), ' '.join(ws[c:])]
    return lineas


# Descripciones condensadas a mano: {texto oficial NDS normalizado: texto condensado (con \n)}
CONDENSADAS = json.loads((HERE / 'condensadas.json').read_text(encoding='utf-8')) \
    if (HERE / 'condensadas.json').exists() else {}


def main():
    B = K.bigramas()
    get = K.base()
    ub = get(UNIT)
    st = get(USTR)
    jp = K.abrir(K.JP)
    ujp, stjp = jp(UNIT), jp(USTR)
    N = (K.NDS / 'logic/sp/unitbase.dat').read_bytes()
    NS = (K.NDS / 'logic/sp/unitbase.STR').read_bytes()
    assert len(ub) == len(N) == REC + NREG * REC
    J = [ujp[REC + i * REC:REC * 2 + i * REC] for i in range(NREG)]
    D = [N[REC + i * REC:REC * 2 + i * REC] for i in range(NREG)]
    m, info_empar = emparejar(J, D)
    ie1 = nombres_ie1(B)

    ub2 = bytearray(ub)
    inf_nombres, recortados, manuales, saltados, fallos = [], [], [], [], []
    tocados = set()

    def escribir(i, body):
        assert len(body) <= 15
        campo = body + bytes(16 - len(body))
        for off in (0, 16):
            ub2[REC + i * REC + off:REC + i * REC + off + 16] = campo
        tocados.add(i)

    for i in range(NREG):
        r = J[i]
        nj = jp_nombre(r)
        if 'ダミー' in r[:48].decode('cp932', 'replace') or '未定' in nj:
            saltados.append(dict(registro=i, japones=nj, motivo='ダミー/未定'))
            continue
        if i == 0:
            escribir(i, K.transportar('Mark'))
            inf_nombres.append(dict(registro=0, japones=nj, texto='Mark', modo='ancho completo sin bigramas'))
            continue
        if i not in m:
            saltados.append(dict(registro=i, japones=nj, motivo='sin pareja NDS'))
            continue
        b = m[i]
        corto = K.dec_nds(D[b][32:64])
        completo = K.dec_nds(D[b][:32])
        if corto is None:
            fallos.append(dict(registro=i, japones=nj, motivo='NDS indescifrable'))
            continue
        oficial = K.normalizar(corto).strip()
        modo = 'oficial'
        if cabe(B, oficial):
            texto = oficial
            if oficial != corto:
                modo = 'oficial sin apóstrofo'
        else:
            texto, motivo = None, None
            ws = oficial.split()
            for n in range(len(ws) - 1, 0, -1):
                if cabe(B, ' '.join(ws[:n])):
                    texto = ' '.join(ws[:n])
                    motivo = f'no cabe en 7 casillas / 15 B; se quitan las palabras finales {ws[n:]}'
                    break
            if texto is None:
                previo = ie1.get(nj)
                if previo and oficial.startswith(previo) and cabe(B, previo):
                    texto, motivo = previo, 'no cabe en 7 casillas / 15 B; recorte igual que IE1 v89'
                else:
                    texto = recortar(B, ws[0] if ws else oficial)
                    motivo = 'no cabe en 7 casillas / 15 B; prefijo más largo que cabe (convención IE1)'
            modo = 'recortado'
            recortados.append(dict(registro=i, japones=nj, nds_completo=completo, nds_corto=corto, texto=texto,
                                   motivo=motivo))
        body = B.nombre(texto)
        assert igual(B.texto(body), texto), (i, texto, B.texto(body))
        escribir(i, body)
        inf_nombres.append(dict(registro=i, nds=b, japones=nj, nds_completo=completo, nds_corto=corto,
                                texto=texto, modo=modo, bytes=len(body)))

    # ---------------------------------------------------------------- descripciones
    ptr = lambda r: int.from_bytes(r[94:96], 'little')
    usados = collections.defaultdict(list)
    for i in range(NREG):
        if ptr(J[i]):
            usados[ptr(J[i]) * 32].append(i)
    offs = sorted(usados)
    st2 = bytearray(st)
    inf_desc, condensadas, desc_saltadas, desc_fallos = [], [], [], []
    for k, off in enumerate(offs):
        if off >= len(stjp):
            continue
        fin_jp = stjp.index(b'\0', off)
        jp_body = stjp[off:fin_jp]
        if not jp_body:
            continue
        sig = offs[k + 1] if k + 1 < len(offs) else len(stjp)
        z = fin_jp
        while z < sig and stjp[z] == 0:
            z += 1
        hueco = z - off                       # incluye el NUL
        n_lineas = jp_body.count(b'\n') + 1
        regs = usados[off]
        vivos = [i for i in regs if i in tocados]
        textos = {}
        for i in regs:
            if i not in m:
                continue
            pn = ptr(D[m[i]])
            if not pn:
                continue
            t = K.dec_nds(NS[pn * 128:(pn + 1) * 128])
            if t and not re.search('[぀-ヿ一-鿿]', t):
                textos.setdefault(t, []).append(i)
        if not vivos or not textos:
            desc_saltadas.append(dict(offset=off, registros=regs,
                                      motivo='sin registro traducido' if not vivos else 'sin descripción NDS'))
            continue
        if len(textos) > 1:
            desc_fallos.append(dict(offset=off, registros=regs, motivo='descripciones NDS distintas',
                                    textos=list(textos)))
        oficial = next(iter(textos))
        norm = K.normalizar(oficial).strip().replace('%', '％').replace('−', '-')   # sin % (printf); − sin glifo
        texto = None
        modo = 'oficial'
        lineas = norm.split('\n')
        try:
            if len(lineas) == n_lineas and all(B.libre(x)[1] <= MAX_LINEA for x in lineas):
                texto = norm
            else:
                pl = partir_lineas(B, norm.split(), n_lineas)
                if pl is not None:
                    texto, modo = '\n'.join(pl), 'oficial con saltos rehechos'
        except ValueError as e:
            modo = f'error: {e}'
        if texto is not None:
            body = B.libre(texto)[0]
            if len(body) + 1 > hueco:
                texto, modo = None, 'no cabe en el hueco'
        if texto is None:
            c = CONDENSADAS.get(norm)
            if c is None:
                desc_fallos.append(dict(offset=off, registros=regs, oficial=norm, lineas=n_lineas, hueco=hueco,
                                        motivo=modo))
                continue
            texto = c
            causa, modo = modo, 'condensada'
            condensadas.append(dict(offset=off, registros=regs, oficial=norm, texto=c, hueco=hueco,
                                    motivo=f'{causa}: hueco de {hueco} B; solo se quitan palabras del oficial'))
        body, maxc = B.libre(texto)
        assert maxc <= MAX_LINEA and len(body) + 1 <= hueco, (off, texto, maxc, len(body), hueco)
        assert body.count(b'\n') == n_lineas - 1, (off, texto)
        assert igual(B.texto(body), texto.replace(chr(10), '¤')), (off, texto, B.texto(body))
        assert b'%' not in body, (off, texto)
        st2[off:z] = body + bytes(z - off - len(body))
        inf_desc.append(dict(offset=off, registros=regs, lineas=n_lineas, hueco=hueco, bytes=len(body) + 1,
                             casillas_max=maxc, texto=texto, modo=modo))

    # ---------------------------------------------------------------- validación
    for i in range(NREG):
        a, d = ub[REC + i * REC:REC * 2 + i * REC], ub2[REC + i * REC:REC * 2 + i * REC]
        assert a[32:] == d[32:], i
        if i not in tocados:
            assert a == d, i
        else:
            assert d[15] == 0 and d[31] == 0
            assert d[:16] == d[16:32]
    assert ub[:REC] == ub2[:REC]
    zonas = [(e['offset'], e['offset'] + e['hueco']) for e in inf_desc]
    for p in range(len(st)):
        if st[p] != st2[p]:
            j = bisect.bisect_right(zonas, (p, 1 << 62)) - 1
            assert j >= 0 and zonas[j][0] <= p < zonas[j][1], p
    assert len(st2) == len(st) and len(ub2) == len(ub)

    out = HERE / 'extra'
    if out.exists():
        shutil.rmtree(out)
    for rel, antes, despues in ((UNIT, ub, ub2), (USTR, st, st2)):
        if bytes(despues) != antes:
            (out / rel).parent.mkdir(parents=True, exist_ok=True)
            (out / rel).write_bytes(bytes(despues))
    resumen = dict(
        nombres=len(inf_nombres),
        nombres_oficiales=sum(1 for e in inf_nombres if e['modo'].startswith('oficial')),
        nombres_rol_manual=len(manuales), recortados=len(recortados),
        saltados=len(saltados), fallos_nombres=len(fallos),
        descripciones=len(inf_desc), condensadas=len(condensadas),
        descripciones_saltadas=len(desc_saltadas), descripciones_pendientes=len(desc_fallos),
        saltos_rehechos=sum(1 for e in inf_desc if e['modo'] == 'oficial con saltos rehechos'),
    )
    informe = dict(
        base=str(K.BASE_V02.relative_to(K.ROOT)), resumen=resumen, emparejado=dict(
            metodo='difflib sobre firmas de datos (+64..+96 sin u16 1,2,5,15) + bloques replace 1:1 con '
                   'mismo id (u16 +66)', parejas=len(m), **info_empar),
        recortados=recortados, rol_manual=manuales, saltados=saltados, fallos_nombres=fallos,
        condensadas=condensadas, descripciones_pendientes=desc_fallos, descripciones_saltadas=desc_saltadas,
        nombres=inf_nombres, descripciones=inf_desc,
        salida=[str((out / r).relative_to(HERE)) for r in (UNIT, USTR) if (out / r).exists()],
    )
    (HERE / 'informe.json').write_text(json.dumps(informe, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(resumen, ensure_ascii=False))
    print('emparejado', len(m), 'id distinto', len(info_empar['id_distinto']))


if __name__ == '__main__':
    main()
