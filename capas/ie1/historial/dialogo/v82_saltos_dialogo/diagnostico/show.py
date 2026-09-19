import pickle,cro,sys
L=pickle.load(open('dis.pkl','rb'))
D={a:(m,o) for a,m,o in L}
def show(s,e):
    out=[]
    for a in range(s,e,4):
        m,o=D[a]; c=''
        if m.startswith('b'):
            try:
                t=int(o.lstrip('#'),16)
                if t+4 in cro.imps: c=' ; '+cro.imps[t+4]
            except: pass
        if m.startswith('ldr') and '[pc' in o:
            imm=int(o.split('#')[-1].rstrip(']'),16) if '#' in o else 0
            if '#-' in o: imm=-int(o.split('#-')[-1].rstrip(']'),16)
            lit=a+8+imm; c=f' ; ={cro.u32(lit):#x}'+(f' rel{cro.rel[lit]}' if lit in cro.rel else '')
        out.append(f'{a:6x}  {m:8s} {o}{c}')
    return '\n'.join(out)
if __name__=='__main__':
    print(show(int(sys.argv[1],16),int(sys.argv[2],16)))
