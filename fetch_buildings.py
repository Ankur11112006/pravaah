"""Microsoft Global ML building footprints for the Patna AOI."""
import csv, gzip, io, json, math, urllib.request
import geopandas as gpd
from shapely.geometry import shape, box

import sys
sys.path.insert(0, ".")
from pravaah import config
EV  = config.EVENTS[sys.argv[1] if len(sys.argv) > 1 else "patna"]
AOI = EV.aoi
Z = 9

def quadkey(lon, lat, z=Z):
    n = 2**z
    x = int((lon+180.0)/360.0*n)
    lr = math.radians(lat)
    y = int((1.0 - math.log(math.tan(lr)+1/math.cos(lr))/math.pi)/2.0*n)
    qk = ""
    for i in range(z, 0, -1):
        d, m = 0, 1 << (i-1)
        if x & m: d += 1
        if y & m: d += 2
        qk += str(d)
    return qk

need = {quadkey(lo, la) for lo in (AOI[0], AOI[2]) for la in (AOI[1], AOI[3])}
print("AOI quadkeys:", sorted(need))

rows = [r for r in csv.DictReader(open("tmp/ms_links.csv"))
        if r["QuadKey"] in need]
print(f"matching tiles: {len(rows)}")

aoi = box(*AOI); feats = []
for r in rows:
    print(f"  {r['QuadKey']}  {r['Size']}  downloading...")
    raw = urllib.request.urlopen(r["Url"], timeout=600).read()
    txt = gzip.decompress(raw).decode() if raw[:2] == b"\x1f\x8b" else raw.decode()
    kept = 0
    for line in txt.splitlines():
        if not line.strip(): continue
        g = shape(json.loads(line)["geometry"])
        if g.intersects(aoi): feats.append(g); kept += 1
    print(f"      kept {kept:,} in AOI")

gdf = gpd.GeoDataFrame(geometry=feats, crs="EPSG:4326")

# Refuse to write a file that does not span the AOI it claims to cover. The
# Mahanadi AOI was moved inland after this ran once, and the stale file kept its
# old extent: 35% of the box, which put every official shelter 8 km from the
# nearest footprint and read as 'Odisha has no buildings' rather than 'this
# download is old'.
bb = gdf.total_bounds
gap = max(bb[0] - AOI[0], AOI[2] - bb[2], bb[1] - AOI[1], AOI[3] - bb[3])
if len(gdf) == 0 or gap > 0.02:              # about 2 km
    raise SystemExit(
        'COVERAGE GAP: the footprints span '
        f'{tuple(round(v, 3) for v in bb)} but the AOI is {AOI}, short by '
        f'{gap:.3f} degrees on one side. Refusing to write a file with a hole '
        'in it. Check that every matching tile downloaded.')

gdf.to_file(f"data/{EV.name}_buildings.gpkg", driver="GPKG")
print(f"\nTOTAL buildings in AOI: {len(gdf):,}  -> data/{EV.name}_buildings.gpkg")
print(f"  spans {tuple(round(v, 3) for v in bb)}, covering the AOI")
