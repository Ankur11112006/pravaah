"""Step 2b: water depth from flood extent + DEM.
FwDET method (Cohen et al.): the flood edge IS the water surface. For every wet
pixel take the elevation of its nearest boundary pixel as local water level,
depth = that level minus ground. No HAND involved; HAND failed the test."""
import numpy as np, rasterio
from rasterio.warp import reproject, Resampling
from rasterio.windows import from_bounds, transform as wtransform
from scipy.ndimage import distance_transform_edt, binary_erosion, uniform_filter

AOI = (84.90, 25.45, 85.35, 25.75)

with rasterio.open("data/dem_route.tif") as d:
    win = from_bounds(*AOI, d.transform).round_offsets().round_lengths()
    dem = d.read(1, window=win).astype("float32")
    tr, crs = wtransform(win, d.transform), d.crs
prof = dict(driver="GTiff", height=dem.shape[0], width=dem.shape[1], count=1,
            dtype="float32", crs=crs, transform=tr, nodata=np.nan, compress="deflate")

def to_grid(path, band_fn=lambda a: a):
    with rasterio.open(path) as s:
        out = np.zeros(dem.shape, "float32")
        reproject(band_fn(s.read(1).astype("float32")), out, src_transform=s.transform,
                  src_crs=s.crs, dst_transform=tr, dst_crs=crs, resampling=Resampling.average)
    return out

wet = to_grid("data/flood_mask.tif") >= 0.5
with rasterio.open("data/patna_baseline_vv.tif") as s:
    b = s.read(1).astype("float32"); b[b <= 0] = np.nan
    perm = np.zeros(dem.shape, "float32")
    reproject((10*np.log10(b) < -15).astype("float32"), perm, src_transform=s.transform,
              src_crs=s.crs, dst_transform=tr, dst_crs=crs, resampling=Resampling.average)
permanent = perm >= 0.5

# The water body is permanent river PLUS the new fringe. Only its boundary against
# DRY LAND carries the water surface; the fringe's inner boundary is the river itself,
# where the DEM reads riverbed, not water level. Taking that as "edge" zeroed the depths.
water = wet | permanent
edge = water & ~binary_erosion(water, np.ones((3, 3)))
_, idx = distance_transform_edt(~edge, return_indices=True)
wse = dem[idx[0], idx[1]]
wse = uniform_filter(wse, size=9)              # FwDET smoothing of the water surface
depth = np.where(wet & ~permanent, wse - dem, 0.0).astype("float32")
depth[depth < 0] = 0.0

with rasterio.open("data/depth.tif", "w", **prof) as o: o.write(depth, 1)

d_wet = depth[wet & ~permanent]
print(f"wet, previously-dry cells: {len(d_wet):,}  ({len(d_wet)*900/1e6:.0f} km2)")
print(f"depth m: p25={np.percentile(d_wet,25):.2f} med={np.median(d_wet):.2f} "
      f"p75={np.percentile(d_wet,75):.2f} p95={np.percentile(d_wet,95):.2f} max={d_wet.max():.2f}")
print("\nreporting depth classes (PS3-solution):")
for lo, hi, lab in [(0,.3,"0 - 0.3 m"),(.3,1,"0.3 - 1 m"),(1,99,"over 1 m")]:
    m = (d_wet >= lo) & (d_wet < hi)
    print(f"  {lab:<12} {m.sum()*900/1e6:7.1f} km2   {m.mean():6.1%} of flooded")
print("\nroad passability classes (WHAT-WE-ARE-BUILDING Step 4):")
for lo, hi, lab in [(0,.3,"car+bike+walk"),(.3,.5,"bike+walk"),(.5,1.5,"walk / cart"),(1.5,99,"boat only")]:
    m = (d_wet >= lo) & (d_wet < hi)
    print(f"  {lab:<16} {m.mean():6.1%}")
print("\nwrote data/depth.tif")
