"""SAR change-detection flood mask, 30 Sep 2019 vs same-orbit 18 Sep baseline.

Threshold comes from the minimum between the land and water modes of the VV
histogram. Otsu was tried first and returned -10.3 dB: it gets dragged toward
the dominant land mode because water is only ~10% of the scene.
"""
import numpy as np, rasterio
from scipy.ndimage import median_filter, label

def read_db(p):
    with rasterio.open(p) as s:
        a = s.read(1).astype("float32"); prof = s.profile
    a[a <= 0] = np.nan
    return 10*np.log10(a), prof

def valley(x, lo=-25, hi=-2, bins=92):
    """Threshold at the histogram minimum between the water and land modes."""
    v = x[np.isfinite(x)]
    h, e = np.histogram(v[(v > lo) & (v < hi)], bins=bins)
    c = (e[:-1] + e[1:]) / 2
    water_pk = np.argmax(h[c < -14])                        # water mode
    land_pk  = np.argmax(h[c > -11]) + np.sum(c <= -11)     # land mode
    return c[water_pk + np.argmin(h[water_pk:land_pk])]

base, prof = read_db("D:/claude/pravaah/data/s1_vv_baseline.tif")
flood, _   = read_db("D:/claude/pravaah/data/s1_vv_flood.tif")
base_s, flood_s = median_filter(base, 5), median_filter(flood, 5)

T = valley(flood_s)
print(f"water threshold from histogram valley: {T:.2f} dB")

water_base  = base_s  < T
water_flood = flood_s < T
new_water   = water_flood & ~water_base & ((flood_s - base_s) < -3)

lab, n = label(new_water)
sizes = np.bincount(lab.ravel()); sizes[0] = 0
new_water = np.isin(lab, np.flatnonzero(sizes >= 10))   # drop blobs under 1000 m2

px = 100.0/1e6
print(f"  permanent/seasonal water (18 Sep): {water_base.sum()*px:7.1f} km2")
print(f"  all water on 30 Sep:               {water_flood.sum()*px:7.1f} km2")
print(f"  NEW flood water = ground truth:    {new_water.sum()*px:7.1f} km2 ({new_water.mean():.2%} of box)")

prof.update(dtype="uint8", count=1, compress="deflate", nodata=None)
for name, arr in (("truth_flood", new_water), ("permanent_water", water_base)):
    with rasterio.open(f"D:/claude/pravaah/data/{name}.tif", "w", **prof) as d:
        d.write(arr.astype("uint8"), 1)
print("  -> data/truth_flood.tif, data/permanent_water.tif")
