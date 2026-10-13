"""Recompute the schedule/reveal maps exactly as the renderer does and check, for every frame,
that the newest ink revealed in that frame sits under the nib, and that no ink appears while the pen is up."""
import sys,json,numpy as np; import os; sys.path.insert(0,os.path.join(os.path.dirname(os.path.abspath(__file__)),'..'))
from wb import render as R
spec=json.load(open(sys.argv[1])); W,H=(1080,1920) if spec.get('aspect','9:16')=='9:16' else (1920,1080); rng=np.random.default_rng(spec.get('seed',3))
els=R.build(spec,W,H,rng); R.ink_masks(els,W,H); R.INKSET=None
segs,k=R.schedule(els,W,H,float(spec.get('duration',25)),rng,**R.sched_kwargs(spec,W,H,els))
T,A,C,TF,AF,CF=R.reveal_maps(els,segs,W,H)
fps=R.FPS; NF=int(float(spec.get('duration',25))*fps); newest=[]; upink=[]
for f in range(NF):
    t=f/fps; p,drawing,lift,tg,s=R.hand_state(segs,t,W,H)
    nm=(T>t-1/fps)&(T<=t)&(A>0.3); ys,xs=np.nonzero(nm)
    if not len(xs): continue
    if drawing:
        tv=T[ys,xs]; j=np.argmax(tv); newest.append(float(np.hypot(xs[j]-p[0],ys[j]-p[1])))
    else: upink.append((f,int(len(xs)),s['kind'] if s else None))
nd=np.array(newest)
print(f'drawing frames {len(nd)}: newest-ink-to-nib distance median {np.median(nd):.1f}px, p95 {np.percentile(nd,95):.1f}px, max {nd.max():.1f}px (pen radius {els[0]["width"]/2:.1f}px)')
print('frames where ink appeared with pen up:',len(upink), upink[:10])
# instant-reveal check: per element, how many frames its ink takes to appear
for i,e in enumerate(els):
    d=[s for s in segs if s['el']==i and s['kind']=='draw']
    if d: print(i,e['color'],'frames %d'%round((d[-1]['t1']-d[0]['t0'])*fps), end='; ')
print()
