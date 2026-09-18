"""Línea v18 · teclado de nombre de IE2 (issue #73): la tabla de caracteres.

SÍNTOMA
-------
En la candidata probe_ie2_v17 el teclado de nombre de IE2 MUESTRA letras latinas
(texturas `ie02_menu_name_b_font_hira01/kana01`, capa v12) pero al pulsar escribe kana.
Tecleando «LUIS» salió «きシヘモ», que son EXACTAMENTE las celdas (1,1), (1,2), (8,0) y (9,1)
de la rejilla japonesa original de `fcode0/fcode1`. Es decir: la rejilla y las coordenadas
son correctas; lo que el juego lee es la tabla JAPONESA.

MECANISMO (evidencia en `romfs/cro/ina_main2.cro`, versión base JP)
-------------------------------------------------------------------
* Cabecera CRO0: segmento 0 (.text) en 0x180, segmento 1 (.rodata) en 0x212000 (tam. 0x23e10),
  segmento 2 (.data) en 0x29b1c0, tabla de parches internos en 0x24b06c (0x6ac6 entradas de 12 B).
* En .rodata hay la tabla de RAÍCES por juego (offset de fichero 0x214539):
  `/inazuma1/data_iz/`, `/inazuma2/data_iz/`, `/inazuma2/data_iz_blizzard/`,
  `/inazuma3_ogre/data_iz/`, `/inazuma3/data_iz/`.
* La pantalla de nombre de IE2 es `CMainMenuScreenEnterName.cpp` (cadena __FILE__ en
  .rodata, offset de fichero 0x235e10-0x212000 → seg1+0xfc28). Su lista de recursos
  (array de pares {puntero, id} en seg1+0xfabc, punteros rellenados por la tabla de parches
  internos) es:
      nedn_bg01.pac, nedn_bg02.pac, nedn_bg03.pac, nedn_bg06.pac, nedn_c00.pac,
      nedn_i00.pac, nedn_i01.pac, nedn_i02.pac, srd_w70.pac, srd_b70.pac,
      fcode0.txt, fcode1.txt, fcode2.txt, handaku.txt, dakuten.txt, ngword.txt, fcodeck.txt
  (cadenas sueltas en 0x235910..0x23595e del fichero). El formato de ruta que usa el módulo
  es `/data_iz/%s` (cadena en 0x224860) sobre la raíz del juego en curso.
* O sea: IE2 abre `/inazuma2/data_iz/fcode0.txt` … y ESE FICHERO NO EXISTE.
  Comprobado: en TODA la ROM (barrido de bytes sobre el .3ds y el .cia japoneses) la
  secuencia SJIS `ああいいううええおお` / `アアイイウウエエオオ` aparece UNA sola vez,
  en `inazuma1/data_iz/fcode0/1/2.txt` dentro de `archive.fa`. No hay ninguna otra copia:
  ni bajo `inazuma2/`, ni suelta en romfs, ni incrustada en `ina_main2.cro`,
  `ina_main1.cro`, `ina_menu.cro`, `static.crs` ni `exefs/code.bin` (barridos en SJIS,
  UTF-8, UTF-16 y como vectores u16 con zancadas 2..16; tampoco hay constantes 0x829F/
  0x8340 en .text que permitan construir la tabla por aritmética: las filas SJIS del
  gojūon no son equiespaciadas, así que una tabla es imprescindible).
* Por tanto IE2 resuelve `fcode0.txt` a una raíz distinta de la suya, o cae a `inazuma1/`.
  En la candidata instalada `inazuma1/data_iz/fcode0.txt` YA es latina (verificado sobre
  `%APPDATA%/Azahar/load/mods/00040000000BB800/romfs/archive.fa`), luego IE2 NO está
  leyendo esa copia: le falta la suya bajo `/inazuma2/data_iz/`.

ARREGLO DE ESTA CAPA
--------------------
Poner los siete ficheros que pide `CMainMenuScreenEnterName` bajo la raíz de IE2, como
ficheros SUELTOS de romfs (LayeredFS), que es como ya se sirven los .SAD de sonido:
    romfs/inazuma2/data_iz/{fcode0,fcode1,fcode2,dakuten,handaku,ngword,fcodeck}.txt
No se toca `archive.fa` (el constructor rechaza entradas NUEVAS) ni una sola instrucción
del CRO: sólo se añaden datos.

* `fcode0/1/2.txt` se generan con `ie123kit.ie1.graficos.teclado.patch_map` a partir de los
  originales japoneses, de modo que son BYTE A BYTE los mismos que la tabla aprobada de IE1.
  Esto es lo correcto porque la capa v12 copió en IE2 la textura latina de IE1 píxel a píxel:
  misma rejilla de 20x20, mismas letras, mismo ESP, misma flecha de borrar y mismo
  cambio ABC/abc en la celda de «カナ».
* `dakuten/handaku/ngword/fcodeck.txt` se copian TAL CUAL del japonés: la pantalla los carga
  y deben existir, pero con tabla latina las teclas ゛/゜ quedan deshabilitadas (patch_map
  borra sus controles BBBB/CCCC), así que su contenido es inerte.

Uso: python work/ie2/shared/capas/v18/teclado/apply.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[5]
sys.path.insert(0, str(ROOT / 'tools/src'))
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'work/ie1/capas/v37/graficos_nds'))

from ie123kit.nucleo.contenedores.fa import FaArchive          # noqa: E402
from ie123kit.ie1.graficos.teclado import ROWS, patch_map      # noqa: E402

BASE = ROOT / 'work/shared/base_3ds/romfs/archive.fa'
#: textura latina de IE2 ya aprobada en la capa v12 (de ahí salen las vistas previas)
NAME_B = ROOT / 'work/ie2/shared/capas/v12/graficos/extra/inazuma2/data_iz/a_menu/name_b.arc'

RAIZ_IE1 = 'inazuma1/data_iz/'
#: destino: raíz propia de IE2, tal y como la compone el CRO (raíz + "/data_iz/%s")
DESTINO = HERE / 'romfs/inazuma2/data_iz'

#: fcodeN.txt -> modo de patch_map (0 mayúsculas, 1 minúsculas, 2 mayúsculas sin la tecla de modo)
TRADUCIDOS = {'fcode0.txt': 0, 'fcode1.txt': 1, 'fcode2.txt': 2}
#: se copian tal cual: la pantalla los carga, pero con tabla latina su contenido es inerte
COPIADOS = ('dakuten.txt', 'handaku.txt', 'ngword.txt', 'fcodeck.txt')

CELDA = 20
ESCALA = 4


def _texturas():
    from ui_archive import entries, unwrap
    from ctpk_ui import decode, metadata
    raw = unwrap(NAME_B.read_bytes())
    salida = {}
    for off, length, _ in entries(raw):
        b = raw[off:off + length]
        if b[:4] == b'CTPK':
            nombre = metadata(b)[0]
            if 'font_' in nombre:
                salida[nombre] = decode(b).convert('RGBA')
    return salida


def _preview(imagen, datos, nombre):
    """Textura v12 a 4x con la rejilla de 20 px y, en cada celda, el carácter que ESCRIBE."""
    im = imagen.resize((imagen.width * ESCALA, imagen.height * ESCALA), Image.NEAREST)
    fondo = Image.new('RGBA', im.size, (24, 24, 32, 255))
    fondo.alpha_composite(im)
    im = fondo
    d = ImageDraw.Draw(im)
    paso = CELDA * ESCALA
    for x in range(0, im.width + 1, paso):
        d.line((x, 0, x, im.height), fill=(255, 64, 64, 160))
    for y in range(0, im.height + 1, paso):
        d.line((0, y, im.width, y), fill=(255, 64, 64, 160))
    try:
        tipo = ImageFont.truetype('C:/Windows/Fonts/arialbd.ttf', 22)
    except OSError:
        tipo = ImageFont.load_default()
    from ie123kit.nucleo.texto.ancho_completo import decode_fullwidth
    for fila in range(6):
        for col in range(10):
            # ojo: los huecos son ESPACIOS ASCII de 1 byte, así que hay que indexar por BYTES
            off = fila * 52 + (col * 2 + (1 if col >= 5 else 0)) * 2
            par = datos[off:off + 2]
            if par == b'  ':
                continue
            d.text((col * paso + 3, fila * paso + 1), decode_fullwidth(par),
                   fill=(120, 255, 120, 255), font=tipo)
    im.save(HERE / 'previews' / f'{nombre}_rejilla.png')


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    arc = FaArchive(str(BASE))
    DESTINO.mkdir(parents=True, exist_ok=True)
    informe = {'mecanismo': 'romfs suelto /inazuma2/data_iz/ (LayeredFS); archive.fa y CRO intactos',
               'nota_constructor': (
                   'ie123kit.nucleo.construir.candidata sólo sabe de extra/ (entradas YA existentes de '
                   'archive.fa) y de romfs/cro/*.cro; NO copia romfs/ suelto. Estos siete ficheros hay '
                   'que copiarlos al árbol de la candidata igual que se hace con los .SAD de sonido '
                   '(romfs/<juego>/data_iz/...), que el instalador ya lleva a '
                   'Azahar/load/mods/<TID>/romfs/. No se puede usar extra/: el constructor rechaza '
                   'entradas NUEVAS en archive.fa y bajo inazuma2/ no existe ningún fcode*.'),
               'ficheros': {}, 'runtime_verified': False}
    generados = {}
    for nombre, modo in TRADUCIDOS.items():
        original = arc.read(RAIZ_IE1 + nombre)
        nuevo = patch_map(original, modo)
        (DESTINO / nombre).write_bytes(nuevo)
        generados[nombre] = nuevo
        informe['ficheros'][nombre] = {'origen': RAIZ_IE1 + nombre, 'modo': modo,
                                       'bytes': len(nuevo), 'traducido': True,
                                       'igual_que_ie1': True}
    for nombre in COPIADOS:
        datos = arc.read(RAIZ_IE1 + nombre)
        (DESTINO / nombre).write_bytes(datos)
        informe['ficheros'][nombre] = {'origen': RAIZ_IE1 + nombre, 'bytes': len(datos),
                                       'traducido': False}
    texturas = _texturas()
    for nombre, imagen in texturas.items():
        clave = 'fcode1.txt' if 'kana01' in nombre else 'fcode0.txt'
        _preview(imagen, generados[clave], nombre.replace('.tga', ''))
    informe['previews'] = sorted(p.name for p in (HERE / 'previews').glob('*.png'))
    informe['rejilla'] = {'celda_px': CELDA, 'filas': ROWS}
    (HERE / 'report.json').write_text(json.dumps(informe, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(informe, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
