import subprocess, numpy as np, sys
def dec(v,w=240,h=320):
    p=subprocess.Popen(['ffmpeg','-v','error','-i',v,'-f','rawvideo','-pix_fmt','yuv420p','-'],stdout=subprocess.PIPE)
    t=w*h*3//2; out=[]
    while True:
        b=p.stdout.read(t)
        if len(b)<t: break
        out.append(np.frombuffer(b,np.uint8).copy())
    return np.stack(out)
if __name__=="__main__":
     for n in ['a2m03','op00','a2m14']:
        F=dec(n+'.moflex'); Y=F[:,:240*320].reshape(-1,320,240)
        np.save(n+'_yuv.npy',F)
        # rotated: display row y = column? band cols 0-39
        colmax=Y.max(axis=(0,1)); colmean=Y.mean(axis=(0,1))
        print(n,len(F),'col max',colmax[:48].tolist()); print(' col mean',np.round(colmean[:48]).tolist()); print(' tail max', colmax[-44:].tolist())
        rows=Y.max(axis=(0,2)); print(' row max first/last',rows[:6].tolist(),rows[-6:].tolist())
