"""Shelter capacity from measured roof area, not from a guess.

NDMA, Guidelines on Minimum Standards of Relief, section 2(c):
  "In the relief centers, 3.5 Sq.m. of covered area per person with basic
   lighting facilities shall be catered to accommodate the victims."

So capacity = covered area / 3.5. The covered area is the Microsoft ML building
footprints that fall inside the OSM boundary of each school, college or
community centre. Nothing here is assumed except that every roofed square metre
on the campus can be slept under, which is stated as optimistic.
"""
import json, os, sys
import numpy as np, geopandas as gpd, pandas as pd
from shapely.geometry import Polygon
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, ".")
from pravaah import config, hazard

EV = sys.argv[1] if len(sys.argv) > 1 else "patna"
SQM_PER_PERSON = 3.5          # NDMA minimum standard
_ev = config.EVENTS[EV]

# Every area here is measured in metres, so the projection has to suit the
# event. UTM 45N was hardcoded, which is right for Bihar and 10 degrees off for
# Delhi: outside its own zone UTM scale grows quadratically, and area with the
# square of that, so Delhi's roofs were coming out about 2% too large. Derive
# the zone from the AOI instead.
_zone = int((sum(_ev.aoi[0::2]) / 2 + 180) // 6) + 1
UTM = f"EPSG:{32600 + _zone}"        # northern hemisphere
print(f"measuring in {UTM} (UTM {_zone}N), chosen from the AOI")

els = json.load(open(f"data/{EV}_osm_shelter_poly.json", encoding="utf-8"))["elements"]
rows = []
for e in els:
    g = e.get("geometry") or []
    if len(g) < 4:
        continue
    ring = [(p["lon"], p["lat"]) for p in g]
    if ring[0] != ring[-1]:
        ring.append(ring[0])
    try:
        poly = Polygon(ring)
    except Exception:
        continue
    if not poly.is_valid:
        poly = poly.buffer(0)
    if poly.is_empty:
        continue
    t = e.get("tags", {})
    rows.append(dict(osm_id=e["id"], geometry=poly,
                     kind=t.get("amenity") or t.get("building"),
                     name=t.get("name", "")))
sh = gpd.GeoDataFrame(rows, crs="EPSG:4326").to_crs(UTM)

# one campus is often several overlapping ways; merge anything that touches
merged = gpd.GeoDataFrame(
    geometry=list(sh.geometry.union_all().geoms), crs=UTM)
merged["campus"] = range(len(merged))
tag = gpd.sjoin(sh, merged, predicate="intersects", how="left")
best = (tag.assign(a=tag.geometry.area)
           .sort_values("a", ascending=False)
           .groupby("campus").first()[["kind", "name"]])
merged = merged.merge(best, on="campus", how="left")
print(f"shelter sites: {len(sh)} OSM polygons -> {len(merged)} distinct campuses")

# Official shelters, where the state publishes them. OSM had two mapped campuses
# in the Mahanadi delta, which would have set the evacuation capacity of a
# cyclone-prone coast at 252 people. That is a statement about OSM coverage, not
# about Odisha: OSDMA publishes 776 built shelters with coordinates. They arrive
# as points rather than campus polygons, so each one takes the footprints within
# OSDMA_R metres of it and is measured by exactly the same rule as an OSM campus.
OSDMA_R = 60
osdma_path = "data/osdma_shelters.json"
if os.path.exists(osdma_path):
    w, s_, e_, n_ = _ev.aoi
    pts = [r for r in json.load(open(osdma_path, encoding="utf-8"))["shelters"]
           if w <= r["lon"] <= e_ and s_ <= r["lat"] <= n_]
    if pts:
        op = gpd.GeoDataFrame(
            pts, geometry=gpd.points_from_xy([r["lon"] for r in pts],
                                             [r["lat"] for r in pts]),
            crs="EPSG:4326").to_crs(UTM)
        op["geometry"] = op.geometry.buffer(OSDMA_R)
        # drop any that already sit inside a campus OSM had, so nobody is
        # sheltered twice in the same building
        dup = gpd.sjoin(op, merged, predicate="intersects", how="left")
        keep = op[dup.groupby(level=0)["index_right"].first().isna().values]
        add = gpd.GeoDataFrame(
            dict(campus=range(len(merged), len(merged) + len(keep)),
                 kind="osdma_" + keep["kind"].str.lower().str.replace(
                     r"[^a-z]", "", regex=True).replace("", "shelter").values,
                 name=keep["name"].values),
            geometry=list(keep.geometry), crs=UTM)
        merged = pd.concat([merged, add], ignore_index=True)
        print(f"  OSDMA: {len(pts)} official shelters in the AOI, "
              f"{len(pts) - len(keep)} already mapped by OSM, {len(keep)} added")
    else:
        print(f"  OSDMA: no official shelters inside this AOI")

b = gpd.read_file(hazard.buildings_path(EV, _ev.aoi)).to_crs(UTM)
b["roof"] = b.geometry.area
j = gpd.sjoin(b, merged, predicate="intersects", how="inner")
agg = j.groupby("campus").agg(roof_m2=("roof", "sum"), n_buildings=("roof", "size"))
out = merged.merge(agg, on="campus", how="left")
out["roof_m2"] = out.roof_m2.fillna(0.0)
out["n_buildings"] = out.n_buildings.fillna(0).astype(int)
out["cap"] = (out.roof_m2 / SQM_PER_PERSON).round().astype(int)
out["site_m2"] = out.geometry.area.round().astype(int)

empty = int((out.cap == 0).sum())
use = out[out.cap > 0].copy()
c = use.to_crs("EPSG:4326").geometry.centroid
use["lon"], use["lat"] = c.x.values, c.y.values

print(f"  {empty} campuses have no mapped building inside and get NO capacity, "
      f"rather than a guessed one")
print(f"  usable shelters: {len(use)}   total capacity: {use.cap.sum():,} people")
print(f"  measured roof area: {use.roof_m2.sum()/1e4:.1f} ha across "
      f"{use.n_buildings.sum():,} building footprints\n")
print(f"  {'kind':<18}{'sites':>7}{'roof m2':>12}{'capacity':>10}{'median cap':>12}")
for k, grp in use.groupby("kind"):
    print(f"  {str(k):<18}{len(grp):>7}{grp.roof_m2.sum():>12,.0f}"
          f"{grp.cap.sum():>10,}{grp.cap.median():>12,.0f}")

print(f"\n  largest ten by capacity:")
for _, r in use.sort_values("cap", ascending=False).head(10).iterrows():
    nm = r["name"] or f"unnamed {r.kind}"
    print(f"    {nm[:42]:<44}{r.kind:<16}{r.roof_m2:>9,.0f} m2 -> {r.cap:>6,}")

use[["lon", "lat", "cap", "kind", "name", "roof_m2", "n_buildings", "site_m2"]] \
    .to_csv(f"data/{EV}_shelters_measured.csv", index=False)
print(f"wrote data/{EV}_shelters_measured.csv")
print(f"assumption that remains: every roofed m2 on a campus is usable floor. "
      f"Real usable share is lower, so this is an UPPER bound on capacity.")
