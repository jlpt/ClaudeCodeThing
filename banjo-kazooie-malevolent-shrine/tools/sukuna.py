"""Turn Banjo's player models (0x34E high poly, 0x34D low poly) into Sukuna.

Recolours (vertex colours and texture palettes) and adds new geometry, all attached to
Banjo's own skeleton so it animates with him:
  * skin-toned fur, red eyes, dark-blue jeans for the shorts, brown belt, red sneakers
  * pink spiky hair (cones rooted on the head surface)
  * black bands around the upper arms and wrists
  * face markings: a second pair of eyes under his eyes, cheek stripes, forehead mark
  * chest markings on the pecs and lines down the stomach
Markings are drawn in a front-view plane and projected onto the mesh by ray casting,
then lifted slightly along the surface normal.

usage: sukuna.py in.model.bin out.model.bin [preview.png]
"""
import math, struct, sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bkmodel import Model, parse_tris
from bkparse import load_bones

SKIN = (242, 196, 158)
SKIN_LIGHT = (250, 214, 186)
HAIR = (236, 138, 150)
HAIR_TIP = (250, 176, 180)
HAIR_ROOT = (196, 98, 116)
INK = (22, 12, 16)
DENIM = (44, 72, 140)
BELT = (118, 74, 40)
SNEAKER = (196, 34, 36)
SOLE = (236, 232, 226)
EYE_RED = (206, 24, 30)

# texture roles, by texture index in each model (see texture dumps)
TEX_ROLES = {
    "034E": dict(head_fur=[13, 19], eyelid=[14, 16], eye=[18], shorts=[6, 7], belt=[5, 10], footpad=[3, 8], nose=[4]),
    "034D": dict(head_fur=[12, 18], eyelid=[13, 15], eye=[17], shorts=[5, 6], belt=[4, 9], footpad=[2, 7], nose=[3]),
}
BANJO_BONES = {2, 4, 7, 9, 11, 13, 15, 17, 19, 21, 23, 25, 27, 29, 31, 42}
FEET = {7, 21}
SHORTS = {4}

def lum(c):
    return 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]

def shade(target, factor):
    return tuple(max(0, min(255, int(round(t * factor)))) for t in target)

def hue(c):
    r, g, b = [x / 255.0 for x in c[:3]]
    mx, mn = max(r, g, b), min(r, g, b)
    if mx - mn < 1e-6: return 0.0, 0.0, mx
    if mx == r: h = ((g - b) / (mx - mn)) % 6
    elif mx == g: h = (b - r) / (mx - mn) + 2
    else: h = (r - g) / (mx - mn) + 4
    return h * 60.0, (mx - mn) / mx, mx

def is_brown(c):
    h, s, v = hue(c)
    return 5 <= h <= 45 and s > 0.55 and c[0] > c[2]

def is_peach(c):
    h, s, v = hue(c)
    return (h < 30 or h > 340) and 0.2 < s <= 0.6 and v > 0.35

def is_yellow(c):
    h, s, v = hue(c)
    return 38 <= h <= 65 and s > 0.6

def hair_region(p):
    x, y, z = p
    return y > 111 or z < -3 or (abs(x) > 11 and y > 104)

def is_blue(c):
    h, s, v = hue(c)
    return 190 <= h <= 250 and s > 0.35

