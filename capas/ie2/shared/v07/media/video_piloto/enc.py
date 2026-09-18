import numpy as np, subprocess, sys, os
sys.path.insert(0, r'C:/Users/luish/Projects/inazuma-eleven-123-spanish/tools/src')
from pathlib import Path
from ie123kit.nucleo.media.moflex import set_moflex_rotation
M=r'C:/Users/luish/Projects/inazuma-eleven-123-spanish/work/shared/herramientas/media_tools/mobipeg-v2.1-x86/ffmpeg.exe'
W,H=240,320
def limpiar(n):
    F=np.load(n+'_yuv.npy').copy(); Y=F[:,:W*H].reshape(-1,H,W)
    U=F[:,W*H:W*H+W*H//4].reshape(-1,H//2,W//2); V=F[:,W*H+W*H//4:].reshape(-1,H//2,W//2)
    orig=Y.copy()
    base=np.median(Y[:,:,0:6].reshape(len(F),-1),axis=1).astype(np.uint8)
    mask=np.abs(Y[:,:,0:32].astype(int)-base[:,None,None])>1
    Y[:,:,0:32]=base[:,None,None]
    # suave: cols 32-33 hacia la imagen con mezcla (solo donde habia texto cercano)
    U[:,:,0:16]=128; V[:,:,0:16]=128
    np.save(n+'_mask.npy',mask.any(axis=1))
    F.tofile(n+'_clean.yuv'); return len(F)
def enc(raw,out,qp,fps='24'):
    subprocess.run([M,'-y','-hide_banner','-loglevel','error','-f','rawvideo','-pix_fmt','yuv420p','-s:v','240x320','-r',fps,'-i',raw,'-an','-c:v','mobiclip','-mobiclip','1','-moflex','1','-qp',str(qp),'-pix_fmt','yuv420p','-threads','1','-x264opts','mvrange=32','-f','moflex',out],check=True)
    set_moflex_rotation(Path(out),1)
if __name__=='__main__':
    for n in sys.argv[2:]:
        if not os.path.exists(n+'_clean.yuv'): print(n,limpiar(n))
        for qp in sys.argv[1].split(','):
            enc(n+'_clean.yuv',f'{n}_qp{qp}.moflex',qp); print(n,qp,os.path.getsize(f'{n}_qp{qp}.moflex'),os.path.getsize(n+'.moflex'))
