import numpy as np, rasterio
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

def db(p):
    with rasterio.open(p) as s:
        a = s.read(1).astype("float32"); prof = s.profile
    a[a <= 0] = np.nan
    return 10*np.log10(a), prof

base, prof = db("data/patna_baseline_vv.tif")
flood, _   = db("data/patna_flood_vv.tif")

for n, a in [("baseline 18 Sep", base), ("flood 30 Sep", flood)]:
    q = np.nanpercentile(a, [1, 5, 25, 50, 75, 99])
    print(f"{n:16} dB  p1={q[0]:6.1f} p5={q[1]:6.1f} p25={q[2]:6.1f} "
          f"med={q[3]:6.1f} p75={q[4]:6.1f} p99={q[5]:6.1f}")

# Otsu on the pooled histogram to split water / land
sample = flood[np.isfinite(flood)]
hist, edges = np.histogram(sample, bins=256, range=(-30, 5))
p = hist / hist.sum(); c = np.cumsum(p); m = np.cumsum(p * ((edges[:-1]+edges[1:])/2))
mt = m[-1]
var = (mt*c - m)**2 / np.maximum(c*(1-c), 1e-12)
thr = ((edges[:-1]+edges[1:])/2)[np.nanargmax(var)]
print(f"\nOtsu water threshold: {thr:.1f} dB")

w_base, w_flood = base < thr, flood < thr
new_water = w_flood & ~w_base
px = 10*10/1e6   # km2 per pixel
print(f"permanent-ish water (baseline): {w_base.sum()*px:8.1f} km2")
print(f"water on flood day           : {w_flood.sum()*px:8.1f} km2")
print(f"NEW water (flood signal)     : {new_water.sum()*px:8.1f} km2  "
      f"= {new_water.mean():.1%} of AOI")

np.save("data/new_water.npy", new_water)
with rasterio.open("data/flood_mask.tif", "w", **(prof | {"dtype":"uint8","count":1,"compress":"deflate"})) as d:
    d.write(new_water.astype("uint8"), 1)

fig, ax = plt.subplots(1, 3, figsize=(19, 5))
ax[0].imshow(base, cmap="gray", vmin=-25, vmax=0);  ax[0].set_title("VV 18 Sep (baseline)")
ax[1].imshow(flood, cmap="gray", vmin=-25, vmax=0); ax[1].set_title("VV 30 Sep (flood)")
ax[2].imshow(new_water, cmap="Blues");              ax[2].set_title(f"new water = {new_water.sum()*px:.0f} km2")
for a in ax: a.axis("off")
plt.tight_layout(); plt.savefig("out/sar_check.png", dpi=90)
print("\nwrote out/sar_check.png")
