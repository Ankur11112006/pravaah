"""Cross-check GHS-POP against the Census of India, because exposure rests on it.

Every "N people in the water" figure this project reports comes from GHS-POP
R2023A, which is a MODEL: it takes national census counts and redistributes them
onto a 100 m grid using built-up area detected from satellite. If that
redistribution is biased, every exposure number is wrong by the same factor and
nothing else in the pipeline would notice, because nothing else counts people.

So compare it against the thing it claims to redistribute. Sum GHS-POP inside
the Patna district boundary and hold it against the Census of India count for
the same district. They are nine years apart, so they should NOT be equal: the
question is whether the difference is ordinary urban growth or model bias.

The district is used rather than a block because the census publishes an exact,
citable district total, and because the district polygon can be checked against
the published district area before any population is compared to it. A boundary
that is the wrong shape would otherwise pass silently.

    .venv/Scripts/python.exe census_check.py
"""
import io, json, os, sys, urllib.parse, urllib.request
import numpy as np, rasterio
from rasterio.features import geometry_mask
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, ".")

# Census of India, District Census Handbook, Patna district, Bihar.
# https://www.census2011.co.in/census/district/82-patna.html
CENSUS_2011, CENSUS_2001 = 5_838_465, 4_718_592
CENSUS_AREA_KM2 = 3202
GHS_EPOCH = 2020
TOLERANCE = 0.30     # GHSL's own reported accuracy for South Asian settlements

OVERPASS = "https://overpass-api.de/api/interpreter"
CACHE = "data/patna_district.json"


def district():
    if os.path.exists(CACHE):
        return json.load(open(CACHE, encoding="utf-8"))
    q = ('[out:json][timeout:180];'
         'rel["boundary"="administrative"]["admin_level"="5"]["name"="Patna"]'
         '(25.0,84.5,26.0,86.5);out geom;')
    req = urllib.request.Request(
        OVERPASS, data=urllib.parse.urlencode({"data": q}).encode(),
        headers={"User-Agent": "pravaah/1.0 census-check"})
    with urllib.request.urlopen(req, timeout=240) as r:
        d = json.load(r)
    if not d.get("elements"):
        sys.exit("Overpass returned no Patna district relation; try again later.")
    json.dump(d, io.open(CACHE, "w", encoding="utf-8"))
    return d


def polygon(rel):
    """The relation's outer ways stitched into one polygon.

    Overpass returns a district boundary as several dozen unordered way
    fragments, some reversed. Rather than reassemble them by hand, hand the
    segments to shapely and let it close the ring; a hand-rolled stitcher gets
    the direction wrong and silently yields an empty polygon, which then reads
    as a district with nobody in it."""
    from shapely.geometry import LineString, mapping
    from shapely.ops import polygonize, unary_union, linemerge
    lines = [LineString([(p["lon"], p["lat"]) for p in m["geometry"]])
             for m in rel.get("members", [])
             if m.get("type") == "way" and m.get("role") in ("outer", "")
             and len(m.get("geometry", [])) > 1]
    polys = list(polygonize(linemerge(unary_union(lines))))
    if not polys:
        sys.exit("the boundary ways do not close into a polygon")
    return mapping(max(polys, key=lambda g: g.area))


def main():
    import glob
    hit = glob.glob("data/GHS_POP_*_R7_C27.tif")
    if not hit:
        sys.exit("GHS-POP tile R7_C27 is missing from data/; it covers Patna district.")
    rel = district()["elements"][0]
    geom = polygon(rel)
    print(f"boundary: {rel['tags'].get('name')} "
          f"(admin_level {rel['tags'].get('admin_level')}, OSM relation {rel['id']})")

    with rasterio.open(hit[0]) as s:
        from rasterio.warp import transform_geom
        g = transform_geom("EPSG:4326", s.crs, geom)
        xs = [p[0] for p in g["coordinates"][0]]
        ys = [p[1] for p in g["coordinates"][0]]
        win = rasterio.windows.from_bounds(min(xs), min(ys), max(xs), max(ys),
                                           s.transform).round_offsets().round_lengths()
        a = s.read(1, window=win).astype("float64")
        tr = rasterio.windows.transform(win, s.transform)
        inside = ~geometry_mask([g], a.shape, tr, invert=False)
        if s.crs.is_geographic:
            # this GHSL variant is 3 arc-second lat/lon, so a cell is degrees,
            # not metres, and its ground area shrinks with the cosine of the
            # latitude. Multiplying the two degree sizes gives 0.0000007, which
            # is how the district first came out with an area of zero.
            lat = (min(ys) + max(ys)) / 2
            cell_km2 = (abs(tr.a) * 111.320 * np.cos(np.radians(lat))
                        * abs(tr.e) * 110.574)
        else:
            cell_km2 = abs(tr.a * tr.e) / 1e6

    area = inside.sum() * cell_km2
    ghs = float(a[inside][a[inside] > 0].sum())
    print(f"  polygon area: {area:,.0f} km2   census publishes {CENSUS_AREA_KM2:,} km2 "
          f"({(area - CENSUS_AREA_KM2) / CENSUS_AREA_KM2:+.1%})")
    if abs(area - CENSUS_AREA_KM2) / CENSUS_AREA_KM2 > 0.10:
        print("  the boundary does not match the published district area, so the")
        print("  population comparison below would be comparing different places.")
        sys.exit(1)

    rate = (CENSUS_2011 / CENSUS_2001) ** 0.1 - 1
    proj = CENSUS_2011 * (1 + rate) ** (GHS_EPOCH - 2011)
    err = (ghs - proj) / proj
    print(f"\n  GHS-POP {GHS_EPOCH} inside it: {ghs:,.0f}")
    print(f"  Census 2001:              {CENSUS_2001:,}")
    print(f"  Census 2011:              {CENSUS_2011:,}")
    print(f"  implied growth:           {rate:.2%} per year")
    print(f"  2011 carried to {GHS_EPOCH}:    {proj:,.0f}")
    print(f"\n  GHS-POP reads {err:+.1%} against the census carried forward.")
    if abs(err) <= TOLERANCE:
        print(f"  Inside the +/-{TOLERANCE:.0%} GHSL reports for South Asian")
        print("  settlements, so exposure counts are usable at the scale we quote them.")
    else:
        print(f"  OUTSIDE +/-{TOLERANCE:.0%}. Every exposure figure in this project")
        print("  inherits this bias and must be quoted as a range, not a count.")
    print("\n  What this does NOT test: how GHS-POP places people WITHIN the")
    print("  district. A model can total correctly and still put the wrong people")
    print("  on the floodplain, and no open dataset we found settles that.")
    json.dump(dict(ghs_pop=ghs, census_2011=CENSUS_2011, census_2001=CENSUS_2001,
                   projected=proj, rel_error=err, polygon_km2=area,
                   census_km2=CENSUS_AREA_KM2, osm_relation=rel["id"]),
              io.open("out/census_check.json", "w", encoding="utf-8"), indent=1)
    print("\n  wrote out/census_check.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
