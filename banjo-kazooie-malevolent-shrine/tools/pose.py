import os, sys, math
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bkparse import load_bones, load_anim

SCALE, BONES = load_bones()

def sample(anim, frame):
    vals = {}
    for bone, comp, keys in anim["elems"]:
        if frame <= keys[0][2]: v = keys[0][3]
        elif frame >= keys[-1][2]: v = keys[-1][3]
        else:
            for a, b in zip(keys, keys[1:]):
                if a[2] <= frame <= b[2]:
                    t = (frame - a[2]) / max(1, b[2]-a[2]); v = a[3] + (b[3]-a[3])*t; break
        vals[(bone, comp)] = v
    return vals

def rx(a):
    c,s=math.cos(a),math.sin(a); return np.array([[1,0,0],[0,c,-s],[0,s,c]])
def ry(a):
    c,s=math.cos(a),math.sin(a); return np.array([[c,0,s],[0,1,0],[-s,0,c]])
def rz(a):
    c,s=math.cos(a),math.sin(a); return np.array([[c,-s,0],[s,c,0],[0,0,1]])

ORDER = "zyx"  # column-vector product order R = R[0] R[1] R[2]
def rot(p, y, r):
    m = {"x": rx(math.radians(p)), "y": ry(math.radians(y)), "z": rz(math.radians(r))}
    R = np.eye(3)
    for ch in ORDER: R = R @ m[ch]
    return R

def mat4(R=np.eye(3), t=(0,0,0), s=(1,1,1)):
    M = np.eye(4); M[:3,:3] = R @ np.diag(s); M[:3,3] = t; return M

def fk(vals):
    mats = []
    for b in BONES:
        bid = b["bone_id"]; p = np.array(b["pos"])
        g = lambda c, d: vals.get((bid, c), d)
        R = rot(g(0,0), g(1,0), g(2,0))
        S = (g(3,1), g(4,1), g(5,1))
        T = np.array((g(6,0), g(7,0), g(8,0))) * SCALE
        par = mats[b["parent"]] if b["parent"] >= 0 else np.eye(4)
        M = par @ mat4(t=p+T) @ mat4(R=R, s=S) @ mat4(t=-p)
        mats.append(M)
    joints = [ (mats[i] @ np.append(np.array(b["pos"]),1))[:3] for i,b in enumerate(BONES)]
    return mats, joints

BANJO = set(range(0, 36))  # banjo + backpack bones
COL = {}
for i in range(4,10): COL[i]=(90,90,255)     # leg (-x)
for i in range(10,16): COL[i]=(40,160,255)   # leg (+x)
for i in range(18,24): COL[i]=(255,60,60)    # arm (-x)
for i in range(24,30): COL[i]=(255,160,0)    # arm (+x)
for i in range(30,33): COL[i]=(40,200,40)    # head/nose

def draw(vals, path, title="", views=("front","side","top")):
    mats, J = fk(vals)
    W,H = 300, 300
    img = Image.new("RGB", (W*len(views), H+20), "white")
    d = ImageDraw.Draw(img)
    for vi, view in enumerate(views):
        ox = vi*W
        def proj(v):
            x,y,z = v
            if view=="front": u,w = -x, y      # camera in front (+z) looking at banjo: banjo's +x appears on viewer's left
            elif view=="side": u,w = z, y       # banjo faces right
            else: u,w = -x, -z                  # top view, front of banjo toward bottom
            return (ox + W/2 + u*1.6, H - 20 - w*1.6 if view!="top" else H/2 + w*1.6)
        d.text((ox+5,5), view, fill="black")
        d.line([(ox,0),(ox,H)], fill="gray")
        for i,b in enumerate(BONES):
            if i not in BANJO or b["parent"] < 0: continue
            a = proj(J[b["parent"]]); c = proj(J[i])
            d.line([a,c], fill=COL.get(i,(0,0,0)), width=3)
        # hand / foot tips: extend last segment
        for last, prev in ((23,21),(29,27),(9,7),(15,13)):
            v = J[last] + (J[last]-J[prev])*0.6
            d.line([proj(J[last]), proj(v)], fill=COL[last], width=5)
        # nose
        d.ellipse([proj(J[32])[0]-3, proj(J[32])[1]-3, proj(J[32])[0]+3, proj(J[32])[1]+3], fill=(0,150,0))
    d.text((5,H), title, fill="black")
    img.save(path)

if __name__ == "__main__":
    uid = int(sys.argv[1],16); fr = float(sys.argv[2]); out = sys.argv[3]
    if len(sys.argv) > 4: ORDER = sys.argv[4]
    a = load_anim(uid)
    draw(sample(a, fr), out, "anim %X frame %s order %s" % (uid, fr, ORDER))
