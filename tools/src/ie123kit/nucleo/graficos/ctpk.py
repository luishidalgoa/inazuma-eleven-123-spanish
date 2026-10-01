"""Lossless pixel access for uncompressed CTPK UI textures used by IE1."""
import struct

from PIL import Image


def metadata(data):
    if data[:4] != b'CTPK' or struct.unpack_from('<H',data,6)[0] != 1:
        raise ValueError('expected single-texture CTPK')
    texoff = struct.unpack_from('<I',data,8)[0]
    nameoff,size,relative,fmt = struct.unpack_from('<IIII',data,32)
    width,height = struct.unpack_from('<HH',data,48)
    name = data[nameoff:data.index(0,nameoff)].decode('utf-8')
    return name,width,height,fmt,texoff+relative,size


def pixel_index(x,y,width):
    morton = sum(((x>>b)&1)<<(2*b) | ((y>>b)&1)<<(2*b+1) for b in range(3))
    return ((y//8)*(width//8)+x//8)*64+morton


def decode(data):
    _,w,h,fmt,off,_size = metadata(data)
    if fmt in (12, 13):
        import texture2ddecoder
        image=Image.new('RGBA',(w,h))
        pos=off
        con_alfa=fmt==13
        for y in range(0,h,8):
            for x in range(0,w,8):
                for dx,dy in ((0,0),(4,0),(0,4),(4,4)):
                    if con_alfa:
                        alpha=int.from_bytes(data[pos:pos+8],'little')
                        pos+=8
                    block=Image.frombytes('RGBA',(4,4),texture2ddecoder.decode_etc1(data[pos:pos+8][::-1],4,4),'raw','BGRA')
                    pos+=8
                    if con_alfa:
                        for yy in range(4):
                            for xx in range(4):
                                pixel=block.getpixel((xx,yy))
                                block.putpixel((xx,yy),pixel[:3]+(((alpha>>(4*(xx*4+yy)))&15)*17,))
                    image.paste(block,(x+dx,y+dy))
        return image
    image = Image.new('RGBA',(w,h))
    pixels=image.load()
    for y in range(h):
        for x in range(w):
            i=pixel_index(x,y,w)
            if fmt==0:
                a,b,g,r=data[off+4*i:off+4*i+4]
            elif fmt==1:
                b,g,r=data[off+3*i:off+3*i+3];a=255
            elif fmt==5:
                a,r=data[off+2*i:off+2*i+2];g=b=r
            elif fmt==9:
                v=data[off+i];r=g=b=(v>>4)*17;a=(v&15)*17
            elif fmt==7:
                r=g=b=data[off+i];a=255
            elif fmt==8:
                r=g=b=255;a=data[off+i]
            elif fmt in (2,3,4):
                v=struct.unpack_from('<H',data,off+2*i)[0]
                if fmt==2:r,g,b,a=((v>>11)&31)*255//31,((v>>6)&31)*255//31,((v>>1)&31)*255//31,(v&1)*255
                elif fmt==3:r,g,b,a=((v>>11)&31)*255//31,((v>>5)&63)*255//63,(v&31)*255//31,255
                else:r,g,b,a=((v>>12)&15)*17,((v>>8)&15)*17,((v>>4)&15)*17,(v&15)*17
            elif fmt==11:
                r=g=b=255;a=((data[off+i//2]>>(4*(i%2)))&15)*17
            else:
                raise ValueError('unsupported CTPK pixel format '+str(fmt))
            pixels[x,y]=(r,g,b,a)
    return image


def encode(data,image):
    _,w,h,fmt,off,_size=metadata(data)
    if image.size != (w,h):raise ValueError('texture dimensions changed')
    if fmt in (12, 13):
        import etcpak
        original=decode(data)
        result=bytearray(data);pos=off
        paso=16 if fmt==13 else 8
        for y in range(0,h,8):
            for x in range(0,w,8):
                for dx,dy in ((0,0),(4,0),(0,4),(4,4)):
                    box=(x+dx,y+dy,x+dx+4,y+dy+4)
                    block=image.crop(box).convert('RGBA')
                    # ETC is lossy: preserve original compressed blocks whenever
                    # their decoded pixels were not edited.
                    if block.tobytes()!=original.crop(box).tobytes():
                        if fmt==13:
                            alpha=sum(round(block.getpixel((xx,yy))[3]/17)<<(4*(xx*4+yy)) for yy in range(4) for xx in range(4))
                            result[pos:pos+8]=alpha.to_bytes(8,'little')
                        result[pos+paso-8:pos+paso]=etcpak.compress_etc1_rgb(block.tobytes(),4,4)[::-1]
                    pos+=paso
        return bytes(result)
    result=bytearray(data);pixels=image.convert('RGBA').load()
    for y in range(h):
        for x in range(w):
            r,g,b,a=pixels[x,y];i=pixel_index(x,y,w)
            if fmt==0:result[off+4*i:off+4*i+4]=bytes((a,b,g,r))
            elif fmt==1:result[off+3*i:off+3*i+3]=bytes((b,g,r))
            elif fmt==5:result[off+2*i:off+2*i+2]=bytes((a,r))
            elif fmt==9:result[off+i]=(round(r/17)<<4)|round(a/17)
            elif fmt==7:result[off+i]=round((r*299+g*587+b*114)/1000)
            elif fmt==8:result[off+i]=a
            elif fmt in (2,3,4):
                if fmt==2:v=(round(r*31/255)<<11)|(round(g*31/255)<<6)|(round(b*31/255)<<1)|int(a>=128)
                elif fmt==3:v=(round(r*31/255)<<11)|(round(g*63/255)<<5)|round(b*31/255)
                else:v=(round(r/17)<<12)|(round(g/17)<<8)|(round(b/17)<<4)|round(a/17)
                struct.pack_into('<H',result,off+2*i,v)
            elif fmt==11:
                shift=4*(i%2);pos=off+i//2
                result[pos]=(result[pos]&~(15<<shift))|(round(a/17)<<shift)
            else:raise ValueError('unsupported CTPK pixel format')
    return bytes(result)
