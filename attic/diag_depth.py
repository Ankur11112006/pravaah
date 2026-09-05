import numpy as np, rasterio
from rasterio.warp import reproject, Resampling
from rasterio.windows import from_bounds, transform as wtransform
from scipy.ndimage import distance_transform_edt
AOI=(84.90,25.45,85.35,25.75)
with rasterio.open("data/dem_route.tif") as d:
    win=from_bounds(*AOI,d.transform).round_offsets().round_lengths()
    dem=d.read(1,window=win).astype("float32"); tr=wtransform(win,d.transform); crs=d.crs
with rasterio.open("data/depth.tif") as s: depth=s.read(1)
def grid(arr,src):
    o=np.zeros(dem.shape,"float32")
    reproject(arr,o,src_transform=src.transform,src_crs=src.crs,dst_transform=tr,dst_crs=crs,
              resampling=Resampling.average); return o
with rasterio.open("data/flood_mask.tif") as f: wet=grid(f.read(1).astype("float32"),f)>=0.5
with rasterio.open("data/patna_baseline_vv.tif") as s:
    b=s.read(1).astype("float32"); b[b<=0]=np.nan
    perm=grid((10*np.log10(b)<-15).astype("float32"),s)>=0.5
dist=distance_transform_edt(~perm)*30.0
print("new-flood cells by distance from permanent water:")
tot=(wet&~perm).sum()
for lo,hi in [(0,100),(100,300),(300,1000),(1000,3000),(3000,99999)]:
    m=(wet&~perm)&(dist>=lo)&(dist<hi)
    if m.sum(): print(f"  {lo:>5}-{hi if hi<9999 else '+':<6} m  {m.sum()*900/1e6:6.1f} km2  {m.sum()/tot:6.1%}   mean depth {depth[m].mean():.2f} m")
print(f"\nmedian distance of new flood from the river: {np.median(dist[wet&~perm]):.0f} m")
print(f"terrain slope check: elevation range over the flooded fringe = "
      f"{np.percentile(dem[wet&~perm],5):.1f} to {np.percentile(dem[wet&~perm],95):.1f} m")
