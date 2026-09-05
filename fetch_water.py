"""Permanent water bodies from OSM, for any event.

Needed because deriving 'permanent' as the intersection of a short forecast
window is wrong: during a sustained flood every frame is wet, so the flood
masks itself out. A river is permanent because it is a river, not because it
was wet for 21 hours."""
import json, sys, time, urllib.parse, urllib.request
sys.stdout.reconfigure(encoding="utf-8"); sys.path.insert(0, ".")
from pravaah import config

EV = config.EVENTS[sys.argv[1] if len(sys.argv) > 1 else "mahanadi"]
W, S, E, N = EV.aoi
Q = f"""[out:json][timeout:300];
(
  way["natural"="water"]({S},{W},{N},{E});
  way["waterway"="riverbank"]({S},{W},{N},{E});
  relation["natural"="water"]({S},{W},{N},{E});
);
out geom;"""
body = urllib.parse.urlencode({"data": Q}).encode()
req = urllib.request.Request("https://overpass-api.de/api/interpreter", body,
    {"Content-Type": "application/x-www-form-urlencoded",
     "User-Agent": "pravaah-flood-research/1.0"})
for a in range(4):
    try:
        raw = urllib.request.urlopen(req, timeout=900).read(); break
    except Exception as e:
        print(f"  attempt {a+1} failed ({e}); retrying"); time.sleep(30)
else:
    raise SystemExit("Overpass would not serve water polygons")
out = f"data/{EV.name}_osm_water.json"
open(out, "wb").write(raw)
n = len(json.loads(raw.decode())["elements"])
print(f"  {n:,} water polygons -> {out}")
