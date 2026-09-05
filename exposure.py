"""Step 3: who is in the wet squares.
Compute on the 30 m grid; attach a human label only for display."""
import json, sys
import numpy as np, rasterio, geopandas as gpd, pandas as pd
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, ".")
from pravaah import config as _c, hazard
EV    = sys.argv[1] if len(sys.argv) > 1 else "patna"
cfg_ev = _c.EVENTS[EV]
DEPTH = sys.argv[2] if len(sys.argv) > 2 else f"out/depth/{EV}_2019-09-30.tif"
from rasterio.warp import reproject, Resampling
from scipy.spatial import cKDTree

with rasterio.open(DEPTH) as d:
    depth, tr, crs, shape = d.read(1), d.transform, d.crs, d.shape
with rasterio.open(f"out/{EV}_permanent.tif") as d:
    channel = d.read(1).astype(bool)
wet = (depth > _c.WET_M) & ~channel   # below WET_M is noise, not flood

# population on the same grid (GHS-POP 2020, 100 m, counts per cell -> density-preserving)
pop = np.zeros(shape, "float32")
pop = hazard.population(pop.shape, tr, crs, cfg_ev.aoi)

b = gpd.read_file(hazard.buildings_path(EV, cfg_ev.aoi))
c = b.geometry.centroid
inv = ~tr
col, row = inv * (c.x.values, c.y.values)
row, col = np.floor(row).astype(int), np.floor(col).astype(int)
ok = (row >= 0) & (row < shape[0]) & (col >= 0) & (col < shape[1])
bd = np.full(len(b), np.nan); bd[ok] = depth[row[ok], col[ok]]

places = hazard.named_places(f"data/{EV}_osm_places.json")
pxy = np.array([[p[0], p[1]] for p in places])
pnm = [p[2] for p in places]
tree = cKDTree(pxy)

rr, cc = np.nonzero(wet)
xs, ys = tr * (cc + .5, rr + .5)
_, near = tree.query(np.c_[xs, ys])

df = pd.DataFrame({"place": [pnm[i] for i in near], "depth": depth[wet], "pop": pop[wet]})
bl = pd.DataFrame({"place": [pnm[i] for i in tree.query(np.c_[c.x.values[ok], c.y.values[ok]])[1]],
                   "depth": bd[ok]})
bl = bl[bl.depth > 0]

g = df.groupby("place").agg(cells=("depth","size"), people=("pop","sum"),
                            med_depth=("depth","median"), max_depth=("depth","max"))
g["buildings"] = bl.groupby("place").size()
g["buildings"] = g.buildings.fillna(0).astype(int)
g["km2"] = g.cells*900/1e6
g = g.sort_values("people", ascending=False)

print(f"TOTAL wet: {wet.sum()*900/1e6:.0f} km2   "
      f"{int(df['pop'].sum()):,} people   {len(bl):,} buildings\n")
print(f"{'reporting unit':<22}{'km2':>7}{'people':>9}{'bldgs':>8}{'med d':>7}{'max d':>7}")
print("-"*60)
for p, r in g.head(12).iterrows():
    print(f"{p[:21]:<22}{r.km2:7.1f}{int(r.people):9,}{r.buildings:8,}{r.med_depth:7.2f}{r.max_depth:7.2f}")

crit = json.load(open(f"data/{EV}_osm_shelters.json", encoding="utf-8"))["elements"]
n_wet = 0
for x in crit:
    lon = x.get("lon") or x.get("center", {}).get("lon")
    lat = x.get("lat") or x.get("center", {}).get("lat")
    if lon is None: continue
    cx, cy = inv * (lon, lat); cx, cy = int(cy), int(cx)
    if 0 <= cx < shape[0] and 0 <= cy < shape[1] and depth[cx, cy] > 0: n_wet += 1
print(f"\ncritical facilities inside the wet zone: {n_wet} of {len(crit)}")
g.to_csv(f"out/{EV}_exposure.csv")
