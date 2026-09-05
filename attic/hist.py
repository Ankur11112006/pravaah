import numpy as np, rasterio
def db(p):
    with rasterio.open(p) as s: a=s.read(1).astype("float32")
    a[a<=0]=np.nan; return 10*np.log10(a)
base=db("data/patna_baseline_vv.tif"); flood=db("data/patna_flood_vv.tif")
diff=flood-base
for name,a,rng in [("BASELINE",base,(-30,5)),("FLOOD",flood,(-30,5)),("DIFF flood-base",diff,(-15,15))]:
    h,e=np.histogram(a[np.isfinite(a)],bins=45,range=rng)
    h=h/h.max()
    print(f"\n--- {name} ---")
    for i in range(len(h)):
        if h[i]>0.008: print(f"  {e[i]:6.1f} {'#'*int(h[i]*60)}")
print("\nDIFF percentiles:", np.round(np.nanpercentile(diff,[1,5,10,25,50,75,95,99]),2))
