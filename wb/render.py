"""Whiteboard explainer renderer.  python3 -m wb.render spec.json
Pipeline: spec -> elements (text / line art) -> skeleton strokes (junction-split, reading order)
-> timeline (pen draws at eased speed, micro-pauses, lifted travel) -> per-pixel reveal-time maps
-> frames (board + ink + hand sprite pinned to tip) -> ffmpeg -> marker SFX mix."""
import json, sys, os, math, subprocess, numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from scipy.ndimage import distance_transform_edt, gaussian_filter, binary_fill_holes, zoom
from . import strokes as SK, icons
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONTS={'patrick':ROOT+'/fonts/PatrickHand-Regular.ttf','caveat':ROOT+'/fonts/Caveat-VariableFont_wght.ttf'}
COLORS={'black':(30,32,36),'green':(28,140,92),'red':(214,52,46),'blue':(36,84,196)}
FPS=30

INKSET=None
def col(c):
    if isinstance(c,str) and INKSET and c in INKSET: return tuple(INKSET[c])
    return tuple(COLORS.get(c,c)) if isinstance(c,str) else tuple(c)

# ---------------- board ----------------
def make_board(W,H,seed=1):
    r=np.random.default_rng(seed); y,x=np.mgrid[0:H,0:W].astype(np.float32)
    base=np.array([233,234,230],np.float32)
    shade=1-0.06*((x/W-0.35)**2+(y/H-0.4)**2)                    # soft light falloff
    img=base*shade[...,None]
    n=zoom(r.normal(0,1,(H//8+1,W//8+1)),8,order=1)[:H,:W]
    img+= (n*1.6)[...,None]+r.normal(0,1.1,(H,W,1))               # subtle texture
    # glare: soft diagonal band (like a photographed board under a window)
    d=(y-(0.30*H-0.22*(x)))/(0.045*H)
    g=np.exp(-d**2)*(1-0.6*x/W)
    img=img+g[...,None]*22
    sm=gaussian_filter(r.normal(0,1,(H//16+1,W//16+1)),2)          # faint ghosting from old erasing
    img-= zoom(np.clip(sm,0,None),16,order=1)[:H,:W,None]*3
    # thin aluminium frame top/right
    t=int(0.012*W)
    img[:t]=np.array([200,202,204])-np.linspace(0,30,t)[:,None,None]
    img[:,W-t:]=np.array([196,198,200])-np.linspace(30,0,t)[None,:,None]
    return np.clip(img,0,255).astype(np.float32)

# ---------------- elements -> thin skeleton strokes ----------------
def wobble_poly(poly,rng,amp=2.2,step=6):
    P=np.array(poly,float); out=[]
    for a,b in zip(P[:-1],P[1:]):
        n=max(2,int(np.linalg.norm(b-a)/step)); t=np.linspace(0,1,n,endpoint=False)
        out.append(a+(b-a)*t[:,None])
    out.append(P[-1:]); Q=np.vstack(out)
    # low-frequency hand tremor, perpendicular-ish, smooth
    k=len(Q); s=np.cumsum(np.r_[0,np.linalg.norm(np.diff(Q,axis=0),axis=1)])
    ph=rng.uniform(0,6,4)
    off=np.stack([np.sin(s/37+ph[0])+0.5*np.sin(s/13+ph[1]), np.sin(s/41+ph[2])+0.5*np.sin(s/17+ph[3])],1)*amp*0.6
    return Q+off

def line_strokes(polys,box,W,H,rng,amp=2.2,rot=0.0):
    x,y,w,h=box; im=Image.new('L',(W,H),0); d=ImageDraw.Draw(im)
    c,s=math.cos(rot),math.sin(rot)
    for p in polys:
        P=np.array(p,float); P=np.c_[x+P[:,0]*w, y+P[:,1]*h]
        cx,cy=x+w/2,y+h/2; P=np.c_[cx+(P[:,0]-cx)*c-(P[:,1]-cy)*s, cy+(P[:,0]-cx)*s+(P[:,1]-cy)*c]
        Q=wobble_poly(P,rng,amp)
        d.line([tuple(q) for q in Q],fill=255,width=3,joint='curve')
    m=np.asarray(im)>0
    return SK.order(SK.trace(SK.skel(m),min_spur=8))

def char_strokes(ch,font,xy,W,H,rng,rot_deg=0.0):
    if ch.strip()=='' : return []
    b=font.getbbox(ch); pad=20
    im=Image.new('L',(b[2]-b[0]+2*pad,b[3]-b[1]+2*pad),0)
    ImageDraw.Draw(im).text((pad-b[0],pad-b[1]),ch,font=font,fill=255)
    if rot_deg: im=im.rotate(rot_deg,resample=Image.BICUBIC)
    m=np.asarray(im)>110
    st=SK.order(SK.trace(SK.skel(m),min_spur=max(5,font.size*0.09)))
    ox,oy=xy[0]+b[0]-pad, xy[1]+b[1]-pad
    return [P+np.array([ox,oy]) for P in st]

def text_units(text,font,x,y,W,H,rng,anchor='l',jitter=1.0,tracking=1.0):
    """word-by-word units; per-glyph slight rotation/baseline jitter so lettering is hand-made"""
    words=text.split(' '); sp=font.getlength(' ')
    total=sum(font.getlength(w)*tracking for w in words)+sp*(len(words)-1)
    if anchor=='c': x=x-total/2
    elif anchor=='r': x=x-total
    units=[]; cx=x
    for w in words:
        st=[]
        for ch in w:
            dy=rng.normal(0,1.6*jitter); rt=rng.normal(0,1.6*jitter)
            st+=char_strokes(ch,font,(cx,y+dy),W,H,rng,rt)
            cx+=font.getlength(ch)*tracking
        units.append(dict(strokes=st,kind='text'))
        cx+=sp
    return units,(x,x+total)

# ---------------- layout: generic elements and two-column comparison ----------------
def hershey_units(text,size,x,y,rng,anchor='l',font='futural'):
    """centreline stroke-order text (Hershey single-line font) with hand jitter; word-by-word units"""
    from . import real as RL
    cap=size*0.58; sts,total=RL.hershey_strokes(text,cap,font)
    if anchor=='c': x=x-total/2
    elif anchor=='r': x=x-total
    base=y+size*0.30+cap                                   # baseline (matches the TTF layout)
    units={}; jit={}
    for ci,wi,st in sts:
        if ci not in jit: jit[ci]=(rng.normal(0,1.8),rng.normal(0,1.2),1+rng.normal(0,0.03))
        rot,dy,sc=jit[ci]; P=st.copy()
        cx=P[:,0].mean() if len(P) else 0
        th=math.radians(rot); c_,s_=math.cos(th),math.sin(th)
        X=(P[:,0]-cx)*sc; Y=P[:,1]*sc
        P=np.c_[cx+X*c_-Y*s_-0.07*Y, X*s_+Y*c_]           # per-glyph tilt + slight forward slant
        P=P+np.array([x,base+dy])
        if len(P)<2: continue
        Q=wobble_poly(P,rng,amp=0.9,step=4)
        units.setdefault(wi,[]).append(Q)
    out=[dict(strokes=units[k],kind='text') for k in sorted(units)]
    return out,(x,x+total)

def build(spec,W,H,rng):
    """Returns ordered list of elements: dict(units=[...], color, width, fill=None, at=None)"""
    els=[]
    fpath=FONTS.get(spec.get('font','patrick'),FONTS['patrick'])
    def F(px): return ImageFont.truetype(fpath,int(px))
    U=W/1080.0                                   # layout unit
    land=W>H
    def T(text,size,x,y,color='black',anchor='l',maxw=None,**kw):
        if maxw and str(spec.get('font','')).startswith('hershey'):
            from . import real as RL
            while RL.hershey_strokes(text,size*U*0.58)[1]>maxw and size>10: size*=0.95
        if str(spec.get('font','')).startswith('hershey'): u,ext=hershey_units(text,size*U,x,y,rng,anchor,spec['font'].split(':')[1] if ':' in spec['font'] else 'futural')
        else: u,ext=text_units(text,F(size*U),x,y,W,H,rng,anchor)
        tw=spec.get('pen_width',9)*U*(min(1,max(0.6,size/spec.get('heading_size',118)))**0.5 if spec.get('text_pen_scale') else 1)
        els.append(dict(units=u,color=color,width=tw,**kw)); return ext
    def L(name_or_polys,box=None,color='black',amp=2.2,**kw):
        polys=icons.LIB[name_or_polys]() if isinstance(name_or_polys,str) else name_or_polys
        st=line_strokes(polys,box,W,H,rng,amp*U)
        els.append(dict(units=[dict(strokes=st,kind='line')],color=color,width=spec.get('pen_width',9)*U,**kw))
    cs=spec.get('colors',{})
    INK=cs.get('text','black'); POS=cs.get('positive','green'); NEG=cs.get('negative','red')
    if spec.get('layout')=='two_column':
        cols=spec['columns']; top=0.10*H if not spec.get('title') else 0.16*H
        if spec.get('title'): T(spec['title'],90 if not land else 70,W/2,0.04*H,INK,'c')
        hs=spec.get('heading_size',118 if not land else 80); ls=spec.get('item_size',60 if not land else 44)
        cx=[W*0.25,W*0.75]; dv_top=top-0.02*H; dv_bot=(0.70 if not land else 0.80)*H
        # headings: left, divider, right
        T(cols[0]['heading'],hs,cx[0],top,cols[0].get('heading_color',INK),'c')
        L('vline',(W/2-10,dv_top,20,dv_bot-dv_top),INK,amp=3)
        T(cols[1]['heading'],hs,cx[1],top,cols[1].get('heading_color',INK),'c')
        iy=top+(0.11 if not land else 0.17)*H; ih=spec.get('icon_h',0.17 if not land else 0.30)*H
        for i,c in enumerate(cols):
            for ic in c.get('icons',[]):
                rw,rh=ic.get('size',[0.5,1.0]); dx,dy=ic.get('offset',[0,0])
                bw=ih*rw; bh=ih*rh
                L(ic['name'],(cx[i]+dx*ih-bw/2,iy+dy*ih,bw,bh),ic.get('color',INK),fill=ic.get('fill'))
        ly=iy+ih+(0.05 if not land else 0.07)*H; step=spec.get('item_step',0.052 if not land else 0.09)*H
        if str(spec.get('font','')).startswith('hershey'):   # one size for every list item (fit the longest)
            from . import real as RL
            for i,c in enumerate(cols):
                for it in c.get('items',[]):
                    room=(W*spec.get('item_room',0.44)-ls*0.75*U*1.4) if i==0 else (W*0.41-ls*0.75*U*1.1)
                    while RL.hershey_strokes(it['text'],ls*U*0.58)[1]>room and ls>10: ls*=0.96
        mk=ls*0.75*U
        for i,c in enumerate(cols):
            x0=W*0.055 if i==0 else W*0.535
            for j,it in enumerate(c.get('items',[])):
                y=ly+j*step; mark=it.get('mark'); side=c.get('mark_side','left' if i==0 else 'right')
                mcol=POS if mark=='tick' else NEG
                if side=='left':
                    xs,xe=T(it['text'],ls,x0+mk*1.4,y,INK,maxw=W*0.42-mk*1.4)
                    if mark: L(mark,mark=True,box=(x0,y+ls*U*(0.25 if str(spec.get('font','')).startswith('hershey') else 0.05),mk,mk*(0.9 if mark=='tick' else 0.7)),color=mcol,amp=1.2)
                else:
                    xs,xe=T(it['text'],ls,x0,y,INK,maxw=W*0.40-mk*1.1)
                    if mark: L(mark,mark=True,box=(xe+0.45*mk,y+ls*U*(0.36 if str(spec.get('font','')).startswith('hershey') else 0.18),mk*(0.9 if mark=='tick' else 0.6),mk*(0.9 if mark=='tick' else 0.6)),color=mcol,amp=1.2)
        if spec.get('takeaway'):
            ts=ls*1.25
            f=F(ts*U)
            while f.getlength(spec['takeaway'])>W*0.9: ts*=0.95; f=F(ts*U)
            T(spec['takeaway'],ts,W/2,dv_bot+0.035*H,INK,'c',maxw=W*0.88)
    else:
        # generic free layout: elements with fractional coords
        if spec.get('title'): T(spec['title'],100,W/2,0.05*H,INK,'c')
        for e in spec.get('elements',[]):
            if e['type']=='text': T(e['text'],e.get('size',64),e['x']*W,e['y']*H,e.get('color',INK),e.get('anchor','l'),at=e.get('at'))
            elif e['type'] in ('icon','path'):
                polys=e['name'] if e['type']=='icon' else e['polylines']
                b=e['box']; L(polys,(b[0]*W,b[1]*H,b[2]*W,b[3]*H),e.get('color',INK),fill=e.get('fill'),at=e.get('at'))
            elif e['type']=='image':   # clean line-art PNG (dark lines on light)
                im=Image.open(e['path']).convert('L'); b=e['box']; im=im.resize((int(b[2]*W),int(b[3]*H)))
                m=np.zeros((H,W),bool); a=np.asarray(im)<128; y0,x0=int(b[1]*H),int(b[0]*W)
                m[y0:y0+a.shape[0],x0:x0+a.shape[1]]=a
                st=SK.order(SK.trace(SK.skel(m)))
                els.append(dict(units=[dict(strokes=st,kind='line')],color=e.get('color',INK),width=spec.get('pen_width',9)*U,fill=e.get('fill'),at=e.get('at')))
    return els

# ---------------- timeline ----------------
def ease_s(u): return 0.55*(0.5-0.5*np.cos(np.pi*u))+0.45*u
def zigzag(region,spacing):
    ys,xs=np.nonzero(region)
    if len(ys)==0: return None
    pts=[]; flip=False
    for y in np.arange(ys.min()+spacing/2,ys.max(),spacing):
        row=xs[np.abs(ys-y)<1]
        if len(row)==0: continue
        a,b=row.min()+2,row.max()-2
        pts+= [(b,y),(a,y)] if flip else [(a,y),(b,y)]; flip=not flip
    return np.array(pts,float) if len(pts)>=2 else None

TRAY_INKS=[('black',),('green',),('red',)]
def area_of(e,W,H):
    if e.get('area'): return e['area']
    P=np.vstack([P for u in e['units'] for P in u['strokes']]); cx,cy=P[:,0].mean()/W,P[:,1].mean()/H
    return 'bottom' if cy>0.68 else ('top' if cy<0.14 else ('left' if cx<0.5 else 'right'))
def tray_geom(spec,W,H):
    b=spec.get('board',{}); th=int(b.get('tray_h',0.075)*H); ty1=H-int(b.get('floor',0.035)*H); ty0=ty1-th
    return dict(y0=ty0,top=int(th*0.42),y1=ty1)
def sched_kwargs(spec,W,H,els):
    if spec.get('style')!='photo8': return {}
    tg=tray_geom(spec,W,H); last=els[-1]['color']; names=[n for (n,) in TRAY_INKS]
    S=min(W,H); xf=spec.get('board',{}).get('tray_x') or [0.10,0.33,0.56]; xf=xf[names.index(last) if last in names else 0]
    return dict(hold=float(spec.get('end_hold',3.0)),exit_swaps=True,place=(xf*W+0.01*S,tg['y0']+tg['top']-0.016*S))
def schedule(els,W,H,dur,rng,hold=1.6,intro=0.35,swap=True,exit_swaps=False,place=None):
    """Natural durations (all positive): draw = max(min_draw, L/speed); micro-pauses at stroke ends;
    lifted travel; a marker swap (hand lifts off-board, pauses, comes back with the new colour) whenever
    the ink colour changes. Everything is then scaled by ONE factor so all durations stay positive."""
    offp=np.array([W*1.07,H*0.90]) if exit_swaps else np.array([W*1.2,H*1.15]); segs=[]; pen=offp; prevcol=None
    for ei,e in enumerate(els):
        first=True
        same_area=exit_swaps and ei>0 and area_of(e,W,H)==area_of(els[ei-1],W,H)
        if prevcol is not None and swap and col(e['color'])!=prevcol and same_area:
            # quick swap in the same area: short dip toward the bottom-right edge, hand only partly leaves
            dip=np.array([W*0.97,min(H*0.80,pen[1]+0.25*H)])
            segs.append(dict(kind='travel',a=pen,b=dip,dur=0.30,el=ei-1,arc=True,mn=0.26,dip=True))
            segs.append(dict(kind='pause',a=dip,dur=0.16,el=ei,fixed=True)); pen=dip
        elif exit_swaps and ei>0 and not same_area:
            # moving to another part of the board: leave the frame (and swap there if needed)
            segs.append(dict(kind='travel',a=pen,b=offp,dur=0.42,el=ei-1,swapout=True,mn=0.32,arc=True))
            segs.append(dict(kind='hidden',dur=0.14,el=ei,fixed=True)); pen=offp
        elif prevcol is not None and swap and col(e['color'])!=prevcol:
            away=np.clip(pen+np.array([0.30*W,0.20*H]),[0,0],[W*1.25,H*1.2])
            segs.append(dict(kind='travel',a=pen,b=away,dur=0.30,el=ei-1,swapout=True,mn=0.13))
            segs.append(dict(kind='swap',a=away,dur=0.10,el=ei,fixed=True))       # colour changes here, hand off the art
            pen=away
        prevcol=col(e['color'])
        for ui,u in enumerate(e['units']):
            for si,P in enumerate(u['strokes']):
                L=SK.arclen(P)[-1]; tv=np.linalg.norm(P[0]-pen)
                if first or tv>3:
                    segs.append(dict(kind='travel',a=pen,b=P[0],dur=(0.20 if first else 0.05)+tv/2400+(0.08 if (ui and si==0) else 0),el=ei,newel=first,arc=exit_swaps,mn=(0.32 if (exit_swaps and np.allclose(pen,offp)) else ((tv/5000 if tv<200 else 0.03+tv/3500) if exit_swaps else None))))
                    first=False
                text=u['kind']=='text'
                sp=(650 if text else 750)*W/1080
                mind=0.03 if text else 0.20             # small strokes (windows, ticks) still visibly drawn
                segs.append(dict(kind='draw',P=P,dur=max(mind,L/sp)*(2.2 if text else 1),el=ei,text=text,mn=(None if text else ((0.3 if e.get('mark') else max(0.16,min(0.3,L/1000))) if not exit_swaps else max(0.08,min(0.22,L/1600))))))
                segs.append(dict(kind='pause',a=P[-1],dur=rng.uniform(0.02,0.04)*(2 if si==len(u['strokes'])-1 else 1),el=ei))
                pen=P[-1]
        if e.get('fill'):
            reg=binary_fill_holes(e['_inkmask'])&~e['_inkmask'] if '_inkmask' in e else None
            e['_fillreg']=reg
            Z=zigzag(reg,e['width']*1.6) if reg is not None else None
            if Z is not None:
                Zd=np.vstack([wobble_poly([a,b],rng,1.0,4) for a,b in zip(Z[:-1],Z[1:])])
                segs.append(dict(kind='travel',a=pen,b=Zd[0],dur=0.12,el=ei))
                segs.append(dict(kind='fill',P=Zd,dur=max(0.3,SK.arclen(Zd)[-1]/2200),el=ei,mn=0.5)); pen=Zd[-1]
    if place is not None:      # put the marker down on the tray before leaving
        pl=np.array(place,float)
        segs.append(dict(kind='travel',a=pen,b=pl,dur=0.6,el=len(els)-1,arc=True,mn=0.5))
        segs.append(dict(kind='pause',a=pl,dur=0.35,el=len(els)-1,fixed=True,place=True)); pen=pl
    segs.append(dict(kind='travel',a=pen,b=offp,dur=0.6,el=len(els)-1,exit=True,arc=exit_swaps,mn=(0.5 if exit_swaps else None)))
    # one global factor, but line-art strokes keep a minimum on-screen duration (ticks, windows are visibly drawn);
    # the time they need is taken from everything else
    budget=dur-hold-intro; nat=[s['dur'] for s in segs]; pinned=set()
    for _ in range(8):
        fx=sum(s['dur'] for i,s in enumerate(segs) if s.get('fixed') or i in pinned)
        vr=sum(nat[i] for i,s in enumerate(segs) if not(s.get('fixed') or i in pinned))
        k=(budget-fx)/vr; assert k>0.04, f'too much content for {dur}s; lengthen or trim'
        new=False
        for i,s in enumerate(segs):
            if s.get('fixed') or i in pinned: continue
            s['dur']=nat[i]*k
            if s.get('mn') and s['dur']<s['mn']: s['dur']=s['mn']; pinned.add(i); new=True
        if not new: break
    # voiceover sync: 'at' times; waits > 1 s send the hand off-frame and back
    out=[]; t=intro
    for s in segs:
        at=els[s['el']].get('at') if s.get('newel') else None
        if at is not None and at>t:
            wait=at-t
            if wait>1.0:
                out.append(dict(kind='travel',a=s['a'],b=offp,dur=0.45,el=s['el'])); out.append(dict(kind='hidden',dur=wait-0.45,el=s['el'])); s=dict(s,a=offp)
            else: out.append(dict(kind='pause',a=s['a'],dur=wait,el=s['el']))
            t=at
        out.append(s); t+=s['dur']
    segs=out; t=intro
    for s in segs:
        assert s['dur']>0
        s['t0']=t; t+=s['dur']; s['t1']=t
    return segs,k

# ---------------- reveal maps ----------------
INKVAR=0.07; INKOPA=1.0; V8S=False
def reveal_maps(els,segs,W,H):
    global STREAK
    rs=np.random.default_rng(12)
    sx=gaussian_filter(rs.normal(0,1,(H,W)),(0.6,9)); sy=gaussian_filter(rs.normal(0,1,(H,W)),(9,0.6))
    v=INKVAR; blot=zoom(rs.normal(0,1,(H//40+2,W//40+2)),40,order=3)[:H,:W]
    blot=(1-0.5*v+0.5*v*np.clip(blot/blot.std(),-2,2)/2).astype(np.float32) if v>0.08 else 1.0
    STREAK=[((1-v)+v*np.clip(z/z.std(),-1.5,1.5)/1.5)*blot for z in (sx,sy)]
    STREAK=[z.astype(np.float32) for z in STREAK]
    T=np.full((H,W),np.inf,np.float32); A=np.zeros((H,W),np.float32); C=np.zeros((H,W,3),np.float32)
    TF=np.full((H,W),np.inf,np.float32); AF=np.zeros((H,W),np.float32); CF=np.zeros((H,W,3),np.float32)
    for s in segs:
        if s['kind'] not in ('draw','fill'): continue
        e=els[s['el']]; P=s['P']; L=SK.arclen(P); Lt=max(L[-1],1e-6)
        u=np.linspace(0,1,400); tt=s['t0']+u*(s['t1']-s['t0']); ss=ease_s(u)*Lt
        if s['kind']=='fill':
            reg=e['_fillreg']; r=e['width']*1.2
        else: r=e['width']/2
        pad=int(r+4) if s['kind']=='draw' else int(e['width']*2)
        x0=max(0,int(P[:,0].min())-pad); x1=min(W,int(P[:,0].max())+pad+1)
        y0=max(0,int(P[:,1].min())-pad); y1=min(H,int(P[:,1].max())+pad+1)
        if x1<=x0 or y1<=y0: continue
        # dense resample of path, time per sample
        n=max(2,int(Lt*2)); sd=np.linspace(0,Lt,n)
        Q=np.c_[np.interp(sd,L,P[:,0]),np.interp(sd,L,P[:,1])]; tq=np.interp(sd,ss,tt)
        sk=np.zeros((y1-y0,x1-x0),bool); tm=np.full(sk.shape,np.inf,np.float32)
        rm=np.zeros(sk.shape,np.float32); am=np.zeros(sk.shape,np.float32)
        # speed-dependent brush: slower -> wider & darker; ends get a small ink bulge
        vq=np.gradient(sd)/np.maximum(np.gradient(tq),1e-4); vn=np.clip(gaussian_filter(vq,3)/1500,0,1)
        endp=np.clip(1-np.minimum(sd,Lt-sd)/(2.5*r+1e-6),0,1)
        rq=r*(1.12-0.24*vn)*(1+0.10*endp); aq=(0.93-0.13*vn+0.06*endp)
        qi=np.clip(np.round(Q).astype(int)-[x0,y0],0,[x1-x0-1,y1-y0-1])
        for (qx,qy),tv,rv,av in zip(qi,tq,rq,aq):
            if tv<tm[qy,qx]: tm[qy,qx]=tv; rm[qy,qx]=rv; am[qy,qx]=av
            sk[qy,qx]=True
        d,(iy,ix)=distance_transform_edt(~sk,return_indices=True)
        tp=tm[iy,ix]
        c=np.array(col(e['color']),np.float32)
        if s['kind']=='draw':
            rp=rm[iy,ix]; ap=am[iy,ix]
            edge=np.clip(0.86+0.22*(d/np.maximum(rp,1))**2,0,1.08)            # darker rim like real marker
            dvec=P[-1]-P[0]; streak=STREAK[1 if abs(dvec[1])>abs(dvec[0]) else 0][y0:y1,x0:x1]
            a=(np.clip((rp-d)/(1.6 if INKSET else 1.0)+0.6,0,1)*ap*(edge if not INKSET else np.clip(0.9+0.12*(d/np.maximum(rp,1))**2,0,1.02))*streak*INKOPA).clip(0,1).astype(np.float32)
            Ts=T[y0:y1,x0:x1]; As=A[y0:y1,x0:x1]; Cs=C[y0:y1,x0:x1]
            m=a>0; newer=m&(tp<Ts)
            Cs[newer&(As<0.5)]=c
            ov=m&(As>0.3)&(a>0.3)                                                  # overlap: slightly faded
            Ts[m]=np.minimum(Ts[m],tp[m]); As[m]=np.maximum(As[m],a[m]); As[ov]*=0.94
        else:
            rg=reg[y0:y1,x0:x1]; m=rg&(d<=r*1.6)
            TF[y0:y1,x0:x1][m]=np.minimum(TF[y0:y1,x0:x1][m],tp[m]); AF[y0:y1,x0:x1][m]=0.33; CF[y0:y1,x0:x1][m]=c
    return T,A,C,TF,AF,CF

def ink_masks(els,W,H):
    """pre-pass: ink coverage per element (for fills) without timing"""
    for e in els:
        if not e.get('fill'): continue
        m=np.zeros((H,W),bool)
        for u in e['units']:
            for P in u['strokes']:
                q=np.clip(np.round(P).astype(int),0,[W-1,H-1]); m[q[:,1],q[:,0]]=True
        e['_inkmask']=distance_transform_edt(~m)<=e['width']/2+1

# ---------------- hand ----------------
TIP=(38.0,177.0)   # nib contact pixel in assets/hand_cut.png (legacy cartoon hand, not shipped in this kit)
class Hand:
    def __init__(s,path,W,scale,tip=TIP):
        im=Image.open(path).convert('RGBA'); a=np.asarray(im).astype(np.float32).copy()
        a[:166,:52,3]=0                                   # stray board ink above the nib in the cut-out
        al=a[...,3]; tip=np.array(tip,float); H0,W0=al.shape
        # --- sleeve: original sleeve fades (long gradient) into a procedural knit sleeve that runs off-frame
        yy,xx=np.mgrid[0:H0,0:W0]
        keep=np.clip((800-yy)/130,0,1)*np.where(xx<480,np.clip((598-yy)/14,0,1),1)
        sl=a[600:760,520:700][a[600:760,520:700,3]>200][:,:3]; scol=np.median(sl,0) if len(sl) else np.array([150,150,155.])
        padR,padB=1500,1900
        big=np.zeros((H0+padB,W0+padR,4),np.float32); BH,BW=big.shape[:2]
        d=np.array([0.70,0.71]); d/=np.linalg.norm(d)
        c0=np.array([560.,640.]); R0=102.0                 # tube centre/radius at the cuff
        Y,X=np.mgrid[0:BH,0:BW].astype(np.float32); nz=np.random.default_rng(4)
        along=(X-c0[0])*d[0]+(Y-c0[1])*d[1]; nrm=np.array([-d[1],d[0]]); acr=(X-c0[0])*nrm[0]+(Y-c0[1])*nrm[1]
        Rr=R0+0.09*np.clip(along,0,None)                   # sleeve widens slightly toward the shoulder
        # rounded start (behind the cuff) and soft edges: no straight cut anywhere
        dist=np.where(along<0,np.sqrt(along**2+acr**2),np.abs(acr))
        m=np.clip((Rr-dist)/9,0,1)*255
        knit=gaussian_filter(nz.normal(0,1,(BH,BW)),(0.7,2.2))*11
        u=np.clip(acr/Rr,-1,1)
        shade=0.70+0.38*np.sqrt(np.clip(1-u**2,0,1))+0.10*(-u)+0.035*np.sin(along/70+acr/45)    # cylinder shading + folds
        big[...,:3]=np.clip(scol*shade[...,None]+knit[...,None],0,255); big[...,3]=m
        oa=a[...,3:]/255*keep[...,None]
        big[:H0,:W0,:3]=a[...,:3]*oa+big[:H0,:W0,:3]*(1-oa)
        big[:H0,:W0,3]=np.maximum(big[:H0,:W0,3],oa[...,0]*255)
        s.base=big; s.tip0=tip
        # --- marker mask: band along the marker axis, white body + green parts, excluding skin
        hs=np.asarray(Image.fromarray(big[...,:3].astype(np.uint8)).convert('HSV')).astype(np.float32)
        hue,sat,val=hs[...,0]*360/255,hs[...,1]/255,hs[...,2]/255
        band=Image.new('L',(BW,BH),0); ImageDraw.Draw(band).polygon([(24,140),(410,150),(415,250),(24,205)],fill=255)
        band=np.asarray(band)>0
        green=(hue>110)&(hue<200)&(sat>0.25); white=(sat<0.22)&(val>0.5); nib=(val<0.35)&(xx_big(BH,BW)<70)
        from scipy.ndimage import binary_dilation
        gm=binary_dilation(band&(green|nib),iterations=2)&band&(big[...,3]>20)
        s.mk_col=np.maximum(gm.astype(np.float32),gaussian_filter(gm.astype(np.float32),0.8))
        s.mk_body=gaussian_filter((band&white&(big[...,3]>50)).astype(np.float32),0.8)
        s.val=val; s.scale=scale; s.cache={}
        wrist=np.array([470.,520.]); dd=wrist-tip; s.arm_ang=math.degrees(math.atan2(dd[1],dd[0]))
    def sprite(s,color):
        key=tuple(color)
        if key not in s.cache:
            a=s.base.copy(); tgt=np.array(color,np.float32)
            dark=sum(color)<200
            v=s.val[...,None]
            capc=np.clip(tgt*(v/0.5)+(40 if dark else 0)*v,0,255)                 # cap / grip / nib: full ink colour
            bodyc=np.clip((tgt*0.75+(70 if dark else 64))*(0.55+0.5*v),0,255)    # barrel: strong tint of the ink colour
            g=s.mk_col[...,None]; b=s.mk_body[...,None]
            a[...,:3]=a[...,:3]*(1-g)+capc*g; a[...,:3]=a[...,:3]*(1-b)+bodyc*b
            im=Image.fromarray(np.clip(a,0,255).astype(np.uint8),'RGBA')
            sc=s.scale; im=im.resize((int(im.width*sc),int(im.height*sc)),Image.LANCZOS)
            s.cache[key]=im
        return s.cache[key]
    def place(s,frame,tip,color,ang,lift,mark=False):
        """Pins the sprite's nib pixel exactly at `tip` (integer-rounded paste, rotation about the nib)."""
        lift=float(lift); ang=float(ang); im=s.sprite(color); t0=s.tip0*s.scale
        cx,cy=float(t0[0]),float(t0[1])
        # rotate about the nib; paste offset chosen so nib lands on tip (sub-pixel via affine translation)
        ox,oy=math.floor(tip[0]-cx),math.floor(tip[1]-cy); fx,fy=tip[0]-cx-ox,tip[1]-cy-oy
        r=im.rotate(ang,resample=Image.BILINEAR,center=(cx,cy),translate=(fx,fy))
        al=r.split()[3]
        sh=al.resize((al.width//4,al.height//4)).filter(ImageFilter.GaussianBlur(4+5*lift)).resize(al.size)
        sh=sh.point(lambda v:int(v*(0.22-0.08*lift)))
        frame.paste(Image.new('RGB',r.size,(60,60,65)),(ox+int(18+30*lift),oy+int(26+40*lift)),sh)
        frame.paste(r,(ox,oy),al)
        if mark:
            ImageDraw.Draw(frame).ellipse([tip[0]-3,tip[1]-3,tip[0]+3,tip[1]+3],outline=(255,0,255),width=2)

def xx_big(H,W): return np.mgrid[0:H,0:W][1]

def hand_state(segs,t,W,H):
    for s in segs:
        if s['t0']<=t<s['t1']:
            u=(t-s['t0'])/max(s['dur'],1e-6)
            if s['kind'] in ('draw','fill'):
                P=s['P']; L=SK.arclen(P); d=ease_s(u)*L[-1]
                p=np.array([np.interp(d,L,P[:,0]),np.interp(d,L,P[:,1])])
                d2=min(L[-1],d+6); q=np.array([np.interp(d2,L,P[:,0]),np.interp(d2,L,P[:,1])])
                d1=max(0,d-6); o=np.array([np.interp(d1,L,P[:,0]),np.interp(d1,L,P[:,1])])
                tg=q-o
                return p,True,0.0,tg,s
            if s['kind'] in ('pause','swap'): return s['a'],False,(1.0 if s['kind']=='swap' else 0.0),None,s
            if s['kind']=='hidden': return None,False,1.0,None,(s if V8S else None)
            ff=u*u*(3-2*u); p=s['a']+(s['b']-s['a'])*ff
            if s.get('arc'):   # eased arc, bowing toward an off-frame shoulder (bottom-right)
                ff=u*u*u*(u*(6*u-15)+10); a,b=s['a'],s['b']; dv=b-a; n=np.array([dv[1],-dv[0]])/max(np.linalg.norm(dv),1e-6)
                if n[0]+n[1]<0: n=-n
                p=a+dv*ff+n*np.linalg.norm(dv)*0.10*4*ff*(1-ff)
            lift=math.sin(math.pi*u)*min(1,np.linalg.norm(s['b']-s['a'])/150)
            return p,False,lift,None,s
    return (np.array([W*1.07,H*0.90]) if V8S else np.array([W*1.2,H*1.15])),False,1.0,None,None

def main(spec_path):
    spec=json.load(open(spec_path))
    W,H=(1080,1920) if spec.get('aspect','9:16')=='9:16' else (1920,1080)
    dur=float(spec.get('duration',25)); out=spec.get('out',ROOT+'/out/whiteboard.mp4')
    os.makedirs(os.path.dirname(out),exist_ok=True)
    global INKSET,INKVAR
    INKVAR=float(spec.get('ink_unevenness',0.07))
    from . import real as RLx; RLx.XSCALE=float(spec.get('letter_xscale',0.82))
    RLx.DEFAULT_FONT='relief' if spec.get('font')=='hershey:relief' else None
    if spec.get('style') in ('photo6','photo8'):
        from . import real as RL0; INKSET=dict(RL0.REF_INK,**spec.get('ink',{}))
    global INKOPA,V8S
    INKOPA=float(spec.get('ink_opacity',1.0)); V8S=spec.get('style')=='photo8'
    rng=np.random.default_rng(spec.get('seed',3))
    els=build(spec,W,H,rng); ink_masks(els,W,H)
    segs,k=schedule(els,W,H,dur,rng,**sched_kwargs(spec,W,H,els))
    print('elements',len(els),'segments',len(segs),'speed factor',round(k,2),flush=True)
    T,A,C,TF,AF,CF=reveal_maps(els,segs,W,H)
    PHOTO=spec.get('style') in ('photo','photo6','photo8'); V6=spec.get('style') in ('photo6','photo8'); V8=spec.get('style')=='photo8'
    if PHOTO:
        from . import real as RL
        if V8:
            board,LIT,SPEC,FRAME,FSH,TG=RL.board8(W,H,**spec.get('board',{}))
            TRAYC={}
            def tray_for(missing):
                if missing not in TRAYC:
                    TRAYC[missing]=RL.tray_overlay(W,TG,[(n,col(n)) for (n,) in TRAY_INKS],{n:(n!=missing) for (n,) in TRAY_INKS},S=min(W,H),xs=spec.get('board',{}).get('tray_x'),eraser_x=spec.get('board',{}).get('eraser_x') or 0.78)
                return TRAYC[missing]
        else: board,LIT,SPEC,FRAME,FSH=RL.board6(W,H,**spec.get('board',{})) if V6 else RL.board(W,H)
        if LIT.ndim==2: LIT=LIT[...,None]
        hcfg=RL.HANDS.get(spec.get('hand','default')) if spec.get('hand','default') in RL.HANDS else None
        if V6 and hcfg is not None:
            hand=RL.Hand6(ROOT+'/'+hcfg['path'],hcfg.get('scale') or spec.get('hand_scale',0.26),W,H,cfg=hcfg)
        elif V6: hand=RL.Hand6(spec.get('hand',ROOT+'/assets/hand_photo_cut.png'),spec.get('hand_scale',0.26),W,H)
        if not V6: hand=RL.PhotoHand(spec.get('hand',ROOT+'/assets/hand_photo_cut.png'),spec.get('hand_scale',0.2)*(0.8 if W>H else 1),W)
        if V8 and (hcfg is None or hcfg.get('restyle',True)): RL.restyle_sleeve(hand,tuple(spec.get('sleeve_rgb',(122,122,126))))
        if V8 and spec.get('arm_ik'):
            ik=spec['arm_ik']; hand.arm=RL.ArmIK(hand,W,H,tuple(ik.get('shoulder',(1.15,1.15))),ik.get('l1',0.85),ik.get('l2',0.85),tuple(spec.get('sleeve_rgb',(122,122,126))),ik.get('cut',0.74))
        grain=[np.random.default_rng(i).normal(0,2.4,(H,W,1)).astype(np.int16) for i in range(6)]
        spring=RL.Spring(); pose='neutral'; pose_prev='neutral'; pose_mix=1.0; pprev=None
    else:
        board=make_board(W,H)
        # marker texture: slight streakiness and density variation
        r2=np.random.default_rng(9); tex=0.86+0.14*np.clip(zoom(r2.normal(0,1,(H//6+1,W//6+1)),6,order=1)[:H,:W]*0.5+0.5,0,1)
        A=A*tex.astype(np.float32)
        hand=Hand(spec.get('hand',ROOT+'/assets/hand_cut.png'),W,spec.get('hand_scale',1.0)*W/1080*(0.8 if W>H else 1))
    shoulder=np.array([W*1.25,H*1.35])
    silent=out.replace('.mp4','_silent.mp4')
    ff=subprocess.Popen(['ffmpeg','-v','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(FPS),'-i','-',
        '-c:v','libx264','-preset','medium','-crf','18','-pix_fmt','yuv420p','-movflags','+faststart',silent],stdin=subprocess.PIPE)
    NF=int(dur*FPS); ang_s=None; curcol=col('black'); verify=[]; MARK=bool(spec.get('debug_tip',False))
    # incremental compositing: each pixel is blended once, when its reveal time passes
    canvas=board.copy()
    layers=[]
    for TT,AA,CC in ((TF,AF,CF),(T,A,C)):
        idx=np.flatnonzero(np.isfinite(TT)); o=np.argsort(TT.ravel()[idx]); idx=idx[o]
        layers.append([idx,TT.ravel()[idx],AA.ravel()[idx],CC.reshape(-1,3)[idx],0])
    flat=canvas.reshape(-1,3)
    PREV=spec.get('preview_times'); frames=[int(round(x*FPS)) for x in PREV] if PREV else range(NF)
    if PREV: ff.stdin.close(); ff.wait()
    placed=False; last_missing=els[0]['color']; angle_log=[]
    for f in frames:
        t=f/FPS
        for Ly in layers:
            idx,tv,av,cv,pos=Ly; e=np.searchsorted(tv,t,side='right')
            if e>pos:
                ii=idx[pos:e]; a=av[pos:e,None]; flat[ii]=flat[ii]*(1-a)+cv[pos:e]*a; Ly[4]=e
        if PHOTO:   # board lighting applies to ink too (ink lives in albedo space)
            img=canvas*LIT+SPEC[...,None]; img=img*(1-FSH[...,None]); img=img*(1-FRAME[...,3:])+FRAME[...,:3]*FRAME[...,3:]
        else: img=canvas
        if not V6: fr=Image.fromarray(np.clip(img,0,255).astype(np.uint8))
        else: img=np.array(img,np.float32)
        p,drawing,lift,tg,s=hand_state(segs,t,W,H)
        if V8:   # tray: the marker in use is missing until it is put back
            o,sh_,ty=tray_for(None); hh=o.shape[0]      # fixed tray set, identical every frame; hh=o.shape[0]
            reg=img[ty:ty+hh]; reg*=(1-sh_[...,None]); reg[:]=reg*(1-o[...,3:])+o[...,:3]*o[...,3:]
        if s is not None and s['el']>=0: curcol=col(els[s['el']]['color'])
        if V8 and s is not None and p is not None:
            # wrist locked: the hand translates; a small rotation follows position as if pivoting about a far shoulder
            p=np.array(p,float); pv=np.array(spec.get('pivot',[1.6,1.7]))*[W,H]; ref=np.array([0.5*W,0.45*H])
            dphi=math.degrees(math.atan2(*(pv-p)[::-1]))-math.degrees(math.atan2(*(pv-ref)[::-1]))
            ang=float(spec.get('hand_angle',0.0))-float(spec.get('pivot_gain',0.30))*dphi
            bv=(p-pprev) if (pprev is not None and not drawing) else None
            hand.composite(img,p,curcol,ang,lift*0.6,'neutral',None,1.0,bv); pprev=p
            angle_log.append((f,float(p[0]),float(p[1]),ang))
            if drawing:
                nm=(T>t-1/FPS)&(T<=t); ys,xs=np.nonzero(nm)
                if len(xs): verify.append((f,float(np.hypot(xs-p[0],ys-p[1]).max()),int(len(xs))))
        elif s is not None and p is not None:
            p=np.array(p,float)
            if not drawing and lift>0:                   # natural bob while the hand is lifted/travelling
                p=p+np.array([4*math.sin(7.3*t),-10*lift+3*math.sin(5.1*t+1)])
            if V6: base,_sl=hand.choose_angle(p); rot=hand.arm_ang-base
            else:
                v=shoulder-p; base=math.degrees(math.atan2(v[1],v[0]))
                rot=float(np.clip(hand.arm_ang-base,-45,30))*0.85   # PIL rotates CCW for positive angles
            if tg is not None and np.linalg.norm(tg)>0.5:
                ta=math.degrees(math.atan2(tg[1],tg[0])); rot+= -6*math.sin(math.radians(ta))   # lean with tangent
            rot+=1.2*math.sin(1.7*t)+0.6*math.sin(4.3*t+2)  # small natural wrist motion (rotation is about the nib)
            if PHOTO:
                ang_s=spring.step(rot,1/FPS)            # spring: overshoot + settle at stroke ends; tip unaffected
                # pose by stroke direction and speed (crossfade over ~4 frames)
                want='neutral'
                if drawing and tg is not None and np.linalg.norm(tg)>0.5:
                    gx,gy=tg/np.linalg.norm(tg)
                    want=('up' if gy<0 else 'down') if abs(gy)>abs(gx) else ('left' if gx<0 else 'right')
                if want!=pose: pose_prev,pose,pose_mix=pose,want,0.0
                pose_mix=min(1.0,pose_mix+0.25)
                bv=(p-pprev) if (pprev is not None and not drawing) else None
                lx,ly=int(np.clip(p[0],0,W-1)),int(np.clip(p[1],0,H-1))
                if V6: hand.composite(img,p,curcol,ang_s,lift,pose,pose_prev,pose_mix,bv)
                else: fr=hand.render(fr,p,curcol,ang_s,lift,pose_prev,pose,pose_mix,bv,light=float(np.clip(LIT[ly,lx,0]/0.97,0.9,1.05)))
                if pose_mix>=1.0: pose_prev=pose
                pprev=p
                if MARK and not V6: ImageDraw.Draw(fr).ellipse([p[0]-3,p[1]-3,p[0]+3,p[1]+3],outline=(255,0,255),width=2)
            else:
                ang_s=rot if ang_s is None else ang_s*0.8+rot*0.2   # smoothing affects angle only, never the tip position
                hand.place(fr,p,curcol,ang_s,lift,mark=MARK)
            # verification: newly revealed ink this frame vs the nib position
            if drawing:
                nm=(T>t-1/FPS)&(T<=t); ys,xs=np.nonzero(nm)
                if len(xs): verify.append((f,float(np.hypot(xs-p[0],ys-p[1]).max()),int(len(xs))))
        else: pprev=None
        if V8: fr=Image.fromarray(np.clip(np.clip(img,0,255).astype(np.int16)+grain[0],0,255).astype(np.uint8))   # locked-off: one fixed grain pattern, static pixels stay identical
        elif V6: fr=Image.fromarray(RL.camera(np.clip(img,0,255).astype(np.uint8),t,grain))
        elif PHOTO: fr=Image.fromarray(RL.camera(np.asarray(fr),t,grain))
        if PREV: fr.save(out.replace('.mp4',f'_prev_{t:.2f}.png')); continue
        ff.stdin.write(fr.tobytes())
        if f%150==0: print('frame',f,flush=True)
    if PREV: return
    ff.stdin.close(); ff.wait()
    if V8: json.dump(angle_log,open(out.replace('.mp4','_hand.json'),'w'))
    vd=np.array([v[1] for v in verify]); json.dump(dict(frames=verify),open(out.replace('.mp4','_tipcheck.json'),'w'))
    print(f'tip check: {len(vd)} drawing frames, new-ink distance from nib max {vd.max():.1f}px, p95 {np.percentile(vd,95):.1f}px, median {np.median(vd):.1f}px',flush=True)
    json.dump(dict(fps=FPS,dur=dur,segs=[dict(kind=s['kind'],t0=s['t0'],t1=s['t1'],text=s.get('text',False),L=float(SK.arclen(s['P'])[-1]) if 'P' in s else 0) for s in segs]),open(out.replace('.mp4','_timing.json'),'w'))
    if spec.get('sound',True):
        from . import sfx
        sfx.make(out.replace('.mp4','_timing.json'),silent,out,dur,spec.get('voiceover'),[ROOT+'/'+p for p in spec['sfx_sources']] if spec.get('sfx_sources') else None)
    else: os.replace(silent,out)
    print('done',out)
if __name__=='__main__': main(sys.argv[1])
