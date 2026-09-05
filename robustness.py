"""Is the FAIL an artefact of my choices? Vary the drainage threshold, and
add a third predictor (distance to permanent water) as a sanity anchor."""
import numpy as np, rasterio, time
import numpy as _np; _np.in1d = _np.isin
from pysheds.grid import Grid
from rasterio.warp import reproject, Resampling
from rasterio.windows import from_bounds
from scipy.ndimage import distance_transform_edt

AOI = (84.90, 25.45, 85.35, 25.75)

def auc(score, y):
    o = np.argsort(score, kind="mergesort"); y = y[o]
    r = np.arange(1, len(y)+1, dtype="float64")
    npos, nneg = y.sum(), len(y)-y.sum()
    return (r[y==1].sum() - npos*(npos+1)/2)/(npos*nneg)

grid = Grid.from_raster("data/dem_route.tif")
dem  = grid.read_raster("data/dem_route.tif")
fdir = grid.flowdir(grid.resolve_flats(grid.fill_depressions(grid.fill_pits(dem))))
acc  = grid.accumulation(fdir)

with rasterio.open("data/hand.tif") as h:
    win = from_bounds(*AOI, h.transform).round_offsets().round_lengths()
    tr, crs, H, W = h.window_transform(win), h.crs, h.height, h.width
r0, c0 = int(win.row_off), int(win.col_off)
r1, c1 = r0+int(win.height), c0+int(win.width)

with rasterio.open("data/dem_route.tif") as e: elev_full = e.read(1)
elev = elev_full[r0:r1, c0:c1]

# ground truth on the 30 m grid
with rasterio.open("data/flood_mask.tif") as f:
    frac = np.zeros(elev.shape, "float32")
    reproject(f.read(1).astype("float32"), frac, src_transform=f.transform, src_crs=f.crs,
              dst_transform=tr, dst_crs=crs, resampling=Resampling.average)

# permanent water on the same grid, for the distance predictor
with rasterio.open("data/patna_baseline_vv.tif") as s:
    b = s.read(1).astype("float32"); b[b<=0]=np.nan
    perm_src = (10*np.log10(b) < -15).astype("float32")
    perm = np.zeros(elev.shape, "float32")
    reproject(perm_src, perm, src_transform=s.transform, src_crs=s.crs,
              dst_transform=tr, dst_crs=crs, resampling=Resampling.average)
dist = distance_transform_edt(perm < 0.5) * 30.0     # metres to permanent water

ok = np.isfinite(elev) & (elev > 0)
y  = (frac[ok] >= 0.5).astype(int)
print(f"cells={ok.sum():,}  flooded={y.sum():,} ({y.mean():.2%})\n")
print(f"  {'predictor':<34}{'AUC':>8}")
print(f"  {'-'*42}")
print(f"  {'elevation (the dumb baseline)':<34}{auc(-elev[ok], y):8.3f}")

for thr in (500, 1000, 5000, 20000, 50000, 200000):
    hand = np.asarray(grid.compute_hand(fdir, dem, acc > thr), dtype="float32")[r0:r1, c0:c1]
    m = ok & np.isfinite(hand)
    a = auc(-hand[m], (frac[m] >= 0.5).astype(int))
    print(f"  {'HAND, drainage acc>'+str(thr):<34}{a:8.3f}")

print(f"  {'distance to permanent water':<34}{auc(-dist[ok], y):8.3f}")
