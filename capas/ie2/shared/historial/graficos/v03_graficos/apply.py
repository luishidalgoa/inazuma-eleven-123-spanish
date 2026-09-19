"""v03 · gráficos de IE2 (issue #73). No construye candidata ni instala.

Pasos (sin mover atlas ni tamaños; metadata CTPK idéntica; .arc SSZL recomprimidos de verdad):
  1. Texturas CTPK idénticas (píxeles) a una de IE1 que v89 tradujo -> se copia la de IE1.
  2. Trasplante por regiones: por cada textura IE1 traducida, cada zona conexa de píxeles cambiados
     (dilatada 2 px) se copia a la textura IE2 del mismo nombre (ie01_X/ie02_X) y tamaño SOLO si el
     recorte japonés coincide exactamente en esa posición. Las zonas que no coinciden quedan en pendientes.
  3. Sprites DS heredados: .pac_/.pac sueltos de pic2d, pic2d/menu, pic2d/cmd, pic3d, pic3d/script,
     obj2d/rpg con versión en .../sp/ de la NDS española, si ambos decodifican con las mismas medidas.
     Paquetes pic2d/team (pkh/pkb): se reconstruyen con la lista de IDs japonesa y la entrada NDS si existe
     y tiene el mismo tamaño de textura (como v66). pic2d/ending (créditos) queda fuera.
Salida: extra/<ruta del archive>, informe.json, pendientes.json, previews/.
Uso: python apply.py
"""
import json
import re
import struct
from collections import defaultdict

import numpy as np
from PIL import Image
from scipy import ndimage

import comun as C
from pkb_unpack import parse_index

PENDIENTES = []


def zonas_cambiadas(a, b):
    d = np.any(np.asarray(a) != np.asarray(b), -1)
    d = ndimage.binary_dilation(d, iterations=2)
    lab, n = ndimage.label(d)
    return [(s[1].start, s[0].start, s[1].stop, s[0].stop) for s in ndimage.find_objects(lab)]


def indice_ie1():
    jp, tr = C.jp(), C.ie1tr()
    exacto, por_nombre = {}, defaultdict(list)
    for p in jp.rutas('inazuma1/'):
        if not p.endswith(('.arc', '.lzs')) or p not in tr:
            continue
        a = C.U.unwrap(jp.get(p))
        b = C.U.unwrap(tr.get(p))
        ta, tb = C.texturas(a), C.texturas(b)
        if len(ta) != len(tb):
            continue
        for (n1, _, _, x), (n2, _, _, y) in zip(ta, tb):
            if n1 != n2 or x == y or len(x) != len(y):
                continue
            exacto.setdefault(C.clave_pixeles(x), (p, n1, y))
            por_nombre[re.sub(r'^ie0?1_', '', n1)].append((p, n1, x, y))
    return exacto, por_nombre


def recolorear_zona(A, B, X):
    """Si X es A con otra paleta (función de color A->X), aplica la misma función a B."""
    if not np.array_equal(A[..., 3], X[..., 3]):
        return None
    mapa = {}
    for pa, px in zip(A.reshape(-1, 4), X.reshape(-1, 4)):
        k = pa.tobytes()
        v = mapa.setdefault(k, px.tobytes())
        if v != px.tobytes():
            return None
    claves = np.array([np.frombuffer(k, np.uint8) for k in mapa]).astype(int)
    out = np.empty_like(B)
    for i, pb in enumerate(B.reshape(-1, 4)):
        k = pb.tobytes()
        if k not in mapa:
            j = int(np.argmin(((claves - pb.astype(int)) ** 2).sum(1)))
            src = claves[j]
            dst = np.frombuffer(mapa[claves[j].astype(np.uint8).tobytes()], np.uint8).astype(int)
            # conserva el desplazamiento de color relativo (antialias del texto)
            v = np.clip(dst + (pb.astype(int) - src), 0, 255).astype(np.uint8)
            if pb[3] == 0:
                v = pb
            out.reshape(-1, 4)[i] = v
        else:
            out.reshape(-1, 4)[i] = np.frombuffer(mapa[k], np.uint8)
    return out


