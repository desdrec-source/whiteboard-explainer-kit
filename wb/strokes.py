"""Line art -> skeleton -> ordered endpoint-to-endpoint strokes (junctions split)."""
import numpy as np
from skimage.morphology import skeletonize
from scipy.ndimage import convolve, label
NB=[(-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)]

def skel(mask): return skeletonize(mask>0.5)

def trace(sk, min_spur=10):
    """Return list of strokes (Nx2 float arrays, x,y). Junction pixels are removed so every
    stroke runs endpoint->endpoint; junction centroid re-attached to both touching ends."""
    sk=sk.copy().astype(bool)
    deg=convolve(sk.astype(int),np.ones((3,3),int),mode='constant')-1
    junc=sk&(deg>=3)
    jl,nj=label(junc,np.ones((3,3)))
    jc={}
    for k in range(1,nj+1):
        ys,xs=np.nonzero(jl==k); jc[k]=np.array([xs.mean(),ys.mean()])
    edges=sk&~junc
    el,ne=label(edges,np.ones((3,3)))
    H,W=sk.shape; out=[]
    for k in range(1,ne+1):
        ys,xs=np.nonzero(el==k); pts=set(zip(ys.tolist(),xs.tolist()))
        def nbrs(p): return [(p[0]+a,p[1]+b) for a,b in NB if (p[0]+a,p[1]+b) in pts]
        ends=[p for p in pts if len(nbrs(p))<=1]
        start=min(ends,key=lambda p:(p[0],p[1])) if ends else min(pts)   # loop: topmost pixel
        path=[start]; seen={start}; cur=start
        while True:
            nx=[q for q in nbrs(cur) if q not in seen]
            if not nx: break
            nx.sort(key=lambda q:abs(q[0]-cur[0])+abs(q[1]-cur[1]))   # prefer 4-neighbours
            cur=nx[0]; path.append(cur); seen.add(cur)
        P=np.array([[x,y] for y,x in path],float)
        closed=not ends
        # reattach junction centroids touching each end
        tj=[]
        for end in ([path[0],path[-1]] if not closed else []):
            hit=None
            for a,b in NB:
                y,x=end[0]+a,end[1]+b
                if 0<=y<H and 0<=x<W and jl[y,x]: hit=jl[y,x]; break
            tj.append(hit)
        if not closed:
            if tj[0]: P=np.vstack([jc[tj[0]],P])
            if tj[1]: P=np.vstack([P,jc[tj[1]]])
            free_ends=sum(t is None for t in tj)
            L=np.linalg.norm(np.diff(P,axis=0),axis=1).sum() if len(P)>1 else 0
            if free_ends==1 and L<min_spur and nj>0: continue   # skeleton spur
            if len(P)<2: P=np.vstack([P,P+0.5])
        else:
            P=np.vstack([P,P[:1]])
        out.append(P)
    return out

def arclen(P): return np.r_[0,np.cumsum(np.linalg.norm(np.diff(P,axis=0),axis=1))]

def order(strokes, pen=None, reading=True, min_len=8):
    strokes=[S for S in strokes if arclen(S)[-1]>=min_len] or strokes
    """Greedy chaining in reading order. Pen continues through a junction along the best-aligned
    edge; otherwise picks the next stroke nearest in reading order (top-left first) and orients it
    to start at its top/left end (never from the middle)."""
    rem=list(range(len(strokes))); res=[]; prevdir=None
    if pen is None:
        allp=np.vstack(strokes); pen=np.array([allp[:,0].min(),allp[:,1].min()])
    while rem:
        best=None
        # continuity through a junction
        for i in rem:
            S=strokes[i]
            for rev in (False,True):
                P=S[::-1] if rev else S
                if np.linalg.norm(P[0]-pen)<4 and prevdir is not None:
                    d=P[min(len(P)-1,8)]-P[0]; d=d/(np.linalg.norm(d)+1e-9)
                    c=float(d@prevdir)
                    if c>0.6 and (best is None or c>best[0]): best=(c,i,P)
        if best is None:
            def key(i):
                S=strokes[i]; a,b=S[0],S[-1]
                st=a if (a[1]+0.35*a[0])<=(b[1]+0.35*b[0]) else b
                # if one end is at the pen, start there
                if np.linalg.norm(a-pen)<4: st=a
                elif np.linalg.norm(b-pen)<4: st=b
                return np.linalg.norm(st-pen)+ (0.6*max(0,pen[1]-st[1]-30) if reading else 0), st
            i=min(rem,key=lambda i:key(i)[0]); st=key(i)[1]; S=strokes[i]
            P=S if np.allclose(st,S[0]) else S[::-1]
            best=(0,i,P)
        _,i,P=best; rem.remove(i)
        if res and np.linalg.norm(P[0]-res[-1][-1])<4: res[-1]=np.vstack([res[-1],P[1:]])   # pen continues through the junction
        else: res.append(P)
        pen=P[-1]; d=P[-1]-P[max(0,len(P)-9)]; prevdir=d/(np.linalg.norm(d)+1e-9)
    return res
