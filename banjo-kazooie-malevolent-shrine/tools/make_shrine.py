"""Generate a low-poly Malevolent Shrine model in Banjo-Kazooie's model format.

The model is vertex-coloured (no textures), faces +Z like Banjo, sits on y=0 and is
~1000 units tall. The game draws it with depth testing off as a backdrop behind
Banjo, so parts are emitted back-to-front / bottom-to-top (painter's order) and
backface culling handles each convex piece.

usage: make_shrine.py out.model.bin [preview.png]
"""
import math, struct, sys

LIGHT = (-0.45, 0.75, 0.55)
_l = math.sqrt(sum(c * c for c in LIGHT)); LIGHT = tuple(c / _l for c in LIGHT)

def sub(a, b): return (a[0]-b[0], a[1]-b[1], a[2]-b[2])
def cross(a, b): return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
def norm(a):
    l = math.sqrt(sum(c*c for c in a)) or 1.0
    return (a[0]/l, a[1]/l, a[2]/l)

class Mesh:
    def __init__(self):
        self.parts = []          # list of (name, [tri]), tri = ((p,p,p), (c,c,c))
    def part(self, name):
        self.parts.append((name, []))
    def tri(self, a, b, c, col, shade=True, cols=None):
        n = norm(cross(sub(b, a), sub(c, a)))
        k = 0.42 + 0.58 * max(0.0, sum(n[i]*LIGHT[i] for i in range(3))) if shade else 1.0
        def lit(col):
            return tuple(max(0, min(255, int(col[i]*k))) for i in range(3)) + (255,)
        cc = tuple(lit(x) for x in cols) if cols else (lit(col),)*3
        self.parts[-1][1].append(((a, b, c), cc))
    def quad(self, a, b, c, d, col, **kw):
        # a,b,c,d counter-clockwise seen from the front
        self.tri(a, b, c, col, **kw); self.tri(a, c, d, col, **kw)

    def box(self, x0, x1, y0, y1, z0, z1, col, top=None, skip=()):
        p = lambda x, y, z: (x, y, z)
        faces = {
            "front": (p(x0,y0,z1), p(x1,y0,z1), p(x1,y1,z1), p(x0,y1,z1)),
            "back":  (p(x1,y0,z0), p(x0,y0,z0), p(x0,y1,z0), p(x1,y1,z0)),
            "left":  (p(x0,y0,z0), p(x0,y0,z1), p(x0,y1,z1), p(x0,y1,z0)),
            "right": (p(x1,y0,z1), p(x1,y0,z0), p(x1,y1,z0), p(x1,y1,z1)),
            "top":   (p(x0,y1,z1), p(x1,y1,z1), p(x1,y1,z0), p(x0,y1,z0)),
            "bottom":(p(x0,y0,z0), p(x1,y0,z0), p(x1,y0,z1), p(x0,y0,z1)),
        }
        for name in ("back", "bottom", "left", "right", "top", "front"):
            if name in skip: continue
            self.quad(*faces[name], top if (name == "top" and top) else col)

    def frustum(self, cx, cz, r0, r1, y0, y1, sides, col, rot=0.0, cap=True, col_top=None):
        ring = lambda r, y: [(cx + r*math.sin(rot + 2*math.pi*i/sides), y, cz + r*math.cos(rot + 2*math.pi*i/sides)) for i in range(sides)]
        lo, hi = ring(r0, y0), ring(r1, y1)
        order = sorted(range(sides), key=lambda i: lo[i][2])   # back faces first
        for i in order:
            j = (i + 1) % sides
            if r1 > 0:
                self.quad(lo[i], lo[j], hi[j], hi[i], col)
            else:
                self.tri(lo[i], lo[j], (cx, y1, cz), col)
        if cap and r1 > 0:
            for i in range(1, sides - 1):
                self.tri(hi[0], hi[i], hi[i+1], col_top or col)

    def cone_bent(self, base, tip, r, sides, col, bend=(0, 0, 0), segs=3, tipcol=None):
        """tapered horn/fang from base to tip, bowed by `bend` at the middle"""
        pts = []
        for s in range(segs + 1):
            t = s / segs
            b = 4 * t * (1 - t)
            pts.append(tuple(base[i] + (tip[i]-base[i])*t + bend[i]*b for i in range(3)))
        for s in range(segs):
            a, c = pts[s], pts[s+1]
            ra, rc = r * (1 - s/segs), r * (1 - (s+1)/segs)
            ax = norm(sub(c, a))
            u = norm(cross(ax, (0, 0, 1) if abs(ax[2]) < 0.9 else (1, 0, 0)))
            v = cross(ax, u)
            ringa = [tuple(a[k] + ra*(math.cos(2*math.pi*i/sides)*u[k] + math.sin(2*math.pi*i/sides)*v[k]) for k in range(3)) for i in range(sides)]
            ringc = [tuple(c[k] + rc*(math.cos(2*math.pi*i/sides)*u[k] + math.sin(2*math.pi*i/sides)*v[k]) for k in range(3)) for i in range(sides)]
            cc = tipcol if (tipcol and s == segs - 1) else col
            for i in range(sides):
                j = (i + 1) % sides
                if rc > 0.5:
                    self.quad(ringa[i], ringa[j], ringc[j], ringc[i], cc)
                else:
                    self.tri(ringa[i], ringa[j], c, cc)

    def hip_roof(self, hx, hz, y0, y1, ridge, lift, flare, col, under, trim):
        """hip roof: eave rectangle (hx,hz) at y0 with corners lifted by `lift` and pushed out by `flare`,
        ridge of half-length `ridge` at y1. Two rows per slope give the curved, upswept eave."""
        def corner(sx, sz): return (sx*(hx+flare), y0+lift, sz*(hz+flare))
        def mid(sx, sz):    return (sx*hx*0.62, y0 + (y1-y0)*0.42, sz*hz*0.55)
        FL, FR, BR, BL = corner(-1, 1), corner(1, 1), corner(1, -1), corner(-1, -1)
        eF = [(-hx, y0, hz+flare*0.35), (hx, y0, hz+flare*0.35)]
        eB = [(hx, y0, -hz-flare*0.35), (-hx, y0, -hz-flare*0.35)]
        mFL, mFR, mBR, mBL = mid(-1, 1), mid(1, 1), mid(1, -1), mid(-1, -1)
        RL, RR = (-ridge, y1, 0.0), (ridge, y1, 0.0)
        # underside (seen from below) in dark red
        self.quad(FL, BL, BR, FR, under, shade=False)
        # back slope
        self.quad(BR, eB[0], mBR, BR, col); self.quad(eB[0], eB[1], mBL, mBR, col); self.quad(eB[1], BL, mBL, eB[1], col)
        self.quad(mBR, mBL, RL, RR, col)
        # side slopes
        self.quad(BL, FL, mFL, mBL, col); self.tri(mBL, mFL, RL, col)
        self.quad(FR, BR, mBR, mFR, col); self.tri(mFR, mBR, RR, col)
        # front slope (lower flared row, then upper row)
        self.quad(FL, eF[0], mFL, FL, col); self.quad(eF[0], eF[1], mFR, mFL, col); self.quad(eF[1], FR, mFR, eF[1], col)
        self.quad(mFL, mFR, RR, RL, col)
        # gold trim along the front eave
        t = 10
        self.quad(FL, FR, (FR[0], FR[1]-t, FR[2]+2), (FL[0], FL[1]-t, FL[2]+2), trim, shade=False)

