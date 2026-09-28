"""Tiny BPS patch encoder (source-copy aware) for N64 ROM hacks.

usage: mkbps.py original.z64 modified.z64 out.bps
"""
import sys, zlib

def varint(n):
    out = bytearray()
    while True:
        x = n & 0x7F
        n >>= 7
        if n == 0:
            out.append(0x80 | x)
            return out
        out.append(x)
        n -= 1

BLOCK = 16

def match_len(a, ai, b, bi, limit):
    n = 0
    step = 4096
    while n < limit:
        s = min(step, limit - n)
        if a[ai+n:ai+n+s] == b[bi+n:bi+n+s]:
            n += s
            continue
        if step == 1:
            break
        step //= 16 if step > 16 else step
        if step < 1:
            step = 1
    return n

def encode(src, dst, metadata=b""):
    index = {}
    for p in range(0, len(src) - BLOCK + 1, BLOCK):
        index.setdefault(src[p:p+BLOCK], p)

    out = bytearray(b"BPS1")
    out += varint(len(src)) + varint(len(dst)) + varint(len(metadata)) + metadata
    src_rel = 0
    lit_start = None
    t = 0
    n = len(dst)

    def flush_lit(end):
        nonlocal lit_start
        if lit_start is not None and end > lit_start:
            out.extend(varint(((end - lit_start - 1) << 2) | 1))
            out.extend(dst[lit_start:end])
        lit_start = None

    while t < n:
        # 1) same offset in source (SourceRead)
        if t < len(src):
            l = match_len(src, t, dst, t, min(len(src), n) - t)
            if l >= 8:
                flush_lit(t)
                out += varint(((l - 1) << 2) | 0)
                t += l
                continue
        # 2) shifted match anywhere in source (SourceCopy)
        p = index.get(bytes(dst[t:t+BLOCK])) if t + BLOCK <= n else None
        if p is not None:
            l = match_len(src, p, dst, t, min(len(src) - p, n - t))
            # extend backwards into pending literals
            b = 0
            while lit_start is not None and t - b - 1 >= lit_start and p - b - 1 >= 0 and src[p-b-1] == dst[t-b-1]:
                b += 1
            if l + b >= 12:
                flush_lit(t - b)
                start_src = p - b
                rel = start_src - src_rel
                out += varint(((l + b - 1) << 2) | 2)
                out += varint((abs(rel) << 1) | (1 if rel < 0 else 0))
                src_rel = start_src + l + b
                t += l
                continue
        # 3) literal byte (TargetRead)
        if lit_start is None:
            lit_start = t
        t += 1
    flush_lit(n)
    out += zlib.crc32(src).to_bytes(4, "little")
    out += zlib.crc32(dst).to_bytes(4, "little")
    out += zlib.crc32(out).to_bytes(4, "little")
    return bytes(out)

if __name__ == "__main__":
    src = open(sys.argv[1], "rb").read()
    dst = open(sys.argv[2], "rb").read()
    meta = sys.argv[4].encode() if len(sys.argv) > 4 else b""
    patch = encode(src, dst, meta)
    open(sys.argv[3], "wb").write(patch)
    print("patch", len(patch), "bytes")
