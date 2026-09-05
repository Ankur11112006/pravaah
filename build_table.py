"""One row per building: HAND, elevation, and the SAR flood label."""
import numpy as np, rasterio, geopandas as gpd, pandas as pd
from rasterio.warp import transform as warp_pts

b = gpd.read_file("data/patna_buildings.gpkg")
c = b.geometry.centroid
lon, lat = c.x.values, c.y.values
print(f"buildings: {len(b):,}")

def sample(path, xs, ys, src_crs="EPSG:4326"):
    with rasterio.open(path) as s:
        if s.crs.to_string() != src_crs:
            xs, ys = warp_pts(src_crs, s.crs, list(xs), list(ys))
            xs, ys = np.array(xs), np.array(ys)
        r, cc = (~s.transform) * (xs, ys)
        r, cc = np.floor(cc).astype(int), np.floor(r).astype(int)
        ok = (r >= 0) & (r < s.height) & (cc >= 0) & (cc < s.width)
        a = s.read(1)
        out = np.full(len(xs), np.nan, "float32")
        out[ok] = a[r[ok], cc[ok]]
        return out, ok

hand, _  = sample("data/hand.tif", lon, lat)
elev, _  = sample("data/dem_route.tif", lon, lat)
fl, okf  = sample("data/flood_mask.tif", lon, lat)

df = pd.DataFrame({"lon":lon, "lat":lat, "hand":hand, "elev":elev, "flooded":fl})
df = df[np.isfinite(df.hand) & np.isfinite(df.elev) & np.isfinite(df.flooded)]
df["flooded"] = df.flooded.astype(int)
df.to_csv("data/buildings_table.csv", index=False)

n, f = len(df), int(df.flooded.sum())
print(f"usable rows: {n:,}   flooded (SAR): {f:,} = {f/n:.2%}")
print(f"\nHAND  m : flooded {df[df.flooded==1].hand.median():.2f} med | dry {df[df.flooded==0].hand.median():.2f} med")
print(f"ELEV  m : flooded {df[df.flooded==1].elev.median():.2f} med | dry {df[df.flooded==0].elev.median():.2f} med")
print("\nflood rate by HAND band:")
for lo,hi in [(0,0.5),(0.5,1),(1,2),(2,4),(4,8),(8,100)]:
    m=(df.hand>=lo)&(df.hand<hi)
    if m.sum(): print(f"  HAND {lo:>4}-{hi:<4} m  n={m.sum():>7,}  flooded {df[m].flooded.mean():6.2%}")
print("\nflood rate by ELEV band:")
qs=np.percentile(df.elev,[0,10,25,50,75,90,100])
for i in range(len(qs)-1):
    m=(df.elev>=qs[i])&(df.elev<qs[i+1])
    if m.sum(): print(f"  ELEV {qs[i]:5.1f}-{qs[i+1]:<5.1f} m  n={m.sum():>7,}  flooded {df[m].flooded.mean():6.2%}")
