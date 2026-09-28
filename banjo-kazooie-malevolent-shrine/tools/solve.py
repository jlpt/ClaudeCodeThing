import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, itertools
import pose
from design import mudra
best=[]
def cost(p):
    v = mudra(p[0], p[1], p[2], p[3], p[4], p[5], 10)
    _, J = pose.fk(v)
    w = J[23]; e = J[21]; t = J[23] + (J[23]-J[21])*0.6
    c = (w[0]+5)**2 + (w[1]-74)**2 + (w[2]-24)**2
    c += 0.5*((e[0]+30)**2 + (e[1]-68)**2 + (e[2]-8)**2)
    c += 0.3*(t[0]-0)**2 + 0.3*(t[1]-80)**2   # fingertips point up/in
    return c, w, e, t
rng = np.random.default_rng(1)
p = np.array([40,50,0,90,0,0.0]); c,_,_,_ = cost(p)
for it in range(6000):
    q = p + rng.normal(0, 8, 6)
    cq = cost(q)[0]
    if cq < c: p, c = q, cq
c,w,e,t = cost(p)
print(np.round(p,1), round(c,2), np.round(w,1), np.round(e,1), np.round(t,1))
