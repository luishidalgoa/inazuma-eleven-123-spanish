"""nds_dump.py salida.png paquete... : todos los sprites de paquetes SPL/SPD de la NDS ES de IE2 (x2)."""
import sys
sys.path.insert(0, r'C:/Users/luish/Projects/inazuma-eleven-123-spanish/work/ie2/shared/capas/historial/graficos/v06_graficos')
sys.path.insert(0, r'C:/Users/luish/Projects/inazuma-eleven-123-spanish/work/ie1/capas/graficos/graficos_nds')
from PIL import ImageDraw, Image
import base as B
import piezas_nds as PN
C = B.C
PN.NDS = B.HERE.parents[5] / 'ie2' / 'tormenta_de_fuego' / 'fuentes' / 'nds_es' / 'data_iz'
ims = []
for paq in sys.argv[2:]:
    spl = (PN.NDS / 'pic3d/sp' / f'{paq}.SPL').read_bytes()
    spd = (PN.NDS / 'pic3d/sp' / f'{paq}.SPD').read_bytes()
    for name, *_ in PN.L.index(spl, spd):
        try:
            im = PN.sprite_sfp(paq, name).convert('RGBA')
        except Exception as e:
            continue
        z = C.ampliar(im, 2)
        lz = Image.new('RGBA', (max(z.width, 160), z.height + 12), (60, 0, 0, 255))
        lz.paste(z, (0, 12))
        ImageDraw.Draw(lz).text((1, 0), f'{paq}/{name} {im.size}', fill=(255, 255, 0, 255))
        ims.append(lz)
C.hoja(ims, ancho=2000).save(sys.argv[1])
