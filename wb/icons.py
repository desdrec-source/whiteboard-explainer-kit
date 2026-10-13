"""Built-in line-art icons as polylines in a unit box (x right, y down). Add more freely.
Each icon: list of polylines; an optional 'circle' is ('c',cx,cy,r)."""
import math
def _circ(cx,cy,r,n=40,a0=-math.pi/2):
    return [(cx+r*math.cos(a0+2*math.pi*i/n),cy+r*math.sin(a0+2*math.pi*i/n)) for i in range(n+1)]
def _ell(cx,cy,rx,ry,n=30):
    return [(cx+rx*math.cos(-math.pi/2+2*math.pi*i/n),cy+ry*math.sin(-math.pi/2+2*math.pi*i/n)) for i in range(n+1)]
def _rect(x0,y0,x1,y1): return [(x0,y0),(x1,y0),(x1,y1),(x0,y1),(x0,y0)]

def building():
    L=[_rect(0.18,0.0,0.82,0.92)]
    for r in range(4)[:3]:
        for c in range(2):
            x=0.30+c*0.28; y=0.10+r*0.22; L.append(_rect(x,y,x+0.13,y+0.12))
    L.append([(0.44,0.92),(0.44,0.76),(0.58,0.76),(0.58,0.92)])
    L.append([(0.05,0.95),(0.95,0.95)])
    return L
def key():
    return [_circ(0.5,0.18,0.16),[(0.5,0.34),(0.5,0.95)],[(0.5,0.70),(0.66,0.70)],[(0.5,0.84),(0.62,0.84)]]
def house():
    return [[(0.02,0.45),(0.48,0.05),(0.95,0.45)],_rect(0.12,0.40,0.86,0.95),
            [(0.68,0.22),(0.68,0.02),(0.78,0.02),(0.78,0.31)],
            [(0.24,0.95),(0.24,0.68),(0.38,0.68),(0.38,0.95)],
            _rect(0.54,0.55,0.74,0.72),[(0.64,0.55),(0.64,0.72)],[(0.54,0.635),(0.74,0.635)]]
def chain(n=5):
    return [_ell(0.5,0.08+i*0.21,0.32,0.11) for i in range(n)]
def tick(): return [[(0.0,0.55),(0.32,0.95),(1.0,0.0)]]
def cross(): return [[(0.0,0.0),(1.0,1.0)],[(1.0,0.0),(0.0,1.0)]]
def sun(): return [_circ(0.5,0.5,0.22)]+[[(0.5+0.32*math.cos(a),0.5+0.32*math.sin(a)),(0.5+0.46*math.cos(a),0.5+0.46*math.sin(a))] for a in [i*math.pi/4 for i in range(8)]]
def drop(): return [[(0.5,0.02),(0.25,0.5),(0.22,0.65),(0.3,0.85),(0.5,0.95),(0.7,0.85),(0.78,0.65),(0.75,0.5),(0.5,0.02)]]
def leaf(): return [[(0.1,0.9),(0.2,0.4),(0.5,0.12),(0.92,0.05),(0.85,0.5),(0.55,0.82),(0.1,0.9)],[(0.1,0.9),(0.7,0.3)]]
def arrow(): return [[(0.0,0.5),(1.0,0.5)],[(0.78,0.28),(1.0,0.5),(0.78,0.72)]]
def underline(): return [[(0.0,0.5),(1.0,0.45)]]
def vline(): return [[(0.5,0.0),(0.5,1.0)]]
def building8():
    L=[_rect(0.18,0.0,0.82,0.92)]
    for r in range(4):
        for c in range(2):
            x=0.30+c*0.28; y=0.07+r*0.17; L.append(_rect(x,y,x+0.13,y+0.10))
    L.append([(0.43,0.92),(0.43,0.77),(0.57,0.77),(0.57,0.92)])
    L.append([(0.05,0.95),(0.95,0.95)])
    return L
def house_outline(): return [[(0.02,0.45),(0.48,0.05),(0.95,0.45)],_rect(0.12,0.40,0.86,0.95)]
def house_door(): return [[(0.24,0.95),(0.24,0.68),(0.38,0.68),(0.38,0.95)]]
def house_window(): return [_rect(0.54,0.55,0.74,0.72),[(0.64,0.55),(0.64,0.72)],[(0.54,0.635),(0.74,0.635)]]
def house_chimney(): return [[(0.68,0.215),(0.68,0.02),(0.78,0.02),(0.78,0.30)]]
def ellipse(): return [_ell(0.5,0.5,0.5,0.5,48)]
def climb():
    st=[(0.0,0.95),(0.22,0.95),(0.22,0.77),(0.46,0.77),(0.46,0.59),(0.70,0.59),(0.70,0.41),(0.96,0.41)]
    fig=[_circ(0.34,0.40,0.065,24),[(0.34,0.465),(0.34,0.63)],[(0.34,0.63),(0.28,0.77)],[(0.34,0.63),(0.41,0.69),(0.46,0.69)],
         [(0.34,0.52),(0.47,0.40)],[(0.34,0.52),(0.25,0.60)]]
    guide=[[(0.90,0.02),(0.62,0.30),(0.52,0.37)],[(0.52,0.37),(0.49,0.42)],[(0.53,0.38),(0.52,0.44)],[(0.555,0.36),(0.56,0.42)]]
    arrow=[[(0.08,0.70),(0.08,0.30)],[(0.02,0.38),(0.08,0.30),(0.14,0.38)]]
    return [st]+fig+guide+arrow
def maze():
    return [[(0.0,0.18),(0.0,1.0),(1.0,1.0),(1.0,0.0),(0.22,0.0)],[(0.20,0.20),(0.80,0.20),(0.80,0.52)],
            [(0.20,0.20),(0.20,0.80),(0.62,0.80)],[(0.80,0.80),(1.0,0.80)],[(0.38,0.38),(0.62,0.38),(0.62,0.62)]]
def stick():
    return [_circ(0.5,0.14,0.13,24),[(0.5,0.27),(0.5,0.65)],[(0.5,0.65),(0.25,1.0)],[(0.5,0.65),(0.75,1.0)],[(0.15,0.42),(0.85,0.42)]]
LIB=dict(climb=climb,maze=maze,stick=stick,building8=building8,house_outline=house_outline,house_door=house_door,house_window=house_window,house_chimney=house_chimney,ellipse=ellipse,building=building,key=key,house=house,chain=chain,tick=tick,cross=cross,sun=sun,drop=drop,leaf=leaf,arrow=arrow,underline=underline,vline=vline)