BONE, BONE_D = (222, 212, 180), (150, 138, 112)
EYE = (20, 6, 6)
STONE = (70, 52, 50)
LACQ = (150, 16, 18)
BLACK = (28, 22, 26)
MAW = (26, 0, 4)
TOOTH = (240, 236, 214)
ROOF = (34, 28, 36)
UNDER = (110, 14, 14)
GOLD = (210, 160, 50)

def skull(m, x, y, z, s, horns=False):
    m.box(x-30*s, x+30*s, y, y+46*s, z-34*s, z, BONE, skip=("bottom", "back"))
    m.box(x-20*s, x+20*s, y-14*s, y, z-26*s, z-4*s, BONE_D, skip=("top", "back"))   # jaw
    fz = z + 1
    for ex in (-13, 13):
        m.quad((x+(ex-9)*s, y+18*s, fz), (x+(ex+9)*s, y+18*s, fz), (x+(ex+8)*s, y+32*s, fz), (x+(ex-8)*s, y+32*s, fz), EYE, shade=False)
    m.tri((x-4*s, y+8*s, fz), (x+4*s, y+8*s, fz), (x, y+15*s, fz), EYE, shade=False)
    if horns:
        for sx in (-1, 1):
            m.cone_bent((x+sx*28*s, y+36*s, z-16*s), (x+sx*95*s, y+105*s, z-10*s), 11*s, 5, BONE, bend=(sx*30*s, -25*s, 0), tipcol=BONE_D)

