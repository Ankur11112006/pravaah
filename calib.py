"""Can a single water level reproduce the observed extent at a known discharge?
If yes we have a stage-discharge model and therefore a time dimension.
This does NOT predict from terrain; it fits terrain to two observed extents."""
import numpy as np, rasterio
from rasterio.warp import reproject, Resampling
from rasterio.windows import from_bounds, transform as wtransform
from scipy.ndimage import label

AOI = (84.90, 25.45, 85.35, 25.75)
with rasterio.open("data/dem_route.tif") as d:
    w = from_bounds(*AOI, d.transform).round_offsets().round_lengths()
    dem = d.read(1, window=w).astype("float32")
    tr, crs = wtransform(w, d.transform), d.crs

def rg(a, s):
    o = np.zeros(dem.shape, "float32")
    reproject(a, o, src_transform=s.transform, src_crs=s.crs,
              dst_transform=tr, dst_crs=crs, resampling=Resampling.average)
    return o
with rasterio.open("data/flood_mask.tif") as f: new = rg(f.read(1).astype("float32"), f) >= .5
with rasterio.open("data/patna_baseline_vv.tif") as s:
    b = s.read(1).astype("float32"); b[b <= 0] = np.nan
    perm = rg((10*np.log10(b) < -15).astype("float32"), s) >= .5

PX = 900/1e6
obs = {"2019-09-18": perm.sum()*PX, "2019-09-30": (perm | new).sum()*PX}
Q   = {"2019-09-18": 35155.0,       "2019-09-30": 44667.0}
print(f"observed water area:  18 Sep {obs['2019-09-18']:6.1f} km2 @ {Q['2019-09-18']:,.0f} m3/s")
print(f"                      30 Sep {obs['2019-09-30']:6.1f} km2 @ {Q['2019-09-30']:,.0f} m3/s\n")

seed = perm      # anything hydraulically connected to the river channel
def area_at(level):
    below = (dem < level) & np.isfinite(dem)
    lab, _ = label(below, np.ones((3,3)))
    keep = set(np.unique(lab[seed & (lab > 0)]))
    return (np.isin(lab, list(keep)) & below).sum()*PX

lo, hi = np.nanpercentile(dem, 1), np.nanpercentile(dem, 60)
levels = np.arange(lo, hi, 0.10)
areas = np.array([area_at(l) for l in levels])
print(f"  {'level m':>9}{'connected area km2':>21}")
for l, a in zip(levels[::6], areas[::6]): print(f"  {l:9.2f}{a:21.1f}")

fit = {}
for day, target in obs.items():
    i = int(np.argmin(np.abs(areas - target)))
    fit[day] = levels[i]
    print(f"\n{day}: target {target:.1f} km2 -> level {levels[i]:.2f} m "
          f"(model {areas[i]:.1f} km2, error {areas[i]-target:+.1f})")

dL = fit["2019-09-30"] - fit["2019-09-18"]
dQ = Q["2019-09-30"] - Q["2019-09-18"]
print(f"\nstage-discharge: {dL:.2f} m of stage per {dQ:,.0f} m3/s "
      f"= {dL/dQ*1000:.3f} m per 1000 m3/s")
print("monotonic and positive" if dL > 0 else "NOT monotonic: model rejected")
