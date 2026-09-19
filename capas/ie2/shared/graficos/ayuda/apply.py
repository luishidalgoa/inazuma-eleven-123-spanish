"""v22 · ayuda de IE2 (issue #77). No construye candidata ni instala.

1. Capturas de ayuda (help_b/data/ie02_tt*.arc, help_t/data/ie02_syup_bg*.arc y sus copias en
   demo_bg/data): la captura 3DS (320x240 en una textura 512x256) es la NDS ×1,25 redibujada. La NDS
   española tiene las mismas 68+3 capturas ya en español (pic3d/script/sp/tt*.pac_, syup_bg*.pac_).
   Se superponen sobre la imagen 3DS solo las zonas donde difieren (cabecera, título, bocadillos y
   notas): NDS ampliada ×1,25 (bilineal), ajustada de color al 3DS con una transformación lineal por
   canal calculada fuera de esas zonas. El resto de la captura 3DS queda intacto.
2. Pestañas de la pantalla de ayuda (a_menu/system_b.arc, window_b02: そうさ/システム en 4 estados) y el
   rótulo きほんそうさ (panel_b04): términos oficiales de la NDS (MASTutorial SYDN_T00/B05):
   «Controles» / «Recursos» y «Controles básicos». Se pinta con el motor v06/v03 (texto nítido, sin caja).
3. Reversión de v21/tutorial: MASTutorial.SPF_ japonés (el 3DS no dibuja ese paquete: ver informe).

Salida: extra/<ruta>, informe.json, pendientes.json, previews/.
Uso: python -X utf8 work/ie2/shared/capas/graficos/ayuda/apply.py
"""
from __future__ import annotations

import json
import shutil
import sys
from collections import Counter

import numpy as np
from PIL import Image, ImageFilter

import ayuda22 as K

C = K.C
import pintado_menus as PM  # noqa: E402  (v03/graficos, en el path por v06/base)

UMBRAL = 70          # diferencia RGB (suma) suavizada que marca «texto/UI distinto»
MARGEN = 3           # px alrededor de cada zona
CABECERA = 44        # filas 0..43: barra azul de cabecera (NDS 0..34) se toma entera de la NDS


def mascara_zonas(jp: np.ndarray, up: np.ndarray) -> np.ndarray:
    d = np.abs(jp.astype(int) - up.astype(int)).sum(2).astype(np.float32)
    from scipy import ndimage
    dm = ndimage.uniform_filter(d, 7)
    m = dm > UMBRAL
    m[:CABECERA] = True
    # rectángulos envolventes de cada componente (texto de bocadillo = rectángulo del bocadillo)
    from scipy import ndimage
    lab, n = ndimage.label(ndimage.binary_dilation(m, iterations=4))
    out = np.zeros_like(m)
    for sl in ndimage.find_objects(lab):
        ys, xs = sl
        if (ys.stop - ys.start) * (xs.stop - xs.start) < 40:
            continue
        out[max(ys.start - MARGEN, 0):ys.stop + MARGEN, max(xs.start - MARGEN, 0):xs.stop + MARGEN] = True
    return out


def ajuste_color(jp, up, mask):
    """Transformación lineal por canal up->jp ajustada fuera de las zonas."""
    fuera = ~mask
    res = up.astype(np.float32).copy()
    for c in range(3):
        x, y = up[..., c][fuera].astype(np.float32), jp[..., c][fuera].astype(np.float32)
        if len(x) < 500:
            continue
        a, b = np.polyfit(x, y, 1)
        a = float(np.clip(a, 0.85, 1.15))
        b = float(np.clip(b, -20, 20))
        res[..., c] = up[..., c] * a + b
    return np.clip(res, 0, 255).astype(np.uint8)


def desplazamiento(jp, up, ancho):
    """x donde encaja la NDS ×1,25 (0 en las capturas 320x240; centrada en las 400x240 de la pantalla superior)."""
    if ancho == K.W3:
        return 0
    return min(range(0, ancho - K.W3 + 1),
               key=lambda dx: np.abs(jp[:K.H3, dx:dx + K.W3, :3].astype(int) - up.astype(int)).mean())


def componer(jp_img: Image.Image, nds: Image.Image, ancho: int):
    jp = np.array(jp_img.convert('RGBA'))
    up = np.array(nds.resize((K.W3, K.H3), Image.BILINEAR))
    dx = desplazamiento(jp, up, ancho)
    cap = jp[:K.H3, dx:dx + K.W3, :3]
    mask = mascara_zonas(cap, up)
    upc = ajuste_color(cap, up, mask)
    out = jp.copy()
    z = out[:K.H3, dx:dx + K.W3]
    z[..., :3][mask] = upc[mask]
    return Image.fromarray(out, 'RGBA'), mask, dx


