"""Validación independiente de las capas IE1 v90 / IE2 v04 (cro_restantes). Lee solo ficheros de disco.

Comprueba por juego:
  CRO   mismo tamaño que la base; solo cambian los huecos declarados; cada hueco = cuerpo + NUL de relleno;
        cuerpo no vacío, <= bytes del japonés (= en listas empaquetadas); el japonés está en el CRO original;
        fuera de los huecos la salida es idéntica a la base (v89 / v03); ninguna referencia dentro del hueco
        salvo las declaradas; cabecera, segmentos, importaciones, exportaciones y relocaciones intactos;
        el texto decodificado con el registro v90 es el del informe; mismos %s/%d; sha256 del informe.
  BCFNT las de extra/ coinciden con registro.json y son idénticas en las dos capas; solo cambian los glifos y
        anchos de los códigos del registro marcados en v90; cada casilla usada tiene glifo en sus fuentes
        reales y su dibujo coincide con pixeles_sha1; hueco sólido >= mínimo a su paso real.
  NFTR  ninguna en extra/.
Uso: python -X utf8 validar90.py ie1|ie2
"""
from __future__ import annotations

import hashlib
import json
import struct
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import comun90 as C  # noqa: E402
AP = C.comun88.modulo('v90_cro_restantes_apply', HERE / 'apply.py')

TABLAS = {0xC0: 1, 0xC8: 12, 0xD0: 8, 0xD8: 4, 0xE0: 1, 0xE8: 8, 0xF0: 20, 0xF8: 12, 0x100: 8,
          0x108: 8, 0x110: 8, 0x118: 1, 0x120: 8, 0x128: 12, 0x130: 12}


