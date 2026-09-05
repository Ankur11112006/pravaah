"""Building-level test, the output the spec actually asks for:
'a list of buildings predicted flooded', target recall > 70% and precision > 50%."""
import numpy as np, pandas as pd, rasterio
from pyproj import Transformer

D = "D:/claude/pravaah/data/"
def rd(p):
    with rasterio.open(D+p) as s: return s.read(1)

with rasterio.open(D+"dem30.tif") as s:
    tr, crs, H, W = s.transform, s.crs, s.height, s.width

b = pd.read_csv(D+"buildings_patna.csv")
x, y = Transformer.from_crs("EPSG:4326", crs, always_xy=True).transform(b.lon.values, b.lat.values)
col = ((x - tr.c)/tr.a).astype(int); row = ((y - tr.f)/tr.e).astype(int)
ok = (row >= 0) & (row < H) & (col >= 0) & (col < W)
row, col = row[ok], col[ok]
print(f"buildings on grid: {ok.sum():,} of {len(b):,}")

truth, perm = rd("truth_flood30.tif").astype(bool), rd("permanent_water30.tif").astype(bool)
hand, dem   = rd("hand30.tif"), rd("dem30.tif")

keep = ~perm[row, col]
row, col = row[keep], col[keep]
yb = truth[row, col]
print(f"  after dropping permanent water: {len(yb):,} buildings, "
      f"{yb.sum():,} flooded ({yb.mean():.2%})\n")

def sweep(name, s):
    o = np.argsort(-s, kind="stable")
    tp = np.cumsum(yb[o]); n = np.arange(1, len(yb)+1)
    p, r = tp/n, tp/yb.sum()
    f1 = 2*p*r/np.clip(p+r, 1e-12, None); i = int(np.argmax(f1))
    hit = ((r >= 0.70) & (p >= 0.50)).any()
    print(f"{name:22s} bestF1 {f1[i]:.3f} (P {p[i]:.3f} R {r[i]:.3f}, flags {n[i]/len(yb):5.1%})"
          f"   P@R=.70 {p[r>=0.70].max() if (r>=0.70).any() else 0:.3f}"
          f"   spec target: {'MET' if hit else 'MISSED'}")
    return float(np.sum(np.diff(np.r_[0, r])*p))

print(f"{'':22s} (flag-everything precision = {yb.mean():.3f})")
ah = sweep("HAND",               -hand[row, col])
ad = sweep("BASELINE elevation", -dem[row, col])
print(f"\nPR-AUC  HAND {ah:.4f}  vs  elevation {ad:.4f}   "
      f"-> {'HAND wins' if ah > ad else 'BASELINE wins'}")
