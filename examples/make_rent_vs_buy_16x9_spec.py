"""Landscape (1920x1080) layout of the v9 rent-vs-buy board. Same element order/areas as make_v9_spec.py.
All positions computed in pixels from the renderer's own text metrics (Relief SingleLine)."""
import json,sys; import os; sys.path.insert(0,os.path.join(os.path.dirname(os.path.abspath(__file__)),'..')); from wb import real as RL
W,H=1920,1080; U=W/1080; RL.XSCALE=0.85; RL.DEFAULT_FONT='relief'
DUR=float(sys.argv[1]) if len(sys.argv)>1 else 35; OUTJ=sys.argv[2] if len(sys.argv)>2 else 'rent_vs_buy_16x9.json'
def cap(size): return size*0.58*U
def tw(t,size): return RL.hershey_strokes(t,cap(size))[1]                 # px
def captop(y,size): return y*H+0.30*size*U+cap(size)*2/3                  # px of cap top for a text placed at y
def yfor(top_frac,size): return (top_frac*H-0.30*size*U-cap(size)*2/3)/H   # y that puts the cap top at top_frac
HS,IS,TS=88,58,60
els=[]; E=lambda **k: els.append(k)
def box(x,y,w,h): return [x/W,y/H,w/W,h/H]
E(type='text',text='RENT',size=HS,x=0.26,y=yfor(0.07,HS),anchor='c')
E(type='text',text='BUY',size=HS,x=0.74,y=yfor(0.07,HS),anchor='c')
E(type='icon',name='vline',box=[0.49,0.05,0.02,0.66])
E(type='icon',name='building8',box=[0.155,0.20,0.125,0.235],color='green')
E(type='icon',name='key',box=[0.29,0.29,0.03,0.13],color='green')
hb=[0.615,0.205,0.17,0.23]
for n in ('house_outline','house_door','house_window'): E(type='icon',name=n,box=hb)
E(type='icon',name='house_chimney',box=hb,color='red')
E(type='icon',name='chain',box=[0.80,0.29,0.016,0.145],color='red')
rows=[yfor(v,IS) for v in (0.49,0.567,0.644)]; c=cap(IS); mk=c*1.1
LX=0.055*W; RX=0.535*W
def mark(name,x,y,size=1.0,color='green'):
    top=captop(y,IS)+c*0.05; s=mk*size
    E(type='icon',name=name,box=box(x,top,s,s*(0.9 if name=='tick' else 1.0)),color=color)
for y,t in zip(rows,['FLEXIBLE','LOW START COST','NO REPAIR BILLS']):
    mark('tick',LX,y)
    E(type='text',text=t,size=IS,x=(LX+mk+0.012*W)/W,y=y)
right=['BIG DEPOSIT','REPAIRS ON YOU']
for t,y in zip(right,rows): E(type='text',text=t,size=IS,x=RX/W,y=y)
for t,y in zip(right,rows): mark('cross',RX+tw(t,IS)+0.018*W,y+0.006,0.72,'red')
E(type='text',text='BUILDS EQUITY',size=IS,x=RX/W,y=rows[2])
mark('tick',RX+tw('BUILDS EQUITY',IS)+0.016*W,rows[2])
tk='RENT + INVEST THE DIFFERENCE'; ty=yfor(0.78,TS); x0=0.5*W-tw(tk,TS)/2
E(type='text',text=tk,size=TS,x=0.5,y=ty,anchor='c')
a=x0+tw('RENT + ',TS); b=tw('INVEST',TS); ct=captop(ty,TS); cc=cap(TS)
E(type='icon',name='ellipse',box=box(a-0.035*b-14,ct-0.35*cc,b*1.07+28,cc*1.7),color='green')
# curve from the bottom RENT tick down to the circle
tx,tyy=LX+mk*0.45,captop(rows[2],IS)+c*1.25; ex,ey=a+0.12*b,ct-0.30*cc; cx,cy=tx,ey
pts=[(((1-u)**2*tx+2*u*(1-u)*cx+u*u*ex)/W,((1-u)**2*tyy+2*u*(1-u)*cy+u*u*ey)/H) for u in [i/30 for i in range(31)]]
E(type='path',polylines=[pts],box=[0,0,1,1],color='green')
for i,e in enumerate(els):
    e.setdefault('color','black')
    e['area']='top' if i<3 else 'left' if i<5 else 'right' if i<10 else 'left' if i<16 else 'right' if i<22 else 'bottom'
spec=dict(aspect='16:9',duration=DUR,sound=True,font='hershey:relief',style='photo8',elements=els,
  out='out/rent_vs_buy_16x9.mp4',hand_scale=0.27,pen_width=12/U,text_pen_scale=True,heading_size=HS,
  letter_xscale=0.85,ink_unevenness=0.08,ink_opacity=1.15,ink={'black':[16,15,17],'green':[0,128,72],'red':[212,28,34]},
  board=dict(tray_h=0.10,floor=0.04,glare_y=0.27,glare_slope=0.06,glare_w=0.014,tray_x=[0.20,0.33,0.46],eraser_x=0.62),
  end_hold=3.0,hand_angle=0.0,pivot=[1.25,1.9],pivot_gain=0.30,sleeve_rgb=[122,122,126],
  voiceover=None,sfx_sources=['sfx/marker_lines.wav','sfx/bsb_0807_whiteboard_marker.wav'])
json.dump(spec,open(OUTJ,'w'),indent=1); print(len(els),'elements; widest item px',max(tw(t,IS) for t in ['NO REPAIR BILLS','REPAIRS ON YOU','LOW START COST']),'takeaway px',tw(tk,TS))
