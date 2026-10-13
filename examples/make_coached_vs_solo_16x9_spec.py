"""Landscape (1920x1080) COACHED vs GOING SOLO board, photo8 style; positions in px from the renderer's text metrics."""
import json,sys; import os; sys.path.insert(0,os.path.join(os.path.dirname(os.path.abspath(__file__)),'..')); from wb import real as RL
W,H=1920,1080; U=W/1080; RL.XSCALE=0.85; RL.DEFAULT_FONT='relief'
DUR=float(sys.argv[1]) if len(sys.argv)>1 else 40; OUTJ=sys.argv[2] if len(sys.argv)>2 else 'coached_vs_solo_16x9.json'
def cap(size): return size*0.58*U
def tw(t,size): return RL.hershey_strokes(t,cap(size))[1]
def captop(y,size): return y*H+0.30*size*U+cap(size)*2/3
def yfor(top,size): return (top*H-0.30*size*U-cap(size)*2/3)/H
HS,IS,MS,TS=84,52,50,54
els=[]; E=lambda area,**k: els.append(dict(k,area=area))
def box(x,y,w,h): return [x/W,y/H,w/W,h/H]
E('top',type='text',text='COACHED',size=HS,x=0.26,y=yfor(0.06,HS),anchor='c')
E('top',type='text',text='GOING SOLO',size=HS,x=0.74,y=yfor(0.06,HS),anchor='c')
E('top',type='icon',name='vline',box=[0.49,0.04,0.02,0.60])
E('left',type='icon',name='climb',box=[0.15,0.165,0.23,0.245],color='green')
E('right',type='icon',name='maze',box=[0.655,0.185,0.12,0.205])
E('right',type='icon',name='stick',box=[0.703,0.275,0.025,0.075])
E('right',type='text',text='?',size=80,x=0.80,y=yfor(0.17,80),color='red')
rows=[yfor(v,IS) for v in (0.445,0.512,0.579)]; c=cap(IS); mk=c*1.1
LX=0.06*W; RX=0.535*W
def mark(area,name,x,y,size=1.0,color='green'):
    top=captop(y,IS)+c*0.05; s=mk*size
    E(area,type='icon',name=name,box=box(x,top,s,s*(0.9 if name=='tick' else 1.0)),color=color)
for (t,m),y in zip([('FASTER RESULTS','tick'),('ACCOUNTABILITY','tick'),('UPFRONT COST','cross')],rows):
    if m=='tick': mark('left','tick',LX,y)
    else: mark('left','cross',LX+mk*0.14,y+0.004,0.72,'red')
    E('left',type='text',text=t,size=IS,x=(LX+mk+0.012*W)/W,y=y)
for t,y in zip(['TRIAL AND ERROR','EASY TO STALL'],rows): E('right',type='text',text=t,size=IS,x=RX/W,y=y)
for t,y in zip(['TRIAL AND ERROR','EASY TO STALL'],rows): mark('right','cross',RX+tw(t,IS)+0.018*W,y+0.004,0.72,'red')
E('right',type='text',text='NO FEES',size=IS,x=RX/W,y=rows[2])
mark('right','tick',RX+tw('NO FEES',IS)+0.016*W,rows[2])
# maths row (full width)
m1='9 MONTHS \u00d7 $500 = $4,500 LOST'; m2='COACH = $1,000'; gap=0.05*W; mc=cap(MS)
tot=tw(m1,MS)+gap+tw(m2,MS)+mc*1.3; mx=0.5*W-tot/2; my=yfor(0.665,MS); mt=captop(my,MS)
E('bottom',type='text',text=m1,size=MS,x=mx/W,y=my)
u0=mx+tw('9 MONTHS \u00d7 $500 = ',MS); u1=mx+tw(m1,MS)
E('bottom',type='path',polylines=[[(u0/W,(mt+mc*1.28)/H),((u0+u1)/2/W,(mt+mc*1.32)/H),(u1/W,(mt+mc*1.26)/H)]],box=[0,0,1,1],color='red')
x2=mx+tw(m1,MS)+gap
E('bottom',type='text',text=m2,size=MS,x=x2/W,y=my)
E('bottom',type='icon',name='tick',box=box(x2+tw(m2,MS)+0.012*W,mt+mc*0.05,mc*1.1,mc*1.0),color='green')
# takeaway
tk='THE RIGHT COACH PAYS FOR ITSELF'; ty=yfor(0.775,TS); x0=0.5*W-tw(tk,TS)/2
E('bottom',type='text',text=tk,size=TS,x=0.5,y=ty,anchor='c')
a=x0+tw('THE RIGHT ',TS); b=tw('COACH',TS); ct=captop(ty,TS); cc=cap(TS)
E('bottom',type='icon',name='ellipse',box=box(a-0.04*b-12,ct-0.32*cc,b*1.08+24,cc*1.62),color='green')
for e in els: e.setdefault('color','black')
spec=dict(aspect='16:9',duration=DUR,sound=True,font='hershey:relief',style='photo8',elements=els,
  out='out/coached_vs_solo_16x9.mp4',hand_scale=0.27,pen_width=12/U,text_pen_scale=True,heading_size=HS,
  letter_xscale=0.85,ink_unevenness=0.08,ink_opacity=1.15,ink={'black':[16,15,17],'green':[0,128,72],'red':[212,28,34]},
  board=dict(tray_h=0.10,floor=0.04,glare_y=0.27,glare_slope=0.06,glare_w=0.014,tray_x=[0.20,0.33,0.46],eraser_x=0.62),
  end_hold=3.0,hand_angle=0.0,pivot=[1.25,1.9],pivot_gain=0.30,sleeve_rgb=[122,122,126],
  voiceover=None,sfx_sources=['sfx/marker_lines.wav','sfx/bsb_0807_whiteboard_marker.wav'])
json.dump(spec,open(OUTJ,'w'),indent=1)
print(len(els),'elements; left max end',max(LX+mk+0.012*W+tw(t,IS) for t in ['FASTER RESULTS','ACCOUNTABILITY','UPFRONT COST'])/W,
 'right max end',max(RX+tw(t,IS)+0.018*W+mk*0.72 for t in ['TRIAL AND ERROR','EASY TO STALL'])/W,'maths',mx/W,(mx+tot)/W,'takeaway',x0/W,(x0+tw(tk,TS))/W)
