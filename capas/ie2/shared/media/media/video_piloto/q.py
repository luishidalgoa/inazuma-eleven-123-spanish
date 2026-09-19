import numpy as np, sys, cv2
from an import dec
W,H=240,320
def ssim(a,b):
    a=a.astype(np.float64); b=b.astype(np.float64); C1,C2=6.5025,58.5225
    g=lambda x: cv2.GaussianBlur(x,(11,11),1.5)
    ma,mb=g(a),g(b); sa=g(a*a)-ma*ma; sb=g(b*b)-mb*mb; sab=g(a*b)-ma*mb
    return (((2*ma*mb+C1)*(2*sab+C2))/((ma*ma+mb*mb+C1)*(sa+sb+C2))).mean()
def medir(ref, out):
    A=np.load(ref+'_yuv.npy')[:,:W*H].reshape(-1,H,W); B=dec(out)[:,:W*H].reshape(-1,H,W)
    assert len(A)==len(B),(len(A),len(B))
    a=A[:,:,36:].astype(float); b=B[:,:,36:].astype(float)  # zona sin texto (imagen)
    mse=((a-b)**2).mean(); ps=10*np.log10(255**2/mse)
    ss=np.mean([ssim(A[i,:,36:],B[i,:,36:]) for i in range(0,len(A),4)])
    band=np.abs(B[:,:,0:32].astype(int)-25).max()
    return len(B),ps,ss,band
if __name__=='__main__':
    print(sys.argv[2], medir(sys.argv[1],sys.argv[2]))
