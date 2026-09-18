import sys, numpy as np, subprocess
from pathlib import Path
from PIL import Image, ImageDraw
MEDIA=Path(r'C:/Users/luish/Projects/inazuma-eleven-123-spanish/work/ie2/shared/capas/v07/media')
sys.path.insert(0,str(MEDIA))
import comun_media as C
OUT=MEDIA/'video_piloto'; OUT.mkdir(exist_ok=True)
D=Path(__file__).resolve().parent
def rgb(v):
    v=str(D/v)
    p=subprocess.Popen(['ffmpeg','-v','error','-i',v,'-f','rawvideo','-pix_fmt','rgb24','-'],stdout=subprocess.PIPE)
    fr=[]
    while True:
        b=p.stdout.read(240*320*3)
        if len(b)<240*320*3: break
        fr.append(b)
    return fr
def img(b): return Image.frombytes('RGB',(240,320),b).rotate(90,expand=True)
def hoja(n, antes, despues, dat_antes, dat_desp, titulo):
    A=rgb(antes); B=rgb(despues)
    sa=C.leer_dat(dat_antes); sb=C.leer_dat(dat_desp) if dat_desp else sa
    filas=[]
    for k,s in enumerate(sa):
        s2=sb[min(k,len(sb)-1)]
        for fr in (0.15,0.5,0.85):
            fa=min(len(A)-1,int((s.inicio+(s.fin-s.inicio)*fr)*24/30))
            fb=min(len(B)-1,int((s2.inicio+(s2.fin-s2.inicio)*fr)*24/30)) if dat_desp else fa
            filas.append((k,fa,fb))
    ancho=320*2+10; alto=240+40*3*2+20
    H=Image.new('RGB',(ancho,30+len(filas)*alto),(18,18,24)); d=ImageDraw.Draw(H)
    d.text((6,8),titulo,fill=(230,230,230))
    for i,(k,fa,fb) in enumerate(filas):
        y=30+i*alto; ia=img(A[fa]); ib=img(B[fb])
        H.paste(ia,(0,y+16)); H.paste(ib,(330,y+16))
        d.text((4,y+2),f'sub #{k}  antes f{fa}',fill=(200,200,200)); d.text((334,y+2),f'despues f{fb}',fill=(200,200,200))
        za=ia.crop((0,196,320,240)).resize((960,132),Image.NEAREST).crop((0,0,ancho,132))
        zb=ib.crop((0,196,320,240)).resize((960,132),Image.NEAREST).crop((0,0,ancho,132))
        # zoom x3 de la banda (320 px centrales -> ventana central)
        za=ia.crop((52,196,269,240)).resize((651,132),Image.NEAREST); zb=ib.crop((52,196,269,240)).resize((651,132),Image.NEAREST)
        H.paste(za,(0,y+258)); H.paste(zb,(0,y+258+134))
    p=OUT/f'{n}_antes_despues.png'; H.save(p); print(p, len(filas))
jp=lambda n: C.dat_jp(n+'.dat')
hoja('a2m03','a2m03.moflex','a2m03_qp12.moflex',jp('a2m03'),None,'a2m03: izq JP original | der limpio qp12. Debajo: banda x3 antes / despues')
hoja('op00','op00.moflex','op00_qp12.moflex',jp('op00'),None,'op00: izq JP original | der limpio qp12. Debajo: banda x3 antes / despues')
hoja('a2m14','a2m14.moflex','a2m14_nds_qp12.moflex',jp('a2m14'),(C.TXT_ES/'a2m14.dat').read_bytes(),'a2m14: izq JP (tiempos JP) | der NDS ES convertido (tiempos ES). Debajo: banda x3 JP / NDS')
