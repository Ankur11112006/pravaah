"""Full falsification test: every drainage definition, plus the dumb baselines."""
import numpy as np, rasterio
np.in1d = np.isin
from pysheds.grid import Grid
from pysheds.view import Raster
from scipy.ndimage import distance_transform_edt

D = "D:/claude/pravaah/data/"
def rd(p):
    with rasterio.open(D+p) as s: return s.read(1)

grid = Grid.from_raster(D+"dem30.tif")
dem_r = grid.read_raster(D+"dem30.tif")
cond  = grid.resolve_flats(grid.fill_depressions(grid.fill_pits(dem_r)))
fdir  = grid.flowdir(cond)
acc   = grid.accumulation(fdir)

rivers = rd("rivers30.tif").astype(bool)
masks = {f"HAND acc>{k}km2": (acc > k*1e6/900) for k in (1, 5, 25)}
masks["HAND OSM rivers"] = Raster(rivers, viewfinder=dem_r.viewfinder)

preds = {}
for name, m in masks.items():
    h = np.asarray(grid.compute_hand(fdir, dem_r, m), "float32")
    h[~np.isfinite(h)] = np.nanmax(h[np.isfinite(h)])
    preds[name] = -h
    print(f"{name:22s} drainage cells {m.sum():>8,}  HAND median {np.median(h):.2f} m")

dem = rd("dem30.tif")
preds["BASELINE elevation"]      = -dem
preds["BASELINE dist to river"]  = -distance_transform_edt(~rivers)*30

truth, perm = rd("truth_flood30.tif").astype(bool), rd("permanent_water30.tif").astype(bool)
valid = np.isfinite(dem) & ~perm
y = truth[valid]
print(f"\ncells {valid.sum():,}   flooded {y.sum():,} ({y.mean():.2%})   "
      f"flag-everything precision {y.mean():.4f}\n")

def score(s, y):
    o = np.argsort(-s, kind="stable")
    tp = np.cumsum(y[o]); n = np.arange(1, len(y)+1)
    p, r = tp/n, tp/y.sum()
    f1 = 2*p*r/np.clip(p+r, 1e-12, None)
    return float(np.sum(np.diff(np.r_[0, r])*p)), float(f1.max()), \
           float(p[r >= 0.70].max() if (r >= 0.70).any() else 0)

print(f"{'predictor':24s} {'PR-AUC':>8s} {'bestF1':>8s} {'P@R=.70':>9s}")
print("-"*53)
rows = []
for name, s in preds.items():
    ap, f1, p70 = score(s[valid], y)
    rows.append((name, ap, f1, p70))
    print(f"{name:24s} {ap:8.4f} {f1:8.4f} {p70:9.3f}")

best_model = max(r for r in rows if r[0].startswith("HAND"))
best_base  = max(r for r in rows if r[0].startswith("BASELINE"))
print("-"*53)
print(f"best model    : {best_model[0]}  PR-AUC {best_model[1]:.4f}")
print(f"best baseline : {best_base[0]}  PR-AUC {best_base[1]:.4f}")
print(f"VERDICT: model {'BEATS' if best_model[1] > best_base[1] else 'LOSES TO'} the dumb baseline")
