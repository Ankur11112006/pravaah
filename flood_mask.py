"""Ground truth: open-water flood extent, Patna, 30 Sep 2019.
Standard S1 method: absolute water threshold + significant drop vs same-orbit baseline."""
import numpy as np, rasterio
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

W_DB, DROP_DB = -15.0, 3.0     # literature-standard VV water threshold; drop kills speckle
PX_KM2 = 1e-4                  # 10 m pixel

def db(p):
    with rasterio.open(p) as s: a=s.read(1).astype("float32"); prof=s.profile
    a[a<=0]=np.nan; return 10*np.log10(a), prof

base,prof = db("data/patna_baseline_vv.tif")
flood,_   = db("data/patna_flood_vv.tif")

permanent = base < W_DB
wet       = flood < W_DB
newflood  = wet & ~permanent & ((flood - base) < -DROP_DB)

print(f"AOI                     {np.isfinite(flood).sum()*PX_KM2:8.1f} km2")
print(f"permanent water (18Sep) {permanent.sum()*PX_KM2:8.1f} km2  {permanent.mean():5.1%}")
print(f"water on 30 Sep         {wet.sum()*PX_KM2:8.1f} km2  {wet.mean():5.1%}")
print(f"NEW FLOOD               {newflood.sum()*PX_KM2:8.1f} km2  {newflood.mean():5.1%}")

print("\nthreshold sensitivity (new flood km2):")
for w in (-13,-14,-15,-16,-17):
    row=[f"{((flood<w)&~(base<w)&((flood-base)<-d)).sum()*PX_KM2:7.1f}" for d in (2,3,4,5)]
    print(f"  water<{w:4} dB   drop>2/3/4/5 dB: {' '.join(row)}")

prof.update(dtype="uint8", count=1, compress="deflate", nodata=None)
with rasterio.open("data/flood_mask.tif","w",**prof) as d: d.write(newflood.astype("uint8"),1)

fig,ax=plt.subplots(1,3,figsize=(20,5.2))
ax[0].imshow(base,cmap="gray",vmin=-22,vmax=2);  ax[0].set_title("VV 18 Sep 2019  (baseline, same orbit)")
ax[1].imshow(flood,cmap="gray",vmin=-22,vmax=2); ax[1].set_title("VV 30 Sep 2019  (flood peak)")
rgb=np.zeros(base.shape+(3,)); g=np.clip((flood+22)/24,0,1)
rgb[...,0]=rgb[...,1]=rgb[...,2]=g
rgb[newflood]=[0.1,0.45,1.0]; rgb[permanent]=[0.35,0.35,0.35]
ax[2].imshow(rgb); ax[2].set_title(f"blue = new flood {newflood.sum()*PX_KM2:.0f} km2   grey = permanent water")
for a in ax: a.axis("off")
plt.tight_layout(); plt.savefig("out/flood_mask.png",dpi=95)
print("\nwrote out/flood_mask.png")
