"""Real river channels from OSM. Accumulation cannot find the Ganga because its
catchment lies outside the box, so the drainage network is taken as given."""
import urllib.request, urllib.parse, json, numpy as np, rasterio
from rasterio.features import rasterize
from rasterio.warp import transform_geom

q = """[out:json][timeout:240];
(way["waterway"~"^(river|canal)$"](25.30,84.75,25.90,85.50);
 way["natural"="water"](25.30,84.75,25.90,85.50);
 way["waterway"="riverbank"](25.30,84.75,25.90,85.50););
out geom;"""
req = urllib.request.Request("https://overpass-api.de/api/interpreter",
                             data=urllib.parse.urlencode({"data": q}).encode(),
                             headers={"User-Agent": "pravaah-flood-test/0.1"})
raw = urllib.request.urlopen(req, timeout=300).read()
els = json.loads(raw)["elements"]
print(f"OSM elements: {len(els)}")

geoms = []
for e in els:
    g = e.get("geometry")
    if not g or len(g) < 2:
        continue
    coords = [(p["lon"], p["lat"]) for p in g]
    closed = coords[0] == coords[-1] and len(coords) >= 4
    geoms.append({"type": "Polygon", "coordinates": [coords]} if closed
                 else {"type": "LineString", "coordinates": coords})
print(f"  usable geometries: {len(geoms)}")

with rasterio.open("D:/claude/pravaah/data/dem30.tif") as s:
    prof, crs, tr, shape = s.profile, s.crs, s.transform, (s.height, s.width)
utm = [transform_geom("EPSG:4326", crs, g) for g in geoms]
mask = rasterize(utm, out_shape=shape, transform=tr, fill=0, default_value=1,
                 all_touched=True).astype("uint8")
print(f"  river cells: {mask.sum():,} ({mask.mean():.2%} of grid)")

prof8 = {**prof, "dtype": "uint8", "nodata": None}
with rasterio.open("D:/claude/pravaah/data/rivers30.tif", "w", **prof8) as d: d.write(mask, 1)
print("  -> data/rivers30.tif")
