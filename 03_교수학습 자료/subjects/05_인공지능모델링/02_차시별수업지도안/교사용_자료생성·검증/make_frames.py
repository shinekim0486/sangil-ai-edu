import numpy as np
rng=np.random.default_rng(1014)
LAB=['left','straight','right']
def frame(lab,H,W):
    floor=np.array([112,110,104])+rng.normal(0,6,3)
    img=np.ones((H,W,3))*floor
    img+=rng.normal(0,5,(H,W,1))
    # line from bottom center-ish to top shifted by label
    base=W*(0.5+rng.normal(0,0.05))
    shift={'left':-0.35,'straight':0.0,'right':0.35}[lab]*W+rng.normal(0,W*0.06)
    tape=np.array([228,188,42])+rng.normal(0,8,3)
    lw=max(2,W//14)
    for r in range(H):
        t=1-r/(H-1)  # 1 at top
        c=base+shift*t
        x0=int(round(c-lw/2)); 
        img[r,max(0,x0):max(0,x0+lw)]=tape
    return np.clip(img,0,255).astype(np.uint8)
def make(n,H,W,p=(0.25,0.5,0.25)):
    ys=rng.choice(3,size=n,p=p)
    X=np.stack([frame(LAB[k],H,W) for k in ys]); y=np.array([LAB[k] for k in ys])
    return X,y
Xt,yt=make(300,24,32)
np.savez_compressed('train_frames.npz',X=Xt,y=yt)
Xc,yc=make(60,48,64)
Xc=Xc[...,::-1].copy()  # OpenCV BGR
np.savez_compressed('car_frames.npz',X=Xc,y=yc)
print(Xt.shape,Xc.shape)