def trasplantar(blob, cands, ruta, nombre):
    """Devuelve (imagen, zonas_pendientes) o None."""
    _, w, h, fmt, _, _ = C.T.metadata(blob)
    if fmt not in C.EDITABLES:
        return None
    base = np.asarray(C.decodificar(blob))
    ie2 = base.copy()
    for p1, n1, x, y in cands:
        m = C.T.metadata(x)
        if (m[1], m[2]) != (w, h):
            continue
        a, b = np.asarray(C.decodificar(x)), np.asarray(C.decodificar(y))
        ok, fallo = 0, []
        for x0, y0, x1, y1 in zonas_cambiadas(a, b):
            A, B, X = a[y0:y1, x0:x1], b[y0:y1, x0:x1], base[y0:y1, x0:x1]
            if np.array_equal(A, X):
                ie2[y0:y1, x0:x1] = B
                ok += 1
                continue
            cambio = np.any(A != B, -1)
            if np.array_equal(A[cambio], X[cambio]):
                ie2[y0:y1, x0:x1][cambio] = B[cambio]
                ok += 1
                continue
            R = recolorear_zona(A, B, X)
            if R is not None:
                ie2[y0:y1, x0:x1] = R
                ok += 1
                continue
            hecho = False
            for dy in range(-12, 13):
                for dx in range(-12, 13):
                    if hecho or (dx == 0 and dy == 0):
                        continue
                    u0, v0 = x0 + dx, y0 + dy
                    if u0 < 0 or v0 < 0 or u0 + (x1 - x0) > w or v0 + (y1 - y0) > h:
                        continue
                    Y = base[v0:v0 + (y1 - y0), u0:u0 + (x1 - x0)]
                    if np.array_equal(A[cambio], Y[cambio]):
                        ie2[v0:v0 + (y1 - y0), u0:u0 + (x1 - x0)][cambio] = B[cambio]
                        hecho = True
            if hecho:
                ok += 1
            else:
                fallo.append([x0, y0, x1, y1])
        if not ok and not fallo:
            return None
        return Image.fromarray(ie2, 'RGBA'), fallo, f'{p1}:{n1}'
    return None


def texturas_ie2(exacto, por_nombre, ediciones):
    """ediciones[(ruta, nombre)] = dict(imagen, modo, zonas_pendientes)."""
    jp = C.jp()
    for ruta in sorted(jp.rutas('inazuma2/')):
        if not ruta.endswith(('.arc', '.lzs')):
            continue
        raw = C.U.unwrap(jp.get(ruta))
        for nombre, off, ln, blob in C.texturas(raw):
            k = C.clave_pixeles(blob)
            if k in exacto and len(exacto[k][2]) == ln:
                ediciones[(ruta, nombre)] = dict(imagen=C.decodificar(exacto[k][2]), modo='ie1_exacta', pendientes=[])
                continue
            cands = por_nombre.get(re.sub(r'^ie0?2_', '', nombre), [])
            r = trasplantar(blob, cands, ruta, nombre) if cands else None
            if r:
                im, fallo, ref = r
                ediciones[(ruta, nombre)] = dict(imagen=im, modo='ie1_regiones', pendientes=fallo, ie1=ref)


def escribir_texturas(ediciones, informe, previews):
    jp = C.jp()
    por_arc = defaultdict(dict)
    for (ruta, nombre), e in ediciones.items():
        if e['pendientes']:
            PENDIENTES.append(dict(tipo='zona_sin_pintar', arc=ruta, textura=nombre, zonas=e['pendientes'],
                                   ie1=e.get('ie1')))
            continue
        por_arc[ruta][nombre] = e
    for ruta in sorted(por_arc):
        original = jp.get(ruta)
        raw = C.U.unwrap(original)
        salida = bytearray(raw)
        cambios = []
        for nombre, off, ln, blob in C.texturas(raw):
            e = por_arc[ruta].get(nombre)
            if not e:
                continue
            nuevo = C.codificar(blob, e['imagen'])
            if nuevo == blob:
                continue
            salida[off:off + ln] = nuevo
            cambios.append(dict(textura=nombre, modo=e['modo']))
            grupo = e.get('grupo') or (ruta.split('/')[2] if '/a_data_replace/' not in ruta else ruta.split('/')[3])
            antes, despues = C.decodificar(blob), C.decodificar(nuevo)
            previews[grupo].append(C.par(antes, despues, titulo=f'{ruta.split("/")[-1]} {nombre} [{e["modo"]}]'))
            if e['modo'].startswith('pintada'):
                previews['x4_' + grupo].extend(e.get('zoom', []))
        if cambios:
            assert C.U.entries(bytes(salida)) == C.U.entries(raw)
            datos = C.reenvolver(original, bytes(salida))
            destino = C.EXTRA / ruta
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_bytes(datos)
            informe.append(dict(ruta=ruta, clase='textura', cambios=cambios, sszl=original[:4] == b'SSZL',
                                tam_original=len(original), tam_nuevo=len(datos)))


# ------------------------------------------------------------ sprites DS

def dec_pac(d):
    d = C.ds_decomp(d)
    return C.L.decode(d)


SUELTOS = ['pic2d', 'pic2d/menu', 'pic2d/cmd', 'pic2d/title', 'pic3d', 'pic3d/script', 'obj2d/rpg']


