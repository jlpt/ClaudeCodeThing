import os, struct, sys
# extracted decomp assets folder (banjo-kazooie/assets/)
BK = os.environ.get("BK_ASSETS", "banjo-kazooie/assets/").rstrip("/") + "/"

def load_bones(path=None):
    """Banjo high-poly model (asset 0x34E) bone list: pivot, bone id, parent index."""
    d = open(path or BK+"model/034E.model.bin","rb").read()
    hdr = struct.unpack(">IiHhiiiiiiiiiHHf", d[:0x38])
    off = hdr[7]
    scale, count = struct.unpack(">fh", d[off:off+6])
    bones = []
    p = off + 8
    for i in range(count):
        x,y,z,bid,mid = struct.unpack(">fffhh", d[p:p+16]); p += 16
        bones.append(dict(i=i, pos=(x,y,z), bone_id=bid, parent=mid))
    return scale, bones

def load_anim(uid):
    d = open(BK+"anim/%04X.anim.bin" % uid,"rb").read()
    f0, f1, n, pad = struct.unpack(">hhhH", d[:8])
    p = 8
    elems = []
    for _ in range(n):
        w, cnt = struct.unpack(">Hh", d[p:p+4]); p += 4
        bone, comp = w >> 4, w & 0xF
        keys = []
        for _ in range(cnt):
            a, v = struct.unpack(">Hh", d[p:p+4]); p += 4
            keys.append(((a>>15)&1, (a>>14)&1, a & 0x3FFF, v/64.0))
        elems.append((bone, comp, keys))
    return dict(first=f0, last=f1, elems=elems, size=len(d), used=p)

if __name__ == "__main__":
    s, b = load_bones()
    print("scale", s, "bones", len(b))
    for x in b: print(x)
    a = load_anim(int(sys.argv[1],16) if len(sys.argv)>1 else 0x6F)
    print("frames", a["first"], a["last"], "elems", len(a["elems"]), "size", a["size"], "parsed", a["used"])
    for bone, comp, keys in a["elems"]:
        print(bone, comp, len(keys), keys[:3], keys[-1])
