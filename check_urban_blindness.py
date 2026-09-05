"""Is the SAR mask blind to built-up areas? Compare flood rate by building density."""
import numpy as np, pandas as pd, rasterio
from pyproj import Transformer
D = "D:/claude/pravaah/data/"
def rd(p):
    with rasterio.open(D+p) as s: return s.read(1)
with rasterio.open(D+"dem30.tif") as s: tr, crs, H, W = s.transform, s.crs, s.height, s.width

b = pd.read_csv(D+"buildings_patna.csv")
x, y = Transformer.from_crs("EPSG:4326", crs, always_xy=True).transform(b.lon.values, b.lat.values)
col = np.clip(((x-tr.c)/tr.a).astype(int), 0, W-1); row = np.clip(((y-tr.f)/tr.e).astype(int), 0, H-1)
dens = np.zeros((H, W), "int32")
np.add.at(dens, (row, col), 1)

truth, perm, dem = rd("truth_flood30.tif").astype(bool), rd("permanent_water30.tif").astype(bool), rd("dem30.tif")
v = ~perm
print(f"{'building density':>22s} {'cells':>10s} {'flood rate':>11s} {'mean elev':>10s}")
print("-"*57)
for lo, hi, lbl in [(0,0,"0 (open land)"),(1,2,"1-2"),(3,5,"3-5"),(6,10,"6-10"),(11,10**9,"11+ (dense urban)")]:
    m = v & (dens >= lo) & (dens <= hi)
    print(f"{lbl:>22s} {m.sum():>10,} {truth[m].mean():>10.2%} {dem[m].mean():>9.1f} m")
built = v & (dens >= 3)
open_ = v & (dens == 0)
print("-"*57)
print(f"flood rate on open land   : {truth[open_].mean():.2%}")
print(f"flood rate on built-up land: {truth[built].mean():.2%}")
print(f"ratio: open land is {truth[open_].mean()/max(truth[built].mean(),1e-9):.1f}x more likely to be mapped as flooded")
