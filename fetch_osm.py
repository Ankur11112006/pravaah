"""Fetch every OSM layer an event needs, scoped to that event.

    python fetch_osm.py delhi
"""
import json, sys, time, urllib.parse, urllib.request
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, ".")
from pravaah import config

EV = config.EVENTS[sys.argv[1] if len(sys.argv) > 1 else "patna"]
W, S, E, N = EV.aoi
BOX = f"{S},{W},{N},{E}"          # Overpass wants south,west,north,east

QUERIES = {
 "osm_roads": f'''[out:json][timeout:600];
way["highway"~"^(motorway|trunk|primary|secondary|tertiary|unclassified|residential)(_link)?$"]({BOX});
out geom;''',
 "osm_shelters": f'''[out:json][timeout:300];
(
  way["amenity"~"^(school|college|university|community_centre|hospital|townhall)$"]({BOX});
  way["building"~"^(school|college|university|hospital|civic|government|public)$"]({BOX});
  node["amenity"~"^(school|college|community_centre|hospital)$"]({BOX});
);
out center;''',
 # Rural India tags shelters loosely. Cyclone shelters in coastal Odisha are
 # often just building=yes with a name, and NDMA's own guidance names schools,
 # anganwadi centres, community centres and marriage halls, so all of those are
 # asked for rather than a narrow amenity list.
 "osm_shelter_poly": f'''[out:json][timeout:600];
(
  way["amenity"~"^(school|college|university|community_centre|townhall|social_facility|place_of_worship|shelter)$"]({BOX});
  way["building"~"^(school|college|university|civic|government|public|community_centre|hospital|church|temple|mosque|dormitory)$"]({BOX});
  way["emergency"="shelter"]({BOX});
  way["amenity"="shelter"]({BOX});
  relation["amenity"~"^(school|college|university|community_centre)$"]({BOX});
  way[~"^name$"~"[Cc]yclone [Ss]helter|[Ff]lood [Ss]helter|MPCS"]({BOX});
);
out geom;''',
 "osm_places": f'''[out:json][timeout:180];
node["place"~"^(city|town|village|suburb|neighbourhood|hamlet)$"]({BOX});
out;''',
}

for name, q in QUERIES.items():
    out = f"data/{EV.name}_{name}.json"
    t0 = time.time()
    # Overpass wants the query as a form field, not a bare body. A raw POST
    # comes back 406 Not Acceptable.
    body = urllib.parse.urlencode({"data": q}).encode("utf-8")
    req = urllib.request.Request(
        "https://overpass-api.de/api/interpreter", body,
        {"Content-Type": "application/x-www-form-urlencoded",
         "User-Agent": "pravaah-flood-research/1.0"})
    for attempt in range(3):
        try:
            raw = urllib.request.urlopen(req, timeout=900).read()
            break
        except Exception as e:
            print(f"  {name}: attempt {attempt+1} failed ({e}); retrying")
            time.sleep(20)
    else:
        raise SystemExit(f"Overpass would not serve {name}")
    open(out, "wb").write(raw)
    n = len(json.loads(raw.decode("utf-8"))["elements"])
    print(f"  {name:<18}{n:>8,} elements  {len(raw)/1e6:6.1f} MB  "
          f"{time.time()-t0:5.0f}s  -> {out}")
