"""Google Open Buildings, for the places Microsoft does not map.

Microsoft's Global ML Buildings stop at longitude 86.247 in the Mahanadi delta.
That is not a small edge: 51% of the AOI's population lives east of it, and every
official cyclone shelter there had no footprint to measure, so the delta's
evacuation capacity read as 252 people.

Google Open Buildings v3 (CC BY 4.0) covers the same ground. The tile is 1.8 GB
gzipped and is not sorted by latitude, so there is no range request to make: it
is streamed, filtered to the AOI on the centroid columns before any geometry is
parsed, and never written to disk in full.

    .venv/Scripts/python.exe fetch_google_buildings.py mahanadi
"""
import csv, gzip, io, json, sys, time, urllib.request
import geopandas as gpd
from shapely import wkt
from shapely.geometry import box
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, ".")
from pravaah import config

EV = config.EVENTS[sys.argv[1] if len(sys.argv) > 1 else "mahanadi"]
AOI = EV.aoi
MIN_CONF = 0.70          # Google's own suggested cut for built-up analysis
TILES = ("https://openbuildings-public-dot-gweb-research.uw.r.appspot.com"
         "/public/tiles.geojson")


def tiles_for(aoi):
    from shapely.geometry import shape
    d = json.load(urllib.request.urlopen(
        urllib.request.Request(TILES, headers={"User-Agent": "pravaah/1.0"}),
        timeout=120))
    a = box(*aoi)
    return [f["properties"] for f in d["features"]
            if shape(f["geometry"]).intersects(a)]


def main():
    w, s, e, n = AOI
    hits = tiles_for(AOI)
    if not hits:
        sys.exit(f"Google Open Buildings publishes no tile covering {AOI}")
    for t in hits:
        print(f"tile {t['tile_id']} covers the AOI, {t['size_mb']:.0f} MB gzipped")

    geoms, area = [], []
    t0 = time.time()
    for t in hits:
        seen = kept = 0
        req = urllib.request.Request(t["tile_url"],
                                     headers={"User-Agent": "pravaah/1.0"})
        with urllib.request.urlopen(req, timeout=1800) as r:
            with gzip.open(r, mode="rt", encoding="utf-8", newline="") as f:
                for row in csv.DictReader(f):
                    seen += 1
                    if seen % 2_000_000 == 0:
                        print(f"    {seen:>12,} rows, {kept:>7,} kept, "
                              f"{time.time()-t0:>5.0f}s")
                    try:
                        lat = float(row["latitude"]); lon = float(row["longitude"])
                    except (KeyError, ValueError):
                        continue
                    if not (w <= lon <= e and s <= lat <= n):
                        continue
                    if float(row.get("confidence", 1)) < MIN_CONF:
                        continue
                    geoms.append(wkt.loads(row["geometry"]))
                    area.append(float(row.get("area_in_meters", 0)))
                    kept += 1
        print(f"  {t['tile_id']}: {seen:,} rows scanned, {kept:,} inside the AOI")

    if not geoms:
        sys.exit("nothing fell inside the AOI; check the bounds")
    g = gpd.GeoDataFrame(dict(area_m2=area), geometry=geoms, crs="EPSG:4326")
    out = f"data/{EV.name}_buildings_google.gpkg"
    g.to_file(out, driver="GPKG")
    bb = g.total_bounds
    print(f"\n{len(g):,} buildings (confidence >= {MIN_CONF}) -> {out}")
    print(f"  spans {tuple(round(v, 3) for v in bb)}")
    print(f"  AOI   {AOI}")
    print(f"  took {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
