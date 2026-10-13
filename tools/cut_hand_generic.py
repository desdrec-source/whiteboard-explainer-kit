"""Cut a hand+marker(+sleeve) from a licensed photo: rembg (isnet-general-use) on a crop, keep the largest
component, add back the dark nib by luminance, remove board ink touching the nib, soft edge.
usage: python3 cut_hand_generic.py <name>  (parameters in HANDSRC below)"""
import sys,json,numpy as np,cv2
from PIL import Image,ImageDraw
from rembg import remove,new_session
HANDSRC={
 'deep':dict(src='assets/src/p6209796.jpg',crop=(2300,1150,6000,4000),nib=(2409,1452),
            nibbox=(2380,1400,2470,1500),ink_cut=[(2300,1150),(2405,1150),(2405,1700),(2300,1700)]),
 'light_medium':dict(src='assets/src/p8518882.jpg',crop=(1450,950,2160,3840),nib=(1558,1033),
            nibbox=(1545,1015,1600,1060),ink_cut=[(1450,950),(1553,950),(1553,1100),(1450,1100)]),
}
n=sys.argv[1]; P=HANDSRC[n]
im=Image.open(P['src']).convert('RGB'); X0,Y0,X1,Y1=P['crop']; c=im.crop(P['crop'])
s=min(1.0,1600/max(c.size)); sm=c.resize((int(c.width*s),int(c.height*s)),Image.LANCZOS)
a=np.asarray(remove(sm,session=new_session('isnet-general-use'),only_mask=True).resize(c.size,Image.LANCZOS)).astype(np.float32)
lum=np.asarray(c.convert('L')).astype(np.float32)
bx0,by0,bx1,by1=[v-o for v,o in zip(P['nibbox'],(X0,Y0,X0,Y0))]
nb=np.zeros(a.shape,bool); nb[by0:by1,bx0:bx1]=True
a=np.maximum(a,((lum<100)&nb)*255.0)
k=Image.new('L',c.size,255); ImageDraw.Draw(k).polygon([(x-X0,y-Y0) for x,y in P['ink_cut']],fill=0)
a=a*np.asarray(k,np.float32)/255
b=(a>128).astype(np.uint8); _,l,st,_=cv2.connectedComponentsWithStats(b); kk=1+np.argmax(st[1:,4])
a=a*(cv2.GaussianBlur((l==kk).astype(np.float32),(0,0),1.5)>0.5); a=np.clip((a-30)/170,0,1)*255; a=cv2.GaussianBlur(a,(0,0),1.0)   # stretch rembg's soft interior to solid
out=f'assets/hand_{n}_cut.png'
Image.fromarray(np.dstack([np.asarray(c),a.clip(0,255).astype(np.uint8)]),'RGBA').save(out)
tip=(P['nib'][0]-X0,P['nib'][1]-Y0); print(out,c.size,'tip',tip)
# zoomed nib check
z=Image.open(out); bg=Image.new('RGBA',z.size,(255,0,255,255)); bg.alpha_composite(z)
zz=bg.crop((tip[0]-60,tip[1]-60,tip[0]+60,tip[1]+60)).resize((480,480),Image.NEAREST); d=ImageDraw.Draw(zz)
d.ellipse([240-6,240-6,240+6,240+6],outline=(0,255,0),width=2); zz.convert('RGB').save(f'/tmp/nibcheck_{n}.png')
bg.convert('RGB').resize((z.width//4,z.height//4)).save(f'/tmp/cutview_{n}.png')