# ---------------------------------------------------------------- palette recolour
def rgba16_get(d, o):
    v = struct.unpack(">H", d[o:o+2])[0]
    return [((v >> 11) & 31) * 255 // 31, ((v >> 6) & 31) * 255 // 31, ((v >> 1) & 31) * 255 // 31, v & 1]

def rgba16_set(d, o, c, a):
    v = (int(c[0]) * 31 // 255) << 11 | (int(c[1]) * 31 // 255) << 6 | (int(c[2]) * 31 // 255) << 1 | a
    d[o:o+2] = struct.pack(">H", v)

def recolour_palette(m, t, fn):
    base = m.tex_data + t["off"]
    n = 16 if t["type"] & 1 else 256
    for k in range(n):
        c = rgba16_get(m.d, base + 2 * k)
        nc = fn(c[:3])
        if nc is not None:
            rgba16_set(m.d, base + 2 * k, nc, c[3])

def fur_to(target, ref=70.0, lo=0.55, hi=1.08):
    def f(c):
        if is_brown(c) or (lum(c) < 60 and c[0] > c[2] + 10):
            return shade(target, max(lo, min(hi, 0.7 + 0.3 * lum(c) / ref)))
        return None
    return f

# ---------------------------------------------------------------- geometry helpers
class Geo:
    """new triangles grouped per bone matrix index"""
    def __init__(self):
        self.groups = {}
    def tri(self, mtx, a, b, c, ca, cb=None, cc=None):
        self.groups.setdefault(mtx, []).append(((a, ca), (b, cb or ca), (c, cc or ca)))

def norm(v):
    n = np.linalg.norm(v)
    return v / n if n > 1e-9 else v

class Surface:
    """ray casting against the model's bind-pose triangles of some bones"""
    def __init__(self, m, tris, bid, bone_ids):
        sel = [t for t in tris if bid.get(t[4]) in bone_ids]
        self.v0 = np.array([m.vert(t[0])["pos"] for t in sel], float)
        self.v1 = np.array([m.vert(t[1])["pos"] for t in sel], float)
        self.v2 = np.array([m.vert(t[2])["pos"] for t in sel], float)
        self.mtx = np.array([t[4] for t in sel])
    def cast(self, origin, direction):
        o = np.array(origin, float); d = np.array(direction, float)
        e1 = self.v1 - self.v0; e2 = self.v2 - self.v0
        p = np.cross(d, e2); det = np.einsum("ij,ij->i", e1, p)
        ok = np.abs(det) > 1e-9
        inv = np.where(ok, 1.0 / np.where(ok, det, 1), 0)
        tv = o - self.v0
        u = np.einsum("ij,ij->i", tv, p) * inv
        q = np.cross(tv, e1)
        v = (q @ d) * inv
        t = np.einsum("ij,ij->i", e2, q) * inv
        hit = ok & (u >= 0) & (v >= 0) & (u + v <= 1) & (t > 0)
        if not hit.any(): return None
        idx = np.where(hit)[0][np.argmin(t[hit])]
        n = norm(np.cross(e1[idx], e2[idx]))
        if n @ d > 0: n = -n
        return o + d * t[idx], n, int(self.mtx[idx])

def project_front(surf, x, y, lift=0.7):
    h = surf.cast((x, y, 200.0), (0, 0, -1))
    if h is None: return None
    p, n, mtx = h
    return p + n * lift, n, mtx

def decal_polygon(geo, surf, pts2d, colour, lift=0.7):
    """filled polygon given in the front-view plane, projected onto the surface (fan from centroid)"""
    cx = sum(p[0] for p in pts2d) / len(pts2d); cy = sum(p[1] for p in pts2d) / len(pts2d)
    c = project_front(surf, cx, cy, lift)
    ring = [project_front(surf, x, y, lift) for x, y in pts2d]
    if c is None or any(r is None for r in ring): return False
    mtx = c[2]
    for i in range(len(ring)):
        a, b = ring[i][0], ring[(i + 1) % len(ring)][0]
        geo.tri(mtx, tuple(c[0]), tuple(a), tuple(b), colour)
    return True

def decal_stroke(geo, surf, pts2d, width, colour, lift=0.7):
    """thick polyline in the front-view plane, as quads projected onto the surface"""
    for (x0, y0), (x1, y1) in zip(pts2d, pts2d[1:]):
        dx, dy = x1 - x0, y1 - y0; L = math.hypot(dx, dy) or 1
        nx, ny = -dy / L * width / 2, dx / L * width / 2
        decal_polygon(geo, surf, [(x0 - nx, y0 - ny), (x1 - nx, y1 - ny), (x1 + nx, y1 + ny), (x0 + nx, y0 + ny)], colour, lift)

def ellipse(cx, cy, rx, ry, n=10, rot=0.0):
    return [(cx + rx * math.cos(2 * math.pi * k / n) * math.cos(rot) - ry * math.sin(2 * math.pi * k / n) * math.sin(rot),
             cy + rx * math.cos(2 * math.pi * k / n) * math.sin(rot) + ry * math.sin(2 * math.pi * k / n) * math.cos(rot)) for k in range(n)]

def band(geo, m, tris, bid, idx_of, bone_id, x_center, width, colour, grow=0.35):
    """ring around a limb that runs along x in the bind pose"""
    mtx = idx_of[bone_id]
    pts = [m.vert(v)["pos"] for t in tris if t[4] == mtx for v in t[:3]]
    near = [p for p in pts if abs(p[0] - x_center) < 3.5]
    if len(near) < 3:
        near = sorted(pts, key=lambda p: abs(p[0] - x_center))[:8]
    cy = sum(p[1] for p in near) / len(near); cz = sum(p[2] for p in near) / len(near)
    rs = sorted(math.hypot(p[1] - cy, p[2] - cz) for p in near)
    r = rs[len(rs) // 2] + grow
    n = 12
    for k in range(n):
        a0 = 2 * math.pi * k / n; a1 = 2 * math.pi * (k + 1) / n
        p = [(x_center - width / 2, cy + r * math.cos(a0), cz + r * math.sin(a0)),
             (x_center + width / 2, cy + r * math.cos(a0), cz + r * math.sin(a0)),
             (x_center + width / 2, cy + r * math.cos(a1), cz + r * math.sin(a1)),
             (x_center - width / 2, cy + r * math.cos(a1), cz + r * math.sin(a1))]
        # both windings so the band shows from any side
        geo.tri(mtx, p[0], p[1], p[2], colour); geo.tri(mtx, p[0], p[2], p[3], colour)
        geo.tri(mtx, p[0], p[2], p[1], colour); geo.tri(mtx, p[0], p[3], p[2], colour)

def spike(geo, mtx, base, direction, length, radius, rng):
    d = norm(np.array(direction, float))
    u = norm(np.cross(d, np.array([0.3, 1.0, 0.2])))
    v = np.cross(d, u)
    tip = tuple(np.array(base) + d * length)
    ring = [tuple(np.array(base) + radius * (math.cos(a) * u + math.sin(a) * v)) for a in
            [rng * 0.7 + k * math.pi / 2 for k in range(4)]]
    for k in range(4):
        a, b = ring[k], ring[(k + 1) % 4]
        geo.tri(mtx, a, b, tip, HAIR_ROOT, HAIR_ROOT, HAIR_TIP)
    geo.tri(mtx, ring[0], ring[2], ring[1], HAIR_ROOT); geo.tri(mtx, ring[0], ring[3], ring[2], HAIR_ROOT)

def hash01(*k):
    h = 2166136261
    for x in k:
        h = ((h ^ (int(x * 1000) & 0xFFFFFFFF)) * 16777619) & 0xFFFFFFFF
    return (h & 0xFFFF) / 65535.0

# ---------------------------------------------------------------- face reshaping
def reshape_face(m, tris, bid, bones):
    """Flatten the snout (the 'nose' bone 42 spans the whole muzzle) back to a human face
    just in front of the eyes, lower its bridge below the eyes, and fold the ears down."""
    seen = set()
    for (a, b, c, tex, mtx) in tris:
        if bid.get(mtx) not in (19, 42): continue
        for v in (a, b, c):
            if v in seen: continue
            seen.add(v)
            x, y, z = m.vert(v)["pos"]
            if z > 22:
                t = z - 22
                w = max(0.0, min(1.0, (t - 5.5) / 8.0))     # 0 at the eyes, 1 on the snout
                z = 22 + t * 0.25
                if y > 103: y = y - (y - 103) * 0.8 * w
                x = x * (1 - 0.25 * w)
            if y > 112 and abs(x) > 7 and z > -6:        # bear ears: tuck them into the hair
                y = 112 + (y - 112) * 0.2
                x = x * 0.8
            o = m.vtx_base + 16 * v
            m.d[o:o+6] = struct.pack(">3h", int(round(x)), int(round(y)), int(round(z)))
    # move the snout bone's pivot onto the new face so its small wiggles stay in place
    for b in bones:
        if b["bone_id"] == 42:
            o = m.anim + 8 + 16 * b["i"]
            px, py, pz = struct.unpack(">3f", m.d[o:o+12])
            m.d[o:o+12] = struct.pack(">3f", px, py, 22 + (pz - 22) * 0.25)

# ---------------------------------------------------------------- the transformation
def sukunafy(path_in, path_out):
    name = os.path.basename(path_in)[:4]
    roles = TEX_ROLES[name]
    m = Model(path_in)
    tris, vbone = parse_tris(m)
    scale, bones = load_bones(path_in)
    bid = {b["i"]: b["bone_id"] for b in bones}
    idx_of = {b["bone_id"]: b["i"] for b in bones}

    # 0. reshape the head: flatten the bear snout into a face, fold the ears under the hair
    reshape_face(m, tris, bid, bones)

    # 1. vertex colours on Banjo's body
    done = set()
    for (a, b, c, tex, mtx) in tris:
        bone = bid.get(mtx)
        if bone not in BANJO_BONES: continue
        for v in (a, b, c):
            if v in done: continue
            done.add(v)
            col = m.vert(v)["col"]; rgb = col[:3]
            new = None
            if bone == 19 and (tex is None or tex in roles["head_fur"]) and (is_brown(rgb) or tex is not None) and \
                    hair_region(m.vert(v)["pos"]):
                g = max(0.45, min(1.0, (lum(rgb) / 255.0 * 1.05) if tex is not None else (0.7 + 0.3 * lum(rgb) / 70)))
                new = shade(HAIR, g)
            elif bone == 19 and tex is not None and tex in roles["head_fur"] + roles["eyelid"]:
                # head fur texture is neutral now: the vertices decide hair (pink) or face (skin)
                p = m.vert(v)["pos"]
                g = max(0.45, min(1.0, lum(rgb) / 255.0 * 1.05))
                new = shade(SKIN, g)
            elif bone in FEET:
                if tex is not None and tex in roles["footpad"]: new = None
                elif is_peach(rgb) or is_brown(rgb) or lum(rgb) < 90: new = shade(SNEAKER, max(0.55, min(1.1, 0.55 + 0.45 * lum(rgb) / 120)))
                elif rgb[0] > 200 and rgb[1] > 200: new = shade(SOLE, 0.9)
            elif bone in SHORTS and (is_yellow(rgb) or is_brown(rgb)):
                new = shade(DENIM, max(0.5, min(1.2, lum(rgb) / 150)))
            elif bone == 42 and lum(rgb) < 40:
                new = (170, 112, 96)         # the black bear nose becomes a skin-toned nose
            elif is_yellow(rgb):
                new = shade(DENIM, max(0.5, min(1.2, lum(rgb) / 150)))
            elif is_brown(rgb):
                new = shade(SKIN, max(0.55, min(1.08, 0.7 + 0.3 * lum(rgb) / 70)))
            elif is_peach(rgb):
                new = shade(SKIN_LIGHT, max(0.55, min(1.05, lum(rgb) / 150)))
            if new is not None:
                m.set_vcol(v, list(new) + [col[3]])

    # 2. texture palettes
    for i in roles["head_fur"]:
        recolour_palette(m, m.textures[i], lambda c: shade((255, 255, 255), max(0.78, min(1.0, 0.7 + 0.5 * lum(c) / 120))))
    for i in roles["nose"]:
        recolour_palette(m, m.textures[i], lambda c: shade((196, 138, 118), max(0.8, min(1.15, 0.85 + lum(c) / 400))))
    for i in roles["eyelid"]:
        def lid(c):
            if is_blue(c): return shade(EYE_RED, max(0.4, min(1.2, lum(c) / 90)))
            return fur_to(SKIN)(c)
        recolour_palette(m, m.textures[i], lid)
    for i in roles["eye"]:
        recolour_palette(m, m.textures[i], lambda c: shade(EYE_RED, max(0.35, min(1.2, lum(c) / 90))) if is_blue(c) else None)
    for i in roles["shorts"]:
        recolour_palette(m, m.textures[i], lambda c: shade(DENIM, max(0.4, min(1.3, lum(c) / 160))) if (is_yellow(c) or is_brown(c)) else None)
    for i in roles["belt"]:
        recolour_palette(m, m.textures[i], lambda c: shade(BELT, 1.0) if lum(c) < 40 else None)
    for i in roles["footpad"]:   # the toes: red sneaker fronts with a white toe cap
        recolour_palette(m, m.textures[i], lambda c: shade(SNEAKER, max(0.55, min(1.15, lum(c) / 150))) if lum(c) < 200 else shade(SOLE, 0.95))

    # 3. new geometry, fitted to each level of detail and hooked onto the end of that LOD's list
    counts = []
    for lod, (lod_off, last_cmd) in enumerate(lod_chains(m)):
        lod_tris, _ = parse_tris(m, lod=lod)
        geo = build_geometry(m, lod_tris, bid, idx_of)
        append_geometry(m, geo, last_cmd)
        counts.append(sum(len(v) for v in geo.groups.values()))
    open(path_out, "wb").write(m.d)
    return m, counts

def build_geometry(m, tris, bid, idx_of):
    """hair, bands and markings fitted to one LOD's surface"""
    geo = Geo()
    head = Surface(m, tris, bid, {19})
    chest = Surface(m, tris, bid, {2})

    # hair: spikes rooted on the top and back of the head, swept up and back
    k = 0
    for gx in np.arange(-15, 15.1, 3.2):
        for gz in np.arange(-12, 16.1, 3.2):
            jx = gx + (hash01(gx, gz, 1) - 0.5) * 2.0; jz = gz + (hash01(gx, gz, 2) - 0.5) * 2.0
            h = head.cast((jx, 200.0, jz), (0, -1, 0))
            if h is None: continue
            p, n, mtx = h
            if n[1] < 0.25 or p[1] < 112 or p[2] > 13: continue
            out = np.array([jx * 0.06, 0.0, 0.0])
            dirn = n * 0.6 + np.array([0, 1.0, -0.55]) + out + np.array([(hash01(jx, jz, 3) - 0.5) * 0.5, 0, (hash01(jx, jz, 4) - 0.5) * 0.4])
            length = 12.0 + 8.0 * hash01(jx, jz, 5) - (4.0 if jz > 9 else 0.0)
            spike(geo, mtx, tuple(p - n * 1.2), dirn, length, 4.0, hash01(jx, jz, 6))
            k += 1
    for gy in np.arange(100, 121, 2.8):          # back of the head
        for gx in np.arange(-11, 11.1, 3.0):
            h = head.cast((gx, gy, -200.0), (0, 0, 1))
            if h is None: continue
            p, n, mtx = h
            if p[2] > -2 or n[2] > -0.3: continue     # only the real back of the head
            dirn = n * 0.7 + np.array([gx * 0.03, 0.8 + (gy - 100) * 0.02, -0.3])
            spike(geo, mtx, tuple(p - n * 1.2), dirn, 9.0 + 6.0 * hash01(gx, gy, 7), 3.8, hash01(gx, gy, 8))
            k += 1

    # arm bands: two on each upper arm, one near each wrist
    for bone, xs in ((29, (-26.0, -31.0)), (15, (26.0, 31.0))):
        for x in xs:
            band(geo, m, tris, bid, idx_of, bone, x, 2.4, INK)
    band(geo, m, tris, bid, idx_of, 23, -48.5, 2.4, INK)
    band(geo, m, tris, bid, idx_of, 9, 48.5, 2.4, INK)

    # face: the second pair of eyes under his eyes, cheek stripes, forehead mark
    for sx in (-1, 1):
        decal_polygon(geo, head, ellipse(sx * 12.8, 106.5, 2.7, 1.3, 10, rot=sx * 0.25), INK, 0.6)
        decal_polygon(geo, head, ellipse(sx * 12.8, 106.5, 1.9, 0.8, 8, rot=sx * 0.25), (238, 226, 214), 0.8)
        decal_polygon(geo, head, ellipse(sx * 12.8, 106.5, 0.75, 0.75, 6), EYE_RED, 1.0)
        decal_stroke(geo, head, [(sx * 11.0, 102.0), (sx * 14.5, 101.2), (sx * 17.0, 99.5)], 0.9, INK)
        decal_stroke(geo, head, [(sx * 11.5, 99.0), (sx * 14.5, 97.8), (sx * 16.5, 95.8)], 0.9, INK)
        decal_stroke(geo, head, [(sx * 2.0, 119.2), (sx * 4.6, 118.2), (sx * 5.2, 120.0)], 0.8, INK)
    decal_stroke(geo, head, [(-2.0, 119.2), (2.0, 119.2)], 0.8, INK)
    # Sukuna's wide grin
    face = Surface(m, tris, bid, {19, 42})
    grin = [(-8.5, 97.5), (-5.0, 95.0), (0.0, 94.0), (5.0, 95.0), (8.5, 97.5)]
    decal_stroke(geo, face, grin, 1.4, INK, 0.8)
    for k in range(6):
        x = -6.0 + k * 2.4
        decal_polygon(geo, face, [(x - 0.9, 95.4 - abs(x) * 0.1), (x + 0.9, 95.4 - abs(x) * 0.1), (x, 94.2 - abs(x) * 0.1)], (240, 236, 226), 1.0)

    # chest: jagged marks on the pecs, lines down the stomach
    for sx in (-1, 1):
        decal_stroke(geo, chest, [(sx * 3.5, 83.0), (sx * 7.0, 78.5), (sx * 10.0, 82.0), (sx * 13.0, 77.5), (sx * 16.0, 83.5)], 1.6, INK)
        decal_stroke(geo, chest, [(sx * 4.0, 70.0), (sx * 5.0, 64.0)], 1.3, INK)
        decal_stroke(geo, chest, [(sx * 9.5, 71.0), (sx * 10.5, 64.5)], 1.2, INK)

    return geo

# ---------------------------------------------------------------- write new geometry into the model
def lod_chains(m):
    """(branch offset, offset of the last command in that branch) for each top-level LOD command"""
    d = m.d; off = m.geo; out = []
    while True:
        cmd, nxt = struct.unpack(">Ii", d[off:off+8])
        if cmd == 8:
            br = off + struct.unpack(">i", d[off+0x1C:off+0x20])[0]
            last = br
            while True:
                n2 = struct.unpack(">i", d[last+4:last+8])[0]
                if n2 == 0: break
                last += n2
            out.append((br, last))
        if nxt == 0: break
        off += nxt
    return out

def append_geometry(m, geo, link_cmd):
    d = m.d
    while len(d) % 16: d.append(0)
    vtx_bytes = bytearray(); gfx = []   # gfx entries relative to our DL block
    dl_starts = {}
    for mtx, tris in sorted(geo.groups.items()):
        dl_starts[mtx] = len(gfx)
        gfx += [(0xB6000000, 0x001F3204), (0xB7000000, 0x00002204), (0xBB000000, 0x80008000),
                (0xE7000000, 0), (0xFC62FE04, 0x3F15F9FF), (0x06000000, 0x03000010)]
        batch, cache = [], {}
        def flush():
            if not batch: return
            base = len(vtx_bytes) // 16
            for (pos, col), _ in sorted(cache.items(), key=lambda kv: kv[1]):
                p = [int(round(c)) for c in pos]
                vtx_bytes.extend(struct.pack(">3hH2h4B", p[0], p[1], p[2], 0, 0, 0, col[0], col[1], col[2], 255))
            n = len(cache)
            gfx.append(("VTX", n, base))
            for i in range(0, len(batch), 2):
                a = batch[i]
                if i + 1 < len(batch):
                    b = batch[i + 1]
                    gfx.append((0xB1000000 | (a[0]*2 << 16) | (a[1]*2 << 8) | a[2]*2, (b[0]*2 << 16) | (b[1]*2 << 8) | b[2]*2))
                else:
                    gfx.append((0xBF000000, (a[0]*2 << 16) | (a[1]*2 << 8) | a[2]*2))
            batch.clear(); cache.clear()
        for tri in tris:
            keys = [(tuple(float(c) for c in p), tuple(int(x) for x in col[:3])) for p, col in tri]
            new = set(k for k in keys if k not in cache)
            if len(cache) + len(new) > 30: flush()
            idx = []
            for k in keys:
                if k not in cache: cache[k] = len(cache)
                idx.append(cache[k])
            batch.append(idx)
        flush()
        gfx.append((0xB8000000, 0))
    # layout at the end of the file: vertices, then display lists, then geo commands
    vtx_off = len(d); d.extend(vtx_bytes)
    while len(d) % 16: d.append(0)
    gfx_off = len(d)
    seg1 = vtx_off - m.vtx_base
    for g in gfx:
        if g[0] == "VTX":
            _, n, base = g
            w0 = 0x04000000 | (n << 10) | (n * 16 - 1)
            d.extend(struct.pack(">II", w0, 0x01000000 + seg1 + base * 16))
        else:
            d.extend(struct.pack(">II", g[0] & 0xFFFFFFFF, g[1] & 0xFFFFFFFF))
    while len(d) % 16: d.append(0)
    geo_off = len(d)
    items = sorted(dl_starts.items())
    for n_i, (mtx, start) in enumerate(items):
        gfx_index = (gfx_off - m.gfx_base) // 8 + start
        assert gfx_index < 32768
        nxt = 32 if n_i + 1 < len(items) else 0
        d.extend(struct.pack(">IiBbHI", 2, nxt, 0x10, mtx, 0, 0))     # BONE -> branch to LOADDL
        d.extend(struct.pack(">IihhI", 3, 0, gfx_index, 0, 0))         # LOADDL
    # hook the new block onto the end of the LOD's command list
    d[link_cmd+4:link_cmd+8] = struct.pack(">i", geo_off - link_cmd)

if __name__ == "__main__":
    m, counts = sukunafy(sys.argv[1], sys.argv[2])
    print(os.path.basename(sys.argv[1]), "-> added triangles per LOD:", counts, "size", len(m.d))
