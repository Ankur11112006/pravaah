import numpy as np, rasterio
from rasterio.warp import reproject, Resampling
from rasterio.windows import from_bounds, transform as wtransform
from scipy.ndimage import distance_transform_edt
AOI=(77.10,28.50,77.40,28.80)
def auc(s,y):
    o=np.argsort(s,kind="mergesort");y=y[o];r=np.arange(1,len(y)+1,dtype="float64");n=y.sum()
    return (r[y==1].sum()-n*(n+1)/2)/(n*(len(y)-n))
def sweep(s,y):
    o=np.argsort(-s,kind="mergesort");ys=y[o];tp=np.cumsum(ys);fp=np.cumsum(1-ys)
    prec=tp/(tp+fp);rec=tp/y.sum()
    f1=np.where(prec+rec>0,2*prec*rec/np.maximum(prec+rec,1e-12),0);i=int(np.argmax(f1))
    j=np.argmax(rec>=.70) if (rec>=.70).any() else -1
    return auc(s,y),f1[i],prec[i],rec[i],(prec[j] if j>=0 else np.nan)
with rasterio.open("data/delhi_dem.tif") as d:
    w=from_bounds(*AOI,d.transform).round_offsets().round_lengths()
    e=d.read(1,window=w).astype("float32");gt=wtransform(w,d.transform);gc=d.crs
with rasterio.open("data/delhi_hand.tif") as s: h=s.read(1,window=w)
frac=np.zeros(e.shape,"float32")
with rasterio.open("data/delhi_flood_mask.tif") as f:
    reproject(f.read(1).astype("float32"),frac,src_transform=f.transform,src_crs=f.crs,
              dst_transform=gt,dst_crs=gc,resampling=Resampling.average)
with rasterio.open("data/delhi_base_vv.tif") as s:
    b=s.read(1).astype("float32");b[b<=0]=np.nan
    p=np.zeros(e.shape,"float32")
    reproject((10*np.log10(b)<-15).astype("float32"),p,src_transform=s.transform,src_crs=s.crs,
              dst_transform=gt,dst_crs=gc,resampling=Resampling.average)
dist=distance_transform_edt(p<0.5)*30.0
ok=np.isfinite(e)&(e>0)&np.isfinite(h);y=(frac[ok]>=.5).astype(int)
print(f"DELHI YAMUNA 2023  cells={ok.sum():,} flooded={y.sum():,} ({y.mean():.2%})\n")
print(f"  {'predictor':<26}{'AUC':>7}{'bestF1':>9}{'prec':>8}{'recall':>8}{'P@R=70%':>10}")
for n,s in [("HAND",-h[ok]),("elevation (baseline)",-e[ok]),("distance to river",-dist[ok])]:
    a,f1,pp,rr,p70=sweep(s,y)
    print(f"  {n:<26}{a:7.3f}{f1:9.3f}{pp:8.3f}{rr:8.3f}{p70:10.3f}")
print(f"  {'TARGET':<26}{'':>7}{'':>9}{'>0.50':>8}{'>0.70':>8}{'>0.50':>10}")
print(f"\n  new flood is {(frac[ok]>=.5).sum()*900/1e6:.1f} km2; "
      f"median distance from river {np.median(dist[ok][y==1]):.0f} m")
