"""Generate Banjo's Malevolent Shrine hand-sign animation (asset 0x0004).

Every bone/component from frame 0 of the idle animation (0x6F) is kept so the
legs, head and hidden Kazooie match the normal standing pose; the arms, head and
stance are keyframed into the Enma-ten style hand sign and held.
"""
import os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bkparse import load_anim
import pose

LAST = 120            # frames 0..120, played over the state's duration
RAISE, HOLD_END = 10, 106

idle = pose.sample(load_anim(0x6F), 0)

def mudra_values():
    v = {}
    # Banjo's right arm (-x side): shoulder 28, elbow 22, wrist 30
    sh_yaw, sh_roll, sh_pitch, el_yaw, el_roll, wr_yaw = 51.4, 91.0, 67.1, 69.7, -21.1, -65.6
    v[(28,0)], v[(28,1)], v[(28,2)] = sh_pitch, sh_yaw, sh_roll
    v[(22,1)], v[(22,2)] = el_yaw, el_roll
    v[(30,1)] = wr_yaw
    # left arm (+x side) mirrored: shoulder 14, elbow 8, wrist 16
    v[(14,0)], v[(14,1)], v[(14,2)] = sh_pitch, -sh_yaw, -sh_roll
    v[(8,1)], v[(8,2)] = -el_yaw, -el_roll
    v[(16,1)] = -wr_yaw
    # head: lifted slightly so the hand sign under the snout stays visible
    v[(18,0)], v[(18,1)] = -4.0, 0.0
    # wider, braced stance: hips out a little
    v[(24,2)] = idle[(24,2)] - 10.0
    v[(10,2)] = idle[(10,2)] + 10.0
    return v

def build():
    target = mudra_values()
    keys = {}   # (bone, comp) -> list of (frame, value, smooth_in, smooth_out)
    for k in sorted(set(idle) | set(target)):
        base = idle.get(k, 1.0 if k[1] in (3, 4, 5) else 0.0)
        if k in target and abs(target[k] - base) > 1e-3:
            t = target[k]
            # rest -> pose (eased), hold (linear/constant), pose -> rest (eased)
            keys[k] = [(0, base, 1, 1), (RAISE, t, 1, 0), (HOLD_END, t, 0, 1), (LAST, base, 1, 1)]
        else:
            keys[k] = [(0, base, 1, 1), (LAST, base, 1, 1)]
    out = bytearray(struct.pack(">hhhH", 0, LAST, len(keys), 0))
    for (bone, comp), ks in sorted(keys.items()):
        out += struct.pack(">Hh", (bone << 4) | comp, len(ks))
        for f, val, a, b in ks:
            out += struct.pack(">Hh", (a << 15) | (b << 14) | f, int(round(val * 64)))
    return bytes(out)

if __name__ == "__main__":
    data = build()
    open(sys.argv[1], "wb").write(data)
    print("wrote", len(data), "bytes")