def sprites(informe, previews):
    jp = C.jp()
    for carpeta in SUELTOS:
        sp = C.NDS / 'data_iz' / carpeta / 'sp'
        if not sp.is_dir():
            continue
        es = {f.name.lower(): f for f in sp.iterdir() if f.is_file()}
        pref = f'inazuma2/data_iz/{carpeta}/'
        for ruta in sorted(jp.rutas(pref)):
            nombre = ruta[len(pref):]
            if '/' in nombre or not nombre.lower().endswith(('.pac_', '.pac')) or nombre.lower() not in es:
                continue
            orig, nuevo = jp.get(ruta), es[nombre.lower()].read_bytes()
            if orig == nuevo:
                continue
            try:
                a, b = dec_pac(orig), dec_pac(nuevo)
            except Exception as e:  # noqa: BLE001
                PENDIENTES.append(dict(tipo='sprite_no_4bpp', ruta=ruta, motivo=str(e)))
                continue
            if a.size != b.size:
                PENDIENTES.append(dict(tipo='sprite_medidas_distintas', ruta=ruta, jp=a.size, es=b.size))
                continue
            if a.tobytes() == b.tobytes():
                continue
            destino = C.EXTRA / ruta
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_bytes(nuevo)
            informe.append(dict(ruta=ruta, clase='sprite_nds', tam_original=len(orig), tam_nuevo=len(nuevo)))
            previews['sprites_' + carpeta.replace('/', '_')].append(C.par(a, b, titulo=nombre))


def paquetes_equipo(informe, previews):
    jp = C.jp()
    d = 'inazuma2/data_iz/pic2d/team/'
    for pkh in sorted(p for p in jp.rutas(d) if p.endswith('.pkh')):
        pkb = pkh[:-1] + 'b'
        base = pkh.split('/')[-1][:-4]
        fh, fb = C.NDS / 'data_iz/pic2d/team/sp' / (base + '.pkh'), C.NDS / 'data_iz/pic2d/team/sp' / (base + '.pkb')
        if not (fh.exists() and fb.exists()):
            continue
        jh, jb, eh, eb = jp.get(pkh), jp.get(pkb), fh.read_bytes(), fb.read_bytes()
        ij = parse_index(jh)
        ie = {i: (o, s) for i, o, s in parse_index(eh)}
        alin = 4 if all(o % 4 == 0 for _, o, _ in ij) else 1
        cuerpo, tabla, usadas = bytearray(), [], 0
        for i, o, s in ij:
            datos = jb[o:o + s]
            if i in ie:
                cand = eb[ie[i][0]:ie[i][0] + ie[i][1]]
                try:
                    a, b = dec_pac(datos), dec_pac(cand)
                    if a.size == b.size and a.tobytes() != b.tobytes():
                        datos = cand
                        usadas += 1
                        previews['sprites_team'].append(C.par(a, b, titulo=f'{base}:{i}'))
                except Exception:  # noqa: BLE001
                    if cand != datos:
                        PENDIENTES.append(dict(tipo='paquete_entrada_no_decodifica', ruta=pkb, id=i))
            cuerpo.extend(bytes((-len(cuerpo)) % alin))
            tabla.append((i, len(cuerpo), len(datos)))
            cuerpo.extend(datos)
        cuerpo.extend(bytes((-len(cuerpo)) % alin))
        if not usadas:
            continue
        cab = bytearray(jh)
        for k, t in enumerate(tabla):
            struct.pack_into('<III', cab, 0x30 + 12 * k, *t)
        assert [(i, s) for i, _, s in parse_index(bytes(cab))] == [(i, s) for i, _, s in tabla]
        for ruta, datos in ((pkh, bytes(cab)), (pkb, bytes(cuerpo))):
            destino = C.EXTRA / ruta
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_bytes(datos)
        informe.append(dict(ruta=pkb, clase='paquete_nds', entradas_nds=usadas, total=len(ij)))


def main():
    import shutil
    shutil.rmtree(C.EXTRA, ignore_errors=True)
    shutil.rmtree(C.PREVIEWS, ignore_errors=True)
    C.PREVIEWS.mkdir(parents=True)
    informe, previews = [], defaultdict(list)
    exacto, por_nombre = indice_ie1()
    ediciones = {}
    texturas_ie2(exacto, por_nombre, ediciones)
    # celdas_ie1 (trasplante por celdas QNA) desactivado: deja texturas mezcladas y la coincidencia por forma
    # da falsos positivos («Equilibrio» en lugar de «Sí»).
    import pintado
    for ruta, nombre, motivo in pintado.aplicar(ediciones):
        PENDIENTES.append(dict(tipo='pintado_fallido', arc=ruta, textura=nombre, motivo=motivo))
    escribir_texturas(ediciones, informe, previews)
    sprites(informe, previews)
    # paquetes_equipo(informe, previews)  # desactivado: las entradas NDS decodifican vacías (formato distinto)
    for grupo, ims in previews.items():
        for i in range(0, len(ims), 40):
            C.hoja(ims[i:i + 40]).save(C.PREVIEWS / f'{grupo}_{i // 40:02d}.png')
    (C.HERE / 'informe.json').write_text(json.dumps(informe, ensure_ascii=False, indent=1), encoding='utf-8')
    (C.HERE / 'pendientes.json').write_text(json.dumps(PENDIENTES, ensure_ascii=False, indent=1), encoding='utf-8')
    print(len(informe), 'ficheros;', sum(len(r.get('cambios', [])) for r in informe), 'texturas;',
          len(PENDIENTES), 'pendientes')


if __name__ == '__main__':
    main()