def caja_panel(a):
    """bbox del panel sobre el fondo liso (color más frecuente) de las syup_bg."""
    rgb = a[..., :3].astype(int)
    fondo = Counter(map(tuple, rgb[::4, ::4].reshape(-1, 3))).most_common(1)[0][0]
    m = np.abs(rgb - np.array(fondo)).sum(2) > 60
    m[:, :8] = m[:, -8:] = False
    m[:8] = m[-8:] = False
    from scipy import ndimage
    lab, _ = ndimage.label(m)
    grande = np.bincount(lab.ravel())[1:].argmax() + 1
    ys, xs = np.nonzero(lab == grande)
    return xs.min(), ys.min(), xs.max() + 1, ys.max() + 1


def componer_panel(jp_img, nds):
    """syup_bg: el panel 3DS no es la NDS ×1,25; se escala el panel NDS a la caja del panel 3DS."""
    jp = np.array(jp_img.convert('RGBA'))
    x0, y0, x1, y1 = caja_panel(jp[:K.H3, :400])
    n0, m0, n1, m1 = caja_panel(np.array(nds))
    pieza = nds.crop((n0, m0, n1, m1)).resize((x1 - x0, y1 - y0), Image.LANCZOS)
    out = jp.copy()
    out[y0:y1, x0:x1, :3] = np.array(pieza)
    return Image.fromarray(out, 'RGBA'), (x0, y0, x1, y1), (n0, m0, n1, m1)


def capturas(informe, pend, previews):
    jp = C.jp()
    for ruta, nombre in K.capturas():
        f = K.NDS_SP / f'{nombre}.pac_'
        if not f.exists():
            pend.append(dict(tipo='sin_captura_nds', arc=ruta))
            continue
        orig = jp.get(ruta)
        raw = bytearray(C.U.unwrap(orig))
        (tn, off, ln, blob), = C.texturas(bytes(raw))
        antes = C.decodificar(blob)
        a = np.array(antes)
        ancho = 400 if 'syup_bg' in nombre else K.W3      # superior 400x240, inferior 320x240
        assert (a[K.H3:, :, 3] == 0).all() and (a[:, ancho:, 3] == 0).all(), ruta
        if 'syup_bg' in nombre:
            nuevo_img, caja3, cajan = componer_panel(antes, K.nds_captura(nombre))
            mask, dx = np.zeros((1, 1), bool), dict(panel_3ds=[int(v) for v in caja3], panel_nds=[int(v) for v in cajan])
        else:
            nuevo_img, mask, dx = componer(antes, K.nds_captura(nombre), ancho)
        nuevo = C.codificar(blob, nuevo_img)
        raw[off:off + ln] = nuevo
        datos = C.reenvolver(orig, bytes(raw))
        destino = K.EXTRA / ruta
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(datos)
        informe.append(dict(ruta=ruta, clase='captura_ayuda', textura=tn, fuente=f'nds_es/pic3d/script/sp/{nombre}.pac_',
                            zona_px=int(mask.sum()), dx=dx, tam_original=len(orig), tam_nuevo=len(datos)))
        final = C.decodificar(nuevo)
        previews['capturas'].append((nombre if 'demo_bg' not in ruta else nombre + ' (demo_bg)',
                                     antes.crop((0, 0, ancho, K.H3)), final.crop((0, 0, ancho, K.H3))))


# ------------------------------------------------------------------ pestañas (system_b)

BLANCO = (255, 255, 255, 255)


def _op_pestana(arr, caja, texto):
    x0, y0, x1, y1 = caja
    z = arr[y0:y1, x0:x1].reshape(-1, 4)
    fondo = Counter(map(tuple, z)).most_common(1)[0][0]
    fondo = tuple(int(v) for v in fondo)
    otros = [tuple(int(v) for v in c) for c in set(map(tuple, z))]
    otros = [c for c in otros if c != fondo]
    # sombra: el color de trazo más oscuro que no es el fondo (como el japonés)
    oscuros = sorted((c for c in otros if c[3] == 255 and sum(c[:3]) < sum(BLANCO[:3])), key=lambda c: sum(c[:3]))
    sombra = next((c for c in oscuros if abs(sum(c[:3]) - sum(fondo[:3])) > 60), None)
    op = dict(caja=caja, texto=texto, fuente='auto12', borrar='colores',
              colores_borrar=[tuple(int(v) for v in c) for c in otros],
              fondo_color=tuple(int(v) for v in fondo), color=BLANCO, alinear='c')
    if sombra is not None:
        op['sombra'] = (1, 1, tuple(int(v) for v in sombra))
    return op


PESTANAS = {
    # 4 estados (filas de 32 px): pestaña izquierda x 56..154, derecha x 162..264; banda de texto interior
    'ie02_menu_system_window_b02.tga': [((56, y + 7, 154, y + 25), 'Controles') for y in (0, 32, 64, 96)] +
                                       [((162, y + 7, 264, y + 25), 'Recursos') for y in (0, 32, 64, 96)],
    'ie02_menu_system_panel_b04.tga': [((3, 3, 93, 25), 'Controles básicos')],
}


