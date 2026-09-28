"""Python mirror of src/core2/brain.inc dynamics, for tuning activity levels."""
import random, sys
M=0xFFFFFFFF
def H(a,b,c):
    h=((a*0x9E3779B1)&M) ^ (((b+0x7F4A7C15)*0x85EBCA77)&M) ^ (((c+0x165667B1)*0xC2B2AE3D)&M)
    h^=h>>15; h=(h*0x2C1B3C6D)&M; h^=h>>12; h=(h*0x297A2D39)&M; h^=h>>15; return h
IN,HID,OUT=8,6,6; N=IN+HID+OUT; FAN=3; E=(HID+OUT)*FAN; SRC=IN+HID
P=dict(in_gain=0.55, spike_w=2.2, trace_w=0.35, noise_in=0.04, noise=0.18, leak=0.88, thr_up=0.08, thr_relax=0.01)
def dst(e): return IN+e//FAN
def last_rewire(seed,e,g):
    period=3+H(seed,e,77)%6; phase=H(seed,e,99)%period
    if g<=0: return 0
    l=g-((g+phase)%period); return 0 if l<1 else l
def pick(seed,e,ep):
    d=dst(e)
    if d<SRC:
        s=H(seed,e*131+7,ep)%(SRC-1)
        if s>=d: s+=1
    else:
        s=H(seed,e*131+7,ep)%(SRC+HID)
        if s>=SRC: s=IN+(s-SRC)
    return s
def run(seed, frames=3000, dream=False, P=P):
    src=[pick(seed,e,last_rewire(seed,e,0)) for e in range(E)]
    w=[(H(seed,e,5)&0xFFFF)*(1.5/65536)-0.5 for e in range(E)]
    v=[0.0]*N; thr=[1.0]*N; tr=[0.0]*N; rate=[0.0]*N; sp=[0]*N
    rnd=random.Random(seed); counts=[0]*N; phase=0.0
    for f in range(frames):
        inp=[0.0]*IN
        if not dream:
            inp[0]=0.8 if (f//90)%3 else 0.0
            inp[1]=3.0 if f%70==0 else 0.0
            inp[2]=3.0 if f%110==0 else 0.0
            inp[5]=2.5 if (f%400)<12 else 0.0
        phase+=1.3/30
        if phase>=1: phase-=1
        inp[7]=2.5 if phase<0.12 else 0.0
        cur=[inp[i]*P['in_gain']+rnd.random()*P['noise_in'] for i in range(IN)]+[rnd.random()*P['noise'] for _ in range(HID+OUT)]
        for e in range(E):
            cur[dst(e)]+=w[e]*(sp[src[e]]*P['spike_w']+tr[src[e]]*P['trace_w'])
        fired=[0]*N
        for i in range(N):
            v[i]=v[i]*P['leak']+cur[i]; v[i]=max(v[i],-1)
            if v[i]>=thr[i]: fired[i]=1; v[i]=0; thr[i]+=P['thr_up']
            thr[i]+=(1-thr[i])*P['thr_relax']
        for i in range(N):
            tr[i]=tr[i]*0.8+fired[i]; rate[i]=rate[i]*0.96+fired[i]*0.04; sp[i]=fired[i]; counts[i]+=fired[i]
    return [c/frames for c in counts]
if __name__=="__main__":
    for seed in (0x9DA8D6A0,0x12345678,0xCAFEBABE,0x0BADF00D,0x5EED1234):
        r=run(seed); d=run(seed,dream=True)
        print("%08X play in %s | hid %s | out %s || dream out %s" % (seed, " ".join("%.2f"%x for x in r[:IN]), " ".join("%.2f"%x for x in r[IN:SRC]), " ".join("%.2f"%x for x in r[SRC:]), " ".join("%.2f"%x for x in d[SRC:])))
