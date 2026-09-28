"""Banjo-Kazooie model (.model.bin) reader: header, textures, display lists, vertices, geo list."""
import struct

class Model:
    def __init__(self, path):
        self.d = bytearray(open(path, "rb").read())
        d = self.d
        h = struct.unpack(">IiHhiiiiiiiiiHHf", d[:0x38])
        (self.magic, self.geo, self.tex, self.geotype, self.gfx, self.vtx, self.unk14, self.anim,
         self.coll, self.cam, self.mesh, self.animvtx, self.animtex, self.ntri, self.nvtx, self.unk34) = h
        # textures
        self.tex_size, self.tex_count = struct.unpack(">ih", d[self.tex:self.tex+6])
        self.textures = []
        for i in range(self.tex_count):
            o = self.tex + 8 + 16*i
            off, typ, w, h_ = struct.unpack(">ih2xBB6x", d[o:o+16])
            self.textures.append(dict(i=i, off=off, type=typ, w=w, h=h_))
        self.tex_data = self.tex + 8 + 16*self.tex_count   # segment 2 base
        # vertices (segment 1 base)
        self.vtx_base = self.vtx + 24
        self.vcount = struct.unpack(">h", d[self.vtx+20:self.vtx+22])[0]
        self.gfx_count = struct.unpack(">I", d[self.gfx:self.gfx+4])[0]
        self.gfx_base = self.gfx + 8

    def vert(self, i):
        o = self.vtx_base + 16*i
        x,y,z,flag,s,t,r,g,b,a = struct.unpack(">3hH2h4B", self.d[o:o+16])
        return dict(pos=(x,y,z), st=(s,t), col=(r,g,b,a), off=o)

    def set_vcol(self, i, rgba):
        o = self.vtx_base + 16*i + 12
        self.d[o:o+4] = bytes(rgba)

    def gfx_cmd(self, i):
        o = self.gfx_base + 8*i
        return struct.unpack(">II", self.d[o:o+8]) + (o,)

    def texture_image(self, t):
        """decode texture t to RGBA PIL image (CI4/CI8/RGBA16/RGBA32)"""
        from PIL import Image
        d = self.d; base = self.tex_data + t["off"]; w, h = t["w"], t["h"]; typ = t["type"]
        img = Image.new("RGBA", (w, h))
        px = img.load()
        def rgba16(v):
            return (((v>>11)&31)*255//31, ((v>>6)&31)*255//31, ((v>>1)&31)*255//31, 255 if v&1 else 0)
        if typ & 1:   # CI4: 16-colour palette (32 bytes) then 4bpp pixels
            pal = [rgba16(struct.unpack(">H", d[base+2*k:base+2*k+2])[0]) for k in range(16)]
            p = base + 32
            for y in range(h):
                for x in range(w):
                    b = d[p + (y*w + x)//2]
                    idx = (b >> 4) if (x % 2 == 0) else (b & 15)
                    px[x, y] = pal[idx]
        elif typ & 2: # CI8: 256-colour palette (512 bytes) then 8bpp
            pal = [rgba16(struct.unpack(">H", d[base+2*k:base+2*k+2])[0]) for k in range(256)]
            p = base + 512
            for y in range(h):
                for x in range(w):
                    px[x, y] = pal[d[p + y*w + x]]
        elif typ & 4: # RGBA16
            for y in range(h):
                for x in range(w):
                    px[x, y] = rgba16(struct.unpack(">H", d[base + 2*(y*w+x):base + 2*(y*w+x)+2])[0])
        elif typ & 8: # RGBA32
            for y in range(h):
                for x in range(w):
                    o = base + 4*(y*w+x); px[x, y] = tuple(d[o:o+4])
        return img

def parse_geo(m, off=None, bone=-1, out=None, lod=None):
    """walk the geo command list; returns list of (gfx_index, bone_matrix_index).
    With lod=k only the k-th LOD branch of the top level is followed."""
    d = m.d
    if out is None: out = []
    top = off is None
    if off is None: off = m.geo
    lod_i = 0
    while True:
        cmd, nxt = struct.unpack(">Ii", d[off:off+8])
        if cmd == 2:    # BONE
            br = d[off+8]; mid = struct.unpack(">b", d[off+9:off+10])[0]
            if br and (lod is None or not top): parse_geo(m, off+br, mid, out)
        elif cmd == 3:  # LOADDL
            out.append((struct.unpack(">h", d[off+8:off+10])[0], bone))
        elif cmd == 5:  # SKINNING
            k = off + 8
            first = True
            while True:
                gi = struct.unpack(">h", d[k:k+2])[0]
                if gi == 0 and not first: break
                out.append((gi, bone)); first = False; k += 2
        elif cmd == 7:
            out.append((struct.unpack(">h", d[off+10:off+12])[0], bone))
        elif cmd == 1:  # SORT
            b1 = struct.unpack(">h", d[off+0x22:off+0x24])[0]; b2 = struct.unpack(">i", d[off+0x24:off+0x28])[0]
            if b1: parse_geo(m, off+b1, bone, out)
            if b2: parse_geo(m, off+b2, bone, out)
        elif cmd in (0, 6):
            br = struct.unpack(">h", d[off+8:off+10])[0] if cmd == 0 else struct.unpack(">i", d[off+8:off+12])[0]
            if br: parse_geo(m, off+br, bone, out)
        elif cmd == 8:  # LOD
            br = struct.unpack(">i", d[off+0x1C:off+0x20])[0]
            if br and (lod is None or not top or lod == lod_i): parse_geo(m, off+br, bone, out)
            lod_i += 1
        elif cmd == 0xD:
            br = struct.unpack(">h", d[off+0x14:off+0x16])[0]
            if br: parse_geo(m, off+br, bone, out)
        elif cmd == 0xC:
            n = struct.unpack(">h", d[off+8:off+10])[0]
            for k in range(n):
                br = struct.unpack(">i", d[off+12+4*k:off+16+4*k])[0]
                if br: parse_geo(m, off+br, bone, out)
        elif cmd == 0xE:
            br = struct.unpack(">h", d[off+0x10:off+0x12])[0]
            if br: parse_geo(m, off+br, bone, out)
        elif cmd == 0xF:
            br = struct.unpack(">h", d[off+8:off+10])[0]
            if br: parse_geo(m, off+br, bone, out)
        if nxt == 0: return out
        off += nxt

def parse_tris(m, lod=None, with_st=False):
    """decode display lists: returns tris [(vidx0,vidx1,vidx2, tex_index or None, bone)] and vertex->bone"""
    starts = parse_geo(m, lod=lod)
    tex_by_addr = {0x02000000 + t["off"]: t["i"] for t in m.textures}
    tris = []; vbone = {}
    cache = [None]*32; tex = None; textured = False   # the RSP vertex cache persists between lists
    for gi, bone in starts:
        i = gi
        while i < (len(m.d) - m.gfx_base) // 8:
            w0, w1, _ = m.gfx_cmd(i); op = w0 >> 24; i += 1
            if op == 0xB8: break
            if op == 0xFD: tex = tex_by_addr.get(w1, tex)
            if op == 0xBB: textured = bool(w0 & 0xFF)
            if op == 0x04:
                n = (w0 >> 10) & 0x3F; v0 = ((w0 >> 16) & 0xFF) // 2
                base = (w1 & 0xFFFFFF) // 16
                for k in range(n):
                    cache[v0+k] = base + k; vbone.setdefault(base+k, bone)
            if op == 0xBF:
                a,b,c = ((w1>>16)&0xFF)//2, ((w1>>8)&0xFF)//2, (w1&0xFF)//2
                tris.append((cache[a],cache[b],cache[c], tex if textured else None, bone))
            if op == 0xB1:
                a,b,c = ((w0>>16)&0xFF)//2, ((w0>>8)&0xFF)//2, (w0&0xFF)//2
                tris.append((cache[a],cache[b],cache[c], tex if textured else None, bone))
                a,b,c = ((w1>>16)&0xFF)//2, ((w1>>8)&0xFF)//2, (w1&0xFF)//2
                tris.append((cache[a],cache[b],cache[c], tex if textured else None, bone))
    return tris, vbone
