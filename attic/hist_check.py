import numpy as np, rasterio
from scipy.ndimage import median_filter
def read_db(p):
    with rasterio.open(p) as s: a=s.read(1).astype("float32")
    a[a<=0]=np.nan; return 10*np.log10(a)
b=median_filter(read_db("D:/claude/pravaah/data/s1_vv_baseline.tif"),5)
f=median_filter(read_db("D:/claude/pravaah/data/s1_vv_flood.tif"),5)
print("VV dB histogram (flood 30 Sep vs baseline 18 Sep), % of pixels per 1 dB bin")
edges=np.arange(-28,2,1.0)
hb,_=np.histogram(b[np.isfinite(b)],bins=edges); hb=hb/hb.sum()*100
hf,_=np.histogram(f[np.isfinite(f)],bins=edges); hf=hf/hf.sum()*100
for i in range(len(edges)-1):
    print(f"  {edges[i]:6.0f}..{edges[i+1]:<5.0f} base {hb[i]:5.2f} {'#'*int(hb[i]*3):<28} flood {hf[i]:5.2f} {'#'*int(hf[i]*3)}")
px=100.0/1e6
print("\narea (km2) below each absolute threshold:")
for t in (-22,-20,-18,-16,-15,-14,-12,-10):
    wb,wf=(b<t),(f<t)
    new=wf&~wb&((f-b)<-3)
    print(f"  T={t:4.0f} dB   baseline {wb.sum()*px:7.1f}   flood {wf.sum()*px:7.1f}   NEW {new.sum()*px:7.1f}")
