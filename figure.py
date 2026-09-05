import numpy as np, pandas as pd, rasterio
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from rasterio.warp import reproject, Resampling
from rasterio.windows import from_bounds
from scipy.ndimage import distance_transform_edt

AOI=(84.90,25.45,85.35,25.75)
with rasterio.open("data/hand.tif") as h:
    win=from_bounds(*AOI,h.transform).round_offsets().round_lengths()
    hand=h.read(1,window=win); tr=h.window_transform(win); crs=h.crs
with rasterio.open("data/dem_route.tif") as e: elev=e.read(1,window=win)
with rasterio.open("data/flood_mask.tif") as f:
    frac=np.zeros(hand.shape,"float32")
    reproject(f.read(1).astype("float32"),frac,src_transform=f.transform,src_crs=f.crs,
              dst_transform=tr,dst_crs=crs,resampling=Resampling.average)
with rasterio.open("data/patna_baseline_vv.tif") as s:
    b=s.read(1).astype("float32"); b[b<=0]=np.nan
    p=np.zeros(hand.shape,"float32")
    reproject((10*np.log10(b)<-15).astype("float32"),p,src_transform=s.transform,src_crs=s.crs,
              dst_transform=tr,dst_crs=crs,resampling=Resampling.average)
dist=distance_transform_edt(p<0.5)*30.0

ok=np.isfinite(hand)&np.isfinite(elev)&(elev>0); y=(frac[ok]>=0.5).astype(int)

def pr(score,y):
    o=np.argsort(-score,kind="mergesort"); ys=y[o]
    tp=np.cumsum(ys); fp=np.cumsum(1-ys)
    return tp/y.sum(), tp/(tp+fp)

fig,ax=plt.subplots(1,2,figsize=(14.5,5.6))
for name,s,col in [("HAND",-hand[ok],"#d62728"),("elevation (dumb baseline)",-elev[ok],"#1f77b4"),
                   ("distance to river",-dist[ok],"#7f7f7f")]:
    r,pp=pr(s,y); k=slice(None,None,400)
    ax[0].plot(r[k],pp[k],color=col,lw=2,label=name)
ax[0].add_patch(plt.Rectangle((0.70,0.50),0.30,0.50,fc="#2ca02c",alpha=.18,ec="#2ca02c",lw=1.5))
ax[0].text(0.845,0.75,"REQUIRED\nrecall>70%\nprec>50%",ha="center",va="center",fontsize=9,color="#1a661a",weight="bold")
ax[0].axhline(y.mean(),ls=":",c="k",lw=1); ax[0].text(0.02,y.mean()+.015,"random",fontsize=8)
ax[0].set(xlabel="recall",ylabel="precision",xlim=(0,1),ylim=(0,1),
          title="Patna 2019 - flood extent, per 30 m cell")
ax[0].legend(loc="upper right",fontsize=9); ax[0].grid(alpha=.25)

dem=["Copernicus\nGLO-30","NASADEM","ALOS\nAW3D30"]; ev=[.657,.666,.688]; hv=[.657,.644,.656]
x=np.arange(3); w=.36
ax[1].bar(x-w/2,ev,w,label="elevation",color="#1f77b4")
ax[1].bar(x+w/2,hv,w,label="HAND",color="#d62728")
for i in range(3):
    ax[1].text(x[i]-w/2,ev[i]+.004,f"{ev[i]:.3f}",ha="center",fontsize=8.5)
    ax[1].text(x[i]+w/2,hv[i]+.004,f"{hv[i]:.3f}",ha="center",fontsize=8.5)
ax[1].axhline(.5,ls="--",c="k",lw=1); ax[1].text(2.35,.505,"random",fontsize=8)
ax[1].set(xticks=x,xticklabels=dem,ylabel="ROC AUC",ylim=(.5,.72),
          title="DEM A/B - HAND never beats plain elevation")
ax[1].legend(fontsize=9); ax[1].grid(axis="y",alpha=.25)
plt.tight_layout(); plt.savefig("out/verdict.png",dpi=110)
print("wrote out/verdict.png")
