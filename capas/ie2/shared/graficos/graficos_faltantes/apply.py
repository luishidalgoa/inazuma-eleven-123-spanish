"""v22 · gráficos faltantes de IE2 (issue #77). No construye candidata ni instala.

Rótulo de resultado de BATALLA (encuentros 4c4): a_game/battle_start_b.arc,
textura CTPK ie02_battle_start_result_plt_b01.tga (256x128, RGBA5551): tres placas
「バトル勝利」「タイムアップ」「バトル敗北」. Ninguna capa (v03…v21) la tocó: v03 solo
cambió ie02_battle_start_battle_b01 («DUELO») del mismo .arc. La 3DS no tiene pieza
europea equivalente, así que se repinta en el mismo estilo (amarillo 255,238,115 con
contorno azul oscuro 0,8,65 sobre la placa azul 0,90,222), conservando marco y guiones.
Base: el .arc de probe_ie2_v21 (= v05/graficos_snapshot, con «DUELO»).
Duplicados revisados (auditoria_graficos): ie02_menu_form_button_b02 y ie02_menu_form_parts_b02 se llaman
igual en otros .arc pero son gráficos distintos sin texto; ie02_wireless_b_big_btn02 de wireless_off_b.arc
sí conserva japonés pero con otra maqueta (pendiente, ver informe de auditoría).
Salida: extra/<ruta>, informe.json, previews/*_x4.png
"""
import json, sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'historial' / 'graficos' / 'v03_graficos'))
import comun as C  # noqa: E402

BASE_ARC = HERE.parents[1] / 'historial' / 'graficos' / 'v05_graficos_snapshot' / 'extra'
ARC = 'inazuma2/data_iz/a_game/battle_start_b.arc'
TEX = 'ie02_battle_start_result_plt_b01.tga'
CAND = HERE.parents[5] / 'work/shared/candidatas/probe_ie2_v21/archive.fa'
JP = HERE.parents[5] / 'work/shared/base_3ds/romfs/archive.fa'
P = 'inazuma2/data_iz/a_menu/'
DUPLICADAS = [('ie02_wireless_b_big_btn02.tga', P + 'wireless_b.arc', P + 'wireless_off_b.arc'),
              ('ie02_menu_form_button_b02.tga', P + 'formation_b.arc', P + 'wireless_member_b.arc'),
              ('ie02_menu_form_parts_b02.tga', P + 'formation_b.arc', P + 'scout_b.arc')]
TEXTOS = ['¡VICTORIA!', '¡TIEMPO!', 'DERROTA']
AMARILLO, OSCURO, AZUL = (255, 238, 115, 255), (0, 8, 65, 255), (0, 90, 222, 255)


def _moda(fila):
    v, n = np.unique(fila.reshape(-1, 4), axis=0, return_counts=True)
    fuera = [i for i, c in enumerate(v) if tuple(c) not in (AMARILLO, OSCURO)]
    if fuera:   # se ignora el texto (amarillo y su contorno)
        v, n = v[fuera], n[fuera]
    return v[n.argmax()]


def pintar(im):
    a = np.array(im)
    for fila, texto in enumerate(TEXTOS):
        y0 = fila * 32
        zona = a[y0 + 2:y0 + 28]
        ama = np.all(zona[..., :3] == AMARILLO[:3], -1)
        cols = np.where(ama.any(0))[0]
        # los guiones laterales son amarillos pero de 2 px de alto; el texto ocupa el centro
        cols = [c for c in cols if ama[:, c].sum() > 3]
        x0, x1 = min(cols) - 3, max(cols) + 4
        # perfil vertical limpio de la placa: color más frecuente de cada línea (brillo y sombra incluidos)
        perfil = np.array([
                           _moda(a[y, 0:138]) for y in range(y0, y0 + 32)], np.uint8)[:, None]
        a[y0:y0 + 32, x0:x1] = perfil
        fondo = a.copy()
        lienzo = Image.fromarray(a, 'RGBA')
        d = ImageDraw.Draw(lienzo)
        for tam in range(20, 8, -1):
            f = ImageFont.truetype(C.ARIALBD, tam)
            l, t, r, b = d.textbbox((0, 0), texto, font=f, stroke_width=2)
            if r - l <= x1 - x0 and b - t <= 24:
                break
        cx = (x0 + x1 - (r - l)) // 2 - l
        cy = y0 + 3 + (24 - (b - t)) // 2 - t
        d.text((cx, cy), texto, font=f, fill=AMARILLO, stroke_width=2, stroke_fill=OSCURO)
        a = np.array(lienzo)
        # sin antialias: solo los tres colores de la placa
        pal = np.array([AMARILLO, OSCURO, AZUL])
        m = np.any(a != fondo, -1)
        dist = ((a[m][:, None, :3].astype(int) - pal[None, :, :3]) ** 2).sum(-1)
        a[m] = pal[dist.argmin(-1)]
    return Image.fromarray(a, 'RGBA')


def main():
    orig = (BASE_ARC / ARC).read_bytes()
    raw = bytearray(C.U.unwrap(orig))
    for n, off, ln, blob in C.texturas(bytes(raw)):
        if n == TEX:
            antes = C.decodificar(blob)
            nuevo = C.codificar(blob, pintar(antes))
            raw[off:off + ln] = nuevo
            despues = C.decodificar(nuevo)
    out = C.reenvolver(orig, bytes(raw))
    dst = HERE / 'extra' / ARC
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(out)
    (HERE / 'previews').mkdir(exist_ok=True)
    C.par(antes, despues, s=4, titulo=TEX).save(HERE / 'previews' / 'battle_start_result_plt_b01_x4.png')
    json.dump({'issue': 77, 'arc': ARC, 'textura': TEX, 'textos': TEXTOS,
               'base_sha1': C.sha(orig), 'salida_sha1': C.sha(out), 'origen': 'pintado (sin pieza NDS/EU)'},
              open(HERE / 'informe.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('ok', dst)



if __name__ == '__main__':
    main()
