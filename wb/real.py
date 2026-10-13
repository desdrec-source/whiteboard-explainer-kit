"""Photoreal layer: board (albedo + illumination + frame), Hershey centreline text, marker brush params,
photographic hand with poses / spring / shadow / motion blur, camera drift + grain."""
import math, numpy as np, cv2
from PIL import Image, ImageDraw, ImageFilter
from scipy.ndimage import gaussian_filter, zoom

# ---------------- board ----------------
def board(W,H,seed=2,ghost_words=None):
    r=np.random.default_rng(seed); y,x=np.mgrid[0:H,0:W].astype(np.float32)
    alb=np.empty((H,W,3),np.float32); alb[:]=(238,239,236)
    lo=zoom(r.normal(0,1,(H//64+2,W//64+2)),64,order=3)[:H,:W]; alb+=lo[...,None]*1.2      # large-scale unevenness
    # ghosting of old erased marker: faint blurred scribbles/words
    g=Image.new('L',(W,H),0); d=ImageDraw.Draw(g)
    for _ in range(26):
        x0,y0=r.uniform(0,W),r.uniform(0,H); pts=[(x0,y0)]
        for k in range(r.integers(4,12)): pts.append((pts[-1][0]+r.normal(28,22),pts[-1][1]+r.normal(0,16)))
        d.line(pts,fill=int(r.uniform(40,120)),width=int(r.uniform(6,12)),joint='curve')
    for _ in range(7):                                       # eraser swipes
        x0,y0=r.uniform(0,W),r.uniform(0,H); w,h=r.uniform(150,380),r.uniform(50,110)
        d.ellipse([x0,y0,x0+w,y0+h],fill=int(r.uniform(15,35)))
    gh=np.asarray(g.filter(ImageFilter.GaussianBlur(5)),np.float32)/255
    alb-=gh[...,None]*np.array([16,15,10])                  # greyish-blue residue
    alb-= (gaussian_filter(r.normal(0,1,(H,W)),0.8)*1.5)[...,None]   # fine surface texture
    sp=r.random((H,W))>0.99993; alb-=gaussian_filter(sp.astype(np.float32),1.2)[...,None]*120  # specks
    # illumination: soft window light from upper right, falloff + vignette
    L=0.93+0.10*np.exp(-(((x-1.05*W)/(1.1*W))**2+((y+0.15*H)/(1.0*H))**2))
    L*=1-0.10*(((x/W-0.5)/0.75)**2+((y/H-0.5)/0.75)**2)
    L=L.astype(np.float32)
    # specular glare: soft diagonal band, added after lighting
    dd=(y-(0.28*H+0.35*(W-x)))/(0.07*H); spec=(np.exp(-dd**2)*0.55+np.exp(-(dd/3)**2)*0.25)*(0.4+0.6*x/W)
    spec=(spec*14).astype(np.float32)
    # aluminium frame on top and right edges (drawn in the final frame)
    fr=np.zeros((H,W,4),np.float32); t=int(0.028*W)
    prof=np.concatenate([np.linspace(170,215,t//3),np.linspace(215,190,t//3),np.linspace(190,150,t-2*(t//3))])
    fr[:t,:,:3]=prof[:,None,None]; fr[:t,:,3]=1
    fr[:,W-t:,:3]=np.maximum(fr[:,W-t:,:3],prof[::-1][None,:,None]); fr[:,W-t:,3]=1
    fr[t:t+2,:W-t,:3]=110; fr[t:t+2,:W-t,3]=0.6; fr[t:H,W-t-2:W-t,:3]=110; fr[t:H,W-t-2:W-t,3]=0.6   # gap line
    fr[...,:3]+= (gaussian_filter(r.normal(0,1,(H,W)),(0.5,6))*3)[...,None]                    # brushed metal
    sh=np.zeros((H,W),np.float32); sh[t:t+14,:W-t]=np.linspace(0.18,0,14)[:,None]; sh[t:,W-t-14:W-t]=np.maximum(sh[t:,W-t-14:W-t],np.linspace(0,0.18,14)[None,:])
    return alb,L,spec,fr,sh

# ---------------- Hershey centreline text ----------------
_HF={}
XSCALE=0.82; DEFAULT_FONT=None
def hershey_strokes(text,cap_px,font=None,xscale=None):
    if (font or DEFAULT_FONT)=='relief': return relief_strokes(text,cap_px,xscale)
    xscale=XSCALE if xscale is None else xscale
    """returns list of (char_index, word_index, stroke Nx2) in pixel units, origin at baseline-left, y down"""
    from HersheyFonts import HersheyFonts
    font=font or 'futural'
    if font not in _HF: h=HersheyFonts(); h.load_default_font(font); _HF[font]=h
    h=_HF[font]; h.normalize_rendering(cap_px/0.75)
    out=[]; xoff=0.0; wi=0
    for ci,ch in enumerate(text):
        if ch==' ': wi+=1
        sts=[np.array(s,float) for s in h.strokes_for_text(ch)]
        adv=max([s[:,0].max() for s in sts]+[cap_px*0.35]) if sts else cap_px*0.45
        for s in sts:
            s=s.copy(); s[:,0]=s[:,0]*xscale+xoff; s[:,1]=cap_px/0.75-s[:,1]-cap_px/0.75*0.25   # y down, baseline at 0..-cap
            out.append((ci,wi,s))
        xoff+=adv*xscale+cap_px*0.14
    return out,xoff

# ---------------- photographic hand ----------------
class PhotoHand:
    """Pexels photo cut-out. Tip = nib contact pixel (verified on a zoomed crop). Black sleeve continues from
    the wristband off-frame. Poses: mild perspective warps of the same photo (one source photo only)."""
    TIP=(276.0,790.0); BAND_C=(2380.,2140.); AXIS=(0.809,0.588); BAND_R=520.
    def __init__(s,path,scale=0.2,W=1080):
        im=np.asarray(Image.open(path).convert('RGBA')).astype(np.float32)
        h0,w0=im.shape[:2]; sc=scale*W/1080; s.sc=sc
        im=cv2.resize(im,(int(w0*sc),int(h0*sc)),interpolation=cv2.INTER_AREA)
        tip=np.array(s.TIP)*sc; c=np.array(s.BAND_C)*sc; ax=np.array(s.AXIS); R=s.BAND_R*sc
        H0,W0=im.shape[:2]; pad=2600
        big=np.zeros((H0+pad,W0+pad,4),np.float32); BH,BW=big.shape[:2]
        Y,X=np.mgrid[0:BH,0:BW].astype(np.float32)
        al=(X-c[0])*ax[0]+(Y-c[1])*ax[1]; nr=np.array([-ax[1],ax[0]]); ac=(X-c[0])*nr[0]+(Y-c[1])*nr[1]
        Rr=R+0.07*np.clip(al,0,None)
        dist=np.where(al<0,np.hypot(al,ac),np.abs(ac)); m=np.clip((Rr-dist)/4,0,1)
        bandpx=im[...,:3][(im[...,3]>200)&(im[...,:3].sum(-1)<160)]
        base=np.median(bandpx,0) if len(bandpx) else np.array([35,33,35.]); base=np.full(3,base.mean())*np.array([1.0,0.98,1.0])  # neutral charcoal sleeve
        u=np.clip(ac/Rr,-1,1)
        shade=0.75+0.55*np.sqrt(np.clip(1-u**2,0,1))+0.25*np.clip(-u,0,1)
        rng=np.random.default_rng(3); fab=gaussian_filter(rng.normal(0,1,(BH,BW)),(1.0,1.0))*4+gaussian_filter(rng.normal(0,1,(BH,BW)),12)*25
        fold=0.12*np.sin(al/(55*sc*5)+ac/(90*sc*5))
        big[...,:3]=np.clip(base*(shade+fold)[...,None]+fab[...,None],0,255); big[...,3]=m*255*(al>-R*0.3)
        a=im[...,3:]/255
        big[:H0,:W0,:3]=im[...,:3]*a+big[:H0,:W0,:3]*(1-a); big[:H0,:W0,3]=np.maximum(big[:H0,:W0,3],im[...,3])
        s.base=big; s.tip=tip
        d=c-tip; s.arm_ang=math.degrees(math.atan2(d[1],d[0]))
        # marker region (for recolour): barrel band from nib to cap
        mk=Image.new('L',(BW,BH),0); P=lambda x,y:(x*sc,y*sc)
        ImageDraw.Draw(mk).polygon([P(*q) for q in cfg.get('marker_poly',[(262,700),(1960,520),(1990,700),(262,830)])],fill=255)
        hsv=cv2.cvtColor(np.clip(big[...,:3],0,255).astype(np.uint8),cv2.COLOR_RGB2HSV).astype(np.float32)
        white=(hsv[...,1]<60)&(hsv[...,2]>120); nib=(hsv[...,2]<90)&(X<P(380,0)[0])
        mm=np.asarray(mk)>0
        s.m_body=gaussian_filter((mm&white&(big[...,3]>100)).astype(np.float32),0.7)
        s.m_nib=gaussian_filter((mm&nib&(big[...,3]>100)).astype(np.float32),0.7)
        s.val=hsv[...,2:]/255.
        s.cache={}
        # poses: (name, perspective tweak) keep nib fixed
        s.poses={'neutral':(0,0,1.0),'up':(-0.05,0.0,0.97),'down':(0.05,0.0,1.03),'left':(0.0,0.04,0.98),'right':(0.0,-0.04,1.02)}
    def _warp(s,img,p):
        shy,shx,sy=p; t=s.tip
        M=np.array([[1,shx,-shx*t[1]],[shy,sy,t[1]-sy*t[1]-shy*t[0]],[0,0,1]],np.float32)
        return cv2.warpPerspective(img,M,(img.shape[1],img.shape[0]),flags=cv2.INTER_LINEAR)
    def sprite(s,color,pose):
        key=(tuple(color),pose)
        if key not in s.cache:
            a=s.base.copy(); tgt=np.array(color,np.float32); dark=sum(color)<200
            body=np.clip(tgt*(0.45+0.75*s.val)+(70 if dark else 30)*s.val,0,255)     # coloured barrel, photo shading kept
            nibc=np.clip(tgt*(0.6+0.8*s.val),0,255)
            b=s.m_body[...,None]*0.85; n=s.m_nib[...,None]
            a[...,:3]=a[...,:3]*(1-b)+body*b; a[...,:3]=a[...,:3]*(1-n)+nibc*n
            a=s._warp(a,s.poses[pose])
            s.cache[key]=Image.fromarray(np.clip(a,0,255).astype(np.uint8),'RGBA')
            if len(s.cache)>40: s.cache.pop(next(iter(s.cache)))
        return s.cache[key]
    def render(s,frame,tip,color,ang,lift,pose='neutral',pose2=None,mix=0.0,blur_vec=None,light=1.0):
        """returns new PIL RGB frame; nib pixel lands exactly on tip"""
        lift=float(lift); ang=float(ang); tip=np.asarray(tip,float)
        def one(fr,tp):
            im=s.sprite(color,pose)
            if pose2 and mix>0.02: im=Image.blend(im,s.sprite(color,pose2),mix)
            cx,cy=float(s.tip[0]),float(s.tip[1])
            ox,oy=math.floor(tp[0]-cx),math.floor(tp[1]-cy); fx,fy=tp[0]-cx-ox,tp[1]-cy-oy
            r=im.rotate(ang,resample=Image.BILINEAR,center=(cx,cy),translate=(fx,fy))
            al=r.split()[3]
            # soft contact shadow offset down-left; bigger/softer when lifted
            sm=al.resize((al.width//4,al.height//4)).filter(ImageFilter.GaussianBlur(3+6*lift))
            sm=sm.resize(al.size).point(lambda v:int(v*(0.30-0.12*lift)))
            fr.paste(Image.new('RGB',r.size,(92,92,100)),(ox-int(16+40*lift),oy+int(20+44*lift)),sm)
            if light!=1.0: r=Image.merge('RGBA',[*Image.eval(r.convert('RGB'),lambda v:int(min(255,v*light))).split(),al])
            fr.paste(r,(ox,oy),al)
            return fr
        if blur_vec is not None:
            bl=np.linalg.norm(blur_vec); blur_vec=blur_vec*0.5*min(1,24/max(bl*0.5,1e-6))   # 180-degree shutter, capped
        if blur_vec is not None and np.linalg.norm(blur_vec)>4:
            outs=[np.asarray(one(frame.copy(),tip-blur_vec*k),np.float32) for k in (-0.5,0.0,0.5)]
            return Image.fromarray(np.mean(outs,0).astype(np.uint8))
        return one(frame,tip)

class Spring:
    def __init__(s,k=110.0,zeta=0.45): s.k=k; s.c=2*zeta*math.sqrt(k); s.x=None; s.v=0.0
    def step(s,target,dt):
        if s.x is None: s.x=target; return s.x
        a=s.k*(target-s.x)-s.c*s.v; s.v+=a*dt; s.x+=s.v*dt; return s.x

def camera(img,t,grain):
    """subtle handheld drift + grain on the final frame (uint8 HxWx3)"""
    H,W=img.shape[:2]
    dx=1.8*math.sin(0.61*t)+0.9*math.sin(1.37*t+1); dy=1.5*math.sin(0.47*t+2)+0.7*math.sin(1.13*t)
    rot=0.06*math.sin(0.33*t)
    M=cv2.getRotationMatrix2D((W/2,H/2),rot,1.0); M[0,2]+=dx; M[1,2]+=dy
    o=cv2.warpAffine(img,M,(W,H),flags=cv2.INTER_LINEAR,borderMode=cv2.BORDER_REFLECT)
    g=grain[int(t*30)%len(grain)]
    return np.clip(o.astype(np.int16)+g,0,255).astype(np.uint8)

# ======================= v6: matched-to-reference photographic look =======================
REF_INK={'black':(38,34,34),'green':(22,122,84),'red':(196,44,40),'blue':(30,70,170)}
def board6(W,H,seed=2,albedo=(224,220,216),falloff=1.0,vignette=0.16,glare=28,glare_w=0.035,wall=0.0):
    """Tone matched to phone photos of a whiteboard: mid-grey warm-neutral (~185 left, ~150 right),
    diagonal window glare, mottled surface, faint ghosting, blue-grey shadowed corners, frame on right/top."""
    r=np.random.default_rng(seed); y,x=np.mgrid[0:H,0:W].astype(np.float32)
    alb=np.empty((H,W,3),np.float32); alb[:]=albedo
    mott=zoom(r.normal(0,1,(H//48+2,W//48+2)),48,order=3)[:H,:W]+0.5*zoom(r.normal(0,1,(H//12+2,W//12+2)),12,order=3)[:H,:W]
    alb+=mott[...,None]*1.6
    g=Image.new('L',(W,H),0); d=ImageDraw.Draw(g)
    for _ in range(30):
        x0,y0=r.uniform(0,W),r.uniform(0,H); pts=[(x0,y0)]
        for k in range(r.integers(4,12)): pts.append((pts[-1][0]+r.normal(26,20),pts[-1][1]+r.normal(0,15)))
        d.line(pts,fill=int(r.uniform(50,140)),width=int(r.uniform(5,11)),joint='curve')
    for _ in range(8):
        x0,y0=r.uniform(-100,W),r.uniform(0,H); w,h=r.uniform(200,450),r.uniform(60,130)
        d.ellipse([x0,y0,x0+w,y0+h],fill=int(r.uniform(15,40)))
    gh=np.asarray(g.filter(ImageFilter.GaussianBlur(6)),np.float32)/255
    alb-=gh[...,None]*np.array([13,12,9])
    alb-=(gaussian_filter(r.normal(0,1,(H,W)),0.7)*1.3)[...,None]
    # lighting: brighter upper-left (window), falling off to the right and bottom; cool shadows
    L=1.0-falloff*(0.20*(x/W)**1.3+0.16*(y/H)**1.6)
    L*=1-vignette*np.clip(((x/W-0.45)/0.7)**2+((y/H-0.45)/0.75)**2,0,1)
    L=gaussian_filter(L,3).astype(np.float32)
    tint=np.stack([L,L*1.0+0.004,L*1.0+0.018],-1)            # slightly blue-grey where darker
    tint=np.where((L<0.9)[...,None],tint,L[...,None])
    # glare: soft diagonal band rising to the right + a broad sheen
    dd=(y-(0.40*H-0.55*x))/(glare_w*H)
    spec=np.exp(-dd**2)*glare*(1-0.6*x/W)+np.exp(-(dd/4)**2)*9*(1-x/W)
    spec=spec.astype(np.float32)
    fr=np.zeros((H,W,4),np.float32); t=int(0.022*W)
    prof=np.concatenate([np.linspace(120,185,t//3),np.linspace(185,165,t//3),np.linspace(165,110,t-2*(t//3))])
    fr[:,W-t:,:3]=prof[::-1][None,:,None]; fr[:,W-t:,3]=1
    fr[:t,:,:3]=np.maximum(fr[:t,:,:3],prof[:,None,None]); fr[:t,:,3]=1
    fr[...,:3]+=(gaussian_filter(r.normal(0,1,(H,W)),(6,0.5))*3)[...,None]
    if wall>0:   # painted wall beyond the frame on the right edge
        wt=int(wall*W); wx=W-wt
        fr[:,wx-t:wx,:3]=prof[::-1][None,:,None]; fr[:,wx-t:wx,3]=1; fr[:,W-t:,3]=0
        gy=np.linspace(1.0,0.86,H)[:,None]; gx=np.linspace(0.82,1.0,wt)[None,:]
        wc=np.array([214,206,194],np.float32)*(gy*gx)[...,None]+gaussian_filter(r.normal(0,1,(H,wt)),1.2)[...,None]*2.5
        fr[:,wx:,:3]=wc; fr[:,wx:,3]=1
        fr[:,wx:wx+10,:3]*=np.linspace(0.7,1,10)[None,:,None]
        W2=wx
    else: W2=W
    sh=np.zeros((H,W),np.float32); sh[:,W2-t-18:W2-t]=np.linspace(0,0.22,18)[None,:]; sh[t:t+12,:W2-t]=np.maximum(sh[t:t+12,:W2-t],np.linspace(0.15,0,12)[:,None])
    return alb,tint,spec,fr,sh

class Hand6:
    """Large photographic hand, arm enters from the nearest bottom/right edge with as little sleeve as
    possible (angle chosen per frame), feathered + de-haloed edges, graded to the board, light wrap,
    distance-dependent contact shadow, fast cv2 warps straight into the frame."""
    TIP=(276.0,790.0); BAND_C=(2380.,2140.); AXIS=(0.809,0.588); BAND_R=520.
    def __init__(s,path,scale,W,H,board_rgb=(180,176,172),cfg=None):
        cfg=cfg or {}
        for k_,a_ in (('tip','TIP'),('band_c','BAND_C'),('axis','AXIS'),('band_r','BAND_R')):
            if k_ in cfg: setattr(s,a_,tuple(cfg[k_]) if k_!='band_r' else float(cfg[k_]))
        s.cfg=cfg
        im=np.asarray(Image.open(path).convert('RGBA')).astype(np.float32)
        sc=scale; s.W,s.H=W,H
        im=cv2.resize(im,(int(im.shape[1]*sc),int(im.shape[0]*sc)),interpolation=cv2.INTER_AREA)
        a=im[...,3]/255
        # de-halo: replace edge colours with colours pulled from the solid interior
        solid=(a>0.97).astype(np.float32)
        num=cv2.GaussianBlur(im[...,:3]*solid[...,None],(0,0),4); den=cv2.GaussianBlur(solid,(0,0),4)[...,None]
        fillc=num/np.maximum(den,1e-4); edge=(a<0.97)[...,None]
        rgb=np.where(edge,fillc,im[...,:3])
        # feather: erode 1.5px then soften
        a=cv2.GaussianBlur(cv2.erode(a,np.ones((3,3),np.uint8)),(0,0),1.1)
        # grade to the board photo: lower exposure, less contrast/saturation, slight cool, soften
        lum=rgb.mean(-1,keepdims=True)
        rgb=lum+(rgb-lum)*0.82; rgb=(rgb-128)*0.86+128; rgb=rgb*np.array([0.80,0.79,0.80])*cfg.get('grade',1.0)
        rgb=cv2.GaussianBlur(rgb,(0,0),0.6)
        # light wrap: board colour bleeding into the edge band
        wrap=np.clip(cv2.GaussianBlur(1-a,(0,0),3)*a*1.6,0,1)[...,None]*0.45
        rgb=rgb*(1-wrap)+np.array(board_rgb,np.float32)*wrap
        tip=np.array(s.TIP)*sc; c=np.array(s.BAND_C)*sc; ax=np.array(s.AXIS); R=s.BAND_R*sc
        H0,W0=a.shape; pad=int(1400*W/1080)
        big=np.zeros((H0+pad,W0+pad,4),np.float32); BH,BW=big.shape[:2]
        Y,X=np.mgrid[0:BH,0:BW].astype(np.float32)
        al=(X-c[0])*ax[0]+(Y-c[1])*ax[1]; nr=np.array([-ax[1],ax[0]]); ac=(X-c[0])*nr[0]+(Y-c[1])*nr[1]
        Rr=R*0.92+0.05*np.clip(al,0,None); dist=np.where(al<0,np.hypot(al,ac),np.abs(ac))
        m=np.clip((Rr-dist)/2.5,0,1)*(al>-R*0.4)
        u=np.clip(ac/Rr,-1,1); rng=np.random.default_rng(3)
        knit=gaussian_filter(rng.normal(0,1,(BH,BW)),(0.8,0.8))*5+gaussian_filter(rng.normal(0,1,(BH,BW)),10)*10
        shade=0.55+0.45*np.sqrt(np.clip(1-u**2,0,1))+0.18*np.clip(-u,0,1)+0.06*np.sin(al/30+ac/50)
        big[...,:3]=np.clip(np.array(cfg.get('tube_rgb',(46,45,48)),np.float32)*shade[...,None]+knit[...,None],0,255); big[...,3]=m
        if cfg.get('cut_al') is not None:     # drop the photographed arm beyond this point (the tube takes over)
            yy,xx=np.mgrid[0:H0,0:W0].astype(np.float32); alp=(xx-c[0])*ax[0]+(yy-c[1])*ax[1]
            a=a*np.clip((cfg['cut_al']*R-alp)/(0.10*R),0,1)
        big[:H0,:W0,:3]=rgb*a[...,None]+big[:H0,:W0,:3]*(1-a[...,None]); big[:H0,:W0,3]=np.maximum(m[:H0,:W0],a)
        s.base=big; s.tip=tip; s.Lb=float(np.linalg.norm(c-tip)); s.R=R
        d=c-tip; s.arm_ang=math.degrees(math.atan2(d[1],d[0]))
        mk=Image.new('L',(BW,BH),0); P=lambda x,y:(x*sc,y*sc)
        ImageDraw.Draw(mk).polygon([P(*q) for q in cfg.get('marker_poly',[(262,700),(1960,520),(1990,700),(262,830)])],fill=255)
        hsv=cv2.cvtColor(np.clip(big[...,:3],0,255).astype(np.uint8),cv2.COLOR_RGB2HSV).astype(np.float32)
        mm=np.asarray(mk)>0
        s.m_body=gaussian_filter((mm&(hsv[...,1]<70)&(hsv[...,2]>95)&(big[...,3]>0.4)).astype(np.float32),0.8)
        s.m_nib=gaussian_filter((mm&(hsv[...,2]<75)&(X<P(cfg.get('nib_xmax',380),0)[0])&(big[...,3]>0.4)).astype(np.float32),0.8)
        s.val=hsv[...,2:]/255.; s.cache={}
        s.poses={'neutral':(0,0,1.0),'up':(-0.04,0.0,0.975),'down':(0.04,0.0,1.025),'left':(0.0,0.035,0.985),'right':(0.0,-0.035,1.015)}
    def choose_angle(s,p,pref=42.0):
        """arm direction (deg, image coords) from nib toward an edge, minimising visible sleeve"""
        best=None
        for th in np.arange(-20,121,3.0):
            v=np.array([math.cos(math.radians(th)),math.sin(math.radians(th))])
            ts=[]
            if v[0]>1e-3: ts.append((s.W-p[0])/v[0])
            if v[1]>1e-3: ts.append((s.H-p[1])/v[1])
            if v[0]<-1e-3: ts.append(-p[0]/v[0])
            if not ts: continue
            exit_d=min(ts)+s.R*0.6
            sleeve=max(0.0,exit_d-s.Lb)
            cost=sleeve*2.5+abs(th-pref)*3.0
            if best is None or cost<best[0]: best=(cost,th,sleeve)
        return best[1],best[2]
    def sprite(s,color,pose):
        key=(tuple(color),pose)
        if key not in s.cache:
            a=s.base.copy(); tgt=np.array(color,np.float32); dark=sum(color)<200
            body=np.clip(tgt*(0.45+0.70*s.val)+(55 if dark else 20)*s.val,0,255)
            nibc=np.clip(tgt*(0.5+0.7*s.val),0,255)
            b=s.m_body[...,None]*0.85; n=s.m_nib[...,None]
            a[...,:3]=a[...,:3]*(1-b)+body*b; a[...,:3]=a[...,:3]*(1-n)+nibc*n
            shy,shx,sy=s.poses[pose]; t=s.tip
            M=np.array([[1,shx,-shx*t[1]],[shy,sy,t[1]-sy*t[1]-shy*t[0]],[0,0,1]],np.float32)
            a=cv2.warpPerspective(a,M,(a.shape[1],a.shape[0]),flags=cv2.INTER_LINEAR)
            prem=np.dstack([a[...,:3]*a[...,3:],a[...,3:]]).astype(np.float32)
            s.cache[key]=prem
        return s.cache[key]
    def composite(s,img,p,color,ang,lift,pose,pose2=None,mix=1.0,blur=None):
        """img float32 HxWx3 (modified in place). ang: degrees CCW (PIL convention). nib -> p exactly."""
        W,H=s.W,s.H
        src=s.sprite(color,pose)
        if pose2 and pose2!=pose and mix<0.98: src=src*mix+s.sprite(color,pose2)*(1-mix)
        def warp(pp):
            c,sn=math.cos(math.radians(ang)),math.sin(math.radians(ang)); t=s.tip
            M=np.array([[c,sn,pp[0]-(c*t[0]+sn*t[1])],[-sn,c,pp[1]-(-sn*t[0]+c*t[1])]],np.float32)
            return cv2.warpAffine(src,M,(W,H),flags=cv2.INTER_LINEAR,borderValue=0)
        if blur is not None and np.linalg.norm(blur)>3:
            bl=blur*0.5*min(1,20/max(np.linalg.norm(blur)*0.5,1e-6))
            w=(warp(p-bl*0.5)+warp(p)+warp(p+bl*0.5))/3
        else: w=warp(p)
        if getattr(s,'arm',None) is not None:     # IK forearm/upper arm behind the hand
            c_,sn_=math.cos(math.radians(ang)),math.sin(math.radians(ang)); t=s.tip
            M=np.array([[c_,sn_,p[0]-(c_*t[0]+sn_*t[1])],[-sn_,c_,p[1]-(-sn_*t[0]+c_*t[1])]],np.float32)
            rgbA,aA=s.arm.layer(M,s)
            w=w+np.dstack([rgbA*(1-w[...,3:]),aA[...,None]*(1-w[...,3:])])
        A=w[...,3]
        # contact shadow: tight near the nib, broad elsewhere; offset down-left; cool grey
        q=4; As=cv2.resize(A,(W//q,H//q),interpolation=cv2.INTER_AREA)
        yy,xx=np.mgrid[0:H//q,0:W//q]; near=np.exp(-np.hypot(xx*q-p[0],yy*q-p[1])/(220+300*lift))
        tight=cv2.GaussianBlur(np.roll(np.roll(As,int((6+20*lift)/q),0),-int((5+16*lift)/q),1),(0,0),1.2+3*lift)
        broad=cv2.GaussianBlur(np.roll(np.roll(As,int((30+40*lift)/q),0),-int((24+30*lift)/q),1),(0,0),9)
        shad=np.clip(tight*near*0.38+broad*0.22*(1-0.3*lift),0,0.6)
        shad=cv2.resize(shad,(W,H),interpolation=cv2.INTER_LINEAR)*(1-A)
        img*=(1-shad[...,None]*np.array([1.0,0.98,0.93],np.float32))
        img[:]=img*(1-A[...,None])+w[...,:3]
        return img

# ======================= v8: locked-off full-board framing =======================
def board8(W,H,seed=5,tray_x=None,eraser_x=None,albedo=(247,246,243),rim=0.022,tray_h=0.075,floor=0.035,glare=46,glare_y=0.30,glare_slope=0.10,glare_w=0.010):
    """Whole board in a static portrait shot, camera near straight-on, angled slightly down:
    aluminium rim top + sides, marker tray along the bottom (top face visible), a strip of wall below,
    one bright linear ceiling-light glare slanting slightly down left->right across the upper half.
    Returns albedo, lighting, specular, frame RGBA, frame shadow, and tray geometry."""
    r=np.random.default_rng(seed); y,x=np.mgrid[0:H,0:W].astype(np.float32)
    alb=np.empty((H,W,3),np.float32); alb[:]=albedo
    mott=zoom(r.normal(0,1,(H//60+2,W//60+2)),60,order=3)[:H,:W]
    alb+=mott[...,None]*1.2; alb-=(gaussian_filter(r.normal(0,1,(H,W)),0.7)*1.0)[...,None]
    g=Image.new('L',(W,H),0); d=ImageDraw.Draw(g)                      # faint eraser ghosting
    for _ in range(14):
        x0,y0=r.uniform(0,W),r.uniform(0,H); d.ellipse([x0,y0,x0+r.uniform(150,380),y0+r.uniform(40,110)],fill=int(r.uniform(10,28)))
    alb-=(np.asarray(g.filter(ImageFilter.GaussianBlur(14)),np.float32)/255)[...,None]*np.array([10,10,8])
    L=1.0-0.05*(x/W)-0.07*(y/H)**1.5
    L*=1-0.05*np.clip(((x/W-0.5)/0.6)**2+((y/H-0.45)/0.7)**2,0,1)
    tint=np.repeat(L[...,None],3,-1).astype(np.float32)
    yc=glare_y*H+glare_slope*(x-W/2); dd=(y-yc)/(glare_w*H)
    fade=np.clip(1-((x/W-0.45)/0.75)**2,0,1)
    spec=(np.exp(-dd**2)*glare+np.exp(-(dd/6)**2)*glare*0.22)*fade
    spec=spec.astype(np.float32)
    fr=np.zeros((H,W,4),np.float32); t=int(rim*min(W,H))
    prof=np.concatenate([np.linspace(150,205,t//3),np.linspace(205,180,t//3),np.linspace(180,120,t-2*(t//3))])
    fr[:t,:,:3]=prof[:,None,None]; fr[:t,:,3]=1                                  # top rim
    fr[:,:t,:3]=prof[None,:,None]; fr[:,:t,3]=1; fr[:,W-t:,:3]=prof[::-1][None,:,None]; fr[:,W-t:,3]=1
    th=int(tray_h*H); fl=int(floor*H); ty1=H-fl; ty0=ty1-th; top=int(th*0.42)        # tray: top face then front lip
    fr[ty0:ty0+top,:,:3]=np.linspace(168,196,top)[:,None,None]; fr[ty0:ty0+top,:,3]=1
    lip=np.concatenate([np.linspace(214,190,(th-top)//2),np.linspace(190,140,th-top-(th-top)//2)])
    fr[ty0+top:ty1,:,:3]=lip[:,None,None]; fr[ty0+top:ty1,:,3]=1
    fr[ty1:,:,:3]=np.array([196,190,182])*np.linspace(0.78,0.92,fl)[:,None,None]; fr[ty1:,:,3]=1   # wall below
    fr[...,:3]+=(gaussian_filter(r.normal(0,1,(H,W)),(0.5,6))*2.5)[...,None]
    sh=np.zeros((H,W),np.float32); sh[t:t+14,:]=np.linspace(0.16,0,14)[:,None]
    sh[:,t:t+12]=np.maximum(sh[:,t:t+12],np.linspace(0.12,0,12)[None,:]); sh[:,W-t-12:W-t]=np.maximum(sh[:,W-t-12:W-t],np.linspace(0,0.12,12)[None,:])
    sh[ty0-16:ty0,:]=np.maximum(sh[ty0-16:ty0,:],np.linspace(0,0.18,16)[:,None])
    return alb,tint,spec,fr,sh,dict(y0=ty0,top=top,y1=ty1)

def tray_overlay(W,tray,inks,present,eraser=True,S=None,xs=None,eraser_x=0.78):
    S=S or W
    """RGBA strip (rows tray.y0-60 .. tray.y1) with markers lying on the tray (colour -> present?) + an eraser."""
    y0=tray['y0']-70; Hs=tray['y0']+tray['top']-y0+6; o=np.zeros((Hs,W,4),np.float32)
    rest=Hs-8                                     # resting line (on the tray top face)
    def cyl(x0,x1,dia,rgb,yb):
        yy=np.arange(int(yb-dia),int(yb)); u=(yy-(yb-dia/2))/(dia/2)
        sh=np.clip(0.62+0.5*np.sqrt(np.clip(1-u**2,0,1))-0.18*u,0,1.15)
        for k,yv in enumerate(yy):
            if 0<=yv<Hs:
                o[yv,int(x0):int(x1),:3]=np.array(rgb)*sh[k]; o[yv,int(x0):int(x1),3]=np.clip(1.2-abs(u[k])**8,0,1)
    xs=xs or [0.10,0.33,0.56]
    for (name,c),xf in zip(inks,xs):
        if not present.get(name,True): continue
        x0=xf*W; ln=0.17*S; dia=0.032*S
        cyl(x0+ln*0.12,x0+ln*0.88,dia,(232,232,228),rest)               # white barrel
        cyl(x0,x0+ln*0.26,dia*1.05,c,rest)                               # cap
        cyl(x0+ln*0.86,x0+ln,dia*0.92,c,rest)                            # end plug
    if eraser:
        x0=eraser_x*W; w=0.15*S; h=0.050*S
        o[int(rest-h):int(rest-h*0.35),int(x0):int(x0+w),:3]=np.linspace(150,112,int(rest-h*0.35)-int(rest-h))[:,None,None]
        o[int(rest-h*0.35):int(rest),int(x0):int(x0+w),:3]=(70,68,66); o[int(rest-h):int(rest),int(x0):int(x0+w),3]=1
    a=cv2.GaussianBlur(o[...,3],(0,0),0.8); o[...,:3]=cv2.GaussianBlur(o[...,:3],(0,0),0.6); o[...,3]=a
    s=np.zeros_like(a); s[6:,:]=a[:-6,:]; s=cv2.GaussianBlur(s,(0,0),4)*0.35*(1-a)
    return o,s,y0

def restyle_sleeve(hand,sleeve_rgb=(122,122,126),cuff=True,watch=True):
    """Grey sweatshirt sleeve with a ribbed cuff + black square smartwatch on the band (in place)."""
    big=hand.base; BH,BW=big.shape[:2]; sc=hand.tip[0]/hand.TIP[0]
    c=np.array(hand.BAND_C)*sc; ax=np.array(hand.AXIS); nr=np.array([-ax[1],ax[0]]); R=hand.R
    Y,X=np.mgrid[0:BH,0:BW].astype(np.float32)
    al=(X-c[0])*ax[0]+(Y-c[1])*ax[1]; ac=(X-c[0])*nr[0]+(Y-c[1])*nr[1]
    rgb=big[...,:3]; a=big[...,3]
    sl=(al>R*0.18)&(a>0)
    u=np.clip(ac/(R*0.95+0.05*np.clip(al,0,None)),-1,1); rng=np.random.default_rng(8)
    shade=0.60+0.42*np.sqrt(np.clip(1-u**2,0,1))+0.12*np.clip(-u,0,1)+0.04*np.sin(al/38+ac/60)
    knit=gaussian_filter(rng.normal(0,1,(BH,BW)),(0.7,0.7))*4
    col=np.array(sleeve_rgb,np.float32)*shade[...,None]+knit[...,None]
    if cuff:
        cz=(al>R*0.18)&(al<R*0.62)
        rib=0.90+0.10*np.sin(ac/(R*0.035))
        col=np.where(cz[...,None],col*rib[...,None]*0.95,col)
        col=np.where(((al>R*0.58)&(al<R*0.66))[...,None],col*0.85,col)     # seam where the cuff joins the sleeve
    m=np.clip((al-R*0.18)/3,0,1)[...,None]*sl[...,None]
    rgb[:]=rgb*(1-m)+col*m
    if watch:   # square face on the band, facing camera (upper side of the wrist)
        wc=c+ax*(-R*0.02)+nr*(-R*0.15); hs=R*0.36
        lx=(X-wc[0])*ax[0]+(Y-wc[1])*ax[1]; ly=(X-wc[0])*nr[0]+(Y-wc[1])*nr[1]
        q=np.maximum(np.abs(lx)-hs*0.75,0)**2+np.maximum(np.abs(ly)-hs*0.75,0)**2
        face=np.clip((hs*0.25-np.sqrt(q))/2.0,0,1)*(a>0.3)
        sheen=12+30*np.exp(-((lx+ly*0.4)/(hs*0.5))**2)
        fc=np.dstack([np.full((BH,BW),18.)+sheen,np.full((BH,BW),18.)+sheen,np.full((BH,BW),20.)+sheen])
        rim=np.clip((hs*0.25-np.sqrt(q))/2.0,0,1)-np.clip((hs*0.17-np.sqrt(q))/2.0,0,1)
        fc=fc+rim[...,None]*35
        rgb[:]=rgb*(1-face[...,None])+fc*face[...,None]
    hand.cache={}

# ---------------- Relief SingleLine (OFL) centreline font ----------------
_RELIEF=None
def relief_strokes(text,cap_px,xscale=None,path=None):
    """same output as hershey_strokes, from the Relief SingleLine SVG font (neat single-line block capitals)"""
    global _RELIEF
    import re,os
    from svgpathtools import parse_path
    if _RELIEF is None:
        p=path or os.path.join(os.path.dirname(__file__),'..','assets','fonts','ReliefSingleLineSVG-Regular.svg')
        src=open(p).read(); _RELIEF={}
        dflt=float(re.search(r'<font[^>]*horiz-adv-x="([\d.]+)"',src).group(1))
        for m in re.finditer(r'<glyph\b([^>]*)/>',src,re.S):
            at=m.group(1); um=re.search(r'unicode="([^"]+)"',at)
            if not um: continue
            am=re.search(r'horiz-adv-x="([\d.]+)"',at); dm=re.search(r'\sd="([^"]*)"',at)
            import html; u=html.unescape(um.group(1)); adv=float(am.group(1)) if am else dflt; d=dm.group(1) if dm else None
            if len(u)!=1: continue
            subs=[]
            if d:
                for sp in parse_path(d).continuous_subpaths():
                    n=max(4,int(sp.length()/12)); pts=np.array([[sp.point(t).real,sp.point(t).imag] for t in np.linspace(0,1,n)])
                    subs.append(pts)
            _RELIEF[u]=(adv,subs)
    xscale=XSCALE if xscale is None else xscale; k=cap_px/680.0
    out=[]; xoff=0.0; wi=0
    for ci,ch in enumerate(text):
        if ch==' ': wi+=1
        adv,subs=_RELIEF.get(ch,_RELIEF.get(ch.upper(),(400,[])))
        for s in subs:
            q=np.c_[s[:,0]*k*xscale+xoff,-s[:,1]*k+cap_px*2/3]   # same vertical frame as hershey_strokes
            out.append((ci,wi,q))
        xoff+=adv*k*xscale
    return out,xoff


# ======================= v10: 2-bone IK arm (forearm bends/foreshortens instead of sliding) =======================
class ArmIK:
    """Cuts the baked straight sleeve off the hand sprite just past the cuff and draws, every frame, a
    forearm + upper arm from the cuff to a fixed off-screen shoulder, with the elbow from 2-bone IK.
    The forearm leaves the cuff along the sprite's wrist axis (continuous), curves to the elbow, and
    widens when the arm is bent toward the camera (foreshortening)."""
    def __init__(s,hand,W,H,shoulder=(1.15,1.15),l1=0.85,l2=0.85,rgb=(122,122,126),cut=0.74):
        s.W,s.H=W,H; s.S=np.array(shoulder)*[W,H]; s.rgb=np.array(rgb,np.float32)
        sc=hand.tip[0]/hand.TIP[0]; c=np.array(hand.BAND_C)*sc; ax=np.array(hand.AXIS); R=hand.R
        big=hand.base; BH,BW=big.shape[:2]; Y,X=np.mgrid[0:BH,0:BW].astype(np.float32)
        al=(X-c[0])*ax[0]+(Y-c[1])*ax[1]
        big[...,3]*=np.clip((R*(cut+0.06)-al)/(R*0.06),0,1)      # fade the baked sleeve out after the cuff
        hand.cache={}
        s.cuff=c+ax*R*(cut-0.10); s.ax=ax; s.r0=R*0.97
        s.L1=l1*min(W,H)*1.0; s.L2=l2*min(W,H)*1.0
        rng=np.random.default_rng(11)
        s.knit=(1+gaussian_filter(rng.normal(0,1,(H,W)),0.8)*0.05).astype(np.float32)
    def solve(s,wr):
        d=s.S-wr; D=float(np.linalg.norm(d)); L1,L2=s.L1,s.L2
        u=d/max(D,1e-6)
        if D>=L1+L2-1: return wr+u*L2,D
        a=(L2**2-L1**2+D**2)/(2*D); h=math.sqrt(max(L2**2-a**2,0)); n=np.array([-u[1],u[0]])
        e1=wr+u*a+n*h; e2=wr+u*a-n*h
        return (e1 if e1[0]>e2[0] else e2),D                    # elbow out to the right (away from the board)
    def layer(s,M,hand):
        W,H=s.W,s.H
        wr=M[:,:2]@s.cuff+M[:,2]; ax=M[:,:2]@s.ax; ax/=np.linalg.norm(ax)
        el,D=s.solve(wr)
        bend=1-min(1.0,D/(s.L1+s.L2))
        fs=1+0.9*bend                                        # elbow nearer the camera when bent
        r0=s.r0; re=r0*(1.15+0.35*bend)*1.0; rs=r0*1.45*fs**0.3
        # forearm: cubic from the cuff (tangent = wrist axis) to the elbow; upper arm: straight-ish to the shoulder
        k=np.linalg.norm(el-wr)*0.45
        P0,P1,P2,P3=wr,wr+ax*k,el-(el-s.S)/max(np.linalg.norm(el-s.S),1e-6)*k*0.3,el
        tt=np.linspace(0,1,28)[:,None]
        fa=(1-tt)**3*P0+3*(1-tt)**2*tt*P1+3*(1-tt)*tt**2*P2+tt**3*P3
        ua=el+(s.S-el)*np.linspace(0,1,14)[:,None]
        pts=np.vstack([fa,ua[1:]]); rad=np.r_[r0+(re-r0)*tt[:,0]**1.4, re+(rs-re)*np.linspace(0,1,14)[1:]]
        A=np.zeros((H,W),np.float32); Cm=np.zeros((H,W),np.float32)
        for f_,v in ((1.0,0.62),(0.86,0.80),(0.62,0.96),(0.34,1.06)):    # cylinder shading: dark rim -> lit centre
            for (x0,y0),(x1,y1),rr in zip(pts[:-1],pts[1:],rad[:-1]):
                th=max(1,int(2*rr*f_))
                cv2.line(Cm,(int(x0),int(y0)),(int(x1),int(y1)),float(v),th,cv2.LINE_AA)
                if f_==1.0: cv2.line(A,(int(x0),int(y0)),(int(x1),int(y1)),1.0,th,cv2.LINE_AA)
        Cm=cv2.GaussianBlur(Cm,(0,0),5); A=cv2.GaussianBlur(A,(0,0),1.2)
        rgb=(s.rgb[None,None,:]*(Cm*s.knit)[...,None])*A[...,None]
        return rgb.astype(np.float32),A


# ---------------- hand assets (spec: hand: "<name>") ----------------
HANDS={
 'default':dict(path='assets/hand_photo_cut.png',scale=None,restyle=True),
 'deep':dict(path='assets/hand_deep_cut.png',scale=0.415,tip=(107,302),band_c=(2560,1720),axis=(0.807,0.590),band_r=430,
             cut_al=0.7,tube_rgb=(40,40,44),grade=1.12,restyle=False,
             marker_poly=[(95,235),(1240,690),(1215,830),(85,375)],nib_xmax=200),
 'light_medium':dict(path='assets/hand_light_medium_cut.png',scale=1.26,tip=(107,83),band_c=(640,1380),axis=(0.45,0.893),band_r=210,
             cut_al=0.15,tube_rgb=(160,116,46),grade=1.0,restyle=False,
             marker_poly=[(92,40),(665,268),(630,385),(82,135)],nib_xmax=190),
}