def build():
    m = Mesh()
    # --- mound of bones and skulls ------------------------------------------------
    m.part("mound")
    m.frustum(0, 0, 640, 520, 0, 70, 10, BONE_D, rot=math.pi/10, cap=False)
    m.frustum(0, 0, 520, 470, 70, 130, 10, BONE, rot=math.pi/10, col_top=BONE_D)
    # --- stone platform and steps ---------------------------------------------------
    m.part("platform")
    m.box(-360, 360, 130, 185, -300, 250, STONE, top=(95, 70, 66))
    m.part("steps")
    for i in range(3):
        m.box(-130 + i*14, 130 - i*14, 130 + i*18, 148 + i*18, 250 + (2-i)*40, 290 + (2-i)*40, STONE, top=(110, 84, 80), skip=("back",))
    # --- main hall with the maw ---------------------------------------------------------
    m.part("hall")
    m.box(-270, 270, 185, 500, -230, 170, LACQ, skip=("bottom",))
    m.part("maw")
    zf = 171
    m.quad((-215, 205, zf), (215, 205, zf), (230, 470, zf), (-230, 470, zf), MAW, shade=False)
    m.quad((-150, 250, zf+1), (150, 250, zf+1), (160, 420, zf+1), (-160, 420, zf+1), (8, 0, 0), shade=False)
    # lips
    m.box(-240, 240, 468, 490, 160, 190, BLACK)
    m.box(-225, 225, 190, 208, 160, 190, BLACK)
    m.part("teeth")
    n = 9
    for i in range(n):
        x0 = -215 + i * 430 / n; x1 = x0 + 430 / n; xm = (x0 + x1) / 2
        big = i in (1, n - 2)
        m.tri((x1, 468, zf+3), (x0, 468, zf+3), (xm, 468 - (95 if big else 52), zf+3), TOOTH)       # upper row
        m.tri((x0+6, 208, zf+3), (x1-6, 208, zf+3), (xm, 208 + (70 if big else 40), zf+3), TOOTH)   # lower row
    # --- pillars in front of the hall -----------------------------------------------------
    m.part("pillars")
    for x in (-330, -120, 120, 330):
        m.frustum(x, 205, 24, 24, 185, 520, 6, BLACK, cap=False)
        m.frustum(x, 205, 30, 30, 300, 330, 6, LACQ, cap=False)
    # --- cow skulls and skull row on the mound (in front of everything below the hall) -----
    m.part("skulls")
    for i, x in enumerate(range(-420, 421, 105)):
        skull(m, x, 60 + (i % 2) * 18, 505 - abs(x) * 0.18, 0.9)
    skull(m, -250, 190, 330, 1.35, horns=True)
    skull(m, 250, 190, 330, 1.35, horns=True)
    # --- lower roof ------------------------------------------------------------------------
    m.part("roof1")
    m.hip_roof(390, 290, 520, 660, 170, 70, 70, ROOF, UNDER, GOLD)
    # --- upper storey and roof ---------------------------------------------------------------
    m.part("tier2")
    m.box(-170, 170, 610, 740, -120, 110, LACQ, skip=("bottom",))
    m.frustum(-120, 125, 14, 14, 610, 745, 6, BLACK, cap=False)
    m.frustum(120, 125, 14, 14, 610, 745, 6, BLACK, cap=False)
    m.part("roof2")
    m.hip_roof(250, 180, 745, 880, 90, 55, 45, ROOF, UNDER, GOLD)
    # --- horns and spire ------------------------------------------------------------------------
    m.part("horns")
    for sx in (-1, 1):
        m.cone_bent((sx*300, 600, 40), (sx*470, 900, 60), 32, 6, BONE, bend=(sx*80, -40, 0), segs=4, tipcol=BONE_D)
    m.frustum(0, 0, 18, 0, 875, 1010, 6, GOLD)
    return m

