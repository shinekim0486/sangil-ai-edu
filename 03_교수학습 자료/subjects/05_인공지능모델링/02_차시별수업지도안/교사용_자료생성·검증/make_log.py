import numpy as np, pandas as pd
rng=np.random.default_rng(1016)
# track layout: sequence of segments over one lap (fraction of lap)
segs=[('straight',0.22),('right',0.10),('straight',0.10),('S',0.16),('straight',0.12),('left',0.12),('straight',0.08),('right',0.10)]
rows=[]
for run in range(1,11):
    n=int(rng.integers(56,66))
    drift_n=np.convolve(rng.normal(0,6,n+8),np.ones(9)/9,'valid')[:n]
    drift_f=np.convolve(rng.normal(0,9,n+8),np.ones(9)/9,'valid')[:n]
    sdrift=np.convolve(rng.normal(0,0.5,n+8),np.ones(9)/9,'valid')[:n]
    light=[120,125,118,122,128,124,70,74,150,155][run-1]  # 7,8: 그늘(늦은 오후) 9,10: 창가 햇빛
    t=np.linspace(0,1,n,endpoint=False)
    bounds=np.cumsum([0]+[s[1] for s in segs])
    off=rng.normal(0,4)   # driver habit offset px
    for i,tt in enumerate(t):
        k=np.searchsorted(bounds,tt,side='right')-1
        kind=segs[k][0]; u=(tt-bounds[k])/segs[k][1]
        if kind=='straight': curve=0
        elif kind=='right': curve=np.sin(np.pi*u)*1.0
        elif kind=='left': curve=-np.sin(np.pi*u)*1.0
        else: curve=np.sin(2*np.pi*u)*0.8
        far=80+curve*55+off+drift_f[i]+rng.normal(0,1.5)
        near=80+curve*25+off+drift_n[i]+rng.normal(0,1)
        # lighting shifts detected line position in dark/bright runs (detection bias)
        if light<90: far+=12; near+=6
        if light>140: far-=24; near-=10
        steer=curve+sdrift[i]+rng.normal(0,0.05)
        lab='right' if steer>0.35 else ('left' if steer<-0.35 else 'straight')
        rows.append(dict(run=run,frame=i+1,line_near=round(near,1),line_far=round(far,1),bright=int(light+rng.normal(0,3)),label=lab))
df=pd.DataFrame(rows)
df.to_csv('drive_log.csv',index=False)
print(len(df)); print(df.label.value_counts())