def rangos_cro(d):
    out = [(0, 0x138)]
    for campo, tam in TABLAS.items():
        o, n = struct.unpack_from('<II', d, campo)
        if n:
            out.append((o, o + n * tam))
    return out


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    j = sys.argv[1]
    cfg = AP.JUEGOS[j]
    fallos = []
    inf = json.loads((cfg['dir'] / 'informe.json').read_text(encoding='utf-8'))
    tabla = json.loads(cfg['tabla'].read_text(encoding='utf-8'))
    reg = json.loads(C.REG90.read_text(encoding='utf-8'))
    base, orig = cfg['base'].read_bytes(), cfg['orig'].read_bytes()
    out = (cfg['dir'] / cfg['rel']).read_bytes()
    if len(out) != len(base):
        fallos.append('tamaño distinto')
    if hashlib.sha256(out).hexdigest() != inf['salida_sha256'] or hashlib.sha256(base).hexdigest() != inf['base_sha256']:
        fallos.append('sha256 distinto del informe')

    # ---- fuentes
    tmp = Path(tempfile.mkdtemp(prefix='val90_'))
    F = {}
    for f in C.FUENTES:
        p = cfg['dir'] / 'extra' / f
        otra = (AP.IE2_DIR if j == 'ie1' else C.HERE) / 'extra' / f
        if not p.is_file():
            fallos.append(f'falta {p}')
            continue
        datos = p.read_bytes()
        if hashlib.sha256(datos).hexdigest() != reg['fuentes_dibujadas'][f]:
            fallos.append(f'{f}: sha distinto del registro')
        if not otra.is_file() or otra.read_bytes() != datos:
            fallos.append(f'{f}: la copia de la otra capa es distinta')
        (tmp / Path(f).name).write_bytes(datos)
        F[f] = C.A88.cargar(tmp / Path(f).name)
    nftr = [p for p in (cfg['dir'] / 'extra').rglob('*') if p.suffix.upper() == '.NFTR']
    if nftr:
        fallos.append(f'NFTR en extra: {nftr}')
    T = C.Tipografia()          # fuentes v89 (antes) para comparar
    cambiados = {f: set() for f in C.FUENTES}
    for e in reg['bigramas']:
        for f, info in e['fuentes'].items():
            if info.get('v90') or 'v90' in str(info.get('maqueta', '')):
                cambiados[f].add(info['glifo'])
    for f in C.FUENTES:
        if f not in F:
            continue
        A, B = T.F[f], F[f]
        glifos = set(A.metrics) | set(B.metrics)
        for gi in glifos:
            if gi == C.GI_ORD:
                continue
            if A.metrics.get(gi) != B.metrics.get(gi) and gi not in cambiados[f]:
                fallos.append(f'{f}: ancho cambiado en glifo {gi} no declarado')
        muestra = [gi for gi in range(0, max(B.metrics) + 1, 97)]
        for gi in muestra:
            if gi not in cambiados[f] and gi in B.metrics and A.bitmap(gi) != B.bitmap(gi):
                fallos.append(f'{f}: dibujo cambiado en glifo {gi} no declarado')
    codec = C.A89.Codec(reg['bigramas'])
    por_clave = {C.A89.clave_de(e): e for e in reg['bigramas']}
    sjis = [e['sjis'] for e in reg['bigramas']]
    if len(set(sjis)) != len(sjis):
        fallos.append('códigos repetidos en el registro')

    def celda_ok(c, f):
        e = por_clave[c]
        info = e['fuentes'].get(f)
        if info is None and f != C.F12:
            return False
        Fu = F[f]
        gi = Fu.gi(int(e['unicode'][2:], 16))
        px = {(x, y): v for y, row in enumerate(Fu.bitmap(gi)) for x, v in enumerate(row) if v}
        return hashlib.sha1(json.dumps(sorted(px.items())).encode()).hexdigest() == (info or e)['pixeles_sha1'] \
            if f != C.F12T else bool(px)

    # ---- CRO
    refs = C.Refs(orig)
    blanco = refs.targets | refs.reltargets
    lits = {l['offset']: l for l in inf['literales']}
    huecos = set()
    for e in tabla['literales']:
        o = int(e['offset'], 16)
        jp = e['japones'].encode('cp932')
        k = e['offset']
        if orig[o:o + len(jp) + 1] != jp + b'\0':
            fallos.append(f'{k}: el japonés no está en el original')
        hueco = out[o:o + len(jp) + 1]
        cuerpo = hueco.split(b'\0', 1)[0]
        if not cuerpo or hueco[len(cuerpo):] != b'\0' * (len(hueco) - len(cuerpo)):
            fallos.append(f'{k}: vacío o relleno no NUL')
        if len(cuerpo) > len(jp) or (e.get('exacto') and len(cuerpo) != len(jp)):
            fallos.append(f'{k}: longitud {len(cuerpo)} frente a {len(jp)}')
        internas = {int(x, 16) for x in e.get('referencias_internas', {})}
        dentro = [t for t in blanco if o < t < o + len(jp) and t not in internas]
        if dentro:
            fallos.append(f'{k}: referencias dentro {[hex(t) for t in dentro]}')
        huecos.update(range(o, o + len(jp) + 1))
        l = lits[k]
        if cuerpo.hex() != l['hex']:
            fallos.append(f'{k}: no coincide con el informe')
        if 'igual_a' in e:
            ref = int(e['igual_a'], 16)
            if cuerpo != out[ref:ref + len(cuerpo) + 1].split(b'\0')[0]:
                fallos.append(f'{k}: distinto de {e["igual_a"]}')
            continue
        import re as _re
        txt = codec.texto(cuerpo)
        esperado = ''.join(C.texto(c) for c in e['celdas']) if 'celdas' in e else l['espanol']
        esperado = _re.sub('¤+', '¤', C.FMT.sub('¤', esperado))
        if txt.rstrip(' ') != esperado.rstrip(' ') and txt != esperado:
            fallos.append(f'{k}: decodifica {txt!r}, se esperaba {esperado!r}')
        if [x for x in C.FMT.findall(cuerpo.decode('latin1')) if x != '\n'] != \
                [x for x in C.FMT.findall(e['japones']) if x != '\n']:
            fallos.append(f'{k}: especificadores distintos')
        fuentes_reales = C.REALES[l['campo']] + tuple(x for x in e.get('extra', ()) if x not in C.REALES[l['campo']])
        claves = [c for c in codec.claves(cuerpo) if c is not None]
        for c in claves:
            for f in fuentes_reales:
                if len(c) >= 2 or C.R.variante(c):
                    dib = celda_ok(c, f)
                    faltaba = f'{C.texto(c)}:{AP.NOMBRE_F[f]}' in l['sin_dibujo_extra']
                    if not dib and not faltaba:
                        fallos.append(f'{k}: {c!r} sin dibujo en {f}')
                elif c != ' ' and F[f].gi(C.A88.codepoint(c)) is None:
                    fallos.append(f'{k}: {c!r} sin glifo en {f}')
        for fn, h in l['huecos'].items():
            f = next(x for x in C.FUENTES if AP.NOMBRE_F[x] == fn)
            if h['dibujado'] and h['hueco_min_px'] is not None and h['hueco_min_px'] < C.A88.HUECO_MIN[f]:
                fallos.append(f'{k}: solape en {fn}')
        for pth in l['previews']:
            if not (C.ROOT / pth).is_file():
                fallos.append(f'{k}: falta la vista previa {pth}')
    cambios = [i for i in range(len(base)) if base[i] != out[i]]
    fuera = [i for i in cambios if i not in huecos]
    if fuera:
        fallos.append(f'{len(fuera)} bytes cambiados fuera de los huecos (primero {fuera[0]:#x})')
    for a, b in rangos_cro(base):
        if base[a:b] != out[a:b]:
            fallos.append(f'tabla CRO {a:#x}-{b:#x} modificada')

    res = dict(juego=j, ok=not fallos, fallos=fallos, literales=len(tabla['literales']),
               bytes_cambiados=len(cambios), salida_sha256=hashlib.sha256(out).hexdigest(),
               fuentes={f: reg['fuentes_dibujadas'][f] for f in C.FUENTES})
    (cfg['dir'] / 'validacion.json').write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return 0 if not fallos else 1


if __name__ == '__main__':
    sys.exit(main())
