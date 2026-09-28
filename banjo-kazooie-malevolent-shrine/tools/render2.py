"""Z-buffered software renderer for BK models (one LOD), with textures and optional skeletal pose."""
import sys, math, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bkmodel import Model, parse_tris
from PIL import Image

def tex_arrays(m):
    return {t["i"]: np.asarray(m.texture_image(t).convert("RGBA"), dtype=np.float32) for t in m.textures}

def rot_view(view):
    # returns 3x3 matrix mapping model coords -> (screen x right, screen y up, depth toward viewer)
    if view == "front": return np.array([[1,0,0],[0,1,0],[0,0,1]], float)      # camera at +z (Banjo faces +z)
    if view == "back":  return np.array([[-1,0,0],[0,1,0],[0,0,-1]], float)
    if view == "side":  return np.array([[0,0,-1],[0,1,0],[1,0,0]], float)     # camera at +x
    if view == "3q":    # camera front-right, slightly above
        a = math.radians(35); b = math.radians(12)
        ry = np.array([[math.cos(a),0,-math.sin(a)],[0,1,0],[math.sin(a),0,math.cos(a)]])
        rx = np.array([[1,0,0],[0,math.cos(b),-math.sin(b)],[0,math.sin(b),math.cos(b)]])
        return rx @ ry
    raise ValueError(view)

def render(m, tris, view="front", size=512, scale=3.5, center=(0, 75, 0), skip=(), mats=None, vbone=None, st_scale=1/64.0, bg=(70,78,96)):
    texs = tex_arrays(m)
    R = rot_view(view)
    W = H = size
    img = np.zeros((H, W, 3), np.float32); img[:] = bg
    zb = np.full((H, W), -1e9, np.float32)
    cache = {}
    def vinfo(i):
        if i in cache: return cache[i]
        v = m.vert(i); p = np.array(v["pos"], float)
        if mats is not None and vbone is not None and vbone.get(i, -1) >= 0:
            M = mats[vbone[i]]; p = (M @ np.append(p, 1))[:3]
        q = R @ (p - np.array(center))
        sx = W/2 + q[0]*scale; sy = H/2 - q[1]*scale
        cache[i] = (sx, sy, q[2], np.array(v["col"][:3], np.float32), np.array(v["st"], np.float32))
        return cache[i]
    for (a, b, c, tex, bone) in tris:
        if bone in skip or None in (a, b, c): continue
        A, B, C = vinfo(a), vinfo(b), vinfo(c)
        area = (B[0]-A[0])*(C[1]-A[1]) - (C[0]-A[0])*(B[1]-A[1])
        if area >= 0: continue          # back face (N64 culls clockwise-on-screen triangles)
        x0 = int(max(0, math.floor(min(A[0],B[0],C[0])))); x1 = int(min(W-1, math.ceil(max(A[0],B[0],C[0]))))
        y0 = int(max(0, math.floor(min(A[1],B[1],C[1])))); y1 = int(min(H-1, math.ceil(max(A[1],B[1],C[1]))))
        if x0 > x1 or y0 > y1: continue
        xs, ys = np.meshgrid(np.arange(x0, x1+1) + 0.5, np.arange(y0, y1+1) + 0.5)
        w0 = ((B[0]-xs)*(C[1]-ys) - (C[0]-xs)*(B[1]-ys)) / area
        w1 = ((C[0]-xs)*(A[1]-ys) - (A[0]-xs)*(C[1]-ys)) / area
        w2 = 1 - w0 - w1
        inside = (w0 >= -1e-6) & (w1 >= -1e-6) & (w2 >= -1e-6)
        if not inside.any(): continue
        z = w0*A[2] + w1*B[2] + w2*C[2]
        sub = zb[y0:y1+1, x0:x1+1]
        draw = inside & (z > sub)
        if not draw.any(): continue
        col = w0[...,None]*A[3] + w1[...,None]*B[3] + w2[...,None]*C[3]
        if tex is not None:
            T = texs[tex]; th, tw = T.shape[:2]
            s = (w0*A[4][0] + w1*B[4][0] + w2*C[4][0]) * st_scale
            t = (w0*A[4][1] + w1*B[4][1] + w2*C[4][1]) * st_scale
            si = np.floor(s).astype(int) % tw; ti = np.floor(t).astype(int) % th
            texel = T[ti, si]
            col = col * texel[...,:3] / 255.0
            draw = draw & (texel[...,3] > 0)
        sub[draw] = z[draw]
        img[y0:y1+1, x0:x1+1][draw] = col[draw]
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))
