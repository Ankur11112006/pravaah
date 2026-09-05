import numpy as np, rasterio
def db(p):
    with rasterio.open(p) as s: a = s.read(1).astype("float32")
    a[a <= 0] = np.nan
    return 10*np.log10(a)
b, f = db("D:/claude/pravaah/data/s1_vv_baseline.tif"), db("D:/claude/pravaah/data/s1_vv_flood.tif")
print(f"baseline VV dB: mean {np.nanmean(b):6.2f}  p5 {np.nanpercentile(b,5):6.2f}  p50 {np.nanpercentile(b,50):6.2f}")
print(f"flood    VV dB: mean {np.nanmean(f):6.2f}  p5 {np.nanpercentile(f,5):6.2f}  p50 {np.nanpercentile(f,50):6.2f}")
d = f - b
for thr in (-2, -3, -5, -8):
    print(f"  pixels dropping more than {thr} dB: {np.nanmean(d < thr):6.2%}")
print(f"  water-like in baseline (< -15 dB): {np.nanmean(b < -15):.2%}")
print(f"  water-like in flood    (< -15 dB): {np.nanmean(f < -15):.2%}")