def pestanas(informe, pend, previews):
    jp = C.jp()
    orig = jp.get(K.SYSTEM_B)
    base = (K.B6.EXTRA / K.SYSTEM_B)
    base = base.read_bytes() if base.exists() else (K.B6.V03_EXTRA / K.SYSTEM_B).read_bytes() \
        if (K.B6.V03_EXTRA / K.SYSTEM_B).exists() else orig
    raw = bytearray(C.U.unwrap(base))
    cambios = []
    for tn, off, ln, blob in C.texturas(bytes(raw)):
        if tn not in PESTANAS:
            continue
        antes = np.array(C.decodificar(blob))
        arr = antes
        try:
            for caja, texto in PESTANAS[tn]:
                arr = PM.pintar(arr, [_op_pestana(arr, caja, texto)])
        except ValueError as e:
            pend.append(dict(tipo='pintado_fallido', arc=K.SYSTEM_B, textura=tn, motivo=str(e)))
            continue
        nuevo = C.codificar(blob, Image.fromarray(arr, 'RGBA'))
        raw[off:off + ln] = nuevo
        cambios.append(tn)
        previews['pestanas'].append((tn, Image.fromarray(antes, 'RGBA'), C.decodificar(nuevo)))
    if cambios:
        datos = C.reenvolver(orig, bytes(raw))
        destino = K.EXTRA / K.SYSTEM_B
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(datos)
        informe.append(dict(ruta=K.SYSTEM_B, clase='textura', cambios=cambios,
                            base='v06' if (K.B6.EXTRA / K.SYSTEM_B).exists() else 'v03/jp',
                            texto={'そうさ': 'Controles', 'システム': 'Recursos', 'きほんそうさ': 'Controles básicos'},
                            fuente='NDS ES MASTutorial.SPF_ SYDN_T00 (pestañas) y SYDN_B05 (Controles básicos)'))


# ------------------------------------------------------------------ reversión v21

def revertir_mastutorial(informe):
    datos = C.jp().get(K.MASTUTORIAL)
    destino = K.EXTRA / K.MASTUTORIAL
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(datos)
    informe.append(dict(ruta=K.MASTUTORIAL, clase='reversion', revierte='work/ie2/tormenta_de_fuego/capas/graficos/tutorial',
                        motivo='el 3DS no dibuja el paquete DS: la pantalla de ayuda usa a_menu/system_b.arc (CTPK); '
                               'el cambio no tuvo efecto visible. Se deja el japonés para no mezclar datos DS no probados',
                        sha1=C.sha(datos)))


# ------------------------------------------------------------------ previews

def guardar_previews(previews):
    shutil.rmtree(K.PREVIEWS, ignore_errors=True)
    K.PREVIEWS.mkdir(parents=True)
    pares = [C.par(a.crop((0, 0, 280, 128)) if 'window' in t else a, d.crop((0, 0, 280, 128)) if 'window' in t else d,
                   s=4, titulo=t) for t, a, d in previews['pestanas']]
    C.hoja(pares, ancho=max(p.width for p in pares)).save(K.PREVIEWS / 'x4_pestanas.png')
    caps = previews['capturas']
    for i in range(0, len(caps), 6):
        hoja = [C.par(a, d, s=4, titulo=t) for t, a, d in caps[i:i + 6]]
        C.hoja(hoja, ancho=max(p.width for p in hoja)).save(K.PREVIEWS / f'x4_capturas_{i // 6:02d}.png')


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    shutil.rmtree(K.EXTRA, ignore_errors=True)
    informe, pend = [], []
    from collections import defaultdict
    previews = defaultdict(list)
    capturas(informe, pend, previews)
    pestanas(informe, pend, previews)
    revertir_mastutorial(informe)
    guardar_previews(previews)
    pend += [
        dict(tipo='fuera_de_alcance', arc=K.SYSTEM_B, textura='ie02_menu_system_window_b03.tga',
             motivo='サウンド / Bボタンいどう (pantalla de ajustes, no de ayuda): siguen en japonés; fuente NDS: MASConfig.SPF_'),
        dict(tipo='revisar', arc=K.AR + 'help_b/data/ie02_tt10.arc',
             motivo='la nota 3DS citaba el Slide Pad; la NDS oficial nombra el Panel de Control y los botones '
                    '(texto e iconos NDS tal cual, sin el Slide Pad)'),
        dict(tipo='verificar_en_emulador', arc='help_b/help_t',
             motivo='capturas compuestas con zonas NDS ×1,25 (texto más blando que el 3DS); comprobar legibilidad'),
    ]
    (K.HERE / 'informe.json').write_text(json.dumps(informe, ensure_ascii=False, indent=1), encoding='utf-8')
    (K.HERE / 'pendientes.json').write_text(json.dumps(pend, ensure_ascii=False, indent=1), encoding='utf-8')
    print(len(informe), 'ficheros;', sum(r['clase'] == 'captura_ayuda' for r in informe), 'capturas;', len(pend), 'pendientes')
    for p in pend:
        print(' ', p)


if __name__ == '__main__':
    main()
