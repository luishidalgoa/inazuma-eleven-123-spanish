"""IE1 keyboard: fcode0/1/2 are 26 x 6 little-endian two-byte cells + CRLF.

Each visible character occupies two equal cells. AAAA switches mode, DDDD
deletes, and ASCII spaces disable a cell. B/C are Japanese diacritic controls.
The selection grid uses 20x20 px keys (row k at y=20k), as in the Japanese texture.

Regla: rejilla de 20 px por tecla y mapa fcodeN de 314 bytes exactos
(6 filas x 52 bytes + CRLF final); cualquier otro tamaño se rechaza.
"""
from ie123kit.nucleo.texto.teclado import FILAS_LATINAS, parchear_fcode

ROWS=list(FILAS_LATINAS)


def patch_map(original,mode):
    """Mapa fcodeN de IE1 con la tabla latina (motor común en ``nucleo.texto.teclado``)."""
    return parchear_fcode(original,mode)


def texture_operations(mode):
    operations=[]
    for y,row in enumerate(ROWS):
        for x,ch in enumerate(row):
            text='ESP' if ch==' ' else (ch.lower() if mode==1 else ch)
            operations.append({'box':[x*20,y*20+2,x*20+20,y*20+18],'text':text,'size':8 if ch==' ' else 14})
    operations.extend([{'box':[200,2,224,18],'text':'abc' if mode==0 else 'ABC','size':10},{'box':[200,20,224,60],'text':'','size':10}])
    return operations
