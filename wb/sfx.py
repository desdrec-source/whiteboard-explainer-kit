"""Marker SFX: CC0 marker recording -> cleaned scratch pool -> continuous scratches only while the pen
draws (speed-dependent level, random offset/pitch/gain), true silence elsewhere, optional VO ducking."""
import json, numpy as np, subprocess, soundfile as sf, pyloudnorm as pyln, os
from scipy.signal import butter, sosfilt, resample_poly
SR=48000; ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
rng=np.random.default_rng(7)
def hp(x,f): return sosfilt(butter(4,f,btype='high',fs=SR,output='sos'),x)
def lp(x,f): return sosfilt(butter(4,f,btype='low',fs=SR,output='sos'),x)
def load(p):
    x,sr=sf.read(p); x=x.mean(1) if x.ndim>1 else x
    if sr!=SR: x=resample_poly(x,SR,sr)
    return x
def pool_from(paths):
    import noisereduce as nr
    chunks=[]
    for p in paths:
        x=hp(load(p),150)
        env=np.sqrt(np.convolve(x**2,np.ones(2400)/2400,'same'))
        y=nr.reduce_noise(y=x,sr=SR,y_noise=x[env<np.percentile(env,15)],stationary=True,prop_decrease=0.9)
        e=np.sqrt(np.convolve(y**2,np.ones(960)/960,'same')); thr=max(np.percentile(e,20)*6,e.max()*0.04); m=e>thr
        i=0
        while i<len(m):
            if m[i]:
                j=i
                while j<len(m) and m[j]: j+=1
                for a0 in range(i,j,int(4*SR)):          # pieces of at most 4 s
                    b0=min(j,a0+int(4*SR))
                    if b0-a0>0.15*SR: c=y[a0:b0]; chunks.append(c/(np.sqrt((c**2).mean())+1e-9))
                i=j
            else: i+=1
    ov=int(0.06*SR); out=chunks[0]
    for c in chunks[1:]:
        if len(c)<2*ov: continue
        w=np.linspace(0,np.pi/2,ov); out[-ov:]=out[-ov:]*np.cos(w)+c[:ov]*np.sin(w); out=np.concatenate([out,c[ov:]])
    slow=np.sqrt(np.convolve(out**2,np.ones(4800)/4800,'same')); out=out/np.maximum(slow,np.percentile(slow,30))
    return lp(hp(out,300),11000)/np.abs(out).max(), len(chunks)

def scratch(pool,n,speed,text):
    pitch=rng.uniform(0.92,1.08); need=int(n*pitch)+10
    off=int(rng.integers(0,max(1,len(pool)-need-1))); seg=np.resize(pool[off:off+need],need)
    y=np.interp(np.arange(n)*pitch,np.arange(need),seg)
    f=np.clip(speed/900,0.3,1.3)
    g=(0.5+0.5*f)*10**(rng.uniform(-2.5,2.5)/20)*(0.85 if text else 1.0)
    t=np.arange(n)/SR; g=g*(0.85+0.15*np.sin(2*np.pi*rng.uniform(2.5,5)*t+rng.uniform(0,6)))  # pressure flutter
    # pen-down attack: short bright transient at the stroke start
    na=min(n,int(0.035*SR)); att=hp(seg[:na],2500)*np.exp(-np.arange(na)/(0.008*SR))*rng.uniform(0.5,0.8)
    y=y*g; y[:na]+=att*np.max(np.abs(g)) if np.ndim(g) else att*g
    fi=min(n//2,int(0.006*SR)); fo=min(n//2,int(0.045*SR))
    y[:fi]*=np.sin(np.linspace(0,np.pi/2,fi))**2; y[-fo:]*=np.cos(np.linspace(0,np.pi/2,fo))**2
    return y

def make(timing,silent,out,dur,voiceover=None,sources=None):
    tj=json.load(open(timing)); N=int(SR*dur)
    pool,nch=pool_from(sources or [ROOT+'/sfx/marker_lines.wav'])
    iv=[(s['t0'],s['t1'],s['L']/max(s['t1']-s['t0'],1e-3),s['text']) for s in tj['segs'] if s['kind'] in('draw','fill')]
    # merge strokes separated by lifts < 90 ms into one scratch with a soft dip
    groups=[]
    for it in iv:
        if groups and it[0]-groups[-1][-1][1]<0.04: groups[-1].append(it)
        else: groups.append([it])
    x=np.zeros(N)
    for gp in groups:
        a=int(gp[0][0]*SR); b=min(N,int(gp[-1][1]*SR)); n=b-a
        if n<int(0.03*SR): continue
        tt=gp[0][0]+np.arange(n)/SR; sp=np.full(n,300.); dip=np.full(n,0.35)
        for (t0,t1,v,_) in gp: m=(tt>=t0)&(tt<t1); sp[m]=v; dip[m]=1
        dip=np.convolve(dip,np.ones(960)/960,'same')
        x[a:b]+=scratch(pool,n,sp,any(g[3] for g in gp))*dip
    meter=pyln.Meter(SR); act=np.abs(x)>0
    y=pyln.normalize.loudness(x,meter.integrated_loudness(x),-18.0)
    pk=np.abs(resample_poly(y,4,1)).max(); lim=10**(-1.5/20)
    y=lim*np.tanh(y/lim)                      # soft ceiling
    y*=min(1,lim/np.abs(resample_poly(y,4,1)).max())
    if voiceover:   # duck the marker ~10 dB while the voice is present
        v=load(voiceover)[:N]; v=np.pad(v,(0,N-len(v)))
        env=np.sqrt(np.convolve(v**2,np.ones(4800)/4800,'same')); on=(env>env.max()*0.06).astype(float)
        on=np.convolve(on,np.ones(9600)/9600,'same'); y=y*(1-0.68*np.clip(on,0,1))+v*0.9
    y[np.abs(y)<1e-5]=0
    wav=out.replace('.mp4','_mix.wav'); sf.write(wav,y.astype(np.float32),SR,subtype='FLOAT')
    subprocess.run(['ffmpeg','-v','error','-y','-i',silent,'-i',wav,'-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-b:a','192k','-ac','1','-shortest','-movflags','+faststart',out],check=True)
    gaps=y[~(np.convolve(act.astype(float),np.ones(4800),'same')>0)]
    print(f'sfx: chunks {nch}, scratches {len(groups)}, loudness {meter.integrated_loudness(y):.1f} LUFS, peak {20*np.log10(np.abs(y).max()+1e-12):.1f} dBFS, gap rms {"silent" if not len(gaps) or not np.any(gaps) else round(20*np.log10(np.sqrt((gaps**2).mean())),1)}')
