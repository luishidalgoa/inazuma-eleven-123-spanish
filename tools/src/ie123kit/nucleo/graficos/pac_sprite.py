"""Conservative access to the 4-bpp PAC sprites in IE1 SFP SPL/SPD pairs.

Only the verified three-chunk, single-texture layout is supported. Palettes,
dimensions and other metadata are never regenerated.
"""
import struct

from PIL import Image


def parts(data):
    if len(data)<32 or struct.unpack_from('<I',data)[0]!=3:
        raise ValueError('unsupported PAC header')
    pix,size,pal,ps,meta,ms=struct.unpack_from('<6I',data,4)
    if any(o<32 or o+n>len(data) for o,n in [(pix,size),(pal,ps),(meta,ms)]) or ms<16:
        raise ValueError('invalid PAC chunk bounds')
    if data[meta+2]>10 or data[meta+3]>10:
        raise ValueError('invalid texture dimensions')
    width,height=8<<data[meta+2],8<<data[meta+3]
    if size!=width*height//2 or ps<32:
        raise ValueError('only 4-bpp PAC supported')
    colors=[]
    for i in range(16):
        v=struct.unpack_from('<H',data,pal+2*i)[0]
        colors.append(((v&31)*255//31,((v>>5)&31)*255//31,((v>>10)&31)*255//31,0 if i==0 else 255))
    return pix,width,height,colors


def decode(data):
    pix,w,h,colors=parts(data)
    image=Image.new('RGBA',(w,h))
    image.putdata([colors[(data[pix+i//2]>>(4*(i%2)))&15] for i in range(w*h)])
    return image


def encode(original,image):
    pix,w,h,colors=parts(original)
    if image.size!=(w,h):raise ValueError('sprite dimensions changed')
    out=bytearray(original);cache={}
    for i,color in enumerate(image.convert('RGBA').get_flattened_data()):
        shift=4*(i%2);at=pix+i//2;old=(original[at]>>shift)&15
        if color==colors[old]:continue  # Preserve duplicate palette indices too.
        if color not in cache:
            cache[color]=min(range(16),key=lambda j:sum((a-b)**2 for a,b in zip(color,colors[j])))
        out[at]=(out[at]&~(15<<shift))|(cache[color]<<shift)
    return bytes(out)


def index(spl,spd):
    if spl[:4]!=b'SFP\0' or spd[:4]!=b'SFP\0':raise ValueError('not an SFP pair')
    if struct.unpack_from('<I',spl,16)[0]!=len(spl) or struct.unpack_from('<I',spd,16)[0]!=len(spd):
        raise ValueError('SFP file size mismatch')
    names=struct.unpack_from('<I',spl,32)[0]
    if names<48 or (names-32)%16:raise ValueError('invalid SFP directory')
    result=[]
    for entry in range(32,names,16):
        name,size,offset,_=struct.unpack_from('<4I',spl,entry)
        if not names<=name<len(spl) or offset*32+size>len(spd):raise ValueError('SFP entry outside file')
        result.append((spl[name:spl.index(0,name)].decode('ascii'),entry,offset*32,size))
    return result


def decodificar_pac8(datos, ancho=256, alto=192):
    """Imagen RGB de un PAC indexado de 8 bpp de NDS (LZ10 ya descomprimido).

    Disposición verificada en las capturas de ayuda de la NDS española (``pic3d/script/sp/*.pac_``):
    tres trozos declarados en la cabecera (``n``, luego ``(offset, tamaño)`` por trozo) con los
    índices lineales de ``ancho`` x ``alto``, una paleta BGR555 de hasta 256 colores y 16 B de cola.
    No se regenera nada: es solo lectura.
    """
    import numpy as np

    n = struct.unpack_from('<I', datos, 0)[0]
    if n != 3:
        raise ValueError(f'PAC de {n} trozos no admitido')
    (io, isz), (po, ps), _cola = (struct.unpack_from('<2I', datos, 4 + 8 * i) for i in range(n))
    if isz != ancho * alto or ps > 512:
        raise ValueError(f'PAC inesperado: {isz} B de índices, {ps} B de paleta')
    paleta = np.zeros(256, np.int32)
    paleta[:ps // 2] = struct.unpack_from(f'<{ps // 2}H', datos, po)
    lut = np.stack([(paleta & 31) * 255 // 31, ((paleta >> 5) & 31) * 255 // 31,
                    ((paleta >> 10) & 31) * 255 // 31], -1)
    idx = np.frombuffer(datos, np.uint8, isz, io).reshape(alto, ancho)
    return Image.fromarray(lut[idx].astype('uint8'), 'RGB')