# ---------------------------------------------------------------------------------------
def encode(m):
    verts, gfx = [], []
    def g(w0, w1): gfx.append((w0 & 0xFFFFFFFF, w1 & 0xFFFFFFFF))
    g(0xB6000000, 0x001F3204)           # clear geometry mode
    g(0xB7000000, 0x00002204)           # G_SHADE | G_SHADING_SMOOTH | G_CULL_BACK
    g(0xBB000000, 0x80008000)           # texture off
    g(0xE7000000, 0)                     # pipe sync
    g(0xFC62FE04, 0x3F15F9FF)           # the game's vertex-colour combiner (x ENV alpha)
    g(0x06000000, 0x03000010)           # render mode from the renderer's table (segment 3)
    ntris = 0
    for name, tris in m.parts:
        batch, bverts = [], {}
        def flush():
            if not batch: return
            base = len(verts)
            order = sorted(bverts.items(), key=lambda kv: kv[1])
            for (p, c), _ in order: verts.append((p, c))
            n = len(order)
            g(0x04000000 | (n << 10) | (n * 16 - 1), 0x01000000 + base * 16)
            for i in range(0, len(batch), 2):
                a = batch[i]
                if i + 1 < len(batch):
                    b = batch[i+1]
                    g(0xB1000000 | (a[0]*2 << 16) | (a[1]*2 << 8) | a[2]*2, (b[0]*2 << 16) | (b[1]*2 << 8) | b[2]*2)
                else:
                    g(0xBF000000, (a[0]*2 << 16) | (a[1]*2 << 8) | a[2]*2)
            batch.clear(); bverts.clear()
        for (pts, cols) in tris:
            keys = [(tuple(int(round(v)) for v in p), c) for p, c in zip(pts, cols)]
            new = [k for k in keys if k not in bverts]
            if len(bverts) + len(set(new)) > 30:
                flush()
            idx = []
            for k in keys:
                if k not in bverts: bverts[k] = len(bverts)
                idx.append(bverts[k])
            batch.append(idx); ntris += 1
        flush()
    g(0xB8000000, 0)                     # end display list

    xs = [p[0] for p, _ in verts]; ys = [p[1] for p, _ in verts]; zs = [p[2] for p, _ in verts]
    mn = (min(xs), min(ys), min(zs)); mx = (max(xs), max(ys), max(zs))
    ctr = tuple((a + b) // 2 for a, b in zip(mn, mx))
    local = int(max(math.dist(p, ctr) for p, _ in verts)) + 1
    glob = int(max(math.dist(p, (0, 0, 0)) for p, _ in verts)) + 1

    tex = struct.pack(">ihH", 8, 0, 0)
    gfx_b = struct.pack(">II", len(gfx), 0) + b"".join(struct.pack(">II", *w) for w in gfx)
    vtx_b = struct.pack(">12h", *mn, *mx, *ctr, local, len(verts), glob)
    for p, c in verts:
        vtx_b += struct.pack(">3hH2h4B", *p, 0, 0, 0, *c)
    geo_b = struct.pack(">IIhh", 3, 0, 0, 0) + b"\0" * 4      # one LOADDL of display list 0

    off_tex = 0x38
    off_gfx = off_tex + len(tex)
    off_vtx = off_gfx + len(gfx_b)
    off_geo = off_vtx + len(vtx_b)
    hdr = struct.pack(">IiHhiiiiiiiiiHHf", 0x0B, off_geo, off_tex, 0, off_gfx, off_vtx,
                      0, 0, 0, 0, 0, 0, 0, ntris, len(verts), 50.0)
    data = hdr + tex + gfx_b + vtx_b + geo_b
    assert off_gfx % 8 == 0 and off_vtx % 8 == 0 and (off_vtx + 24) % 8 == 0
    return data, ntris, len(verts), glob

def preview(m, path, cam=(0, 260, 1700), look=(0, 380, 0), fov=52, size=(480, 360), zfight_view=False):
    from PIL import Image, ImageDraw
    img = Image.new("RGB", size, (90, 110, 140)); d = ImageDraw.Draw(img)
    fwd = norm(sub(look, cam)); right = norm(cross(fwd, (0, 1, 0))); up = cross(right, fwd)
    f = (size[1] / 2) / math.tan(math.radians(fov / 2))
    def proj(p):
        v = sub(p, cam); z = sum(v[i]*fwd[i] for i in range(3))
        return (size[0]/2 + f * sum(v[i]*right[i] for i in range(3)) / z, size[1]/2 - f * sum(v[i]*up[i] for i in range(3)) / z)
    for name, tris in m.parts:
        for pts, cols in tris:
            s = [proj(p) for p in pts]
            area = (s[1][0]-s[0][0])*(s[2][1]-s[0][1]) - (s[2][0]-s[0][0])*(s[1][1]-s[0][1])
            if area > 0: continue      # clockwise on screen (y down) = back face
            d.polygon(s, fill=tuple(cols[0][:3]))
    img.save(path)

if __name__ == "__main__":
    m = build()
    data, nt, nv, glob = encode(m)
    open(sys.argv[1], "wb").write(data)
    print("model", len(data), "bytes,", nt, "tris,", nv, "verts, radius", glob)
    if len(sys.argv) > 2:
        preview(m, sys.argv[2])
