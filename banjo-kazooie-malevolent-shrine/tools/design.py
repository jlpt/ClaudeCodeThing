import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pose
from bkparse import load_anim
import numpy as np
SP=os.environ.get("POSE_OUT", ".")
base = pose.sample(load_anim(0x6F), 0)

def mudra(sh_yaw, sh_roll, sh_pitch, el_yaw, el_roll, wr_yaw, head_pitch=0, extra=None):
    v = dict(base)
    # banjo's right arm (-x)
    v[(28,0)] = sh_pitch; v[(28,1)] = sh_yaw; v[(28,2)] = sh_roll
    v[(22,1)] = el_yaw;  v[(22,2)] = el_roll
    v[(30,1)] = wr_yaw
    # left arm (+x) mirrored
    v[(14,0)] = sh_pitch; v[(14,1)] = -sh_yaw; v[(14,2)] = -sh_roll
    v[(8,1)] = -el_yaw;  v[(8,2)] = -el_roll
    v[(16,1)] = -wr_yaw
    v[(18,0)] = head_pitch; v[(18,1)] = 0
    if extra: v.update(extra)
    return v

if __name__ == "__main__":
    args = [float(x) for x in sys.argv[1:8]]
    v = mudra(*args)
    _, J = pose.fk(v)
    tipR = J[23] + (J[23]-J[21])*0.6; tipL = J[29] + (J[29]-J[27])*0.6
    print("wristR", np.round(J[23],1), "wristL", np.round(J[29],1), "elbowR", np.round(J[21],1))
    pose.draw(v, SP+"/mudra.png", "mudra " + " ".join(sys.argv[1:8]))
